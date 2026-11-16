"""Client-facing list, reply, resolve and transcript actions for handoff requests."""
from django.db.models import Max
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .api import client_required, error, read_json
from .models import HandoffRequest, PublicChatMessage, PublicChatSession

OPEN_STATUSES = (HandoffRequest.Status.WAITING, HandoffRequest.Status.REPLIED)
MAX_REPLY_CHARS = 1000


def _serialize(h):
    return {
        "id": h.pk,
        "session_id": h.session_id,
        "visitor_name": h.session.visitor_name,
        "visitor_email": h.session.visitor_email,
        "reason": h.reason,
        "status": h.status,
        "session_status": h.session.status,
        "created_at": h.created_at.isoformat(),
        "reminder_sent_at": h.reminder_sent_at.isoformat() if h.reminder_sent_at else None,
        "replied_at": h.replied_at.isoformat() if h.replied_at else None,
        "resolved_at": h.resolved_at.isoformat() if h.resolved_at else None,
    }


@require_GET
@client_required(approved_only=True)
def list_handoffs(request):
    account = request.client_account
    handoffs = HandoffRequest.objects.filter(account=account).select_related("session").order_by("-created_at")[:100]
    open_count = HandoffRequest.objects.filter(account=account, status__in=OPEN_STATUSES).count()
    return JsonResponse({"handoffs": [_serialize(h) for h in handoffs], "open_count": open_count})


@require_GET
@client_required(approved_only=True)
def handoff_detail(request, handoff_id):
    account = request.client_account
    handoff = HandoffRequest.objects.select_related("session").filter(pk=handoff_id, account=account).first()
    if handoff is None:
        return error("Handoff request not found.", 404)
    messages = handoff.session.messages.order_by("seq")
    return JsonResponse(
        {
            "handoff": _serialize(handoff),
            "messages": [
                {"seq": m.seq, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in messages
            ],
        }
    )


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def reply_handoff(request, handoff_id):
    account = request.client_account
    handoff = HandoffRequest.objects.select_related("session").filter(
        pk=handoff_id, account=account, status__in=OPEN_STATUSES
    ).first()
    if handoff is None:
        return error("Handoff request not found, resolved, or expired.", 404)

    data = read_json(request) or {}
    content = str(data.get("content", "")).strip()
    if not content:
        return error("Type a reply first.", 400)
    if len(content) > MAX_REPLY_CHARS:
        return error(f"Keep your reply under {MAX_REPLY_CHARS} characters.", 400)

    session = handoff.session
    next_seq = (session.messages.aggregate(top=Max("seq"))["top"] or 0) + 1
    PublicChatMessage.objects.create(
        session=session, seq=next_seq, role=PublicChatMessage.Role.HUMAN, content=content
    )
    now = timezone.now()
    PublicChatSession.objects.filter(pk=session.pk).update(status=PublicChatSession.Status.HUMAN_REPLIED, updated_at=now)
    HandoffRequest.objects.filter(pk=handoff.pk).update(status=HandoffRequest.Status.REPLIED, replied_at=now)

    return JsonResponse({"message": "Reply sent."}, status=201)


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def resolve_handoff(request, handoff_id):
    account = request.client_account
    handoff = HandoffRequest.objects.filter(pk=handoff_id, account=account, status__in=OPEN_STATUSES).first()
    if handoff is None:
        return error("Handoff request not found or already resolved.", 404)

    now = timezone.now()
    HandoffRequest.objects.filter(pk=handoff.pk).update(status=HandoffRequest.Status.RESOLVED, resolved_at=now)
    # Resolving hands the conversation back to the bot.
    PublicChatSession.objects.filter(pk=handoff.session_id).update(status=PublicChatSession.Status.ACTIVE)
    return JsonResponse({"message": "Marked resolved."})