"""Full client data export (ZIP of JSON/CSV) and self-serve account deletion."""
import csv
import io
import json
import zipfile

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .api import client_required, error, read_json
from .models import (
    BotSettings,
    ClientDocument,
    Conversation,
    FAQEntry,
    Lead,
    Message,
    PublicChatMessage,
    PublicChatSession,
)


def _csv_bytes(headers, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


@require_http_methods(["GET"])
@client_required(approved_only=False)
def export_account(request):
    account = request.client_account
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "account.json",
            json.dumps(
                {
                    "name": account.name,
                    "email": account.email,
                    "company_name": account.company_name,
                    "role": account.role,
                    "website": account.website,
                    "status": account.status,
                    "created_at": account.created_at.isoformat(),
                },
                indent=2,
            ),
        )

        settings_obj = BotSettings.objects.filter(account=account).first()
        if settings_obj:
            zf.writestr(
                "bot_settings.json",
                json.dumps(
                    {
                        "name": settings_obj.name,
                        "greeting": settings_obj.greeting,
                        "tone": settings_obj.tone,
                        "custom_instructions": settings_obj.custom_instructions,
                        "fallback_message": settings_obj.fallback_message,
                        "similarity_threshold": settings_obj.similarity_threshold,
                        "max_answer_length": settings_obj.max_answer_length,
                        "starter_questions": settings_obj.starter_questions,
                    },
                    indent=2,
                ),
            )

        document = ClientDocument.objects.filter(account=account).first()
        if document:
            zf.writestr(
                "document.json",
                json.dumps(
                    {
                        "filename": document.original_filename,
                        "file_type": document.file_type,
                        "uploaded_at": document.uploaded_at.isoformat(),
                        "extracted_text": document.extracted_text,
                    },
                    indent=2,
                ),
            )

        faq_rows = [[e.question, e.answer, e.updated_at.isoformat()] for e in FAQEntry.objects.filter(account=account)]
        zf.writestr("faq_entries.csv", _csv_bytes(["question", "answer", "updated_at"], faq_rows))

        test_rows = []
        for m in Message.objects.filter(conversation__account=account).order_by("created_at"):
            test_rows.append([m.role, m.content, m.is_fallback, m.feedback, m.created_at.isoformat()])
        zf.writestr("test_chat_messages.csv", _csv_bytes(["role", "content", "is_fallback", "feedback", "created_at"], test_rows))

        public_rows = []
        for m in PublicChatMessage.objects.filter(session__account=account).order_by("created_at"):
            public_rows.append([m.role, m.content, m.is_fallback, m.feedback, m.created_at.isoformat()])
        zf.writestr(
            "public_chat_messages.csv",
            _csv_bytes(["role", "content", "is_fallback", "feedback", "created_at"], public_rows),
        )

        lead_rows = [
            [lead.name, lead.email, lead.first_seen_at.isoformat(), lead.last_seen_at.isoformat(), lead.conversation_count]
            for lead in Lead.objects.filter(account=account)
        ]
        zf.writestr("leads.csv", _csv_bytes(["name", "email", "first_seen_at", "last_seen_at", "conversation_count"], lead_rows))

    buf.seek(0)
    response = HttpResponse(buf.read(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="account_export.zip"'
    return response


@csrf_exempt
@require_http_methods(["POST"])
@client_required(approved_only=False)
def delete_account(request):
    account = request.client_account
    data = read_json(request) or {}
    password = str(data.get("password", ""))
    if not password or not account.check_password(password):
        return error("Enter your current password to confirm account deletion.", 400, {"password": "Incorrect password."})

    # Cascades: document, chunks, conversations, messages, leads, API keys, published
    # versions, handoffs, etc. all have on_delete=CASCADE back to ClientAccount.
    account.delete()
    return JsonResponse({"message": "Your account and all associated data have been deleted."})