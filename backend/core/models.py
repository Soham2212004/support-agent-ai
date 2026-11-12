from datetime import timedelta
import uuid

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

class Conversation(models.Model):
    """One chat between a client and the bot, on the client's own document (the test chat)."""

    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "conversation"
        verbose_name_plural = "conversations"

    def __str__(self):
        return f"Conversation {self.pk} ({self.account.email})"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    class Status(models.TextChoices):
        COMPLETE = "complete", "Complete"
        PARTIAL = "partial", "Partial"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    seq = models.PositiveIntegerField()  # 1, 2, 3 ... in the order the messages were sent
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField(blank=True)
    citations = models.JSONField(default=list, blank=True)  # [{"n", "label", "page", "text"}]
    is_fallback = models.BooleanField(default=False)
    fallback_reason = models.CharField(max_length=20, blank=True, default="")  # weak_evidence or no_answer
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETE)
    provider = models.CharField(max_length=20, blank=True, default="")
    llm_model = models.CharField(max_length=100, blank=True, default="")
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["seq"]
        verbose_name = "message"
        verbose_name_plural = "messages"
        constraints = [
            models.UniqueConstraint(fields=["conversation", "seq"], name="unique_message_seq"),
        ]

    def __str__(self):
        return f"{self.role} #{self.seq}"


class ChatUsage(models.Model):
    """How many test messages a client has used on one (UTC) day. Enforces the daily limit."""

    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="chat_usage")
    day = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "chat usage"
        verbose_name_plural = "chat usage"
        constraints = [
            models.UniqueConstraint(fields=["account", "day"], name="unique_chat_usage_day"),
        ]


DEFAULT_BOT_GREETING = "Hello! How can I help you today?"
DEFAULT_BOT_FALLBACK = (
    "I couldn't find the answer to that in your document. "
    "Try rephrasing your question, or ask about something the document covers."
)


class BotSettings(models.Model):
    """Client customization for their support chatbot."""

    class Tone(models.TextChoices):
        FRIENDLY = "friendly", "Friendly"
        PROFESSIONAL = "professional", "Professional"
        CONCISE = "concise", "Concise"

    class AnswerLength(models.TextChoices):
        SHORT = "short", "Short"
        STANDARD = "standard", "Standard"
        DETAILED = "detailed", "Detailed"

    account = models.OneToOneField(ClientAccount, on_delete=models.CASCADE, related_name="bot_settings")
    name = models.CharField(max_length=100, blank=True, default="")
    greeting = models.TextField(blank=True, default=DEFAULT_BOT_GREETING)
    tone = models.CharField(max_length=20, choices=Tone.choices, default=Tone.FRIENDLY)
    custom_instructions = models.TextField(blank=True, default="")
    fallback_message = models.TextField(blank=True, default=DEFAULT_BOT_FALLBACK)

    # answer behavior
    similarity_threshold = models.FloatField(default=0.75)
    show_citations = models.BooleanField(default=True)
    max_answer_length = models.CharField(max_length=20, choices=AnswerLength.choices, default=AnswerLength.STANDARD)

    # conversation experience
    starter_questions = models.JSONField(default=list, blank=True)
    escalation_email = models.EmailField(blank=True, default="")
    avatar_url = models.URLField(max_length=500, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "bot settings"
        verbose_name_plural = "bot settings"

    def __str__(self):
        return f"Settings for {self.account.company_name} ({self.display_name})"

    @property
    def display_name(self):
        val = (self.name or "").strip()
        if val:
            return val
        if self.account_id and self.account.company_name:
            return f"{self.account.company_name} Assistant"
        return "Support Assistant"

    @property
    def active_greeting(self):
        return (self.greeting or "").strip() or DEFAULT_BOT_GREETING

    @property
    def active_fallback(self):
        base = (self.fallback_message or "").strip() or DEFAULT_BOT_FALLBACK
        if self.escalation_email:
            base += f" You can also reach us directly at {self.escalation_email}."
        return base

    @classmethod
    def get_for_account(cls, account):
        obj = cls.objects.filter(account=account).first()
        if obj is None:
            default_name = f"{account.company_name} Assistant" if account.company_name else "Support Assistant"
            obj, _ = cls.objects.get_or_create(
                account=account,
                defaults={
                    "name": default_name,
                    "greeting": DEFAULT_BOT_GREETING,
                    "tone": cls.Tone.FRIENDLY,
                    "custom_instructions": "",
                    "fallback_message": DEFAULT_BOT_FALLBACK,
                },
            )
        return obj


class PublishedBotVersion(models.Model):
    """Immutable chatbot configuration and indexed document captured at publish time."""

    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="published_versions")
    version = models.PositiveIntegerField()
    document_name = models.CharField(max_length=255)
    document_hash = models.CharField(max_length=64)
    document_text = models.TextField()
    document_sections = models.JSONField(default=list)
    document_metadata = models.JSONField(default=dict)
    settings_snapshot = models.JSONField(default=dict)
    embedding_model = models.CharField(max_length=100)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["account", "version"], name="unique_published_bot_version"),
        ]

    def __str__(self):
        return f"{self.account.company_name} bot v{self.version}"


class PublishedBotChunk(models.Model):
    """An immutable copy of a document chunk and its vector for a published bot version."""

    version = models.ForeignKey(PublishedBotVersion, on_delete=models.CASCADE, related_name="chunks")
    ordinal = models.PositiveIntegerField()
    section_label = models.CharField(max_length=200, blank=True)
    page_number = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()
    embedding = VectorField(dimensions=None)
    embedding_model = models.CharField(max_length=100)

    class Meta:
        ordering = ["ordinal"]
        constraints = [
            models.UniqueConstraint(fields=["version", "ordinal"], name="unique_published_chunk_ordinal"),
        ]


class ClientApiKey(models.Model):
    """A hashed client secret; plaintext is returned only when first created."""

    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="api_keys")
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def usable(self):
        now = timezone.now()
        return self.revoked_at is None and (self.expires_at is None or self.expires_at > now)


class AllowedWebsite(models.Model):
    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="allowed_websites")
    origin = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["origin"]
        constraints = [
            models.UniqueConstraint(fields=["account", "origin"], name="unique_allowed_website_origin"),
        ]

    def __str__(self):
        return self.origin


class PublicChatSession(models.Model):
    """One visitor identity and transcript, retained for the configured retention period."""

    token_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="public_chat_sessions")
    version = models.ForeignKey(PublishedBotVersion, on_delete=models.PROTECT, related_name="visitor_sessions")
    visitor_name = models.CharField(max_length=150)
    visitor_email = models.EmailField()
    origin = models.CharField(max_length=300)
    expires_at = models.DateTimeField()
    is_generating = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["created_at"], name="public_session_created_idx")]


class PublicChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    session = models.ForeignKey(PublicChatSession, on_delete=models.CASCADE, related_name="messages")
    seq = models.PositiveIntegerField()
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField(blank=True)
    citations = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, default="complete")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["seq"]
        constraints = [
            models.UniqueConstraint(fields=["session", "seq"], name="unique_public_message_seq"),
        ]


class PublicMonthlyUsage(models.Model):
    account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="public_monthly_usage")
    month = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "month"], name="unique_public_monthly_usage"),
        ]


class PublicRateLimitBucket(models.Model):
    scope = models.CharField(max_length=30)
    key = models.CharField(max_length=100)
    minute = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope", "key", "minute"], name="unique_public_rate_bucket"),
        ]
