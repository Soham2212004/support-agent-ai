from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.models import Group, User
from django.utils.html import format_html

from .models import (
    AdminAuditLog,
    ClientAccount,
    ClientDocument,
    DocumentChunk,
    BotSettings,
    HandoffRequest,
    IndexingLog,
    PurgeHeartbeat,
)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class AuditedViewMixin:
    """Logs every time a staff member opens the list or a detail page for a sensitive model."""

    def changelist_view(self, request, extra_context=None):
        AdminAuditLog.objects.create(
            staff_user=request.user if request.user.is_authenticated else None,
            model_name=str(self.model._meta.verbose_name),
            action=AdminAuditLog.Action.VIEW_LIST,
            ip_address=_client_ip(request),
        )
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        AdminAuditLog.objects.create(
            staff_user=request.user if request.user.is_authenticated else None,
            model_name=str(self.model._meta.verbose_name),
            object_id=str(object_id),
            object_repr=str(obj) if obj else "",
            action=AdminAuditLog.Action.VIEW,
            ip_address=_client_ip(request),
        )
        return super().change_view(request, object_id, form_url, extra_context)
admin.site.site_header = "Support Agent AI"
admin.site.site_title = "Support Agent AI Admin"
admin.site.index_title = "Welcome"

# Keep the admin tidy: hide Django's default Users and Groups.
# To show them again later, delete these lines.
for model in (User, Group):
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass


@admin.register(ClientAccount)
class ClientAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "company_name", "role", "status_badge", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "company_name")
    actions = ["approve_selected", "reject_selected"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Applicant", {"fields": ("name", "email", "role")}),
        ("Company", {"fields": ("company_name", "website", "company_description", "reason")}),
        ("Review", {"fields": ("status", "created_at", "reviewed_at", "rejected_at", "auto_delete_on")}),
    )
    # Everything the applicant typed is read-only; the admin only decides the status.
    readonly_fields = (
        "name", "email", "role", "company_name", "website", "company_description", "reason",
        "created_at", "reviewed_at", "rejected_at", "auto_delete_on",
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {"pending": "#b45309", "approved": "#15803d", "rejected": "#b91c1c"}
        return format_html(
            '<strong style="color:{}">{}</strong>', colors.get(obj.status, "#444"), obj.get_status_display()
        )

    @admin.display(description="Deleted automatically on")
    def auto_delete_on(self, obj):
        when = obj.auto_delete_on
        return when.strftime("%d %b %Y") if when else "-"

    def _set_status(self, request, queryset, status, label):
        count = 0
        for obj in queryset.exclude(status=status):
            obj.status = status
            obj.save()  # save() keeps the review timestamps correct
            count += 1
        self.message_user(request, f"{count} request(s) {label}.", messages.SUCCESS)

    @admin.action(description="Approve selected requests")
    def approve_selected(self, request, queryset):
        self._set_status(request, queryset, ClientAccount.Status.APPROVED, "approved")

    @admin.action(description="Reject selected requests")
    def reject_selected(self, request, queryset):
        self._set_status(request, queryset, ClientAccount.Status.REJECTED, "rejected")


@admin.register(ClientDocument)
class ClientDocumentAdmin(AuditedViewMixin, admin.ModelAdmin):
    list_display = (
        "original_filename", "account", "file_type", "size_kb", "word_count", "index_status", "chunk_count",
        "uploaded_at",
    )
    list_filter = ("file_type", "uploaded_at")
    search_fields = ("original_filename", "account__email", "account__company_name")

    fields = (
        "account", "original_filename", "file_type", "size_bytes", "page_count", "word_count",
        "char_count", "file_path", "content_hash", "uploaded_at", "index_status", "chunk_count",
        "indexed_at", "index_error", "extracted_text", "sections",
    )
    readonly_fields = fields  # view only

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Size")
    def size_kb(self, obj):
        return f"{obj.size_bytes / 1024:.0f} KB"

@admin.register(DocumentChunk)
class DocumentChunkAdmin(AuditedViewMixin, admin.ModelAdmin):
    list_display = ("document", "ordinal", "section_label", "page_number", "char_count", "embedding_model")
    list_filter = ("document", "embedding_model")
    search_fields = ("text", "document__original_filename", "account__email")
    list_select_related = ("document",)
    ordering = ("document__original_filename", "ordinal")
    list_per_page = 50

    fields = (
        "account", "document", "ordinal", "section_label", "page_number", "char_count",
        "embedding_model", "text",
    )
    readonly_fields = fields  # view only; the vector itself is not shown

    def get_queryset(self, request):
        return super().get_queryset(request).defer("embedding")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

from django.utils import timezone  # noqa: E402
from django.utils.html import format_html  # noqa: E402
from django.utils.safestring import mark_safe  # noqa: E402

from .models import Conversation, Message  # noqa: E402


def _when(value):
    """Show a time in the project's time zone, with seconds."""
    return timezone.localtime(value).strftime("%d %b %Y, %I:%M:%S %p")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "message_count", "started", "last_message")
    list_select_related = ("account",)
    search_fields = ("account__email", "account__name", "account__company_name")

    fields = ("account", "started", "last_message", "transcript")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # view only

    @admin.display(description="Messages")
    def message_count(self, obj):
        return obj.messages.count()

    @admin.display(description="Started", ordering="created_at")
    def started(self, obj):
        return _when(obj.created_at)

    @admin.display(description="Last message", ordering="updated_at")
    def last_message(self, obj):
        return _when(obj.updated_at)

    @admin.display(description="Conversation")
    def transcript(self, obj):
        messages = list(obj.messages.order_by("seq"))
        if not messages:
            return "No messages yet."

        blocks = []
        asked_at = None
        for message in messages:
            is_user = message.role == Message.Role.USER
            details = []

            if is_user:
                who = obj.account.name
                background = "rgba(65, 120, 150, 0.18)"
                asked_at = message.created_at
            else:
                who = "Assistant"
                background = "rgba(245, 165, 36, 0.22)" if message.is_fallback else "rgba(128, 128, 128, 0.14)"
                if asked_at:
                    details.append(f"answered in {(message.created_at - asked_at).total_seconds():.1f}s")
                if message.provider:
                    details.append(f"{message.provider} / {message.llm_model}")
                if message.tokens_in or message.tokens_out:
                    details.append(f"{message.tokens_in} tokens in, {message.tokens_out} out")
                if message.is_fallback:
                    details.append(f"no answer found ({message.fallback_reason or 'fallback'})")
                if message.status == Message.Status.PARTIAL:
                    details.append("interrupted")
                sources = ", ".join(f"[{c.get('n')}] {c.get('label', '')}" for c in (message.citations or []))
                if sources:
                    details.append(f"sources: {sources}")

            extra = ""
            if details:
                extra = format_html(
                    '<div style="margin-top:8px;font-size:12px;opacity:0.75;">{}</div>', " | ".join(details)
                )

            blocks.append(
                format_html(
                    '<div style="margin:0 0 12px;padding:10px 14px;border-radius:8px;background:{};">'
                    '<div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:6px;'
                    'font-size:12px;opacity:0.85;"><strong>{}</strong><span>{}</span></div>'
                    '<div style="white-space:pre-wrap;overflow-wrap:anywhere;">{}</div>{}</div>',
                    background,
                    who,
                    _when(message.created_at),
                    message.content or "(empty)",
                    extra,
                )
            )
        return mark_safe("".join(blocks))


@admin.register(BotSettings)
class BotSettingsAdmin(admin.ModelAdmin):
    list_display = ("account", "name", "tone", "updated_at")
    list_select_related = ("account",)
    search_fields = ("account__email", "account__company_name", "name")
    list_filter = ("tone", "updated_at")

    fieldsets = (
        ("Client", {"fields": ("account",)}),
        ("Bot Personality", {"fields": ("name", "tone", "greeting", "avatar_url")}),
        ("Instructions & Fallback", {"fields": ("custom_instructions", "fallback_message", "escalation_email")}),
        ("Answer Behavior", {"fields": ("similarity_threshold", "show_citations", "max_answer_length")}),
        ("Conversation Experience", {"fields": ("starter_questions",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = (
        "account",
        "name",
        "tone",
        "greeting",
        "avatar_url",
        "custom_instructions",
        "fallback_message",
        "escalation_email",
        "similarity_threshold",
        "show_citations",
        "max_answer_length",
        "starter_questions",
        "created_at",
        "updated_at",
    )
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "staff_user", "action", "model_name", "object_id", "object_repr", "ip_address")
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("staff_user__username", "object_id", "object_repr")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AdminAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IndexingLog)
class IndexingLogAdmin(admin.ModelAdmin):
    list_display = ("document", "status", "chunk_count", "started_at", "finished_at")
    list_filter = ("status", "started_at")
    search_fields = ("document__original_filename", "document__account__email")
    list_select_related = ("document",)
    readonly_fields = ("document", "status", "chunk_count", "error", "started_at", "finished_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PurgeHeartbeat)
class PurgeHeartbeatAdmin(admin.ModelAdmin):
    list_display = ("task_name", "last_run_at", "status_badge", "last_result")
    readonly_fields = ("task_name", "last_run_at", "last_result")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Status")
    def status_badge(self, obj):
        from datetime import timedelta
        from django.utils import timezone
        from django.utils.html import format_html

        stale = timezone.now() - obj.last_run_at > timedelta(hours=25)
        color, label = ("#b91c1c", "Stale") if stale else ("#15803d", "OK")
        return format_html('<strong style="color:{}">{}</strong>', color, label)
    
    
    
@admin.register(HandoffRequest)
class HandoffRequestAdmin(admin.ModelAdmin):
    list_display = ("account", "session_visitor", "status", "created_at", "resolved_at")
    list_filter = ("status", "created_at")
    search_fields = ("account__email", "session__visitor_name", "session__visitor_email")
    list_select_related = ("account", "session")
    actions = ["mark_resolved"]

    fields = ("account", "session", "reason", "status", "created_at", "resolved_at")
    readonly_fields = ("account", "session", "reason", "created_at", "resolved_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Visitor")
    def session_visitor(self, obj):
        return f"{obj.session.visitor_name} ({obj.session.visitor_email})"

    @admin.action(description="Mark selected requests resolved")
    def mark_resolved(self, request, queryset):
        from django.utils import timezone

        count = queryset.filter(status=HandoffRequest.Status.OPEN).update(
            status=HandoffRequest.Status.RESOLVED, resolved_at=timezone.now()
        )
        self.message_user(request, f"{count} request(s) marked resolved.", messages.SUCCESS)