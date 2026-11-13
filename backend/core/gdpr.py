"""Visitor-initiated export/delete of their own public-chat data, verified by an emailed token."""
import csv
import hashlib
import io
import json
import logging
import secrets
from datetime import timedelta

from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .api import error, read_json
from .models import PublicChatMessage, PublicChatSession, VisitorDataRequest

logger = logging.getLogger(__name__)

TOKEN_TTL = timedelta(hours=24)


def _make_token():
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


@csrf_exempt
@require_POST
def request_data_action(request):
    """Step 1: visitor provides their email + kind (export/delete); we email a verification link."""
    data = read_json(request)
    if data is None:
        return error("Invalid JSON request body.", 400)

    email = str(data.get("email", "")).strip().lower()
    kind = str(data.get("kind", "")).strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return error("Enter a valid email address.", 400)
    if kind not in (VisitorDataRequest.Kind.EXPORT, VisitorDataRequest.Kind.DELETE):
        return error("kind must be 'export' or 'delete'.", 400)

    raw_token, token_hash = _make_token()
    VisitorDataRequest.objects.create(
        email=email, kind=kind, token_hash=token_hash, expires_at=timezone.now() + TOKEN_TTL
    )

    try:
        send_mail(
            subject="Confirm your data request",
            message=(
                f"We received a request to {kind} the chat data associated with {email}.\n\n"
                f"Confirmation code: {raw_token}\n\n"
                f"This code expires in 24 hours. If you did not request this, ignore this email."
            ),
            from_email=None,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Could not send data-request verification email to %s", email)

    # Always the same response, whether or not the email matches real sessions, to avoid leaking which
    # addresses have chat history.
    return JsonResponse({"message": "If this email has chat history, a confirmation link has been sent."})


@csrf_exempt
@require_POST
def confirm_data_action(request):
    """Step 2: visitor submits the token from the email; we execute the export or deletion."""
    data = read_json(request)
    if data is None:
        return error("Invalid JSON request body.", 400)

    raw_token = str(data.get("token", "")).strip()
    if not raw_token:
        return error("A confirmation code is required.", 400)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    req = VisitorDataRequest.objects.filter(token_hash=token_hash, status=VisitorDataRequest.Status.PENDING).first()
    if req is None:
        return error("This confirmation code is invalid or has already been used.", 404)
    if req.expires_at < timezone.now():
        req.status = VisitorDataRequest.Status.EXPIRED
        req.save(update_fields=["status"])
        return error("This confirmation code has expired. Please request a new one.", 410)

    sessions = PublicChatSession.objects.filter(visitor_email=req.email)

    if req.kind == VisitorDataRequest.Kind.EXPORT:
        payload = []
        for session in sessions:
            payload.append(
                {
                    "session_id": str(session.token_id),
                    "created_at": session.created_at.isoformat(),
                    "messages": [
                        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                        for m in session.messages.order_by("seq")
                    ],
                }
            )
        req.status = VisitorDataRequest.Status.COMPLETED
        req.completed_at = timezone.now()
        req.save(update_fields=["status", "completed_at"])
        return JsonResponse({"email": req.email, "sessions": payload})

    # delete
    deleted_count = sessions.count()
    sessions.delete()
    req.status = VisitorDataRequest.Status.COMPLETED
    req.completed_at = timezone.now()
    req.save(update_fields=["status", "completed_at"])
    return JsonResponse({"message": f"Deleted {deleted_count} chat session(s) for {req.email}."})