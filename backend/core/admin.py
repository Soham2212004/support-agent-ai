from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.models import Group, User
from django.utils.html import format_html

from .models import ClientAccount, ClientDocument, DocumentChunk
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
class ClientDocumentAdmin(admin.ModelAdmin):
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
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "ordinal", "section_label", "page_number", "char_count", "embedding_model")
    list_filter = ("embedding_model",)
    search_fields = ("text", "document__original_filename", "account__email")
    list_select_related = ("document",)

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

from .models import Conversation, Message  # noqa: E402


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    fields = ("seq", "role", "content", "is_fallback", "provider", "llm_model", "tokens_in", "tokens_out", "status")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "message_count", "created_at", "updated_at")
    search_fields = ("account__email",)
    inlines = [MessageInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # view only

    @admin.display(description="Messages")
    def message_count(self, obj):
        return obj.messages.count()
