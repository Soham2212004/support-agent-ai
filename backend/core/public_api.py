"""Short-lived visitor credentials and streaming chat for published bots."""
import json
import logging
from datetime import timedelta
from urllib.parse import urlsplit

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, transaction
from django.db.models import Max
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import llm, rag
from .api import error, read_json
from .models import (
    PublicChatMessage,
    PublicChatSession,
)
from .public_common import (
    MONTHLY_MESSAGE_LIMIT,
    TOKEN_REQUEST_RATE,
    VISITOR_MESSAGE_RATE,
    api_key_from_request,
    monthly_usage,
    normalize_origin,
    origin_is_allowed,
    release_monthly_message,
    reserve_monthly_message,
    reserve_rate_limit,
)

logger = logging.getLogger(__name__)

VISITOR_TOKEN_SALT = "support-agent-ai.public-visitor"
VISITOR_TOKEN_LIFETIME = timedelta(minutes=15)
MAX_MESSAGE_CHARS = 1000
HISTORY_MESSAGES = 10


def _cors(response, origin):
    if origin and origin_is_allowed_for_any_account(origin):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response["Access-Control-Max-Age"] = "600"
        response["Vary"] = "Origin"
    return response


def _request_origin(request):
    raw_origin = request.headers.get("Origin", "")
    if raw_origin:
        return normalize_origin(raw_origin)
    referer = request.headers.get("Referer", "")
    if referer:
        try:
            parsed = urlsplit(referer)
            return normalize_origin(f"{parsed.scheme}://{parsed.netloc}")
        except ValueError:
            return None
    return None


def _public_error(message, status, origin=None):
    return _cors(error(message, status), origin)


@csrf_exempt
def visitor_token(request):
    if request.method != "POST":
        return _public_error("Method not allowed.", 405)
    data = read_json(request)
    if data is None:
        return _public_error("Invalid JSON request body.", 400)

    key = api_key_from_request(request)
    if key is None:
        return _public_error("A valid client API key is required.", 401)

    origin = normalize_origin(data.get("origin", ""))
    request_origin = _request_origin(request)
    if origin is None or (request_origin and request_origin != origin):
        return _public_error("Provide a valid, matching website origin.", 400)
    if not origin_is_allowed(key.account, origin):
        return _public_error("This website origin is not allowed for the chatbot.", 403, origin)
    if not reserve_rate_limit("token", key.pk, TOKEN_REQUEST_RATE):
        return _public_error("Too many visitor-token requests. Try again in a minute.", 429, origin)

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    if not name or len(name) > 150:
        return _public_error("Enter your name (up to 150 characters).", 400, origin)
    try:
        validate_email(email)
    except ValidationError:
        return _public_error("Enter a valid email address.", 400, origin)

    version = key.account.published_versions.filter(is_published=True).first()
    if version is None:
        return _public_error("This chatbot is not currently published.", 409, origin)

    expires_at = timezone.now() + VISITOR_TOKEN_LIFETIME
    session = PublicChatSession.objects.create(
        account=key.account,
        version=version,
        visitor_name=name,
        visitor_email=email,
        origin=origin,
        expires_at=expires_at,
    )
    token = signing.dumps(
        {"session": str(session.token_id), "version": version.pk},
        salt=VISITOR_TOKEN_SALT,
    )
    response = JsonResponse(
        {
            "visitor_token": token,
            "expires_at": expires_at.isoformat(),
            "bot": {
                "name": version.settings_snapshot["display_name"],
                "greeting": version.settings_snapshot["greeting"],
                "version": version.version,
            },
        },
        status=201,
    )
    return _cors(response, origin)


@csrf_exempt
def public_chat(request):
    origin = _request_origin(request)
    if request.method == "OPTIONS":
        if origin is None or not origin_is_allowed_for_any_account(origin):
            return _public_error("This website origin is not allowed.", 403)
        return _cors(JsonResponse({}, status=204), origin)
    if request.method != "POST":
        return _public_error("Method not allowed.", 405, origin)

    if origin is None:
        return _public_error("A valid website Origin header is required.", 403)
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return _public_error("A visitor token is required.", 401, origin)
    try:
        token_data = signing.loads(
            authorization[7:].strip(),
            salt=VISITOR_TOKEN_SALT,
            max_age=int(VISITOR_TOKEN_LIFETIME.total_seconds()),
        )
    except signing.BadSignature:
        return _public_error("The visitor token is invalid or expired.", 401, origin)

    session = (
        PublicChatSession.objects.select_related("account", "version")
        .filter(token_id=token_data.get("session"), version_id=token_data.get("version"))
        .first()
    )
    if session is None or session.expires_at <= timezone.now():
        return _public_error("The visitor token is invalid or expired.", 401, origin)
    if session.account.status != session.account.Status.APPROVED:
        return _public_error("This chatbot is unavailable.", 403, origin)
    if not session.version.is_published:
        return _public_error("This chatbot is no longer published.", 410, origin)
    if origin != session.origin or not origin_is_allowed(session.account, origin):
        return _public_error("This website origin is not allowed for the chatbot.", 403, origin)
    if not reserve_rate_limit("visitor", session.token_id, VISITOR_MESSAGE_RATE):
        return _public_error("Too many messages. Try again in a minute.", 429, origin)

    data = read_json(request)
    if data is None:
        return _public_error("Invalid JSON request body.", 400, origin)
    content = str(data.get("content", "")).strip()
    if not content:
        return _public_error("Type a message first.", 400, origin)
    if len(content) > MAX_MESSAGE_CHARS:
        return _public_error(f"Keep your message under {MAX_MESSAGE_CHARS} characters.", 400, origin)

    try:
        provider = llm.get_provider(data.get("provider"))
    except llm.LLMError as exc:
        return _public_error(str(exc), 400, origin)

    if not PublicChatSession.objects.filter(pk=session.pk, is_generating=False).update(is_generating=True):
        return _public_error("A reply is already being generated for this visitor.", 409, origin)
    if not reserve_monthly_message(session.account):
        PublicChatSession.objects.filter(pk=session.pk).update(is_generating=False)
        return _public_error(
            f"This chatbot has reached its monthly limit of {MONTHLY_MESSAGE_LIMIT} messages.",
            429,
            origin,
        )

    recent = list(session.messages.filter(status="complete").order_by("-seq")[:HISTORY_MESSAGES])
    history = [{"role": message.role, "content": message.content} for message in reversed(recent)]
    next_seq = (session.messages.aggregate(top=Max("seq"))["top"] or 0) + 1
    try:
        with transaction.atomic():
            PublicChatMessage.objects.create(
                session=session, seq=next_seq, role=PublicChatMessage.Role.USER, content=content
            )
            PublicChatSession.objects.filter(pk=session.pk).update(updated_at=timezone.now())
    except DatabaseError:
        PublicChatSession.objects.filter(pk=session.pk).update(is_generating=False)
        release_monthly_message(session.account)
        logger.exception("Could not save public visitor message for session %s", session.pk)
        return _public_error("Could not save your message. Please try again.", 503, origin)

    response = StreamingHttpResponse(
        stream_public_reply(session, history, content, provider, next_seq + 1),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return _cors(response, origin)


def origin_is_allowed_for_any_account(origin):
    from .models import AllowedWebsite

    return AllowedWebsite.objects.filter(origin=origin).exists()


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_public_reply(session, history, content, provider, reply_seq):
    yield sse(
        "meta",
        {
            "version": session.version.version,
            "provider": provider["label"],
            "model": provider["model"],
        },
    )
    streamed = ""
    finished = False

    def release():
        PublicChatSession.objects.filter(pk=session.pk).update(is_generating=False)
        release_monthly_message(session.account)

    def save_partial():
        if streamed:
            PublicChatMessage.objects.create(
                session=session,
                seq=reply_seq,
                role=PublicChatMessage.Role.ASSISTANT,
                content=streamed,
                status="partial",
            )

    try:
        for event in rag.stream_answer(
            session.account,
            None,
            history,
            content,
            provider,
            published_version=session.version,
        ):
            if event["type"] == "token":
                streamed += event["text"]
                yield sse("token", {"text": event["text"]})
                continue

            assistant = PublicChatMessage.objects.create(
                session=session,
                seq=reply_seq,
                role=PublicChatMessage.Role.ASSISTANT,
                content=event["text"],
                citations=event["citations"],
            )
            PublicChatSession.objects.filter(pk=session.pk).update(
                is_generating=False, updated_at=timezone.now()
            )
            finished = True
            yield sse(
                "done",
                {
                    "id": assistant.pk,
                    "text": assistant.content,
                    "citations": assistant.citations,
                    "is_fallback": event["is_fallback"],
                    "usage": monthly_usage(session.account),
                },
            )
            return
    except GeneratorExit:
        if not finished:
            save_partial()
            release()
        raise
    except llm.LLMError as exc:
        save_partial()
        release()
        yield sse("error", {"message": str(exc)})
        return
    except Exception:
        logger.exception("Public chat answer failed for session %s", session.pk)
        save_partial()
        release()
        yield sse("error", {"message": "Something went wrong while answering. Please try again."})
        return

    if not finished:
        release()
        yield sse("error", {"message": "No answer was produced. Please try again."})
