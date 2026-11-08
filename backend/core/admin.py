from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.models import Group, User
from django.utils.html import format_html

from .models import ClientAccount, ClientDocument
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
    list_display = ("original_filename", "account", "file_type", "size_kb", "word_count", "uploaded_at")
    list_filter = ("file_type", "uploaded_at")
    search_fields = ("original_filename", "account__email", "account__company_name")

    fields = (
        "account", "original_filename", "file_type", "size_bytes", "page_count", "word_count",
        "char_count", "file_path", "content_hash", "uploaded_at", "extracted_text", "sections",
    )
    readonly_fields = fields  # view only

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Size")
    def size_kb(self, obj):
        return f"{obj.size_bytes / 1024:.0f} KB"