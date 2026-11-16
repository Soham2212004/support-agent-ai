"""Embeds a single FAQ entry. Runs on the Celery worker, same pattern as document indexing."""
import logging

from django.conf import settings
from django.db import close_old_connections, connection

from .embeddings import embed_passages
from .models import FAQEntry

logger = logging.getLogger(__name__)


def index_faq_entry(entry_id):
    close_old_connections()
    try:
        entry = FAQEntry.objects.get(pk=entry_id)
        text = f"Question: {entry.question}\nAnswer: {entry.answer}"
        vector = embed_passages([text])[0]
        FAQEntry.objects.filter(pk=entry.pk).update(
            embedding=vector,
            embedding_model=settings.EMBEDDING_MODEL,
            index_status=FAQEntry.IndexStatus.READY,
            index_error="",
        )
    except FAQEntry.DoesNotExist:
        pass  # deleted while we were working
    except Exception:
        logger.exception("Indexing failed for FAQ entry %s", entry_id)
        FAQEntry.objects.filter(pk=entry_id).update(
            index_status=FAQEntry.IndexStatus.FAILED,
            index_error="We couldn't prepare this FAQ entry for search. Please try again.",
        )
    finally:
        connection.close()