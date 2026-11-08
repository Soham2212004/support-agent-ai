"""Upload, view and delete the client's single document. Approved clients only."""
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import storage
from .api import client_required, error
from .extraction import ALLOWED_EXTENSIONS, ExtractionError, extract_document, get_extension
from .models import ClientDocument

logger = logging.getLogger(__name__)

PREVIEW_CHARS = 700
ALREADY_HAS_DOCUMENT = "You already have a document. Delete it before uploading a new one."


def serialize_document(doc):
    return {
        "id": doc.pk,
        "filename": doc.original_filename,
        "file_type": doc.file_type,
        "size_bytes": doc.size_bytes,
        "page_count": doc.page_count,
        "word_count": doc.word_count,
        "char_count": doc.char_count,
        "section_count": len(doc.sections),
        "uploaded_at": doc.uploaded_at.isoformat(),
        "preview": doc.extracted_text[:PREVIEW_CHARS],
        "preview_truncated": len(doc.extracted_text) > PREVIEW_CHARS,
    }


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
@client_required(approved_only=True)
def document(request):
    account = request.client_account
    existing = ClientDocument.objects.filter(account=account).first()

    # ---- GET: show the current document (or null) ----
    if request.method == "GET":
        return JsonResponse({"document": serialize_document(existing) if existing else None})

    # ---- DELETE: remove the row; a signal removes the file ----
    if request.method == "DELETE":
        if existing is None:
            return error("You have no document to delete.", 404)
        existing.delete()
        return JsonResponse({"message": "Document deleted."})

    # ---- POST: upload ----
    if existing is not None:
        return error(ALREADY_HAS_DOCUMENT, 409)

    upload = request.FILES.get("file")
    if upload is None:
        return error("Choose a file to upload.", 400)
    if upload.size == 0:
        return error("The file is empty.", 400)
    if upload.size > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        return error(f"That file is too large. The maximum size is {limit_mb} MB.", 413)

    extension = get_extension(upload.name)
    if extension not in ALLOWED_EXTENSIONS:
        return error("Only PDF, DOCX and TXT files are supported.", 400)

    relative_path, digest, size = storage.save_upload(upload, account.pk, extension)

    try:
        result = extract_document(storage.absolute_path(relative_path), extension)
    except ExtractionError as exc:
        storage.delete_file(relative_path)
        return error(str(exc), 400)
    except Exception:
        logger.exception("Unexpected error while extracting text")
        storage.delete_file(relative_path)
        return error("We couldn't process this file. Please try another one.", 400)

    try:
        with transaction.atomic():
            doc = ClientDocument.objects.create(
                account=account,
                original_filename=upload.name[:255],
                file_type=extension,
                size_bytes=size,
                content_hash=digest,
                file_path=relative_path,
                extracted_text=result["text"],
                sections=result["sections"],
                page_count=result["page_count"],
                word_count=result["word_count"],
                char_count=result["char_count"],
            )
    except IntegrityError:  # two uploads at the same moment
        storage.delete_file(relative_path)
        return error(ALREADY_HAS_DOCUMENT, 409)

    return JsonResponse({"document": serialize_document(doc)}, status=201)