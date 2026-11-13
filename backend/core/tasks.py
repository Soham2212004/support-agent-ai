"""Celery tasks: wraps the existing indexing logic so it runs on a worker instead of a bare thread."""
from celery import shared_task

from .indexing import index_document as _index_document_sync


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def index_document_task(self, document_id):
    _index_document_sync(document_id)