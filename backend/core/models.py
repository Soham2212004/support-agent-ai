from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from pgvector.django import VectorField

from .storage import delete_file

# Rejected requests are removed automatically after this many days (about 6 months).
REJECTED_RETENTION_DAYS = 183


class ClientAccount(models.Model):
    """A visitor who registered on the website and is waiting for (or has had) admin review."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    company_name = models.CharField(max_length=200)
    role = models.CharField(max_length=150)
    company_description = models.TextField()
    website = models.URLField(max_length=300)
    reason = models.TextField()
    password = models.CharField(max_length=128)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejected_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "client request"
        verbose_name_plural = "client requests"

    def __str__(self):
        return f"{self.name} ({self.company_name})"

    # ---- password helpers (stored hashed, never in plain text) ----
    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    # ---- review timestamps are kept in sync with the status ----
    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.status == self.Status.PENDING:
            self.reviewed_at = None
            self.rejected_at = None
        else:
            if self.reviewed_at is None:
                self.reviewed_at = now
            if self.status == self.Status.REJECTED:
                if self.rejected_at is None:
                    self.rejected_at = now
            else:
                self.rejected_at = None
        super().save(*args, **kwargs)

    @property
    def auto_delete_on(self):
        if self.status == self.Status.REJECTED and self.rejected_at:
            return self.rejected_at + timedelta(days=REJECTED_RETENTION_DAYS)
        return None

class ClientDocument(models.Model):
    """The one document a client uploads.

    The original file lives on disk (S3 later) and only its path is stored here,
    together with the text extracted from it.
    """

    account = models.OneToOneField(ClientAccount, on_delete=models.CASCADE, related_name="document")
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)  # pdf, docx or txt
    size_bytes = models.PositiveIntegerField()
    content_hash = models.CharField(max_length=64)  # SHA-256 of the file
    file_path = models.CharField(max_length=500)  # relative to STORAGE_ROOT, e.g. documents/3/ab12.pdf
    extracted_text = models.TextField()  # the full text
    # [{"index": 1, "label": "Page 1", "page": 1, "text": "..."}, ...]
    sections = models.JSONField(default=list)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    word_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)

    class IndexStatus(models.TextChoices):
        PENDING = "pending", "Not indexed"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    index_status = models.CharField(max_length=12, choices=IndexStatus.choices, default=IndexStatus.PENDING)
    index_error = models.TextField(blank=True, default="")
    chunk_count = models.PositiveIntegerField(default=0)
    index_started_at = models.DateTimeField(null=True, blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "client document"
        verbose_name_plural = "client documents"

    def __str__(self):
        return f"{self.original_filename} ({self.account.email})"


@receiver(post_delete, sender=ClientDocument)
def remove_document_file(sender, instance, **kwargs):
    """Whenever a document row is deleted (by the user, in admin, or with the account), remove its file."""
    path = instance.file_path
    transaction.on_commit(lambda: delete_file(path))


class DocumentChunk(models.Model):
    """A short passage of a document, with its embedding. Search works on these."""

    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="chunks")
    document = models.ForeignKey(ClientDocument, on_delete=models.CASCADE, related_name="chunks")
    ordinal = models.PositiveIntegerField()  # 1, 2, 3 ... in reading order
    section_label = models.CharField(max_length=200, blank=True)  # "Page 3" or a DOCX heading
    page_number = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()
    char_count = models.PositiveIntegerField()
    # no fixed size, so a different embedding model can be used later without a schema change
    embedding = VectorField(dimensions=None)
    embedding_model = models.CharField(max_length=100)

    class Meta:
        verbose_name = "document chunk"
        verbose_name_plural = "document chunks"
        constraints = [
            models.UniqueConstraint(fields=["document", "ordinal"], name="unique_chunk_ordinal"),
        ]

    def __str__(self):
        return f"{self.document.original_filename} #{self.ordinal}"