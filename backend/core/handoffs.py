"""Client-facing list and resolve actions for handoff requests."""
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .api import client_required, error
from .models import HandoffRequest


def _serialize(h):
    return {
        "id": h.pk,
        "visitor_name": h.session.visitor_name,
        "visitor_email": h.session.visitor_email,
        "reason": h.reason,
        "status": h.status,
        "created_at": h.created_at.isoformat(),
        "resolved_at": h.resolved_at.isoformat() if h.resolved_at else None,
    }


@require_GET
@client_required(approved_only=True)
def list_handoffs(request):
    account = request.client_account
    handoffs = HandoffRequest.objects.filter(account=account).select_related("session").order_by("-created_at")[:100]
    open_count = HandoffRequest.objects.filter(account=account, status=HandoffRequest.Status.OPEN).count()
    return JsonResponse({"handoffs": [_serialize(h) for h in handoffs], "open_count": open_count})


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def resolve_handoff(request, handoff_id):
    account = request.client_account
    updated = HandoffRequest.objects.filter(
        pk=handoff_id, account=account, status=HandoffRequest.Status.OPEN
    ).update(status=HandoffRequest.Status.RESOLVED, resolved_at=timezone.now())
    if not updated:
        return error("Handoff request not found or already resolved.", 404)
    return JsonResponse({"message": "Marked resolved."})