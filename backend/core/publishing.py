"""Client controls for publishing immutable chatbot versions and managing API access."""
import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .api import client_required, error, read_json
from .models import (
    AllowedWebsite,
    BotSettings,
    ClientApiKey,
    ClientAccount,
    ClientDocument,
    DocumentChunk,
    PublishedBotChunk,
    PublishedBotVersion,
    PublicMonthlyUsage,
)
from .public_common import MONTHLY_MESSAGE_LIMIT, current_month, normalize_origin

KEY_GRACE_PERIOD = timedelta(hours=24)


def serialize_version(version):
    return {
        "id": version.pk,
        "version": version.version,
        "document_name": version.document_name,
        "published_at": version.published_at.isoformat(),
        "is_published": version.is_published,
        "chunk_count": version.chunks.count(),
    }


@require_GET
@client_required(approved_only=True)
def publication(request):
    account = request.client_account
    active = PublishedBotVersion.objects.filter(account=account, is_published=True).first()
    versions = PublishedBotVersion.objects.filter(account=account)[:25]
    usage = PublicMonthlyUsage.objects.filter(account=account, month=current_month()).first()
    document = ClientDocument.objects.filter(account=account).first()
    return JsonResponse(
        {
            "published": serialize_version(active) if active else None,
            "versions": [serialize_version(version) for version in versions],
            "document_ready": bool(document and document.index_status == ClientDocument.IndexStatus.READY),
            "usage": {"used": usage.count if usage else 0, "limit": MONTHLY_MESSAGE_LIMIT},
        }
    )


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def publish(request):
    account = request.client_account
    document = ClientDocument.objects.filter(account=account).first()
    if document is None:
        return error("Upload a document before publishing.", 409)
    if document.index_status != ClientDocument.IndexStatus.READY:
        return error("Wait until your document is ready for search before publishing.", 409)

    chunks = list(DocumentChunk.objects.filter(account=account, document=document).order_by("ordinal"))
    if not chunks:
        return error("The document has no indexed passages. Reindex it before publishing.", 409)

    bot_settings = BotSettings.get_for_account(account)
    with transaction.atomic():
        ClientAccount.objects.select_for_update().get(pk=account.pk)
        previous = PublishedBotVersion.objects.filter(account=account).order_by("-version").first()
        version = PublishedBotVersion.objects.create(
            account=account,
            version=(previous.version if previous else 0) + 1,
            document_name=document.original_filename,
            document_hash=document.content_hash,
            document_text=document.extracted_text,
            document_sections=document.sections,
            document_metadata={
                "file_type": document.file_type,
                "size_bytes": document.size_bytes,
                "page_count": document.page_count,
                "word_count": document.word_count,
                "char_count": document.char_count,
            },
            settings_snapshot={
                "name": bot_settings.name,
                "display_name": bot_settings.display_name,
                "greeting": bot_settings.active_greeting,
                "tone": bot_settings.tone,
                "custom_instructions": bot_settings.custom_instructions,
                "fallback_message": bot_settings.active_fallback,
            },
            embedding_model=chunks[0].embedding_model,
        )
        PublishedBotVersion.objects.filter(account=account).exclude(pk=version.pk).update(is_published=False)
        PublishedBotChunk.objects.bulk_create(
            [
                PublishedBotChunk(
                    version=version,
                    ordinal=chunk.ordinal,
                    section_label=chunk.section_label,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    embedding=chunk.embedding,
                    embedding_model=chunk.embedding_model,
                )
                for chunk in chunks
            ],
            batch_size=200,
        )

    return JsonResponse({"message": "Chatbot published.", "version": serialize_version(version)}, status=201)


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def unpublish(request):
    active = PublishedBotVersion.objects.filter(account=request.client_account, is_published=True).first()
    if active is None:
        return error("There is no published chatbot to unpublish.", 409)
    active.is_published = False
    active.save(update_fields=["is_published"])
    return JsonResponse({"message": "Chatbot unpublished."})


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def restore_version(request, version_id):
    account = request.client_account
    version = PublishedBotVersion.objects.filter(account=account, pk=version_id).first()
    if version is None:
        return error("Published version not found.", 404)
    chunks = list(version.chunks.order_by("ordinal"))
    if not chunks:
        return error("This version has no indexed passages and cannot be restored.", 409)

    with transaction.atomic():
        document = ClientDocument.objects.filter(account=account).first()
        if document:
            document.delete()

        text = version.document_text
        sections = version.document_sections
        metadata = version.document_metadata
        restored = ClientDocument.objects.create(
            account=account,
            original_filename=version.document_name,
            file_type=metadata.get("file_type", "txt"),
            size_bytes=metadata.get("size_bytes", len(text.encode("utf-8"))),
            content_hash=version.document_hash,
            file_path="",
            extracted_text=text,
            sections=sections,
            page_count=metadata.get("page_count"),
            word_count=metadata.get("word_count", len(text.split())),
            char_count=metadata.get("char_count", len(text)),
            index_status=ClientDocument.IndexStatus.READY,
            chunk_count=len(chunks),
            indexed_at=timezone.now(),
        )
        DocumentChunk.objects.bulk_create(
            [
                DocumentChunk(
                    account=account,
                    document=restored,
                    ordinal=chunk.ordinal,
                    section_label=chunk.section_label,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    char_count=len(chunk.text),
                    embedding=chunk.embedding,
                    embedding_model=chunk.embedding_model,
                )
                for chunk in chunks
            ],
            batch_size=200,
        )

        settings_snapshot = version.settings_snapshot
        bot_settings = BotSettings.get_for_account(account)
        bot_settings.name = settings_snapshot["name"]
        bot_settings.greeting = settings_snapshot["greeting"]
        bot_settings.tone = settings_snapshot["tone"]
        bot_settings.custom_instructions = settings_snapshot["custom_instructions"]
        bot_settings.fallback_message = settings_snapshot["fallback_message"]
        bot_settings.save()

    return JsonResponse(
        {"message": f"Version {version.version} restored as a draft. Publish to make it live."}
    )


def serialize_key_status(account):
    now = timezone.now()
    usable = ClientApiKey.objects.filter(account=account, revoked_at__isnull=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )
    active = usable.filter(expires_at__isnull=True).first()
    previous = usable.filter(expires_at__isnull=False).order_by("-created_at").first()
    return {
        "configured": bool(active),
        "prefix": active.prefix if active else None,
        "created_at": active.created_at.isoformat() if active else None,
        "previous_expires_at": previous.expires_at.isoformat() if previous else None,
    }


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
@client_required(approved_only=True)
def api_keys(request):
    account = request.client_account
    if request.method == "GET":
        return JsonResponse({"key": serialize_key_status(account)})

    now = timezone.now()
    if request.method == "DELETE":
        ClientApiKey.objects.filter(account=account, revoked_at__isnull=True).update(revoked_at=now)
        return JsonResponse({"message": "All API keys have been revoked.", "key": serialize_key_status(account)})

    raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
    with transaction.atomic():
        ClientApiKey.objects.filter(
            account=account, revoked_at__isnull=True, expires_at__isnull=True
        ).update(expires_at=now + KEY_GRACE_PERIOD)
        ClientApiKey.objects.filter(account=account, expires_at__lte=now).delete()
        key_record = ClientApiKey.objects.create(
            account=account,
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            prefix=raw_key[:15],
        )
    return JsonResponse(
        {
            "message": "Copy this API key now. It will not be shown again.",
            "secret": raw_key,
            "key": serialize_key_status(account),
            "created_at": key_record.created_at.isoformat(),
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
@client_required(approved_only=True)
def allowed_websites(request):
    account = request.client_account
    if request.method == "GET":
        sites = AllowedWebsite.objects.filter(account=account)
        return JsonResponse({"websites": [{"id": site.pk, "origin": site.origin} for site in sites]})

    data = read_json(request)
    if data is None:
        return error("Invalid JSON request body.")
    origin = normalize_origin(data.get("origin", ""))
    if origin is None:
        return error("Enter an origin such as https://www.example.com. Paths are not allowed.")

    if request.method == "DELETE":
        deleted, _ = AllowedWebsite.objects.filter(account=account, origin=origin).delete()
        if not deleted:
            return error("Website origin not found.", 404)
        return JsonResponse({"message": "Website removed."})

    site, created = AllowedWebsite.objects.get_or_create(account=account, origin=origin)
    return JsonResponse(
        {"website": {"id": site.pk, "origin": site.origin}, "message": "Website allowed."},
        status=201 if created else 200,
    )
