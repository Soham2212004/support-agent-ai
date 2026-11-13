"""Per-client analytics: unanswered-question trends and usage stats over the last 7 days."""
from collections import OrderedDict
from datetime import timedelta

from django.db.models import Avg, Q
from django.http import JsonResponse
from django.utils import timezone

import hashlib

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .api import client_required, error, read_json
from .models import DownvoteNote, Message, PublicChatMessage

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


def _collect_test_chat_downvotes(account, cutoff, counts):
    downvoted = (
        Message.objects.filter(
            conversation__account=account,
            role=Message.Role.ASSISTANT,
            feedback=Message.Feedback.DOWN,
            created_at__gte=cutoff,
        )
        .select_related("conversation")
        .order_by("seq")
    )
    for dm in downvoted:
        user_msg = Message.objects.filter(
            conversation=dm.conversation, role=Message.Role.USER, seq=dm.seq - 1
        ).first()
        question = user_msg.content.strip() if user_msg and user_msg.content.strip() else "(unknown question)"
        _record_downvote(counts, question, dm.content, dm.created_at)


def _collect_public_chat_downvotes(account, cutoff, counts):
    downvoted = (
        PublicChatMessage.objects.filter(
            session__account=account,
            role=PublicChatMessage.Role.ASSISTANT,
            feedback=PublicChatMessage.Feedback.DOWN,
            created_at__gte=cutoff,
        )
        .select_related("session")
        .order_by("seq")
    )
    for dm in downvoted:
        user_msg = PublicChatMessage.objects.filter(
            session=dm.session, role=PublicChatMessage.Role.USER, seq=dm.seq - 1
        ).first()
        question = user_msg.content.strip() if user_msg and user_msg.content.strip() else "(unknown question)"
        _record_downvote(counts, question, dm.content, dm.created_at)


def _record_downvote(counts, question, answer, when):
    key = _normalize(question) + "||" + _normalize(answer)
    if not key:
        return
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    if key_hash not in counts:
        counts[key_hash] = {
            "question": question.strip(),
            "answer": answer.strip(),
            "count": 0,
            "last_rated_at": when,
            "key_hash": key_hash,
        }
    counts[key_hash]["count"] += 1
    if when > counts[key_hash]["last_rated_at"]:
        counts[key_hash]["last_rated_at"] = when


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


def export_csv(request):
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed."}, status=405)
    return _handle_export(request)


@client_required(approved_only=True)
def _handle_export(request):
    import csv

    from django.http import HttpResponse

    account = request.client_account
    cutoff = timezone.now() - timedelta(days=WINDOW_DAYS)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="conversations.csv"'
    writer = csv.writer(response)
    writer.writerow(["source", "role", "content", "is_fallback", "fallback_reason", "feedback", "created_at"])

    for m in Message.objects.filter(conversation__account=account, created_at__gte=cutoff).order_by("created_at"):
        writer.writerow(["test_chat", m.role, m.content, m.is_fallback, m.fallback_reason, m.feedback, m.created_at.isoformat()])

    for m in PublicChatMessage.objects.filter(session__account=account, created_at__gte=cutoff).order_by("created_at"):
        writer.writerow(["public_chat", m.role, m.content, m.is_fallback, m.fallback_reason, m.feedback, m.created_at.isoformat()])

    return response


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

    downvote_counts = OrderedDict()
    _collect_test_chat_downvotes(account, cutoff, downvote_counts)
    _collect_public_chat_downvotes(account, cutoff, downvote_counts)

    top_downvoted = sorted(
        downvote_counts.values(), key=lambda row: (-row["count"], -row["last_rated_at"].timestamp())
    )[:MAX_TOP_QUESTIONS]
    notes_by_hash = {
        n.key_hash: n
        for n in DownvoteNote.objects.filter(account=account, key_hash__in=[r["key_hash"] for r in top_downvoted])
    }
    top_downvoted = [
        {
            "key_hash": row["key_hash"],
            "question": row["question"],
            "answer": row["answer"][:280] + ("..." if len(row["answer"]) > 280 else ""),
            "count": row["count"],
            "last_rated_at": row["last_rated_at"].isoformat(),
            "note_status": notes_by_hash[row["key_hash"]].status if row["key_hash"] in notes_by_hash else "open",
            "note": notes_by_hash[row["key_hash"]].note if row["key_hash"] in notes_by_hash else "",
        }
        for row in top_downvoted
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

    downvote_total = test_assistant.filter(feedback=Message.Feedback.DOWN).count() + public_assistant.filter(
        feedback=PublicChatMessage.Feedback.DOWN
    ).count()
    upvote_total = test_assistant.filter(feedback=Message.Feedback.UP).count() + public_assistant.filter(
        feedback=PublicChatMessage.Feedback.UP
    ).count()

    return JsonResponse(
        {
            "window_days": WINDOW_DAYS,
            "total_messages": test_user_count + public_user_count,
            "fallback_count": fallback_total,
            "fallback_rate": round(fallback_total / assistant_total * 100, 1) if assistant_total else 0,
            "avg_tokens_in": round(token_stats["avg_in"] or 0),
            "avg_tokens_out": round(token_stats["avg_out"] or 0),
            "upvote_count": upvote_total,
            "downvote_count": downvote_total,
            "top_unanswered": top_unanswered,
            "top_downvoted": top_downvoted,
        }
    )
    
    
@csrf_exempt
@require_POST
@client_required(approved_only=True)
def save_downvote_note(request):
    account = request.client_account
    data = read_json(request) or {}
    key_hash = str(data.get("key_hash", "")).strip()
    if not key_hash:
        return error("key_hash is required.", 400)
    status = str(data.get("status", "")).strip().lower()
    if status not in (DownvoteNote.Status.OPEN, DownvoteNote.Status.RESOLVED):
        return error("status must be 'open' or 'resolved'.", 400)
    note = str(data.get("note", "")).strip()[:1000]
    question = str(data.get("question", "")).strip()[:500]

    obj, _ = DownvoteNote.objects.update_or_create(
        account=account,
        key_hash=key_hash,
        defaults={"status": status, "note": note, "question": question},
    )
    return JsonResponse({"message": "Saved.", "status": obj.status, "note": obj.note})