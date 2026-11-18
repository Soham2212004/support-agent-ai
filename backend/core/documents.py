"""Upload, view and delete the client's single document. Approved clients only."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from pgvector.django import CosineDistance

from . import storage
from .api import client_required, error, read_json
from .embeddings import embed_query
from .extraction import ALLOWED_EXTENSIONS, ExtractionError, extract_document, get_extension
from .indexing import start_indexing
from .models import ClientDocument, DocumentArchive, DocumentChunk, FAQEntry

logger = logging.getLogger(__name__)

PREVIEW_CHARS = 700
ALREADY_HAS_DOCUMENT = "Please try uploading again in a moment."


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
        "index_status": doc.index_status,
        "index_error": doc.index_error,
        "chunk_count": doc.chunk_count,
    }

def _archive_existing(document):
    """Keep a metadata snapshot before a document is replaced or removed; the post_delete signal removes the file."""
    DocumentArchive.objects.create(
        account=document.account,
        original_filename=document.original_filename,
        file_type=document.file_type,
        size_bytes=document.size_bytes,
        word_count=document.word_count,
        chunk_count=document.chunk_count,
        uploaded_at=document.uploaded_at,
    )
    document.delete()


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
@client_required(approved_only=True, allow_suspended_read=True)
def document(request):
    account = request.client_account
    existing = ClientDocument.objects.filter(account=account).first()

    # ---- GET: show the current document (or null) ----
    if request.method == "GET":
        if existing:
            refresh_stale(existing)
        return JsonResponse({"document": serialize_document(existing) if existing else None})

    # ---- DELETE: remove the row and archive its metadata; a signal removes the file ----
    if request.method == "DELETE":
        if existing is None:
            return error("You have no document to delete.", 404)
        _archive_existing(existing)
        return JsonResponse({"message": "Document deleted."})

    # ---- POST: upload. Replaces any existing document, archiving its metadata first. ----
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
            if existing is not None:
                _archive_existing(existing)
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
                index_status=ClientDocument.IndexStatus.PROCESSING,
                index_started_at=timezone.now(),
            )
    except IntegrityError:  # two uploads at the same moment
        storage.delete_file(relative_path)
        return error(ALREADY_HAS_DOCUMENT, 409)

    start_indexing(doc.pk)  # chunk + embed in the background
    return JsonResponse({"document": serialize_document(doc)}, status=201)


@require_GET
@client_required(approved_only=True, allow_suspended_read=True)
def version_history(request):
    archives = DocumentArchive.objects.filter(account=request.client_account)[:50]
    return JsonResponse(
        {
            "versions": [
                {
                    "filename": a.original_filename,
                    "file_type": a.file_type,
                    "size_bytes": a.size_bytes,
                    "word_count": a.word_count,
                    "chunk_count": a.chunk_count,
                    "uploaded_at": a.uploaded_at.isoformat(),
                    "archived_at": a.archived_at.isoformat(),
                }
                for a in archives
            ]
        }
    )


STALE_AFTER = timedelta(minutes=20)
MAX_QUERY_CHARS = 300


def refresh_stale(doc):
    """If indexing started long ago and never finished (e.g. the server restarted), mark it failed."""
    if (
        doc.index_status == ClientDocument.IndexStatus.PROCESSING
        and doc.index_started_at
        and timezone.now() - doc.index_started_at > STALE_AFTER
    ):
        doc.index_status = ClientDocument.IndexStatus.FAILED
        doc.index_error = "Preparing the document was interrupted. Please try again."
        doc.save(update_fields=["index_status", "index_error"])


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def reindex(request):
    """Prepare the document for search again (also used for documents uploaded before search existed)."""
    doc = ClientDocument.objects.filter(account=request.client_account).first()
    if doc is None:
        return error("You have no document.", 404)

    refresh_stale(doc)
    if doc.index_status != ClientDocument.IndexStatus.PROCESSING:
        doc.index_status = ClientDocument.IndexStatus.PROCESSING
        doc.index_error = ""
        doc.index_started_at = timezone.now()
        doc.save(update_fields=["index_status", "index_error", "index_started_at"])
        start_indexing(doc.pk)

    return JsonResponse({"document": serialize_document(doc)})


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def search(request):
    """Return the passages — from the document and FAQ entries alike — that best match a question."""
    account = request.client_account
    data = read_json(request) or {}
    query = str(data.get("query", "")).strip()

    if not query:
        return error("Type a question to search for.", 400)
    if len(query) > MAX_QUERY_CHARS:
        return error(f"Keep your question under {MAX_QUERY_CHARS} characters.", 400)

    doc = ClientDocument.objects.filter(account=account).first()
    faq_ready = FAQEntry.objects.filter(account=account, index_status=FAQEntry.IndexStatus.READY).exists()
    doc_ready = False
    if doc is not None:
        refresh_stale(doc)
        doc_ready = doc.index_status == ClientDocument.IndexStatus.READY

    if not doc_ready and not faq_ready:
        return error("Upload a document or add a ready FAQ entry first.", 404)

    try:
        vector = embed_query(query)
    except Exception:
        logger.exception("Could not embed the search query")
        return error("Search is unavailable right now. Please try again.", 503)

    candidates = []
    if doc_ready:
        doc_matches = (
            DocumentChunk.objects.filter(account=account, document=doc, embedding_model=settings.EMBEDDING_MODEL)
            .annotate(distance=CosineDistance("embedding", vector))
            .order_by("distance")
            .defer("embedding")[: settings.SEARCH_TOP_K]
        )
        candidates.extend(
            {
                "source": "document",
                "text": chunk.text,
                "section": chunk.section_label,
                "page": chunk.page_number,
                "distance": float(chunk.distance),
            }
            for chunk in doc_matches
        )

    if faq_ready:
        faq_matches = (
            FAQEntry.objects.filter(
                account=account, index_status=FAQEntry.IndexStatus.READY, embedding_model=settings.EMBEDDING_MODEL
            )
            .annotate(distance=CosineDistance("embedding", vector))
            .order_by("distance")[: settings.SEARCH_TOP_K]
        )
        candidates.extend(
            {
                "source": "faq",
                "text": f"Q: {entry.question}\nA: {entry.answer}",
                "section": "FAQ",
                "page": None,
                "distance": float(entry.distance),
            }
            for entry in faq_matches
        )

    candidates.sort(key=lambda row: row["distance"])
    top = candidates[: settings.SEARCH_TOP_K]

    results = [
        {
            "rank": rank,
            "score": round(1 - row["distance"], 3),
            "text": row["text"],
            "section": row["section"],
            "page": row["page"],
            "source": row["source"],
        }
        for rank, row in enumerate(top, start=1)
    ]
    return JsonResponse({"query": query, "results": results})