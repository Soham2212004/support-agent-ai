"""Per-client analytics: unanswered-question trends and usage stats over the last 7 days."""
from collections import OrderedDict
from datetime import timedelta

from django.db.models import Avg, Q
from django.http import JsonResponse
from django.utils import timezone

from .api import client_required
from .models import Message, PublicChatMessage

WINDOW_DAYS = 7
MAX_TOP_QUESTIONS = 15

FALLBACK_REASON_LABELS = {
    "weak_evidence": "No confident match in the document",
    "no_answer": "Document didn't contain an answer",
}


def _normalize(text):
    return " ".join(text.strip().lower().split())


def _collect_test_chat_fallbacks(account, cutoff, counts):
    fallbacks = (
        Message.objects.filter(
            conversation__account=account,
            role=Message.Role.ASSISTANT,
            is_fallback=True,
            created_at__gte=cutoff,
        )
        .select_related("conversation")
        .order_by("seq")
    )
    for fm in fallbacks:
        user_msg = Message.objects.filter(
            conversation=fm.conversation, role=Message.Role.USER, seq=fm.seq - 1
        ).first()
        if not user_msg or not user_msg.content.strip():
            continue
        _record(counts, user_msg.content, fm.fallback_reason, fm.created_at)


def _collect_public_chat_fallbacks(account, cutoff, counts):
    fallbacks = (
        PublicChatMessage.objects.filter(
            session__account=account,
            role=PublicChatMessage.Role.ASSISTANT,
            is_fallback=True,
            created_at__gte=cutoff,
        )
        .select_related("session")
        .order_by("seq")
    )
    for fm in fallbacks:
        user_msg = PublicChatMessage.objects.filter(
            session=fm.session, role=PublicChatMessage.Role.USER, seq=fm.seq - 1
        ).first()
        if not user_msg or not user_msg.content.strip():
            continue
        _record(counts, user_msg.content, fm.fallback_reason, fm.created_at)


def _record(counts, text, reason, when):
    key = _normalize(text)
    if not key:
        return
    if key not in counts:
        counts[key] = {"text": text.strip(), "count": 0, "reason": reason, "last_asked_at": when}
    counts[key]["count"] += 1
    if when > counts[key]["last_asked_at"]:
        counts[key]["last_asked_at"] = when
        counts[key]["reason"] = reason


def analytics(request):
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed."}, status=405)
    return _handle(request)


@client_required(approved_only=True)
def _handle(request):
    account = request.client_account
    cutoff = timezone.now() - timedelta(days=WINDOW_DAYS)

    counts = OrderedDict()
    _collect_test_chat_fallbacks(account, cutoff, counts)
    _collect_public_chat_fallbacks(account, cutoff, counts)

    top_unanswered = sorted(counts.values(), key=lambda row: (-row["count"], -row["last_asked_at"].timestamp()))[
        :MAX_TOP_QUESTIONS
    ]
    top_unanswered = [
        {
            "question": row["text"],
            "count": row["count"],
            "reason": row["reason"],
            "reason_label": FALLBACK_REASON_LABELS.get(row["reason"], row["reason"] or "Unknown"),
            "last_asked_at": row["last_asked_at"].isoformat(),
        }
        for row in top_unanswered
    ]

    test_user_count = Message.objects.filter(
        conversation__account=account, role=Message.Role.USER, created_at__gte=cutoff
    ).count()
    public_user_count = PublicChatMessage.objects.filter(
        session__account=account, role=PublicChatMessage.Role.USER, created_at__gte=cutoff
    ).count()

    test_assistant = Message.objects.filter(
        conversation__account=account,
        role=Message.Role.ASSISTANT,
        status=Message.Status.COMPLETE,
        created_at__gte=cutoff,
    )
    public_assistant = PublicChatMessage.objects.filter(
        session__account=account, role=PublicChatMessage.Role.ASSISTANT, status="complete", created_at__gte=cutoff
    )
    assistant_total = test_assistant.count() + public_assistant.count()
    fallback_total = test_assistant.filter(is_fallback=True).count() + public_assistant.filter(
        is_fallback=True
    ).count()

    token_stats = test_assistant.filter(Q(tokens_in__gt=0) | Q(tokens_out__gt=0)).aggregate(
        avg_in=Avg("tokens_in"), avg_out=Avg("tokens_out")
    )

    return JsonResponse(
        {
            "window_days": WINDOW_DAYS,
            "total_messages": test_user_count + public_user_count,
            "fallback_count": fallback_total,
            "fallback_rate": round(fallback_total / assistant_total * 100, 1) if assistant_total else 0,
            "avg_tokens_in": round(token_stats["avg_in"] or 0),
            "avg_tokens_out": round(token_stats["avg_out"] or 0),
            "top_unanswered": top_unanswered,
        }
    )