"""Client-facing list and transcript view of real visitor conversations (PublicChatSession)."""
from django.db import models
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .api import client_required
from .models import PublicChatSession

PAGE_SIZE = 20


def _serialize_summary(session):
    last_message = session.messages.order_by("-seq").first()
    return {
        "id": session.pk,
        "visitor_name": session.visitor_name,
        "visitor_email": session.visitor_email,
        "status": session.status,
        "message_count": session.messages.count(),
        "started_at": session.created_at.isoformat(),
        "last_message_at": session.updated_at.isoformat(),
        "last_message_preview": (last_message.content[:140] if last_message else ""),
    }


@require_GET
@client_required(approved_only=True, allow_suspended_read=True)
def conversation_list(request):
    account = request.client_account
    search = request.GET.get("search", "").strip()
    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page = 1

    sessions = PublicChatSession.objects.filter(account=account)
    if search:
        sessions = sessions.filter(
            models.Q(visitor_name__icontains=search) | models.Q(visitor_email__icontains=search)
        )

    total = sessions.count()
    start = (page - 1) * PAGE_SIZE
    page_sessions = sessions[start : start + PAGE_SIZE]

    return JsonResponse(
        {
            "conversations": [_serialize_summary(s) for s in page_sessions],
            "total": total,
            "page": page,
            "page_size": PAGE_SIZE,
            "has_more": start + PAGE_SIZE < total,
        }
    )


@require_GET
@client_required(approved_only=True, allow_suspended_read=True)
def conversation_detail(request, session_id):
    account = request.client_account
    session = PublicChatSession.objects.filter(pk=session_id, account=account).first()
    if session is None:
        return JsonResponse({"message": "Conversation not found."}, status=404)

    messages = session.messages.order_by("seq")
    return JsonResponse(
        {
            "conversation": _serialize_summary(session),
            "messages": [
                {
                    "seq": m.seq,
                    "role": m.role,
                    "content": m.content,
                    "citations": m.citations,
                    "is_fallback": m.is_fallback,
                    "feedback": m.feedback,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        }
    )