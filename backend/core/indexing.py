"""Chunk a document, embed the chunks and store them. Runs in a background thread after upload."""
import logging
import re
import threading
import time

from django.conf import settings
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from .chunking import split_text
from .embeddings import embed_passages
from .models import ClientDocument, DocumentChunk, IndexingLog

logger = logging.getLogger(__name__)

# section labels that say nothing useful about the content
GENERIC_LABEL = re.compile(r"^(Page \d+|Text|Document)$")

MAX_EMBED_ATTEMPTS = 3
EMBED_BACKOFF_SECONDS = 5  # multiplied by the attempt number


def build_chunks(document):
    """Split every section of the document. Chunks never cross a page or heading."""
    items = []
    for section in document.sections:
        label = section.get("label", "")
        for piece in split_text(
            section["text"], settings.CHUNK_SIZE_CHARS, settings.CHUNK_OVERLAP_CHARS
        ):
            items.append({"text": piece, "label": label, "page": section.get("page")})
    return items


def _embed_with_retry(to_embed, document_id):
    """Try embedding up to MAX_EMBED_ATTEMPTS times, with a short backoff between attempts."""
    last_error = None
    for attempt in range(1, MAX_EMBED_ATTEMPTS + 1):
        try:
            return embed_passages(to_embed)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Embedding attempt %s/%s failed for document %s: %s", attempt, MAX_EMBED_ATTEMPTS, document_id, exc
            )
            if attempt < MAX_EMBED_ATTEMPTS:
                time.sleep(EMBED_BACKOFF_SECONDS * attempt)
    raise last_error


def index_document(document_id):
    """(Re)build all chunks for one document. Safe to run again."""
    close_old_connections()
    log = None
    try:
        document = ClientDocument.objects.get(pk=document_id)
        log = IndexingLog.objects.create(document=document, status=IndexingLog.Status.STARTED)

        items = build_chunks(document)
        if not items:
            raise ValueError("No text to index.")

        # headings help the model understand a chunk, so they are included when it embeds
        to_embed = [
            item["text"] if GENERIC_LABEL.match(item["label"]) else f"{item['label']}\n{item['text']}"
            for item in items
        ]
        vectors = _embed_with_retry(to_embed, document_id)

        rows = [
            DocumentChunk(
                account_id=document.account_id,
                document=document,
                ordinal=number,
                section_label=item["label"][:200],
                page_number=item["page"],
                text=item["text"],
                char_count=len(item["text"]),
                embedding=vector,
                embedding_model=settings.EMBEDDING_MODEL,
            )
            for number, (item, vector) in enumerate(zip(items, vectors), start=1)
        ]

        with transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()
            DocumentChunk.objects.bulk_create(rows, batch_size=200)
            ClientDocument.objects.filter(pk=document.pk).update(
                index_status=ClientDocument.IndexStatus.READY,
                index_error="",
                chunk_count=len(rows),
                indexed_at=timezone.now(),
            )

        IndexingLog.objects.filter(pk=log.pk).update(
            status=IndexingLog.Status.SUCCEEDED, chunk_count=len(rows), finished_at=timezone.now()
        )
    except ClientDocument.DoesNotExist:
        pass  # deleted while we were working
    except Exception as exc:
        logger.exception("Indexing failed for document %s", document_id)
        ClientDocument.objects.filter(pk=document_id).update(
            index_status=ClientDocument.IndexStatus.FAILED,
            index_error="We couldn't prepare this document for search. Please try again.",
        )
        if log is not None:
            IndexingLog.objects.filter(pk=log.pk).update(
                status=IndexingLog.Status.FAILED, error=str(exc)[:2000], finished_at=timezone.now()
            )
    finally:
        connection.close()
def start_indexing(document_id):
    """Run index_document in the background so the upload request can return straight away."""
    threading.Thread(target=index_document, args=(document_id,), daemon=True).start()