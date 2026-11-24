"""Verifies that one client can never read, modify, or delete another client's data
through any dashboard API endpoint. A failure here means real data leakage between
paying customers, so this is the highest-stakes test file in the project.
"""
import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .api import make_token
from .models import (
    AllowedWebsite,
    BotSettings,
    ClientAccount,
    ClientDocument,
    FAQEntry,
    HandoffRequest,
    Lead,
    Plan,
    PublishedBotVersion,
    PublicChatSession,
)


def make_approved_account(email, company="Acme"):
    plan = Plan.objects.filter(key=Plan.Key.FREE).first()
    account = ClientAccount(
        name="Test User",
        email=email,
        company_name=company,
        role="Owner",
        company_description="A test company",
        website="https://example.com",
        reason="Testing",
        status=ClientAccount.Status.APPROVED,
        plan=plan,
    )
    account.set_password("testpass123")
    account.save()
    return account


def auth_header(account):
    return {"HTTP_AUTHORIZATION": f"Bearer {make_token(account)}"}


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.account_a = make_approved_account("a@example.com", "Company A")
        self.account_b = make_approved_account("b@example.com", "Company B")

        self.document_a = ClientDocument.objects.create(
            account=self.account_a,
            original_filename="secret-a.pdf",
            file_type="pdf",
            size_bytes=100,
            content_hash="hash-a",
            file_path="documents/a/file.pdf",
            extracted_text="Confidential text belonging to Company A",
            sections=[],
            word_count=5,
            char_count=40,
            index_status=ClientDocument.IndexStatus.READY,
        )

        self.faq_a = FAQEntry.objects.create(
            account=self.account_a, question="What is our refund policy?", answer="30 days, no questions asked."
        )

        self.lead_a = Lead.objects.create(account=self.account_a, name="Visitor One", email="visitor1@example.com")

        version_a = PublishedBotVersion.objects.create(
            account=self.account_a,
            version=1,
            document_name="secret-a.pdf",
            embedding_model="intfloat/multilingual-e5-small",
            settings_snapshot={"display_name": "Bot A", "greeting": "Hi", "tone": "friendly", "custom_instructions": "", "fallback_message": "Sorry."},
        )
        self.session_a = PublicChatSession.objects.create(
            account=self.account_a,
            version=version_a,
            visitor_name="Visitor One",
            visitor_email="visitor1@example.com",
            origin="https://clientsite.com",
            expires_at=timezone.now() + timezone.timedelta(minutes=30),
        )
        self.handoff_a = HandoffRequest.objects.create(session=self.session_a, account=self.account_a, reason="Need a human")

    # ---- Document ----
    def test_document_endpoint_returns_only_own_document(self):
        response = self.client.get(reverse("api-document"), **auth_header(self.account_b))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["document"])  # B has no document of their own

        response = self.client.get(reverse("api-document"), **auth_header(self.account_a))
        self.assertEqual(response.json()["document"]["filename"], "secret-a.pdf")

    # ---- FAQ entries ----
    def test_faq_list_is_scoped_per_account(self):
        response = self.client.get(reverse("api-faq-list"), **auth_header(self.account_b))
        self.assertEqual(response.json()["entries"], [])

        response = self.client.get(reverse("api-faq-list"), **auth_header(self.account_a))
        self.assertEqual(len(response.json()["entries"]), 1)

    def test_faq_detail_other_account_returns_404(self):
        url = reverse("api-faq-detail", args=[self.faq_a.pk])
        response = self.client.delete(url, **auth_header(self.account_b))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(FAQEntry.objects.filter(pk=self.faq_a.pk).exists())

    def test_faq_delete_other_account_fails_and_leaves_entry_intact(self):
        url = reverse("api-faq-detail", args=[self.faq_a.pk])
        response = self.client.delete(url, **auth_header(self.account_b))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(FAQEntry.objects.filter(pk=self.faq_a.pk).exists())

    def test_faq_update_other_account_fails(self):
        url = reverse("api-faq-detail", args=[self.faq_a.pk])
        response = self.client.patch(
            url, data=json.dumps({"question": "Hijacked", "answer": "Hijacked"}),
            content_type="application/json", **auth_header(self.account_b),
        )
        self.assertEqual(response.status_code, 404)
        self.faq_a.refresh_from_db()
        self.assertEqual(self.faq_a.question, "What is our refund policy?")

    # ---- Leads ----
    def test_leads_list_is_scoped_per_account(self):
        response = self.client.get(reverse("api-leads"), **auth_header(self.account_b))
        self.assertEqual(response.json()["leads"], [])

    # ---- Bot settings ----
    def test_bot_settings_are_independent_per_account(self):
        url = reverse("api-bot-settings")
        self.client.post(
            url, data=json.dumps({"name": "Account A Bot", "greeting": "hi", "tone": "friendly"}),
            content_type="application/json", **auth_header(self.account_a),
        )
        response = self.client.get(url, **auth_header(self.account_b))
        self.assertNotEqual(response.json().get("name"), "Account A Bot")

    # ---- Conversations ----
    def test_conversation_list_is_scoped_per_account(self):
        response = self.client.get(reverse("api-conversations"), **auth_header(self.account_b))
        self.assertEqual(response.json()["conversations"], [])

    def test_conversation_detail_other_account_returns_404(self):
        url = reverse("api-conversation-detail", args=[self.session_a.pk])
        response = self.client.get(url, **auth_header(self.account_b))
        self.assertEqual(response.status_code, 404)

    # ---- Handoffs ----
    def test_handoff_list_is_scoped_per_account(self):
        response = self.client.get(reverse("api-handoffs"), **auth_header(self.account_b))
        self.assertEqual(response.json()["handoffs"], [])

    def test_handoff_detail_other_account_returns_404(self):
        url = reverse("api-handoff-detail", args=[self.handoff_a.pk])
        response = self.client.get(url, **auth_header(self.account_b))
        self.assertEqual(response.status_code, 404)

    def test_handoff_reply_other_account_fails_and_does_not_reply(self):
        url = reverse("api-handoff-reply", args=[self.handoff_a.pk])
        response = self.client.post(
            url, data=json.dumps({"content": "Hijacked reply"}),
            content_type="application/json", **auth_header(self.account_b),
        )
        self.assertEqual(response.status_code, 404)
        self.handoff_a.refresh_from_db()
        self.assertEqual(self.handoff_a.status, HandoffRequest.Status.WAITING)

    def test_handoff_resolve_other_account_fails(self):
        url = reverse("api-handoff-resolve", args=[self.handoff_a.pk])
        response = self.client.post(url, data=json.dumps({}), content_type="application/json", **auth_header(self.account_b))
        self.assertEqual(response.status_code, 404)
        self.handoff_a.refresh_from_db()
        self.assertEqual(self.handoff_a.status, HandoffRequest.Status.WAITING)
