"""Chat with your document: state, and a streaming endpoint that answers from the document."""
import json
import logging
import os

from django.db import IntegrityError
from django.db.models import F, Max
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import llm, rag
from .api import client_required, error, read_json
from .models import BotSettings, ChatUsage, ClientDocument, Conversation, Message

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1000
HISTORY_MESSAGES = 10


def daily_limit():
    try:
        return int(os.environ.get("CHAT_DAILY_LIMIT", "50"))
    except ValueError:
        return 50


def today():
    return timezone.now().date()  # UTC day


def used_today(account):
    row = ChatUsage.objects.filter(account=account, day=today()).first()
    return row.count if row else 0


def reserve_message(account):
    """Count one message against today's limit. False when the limit is already reached."""
    ChatUsage.objects.get_or_create(account=account, day=today())
    changed = ChatUsage.objects.filter(account=account, day=today(), count__lt=daily_limit()).update(
        count=F("count") + 1
    )
    return changed == 1


def release_message(account):
    """Give the message back (the answer failed, so it should not count)."""
    ChatUsage.objects.filter(account=account, day=today(), count__gt=0).update(count=F("count") - 1)


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def serialize_message(message):
    return {
        "id": message.pk,
        "role": message.role,
        "content": message.content,
        "citations": message.citations,
        "is_fallback": message.is_fallback,
        "provider": message.provider,
        "model": message.llm_model,
    }


@require_GET
@client_required(approved_only=True)
def state(request):
    """Everything the chat box needs on load: readiness, the latest conversation, models, usage."""
    account = request.client_account
    document = ClientDocument.objects.filter(account=account).first()
    conversation = Conversation.objects.filter(account=account).order_by("-updated_at").first()
    settings = BotSettings.get_for_account(account)

    messages = []
    if conversation:
        messages = [serialize_message(m) for m in conversation.messages.all()]

    return JsonResponse(
        {
            "document_ready": bool(document and document.index_status == ClientDocument.IndexStatus.READY),
            "document_name": document.original_filename if document else "",
            "conversation_id": conversation.pk if conversation else None,
            "messages": messages,
            "usage": {"used": used_today(account), "limit": daily_limit()},
            "providers": [
                {"id": p["id"], "label": p["label"], "model": p["model"]} for p in llm.available_providers()
            ],
            "default_provider": llm.default_provider_id(),
            "bot_settings": {
                "name": settings.name or settings.display_name,
                "greeting": settings.active_greeting,
                "tone": settings.tone,
                "custom_instructions": settings.custom_instructions,
                "fallback_message": settings.active_fallback,
                "starter_questions": settings.starter_questions,
                "avatar_url": settings.avatar_url,
            },
        }
    )


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def send_message(request):
    account = request.client_account
    data = read_json(request) or {}

    content = str(data.get("content", "")).strip()
    if not content:
        return error("Type a message first.", 400)
    if len(content) > MAX_MESSAGE_CHARS:
        return error(f"Keep your message under {MAX_MESSAGE_CHARS} characters.", 400)

    document = ClientDocument.objects.filter(account=account).first()
    if document is None:
        return error("Upload a document first.", 409)
    if document.index_status != ClientDocument.IndexStatus.READY:
        return error("Your document isn't ready for chat yet. Wait until it says Ready for search.", 409)

    try:
        provider = llm.get_provider(data.get("provider"))
    except llm.LLMError as exc:
        return error(str(exc), 400)

    conversation = None
    conversation_id = data.get("conversation_id")
    if conversation_id:
        try:
            conversation = Conversation.objects.filter(pk=int(conversation_id), account=account).first()
        except (TypeError, ValueError):
            conversation = None
        if conversation is None:
            return error("Conversation not found.", 404)

    if not reserve_message(account):
        return error(
            f"You've reached today's limit of {daily_limit()} test messages. It resets at midnight UTC.", 429
        )

    if conversation is None:
        conversation = Conversation.objects.create(account=account)

    recent = list(conversation.messages.filter(status=Message.Status.COMPLETE).order_by("-seq")[:HISTORY_MESSAGES])
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]

    next_seq = (conversation.messages.aggregate(top=Max("seq"))["top"] or 0) + 1
    try:
        Message.objects.create(
            conversation=conversation, seq=next_seq, role=Message.Role.USER, content=content,
            status=Message.Status.COMPLETE,
        )
    except IntegrityError:
        release_message(account)
        return error("Please wait for the previous reply to finish.", 409)

    response = StreamingHttpResponse(
        stream_reply(account, document, conversation, history, content, provider, next_seq + 1),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # tells nginx not to hold the stream back
    return response


def stream_reply(account, document, conversation, history, content, provider, reply_seq):
    yield sse("meta", {"conversation_id": conversation.pk, "provider": provider["label"], "model": provider["model"]})

    streamed = ""
    finished = False  # becomes True once a complete answer has been saved

    def give_up():
        """The answer did not complete: keep what was already shown, and do not count the message."""
        if streamed:
            Message.objects.create(
                conversation=conversation, seq=reply_seq, role=Message.Role.ASSISTANT, content=streamed,
                status=Message.Status.PARTIAL, provider=provider["id"], llm_model=provider["model"],
            )
        release_message(account)

    try:
        for event in rag.stream_answer(account, document, history, content, provider):
            if event["type"] == "token":
                streamed += event["text"]
                yield sse("token", {"text": event["text"]})
                continue

            message = Message.objects.create(
                conversation=conversation, seq=reply_seq, role=Message.Role.ASSISTANT, content=event["text"],
                citations=event["citations"], is_fallback=event["is_fallback"],
                fallback_reason=event["fallback_reason"], status=Message.Status.COMPLETE,
                provider=provider["id"], llm_model=provider["model"],
                tokens_in=event["tokens_in"], tokens_out=event["tokens_out"],
            )
            Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
            finished = True
            yield sse(
                "done",
                {
                    "id": message.pk,
                    "text": message.content,
                    "citations": message.citations,
                    "is_fallback": message.is_fallback,
                    "usage": {"used": used_today(account), "limit": daily_limit()},
                },
            )
            return
    except GeneratorExit:  # the browser closed the connection mid-answer
        if not finished:
            give_up()
        raise
    except llm.LLMError as exc:
        give_up()
        yield sse("error", {"message": str(exc)})
        return
    except Exception:
        logger.exception("Chat answer failed")
        give_up()
        yield sse("error", {"message": "Something went wrong while answering. Please try again."})
        return

    give_up()  # the pipeline ended without a final answer (should not happen)
    yield sse("error", {"message": "No answer was produced. Please try again."})
