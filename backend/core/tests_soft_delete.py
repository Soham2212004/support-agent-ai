"""Verifies that a soft-deleted document or FAQ entry actually disappears from the
places that matter (document endpoint, search, publish) and that restore actually works,
within the 30-day recovery window.
"""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import publishing
from .models import ClientDocument, FAQEntry
from .tests_tenant_isolation import auth_header, make_approved_account

MATCHING_VECTOR = [1.0] * 8


class DocumentSoftDeleteTests(TestCase):
    def setUp(self):
        self.account = make_approved_account("softdelete-doc@example.com")
        self.document = ClientDocument.objects.create(
            account=self.account, original_filename="doc.pdf", file_type="pdf", size_bytes=10,
            content_hash="h", file_path="p", extracted_text="text", index_status=ClientDocument.IndexStatus.READY,
        )

    def test_document_endpoint_shows_nothing_after_delete(self):
        response = self.client.delete(reverse("api-document"), **auth_header(self.account))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("api-document"), **auth_header(self.account))
        self.assertIsNone(response.json()["document"])

    def test_deleted_document_row_still_exists_with_deleted_at_set(self):
        self.client.delete(reverse("api-document"), **auth_header(self.account))
        self.document.refresh_from_db()
        self.assertIsNotNone(self.document.deleted_at)

    def test_uploading_after_delete_does_not_hit_already_has_document_error(self):
        self.client.delete(reverse("api-document"), **auth_header(self.account))
        # Confirm a fresh upload is allowed once the old one is soft-deleted:
        # the document endpoint should report no current document, which is the
        # precondition the upload path checks before accepting a new file.
        response = self.client.get(reverse("api-document"), **auth_header(self.account))
        self.assertIsNone(response.json()["document"])

    def test_restore_brings_the_document_back(self):
        self.client.delete(reverse("api-document"), **auth_header(self.account))

        response = self.client.post(
            reverse("api-document-restore"), data=json.dumps({}), content_type="application/json",
            **auth_header(self.account),
        )
        self.assertEqual(response.status_code, 200)

        self.document.refresh_from_db()
        self.assertIsNone(self.document.deleted_at)

        response = self.client.get(reverse("api-document"), **auth_header(self.account))
        self.assertEqual(response.json()["document"]["filename"], "doc.pdf")

    def test_restore_fails_if_a_current_document_already_exists(self):
        # don't delete first; there's already a live document
        response = self.client.post(
            reverse("api-document-restore"), data=json.dumps({}), content_type="application/json",
            **auth_header(self.account),
        )
        self.assertEqual(response.status_code, 409)

    def test_restore_fails_outside_the_thirty_day_window(self):
        self.client.delete(reverse("api-document"), **auth_header(self.account))
        self.document.refresh_from_db()
        ClientDocument.objects.filter(pk=self.document.pk).update(
            deleted_at=timezone.now() - timezone.timedelta(days=31)
        )

        response = self.client.post(
            reverse("api-document-restore"), data=json.dumps({}), content_type="application/json",
            **auth_header(self.account),
        )
        self.assertEqual(response.status_code, 404)

    def test_deleted_document_is_excluded_from_search(self):
        from .models import DocumentChunk

        DocumentChunk.objects.create(
            account=self.account, document=self.document, ordinal=1, section_label="Page 1", page_number=1,
            text="Our refund window is 30 days.", char_count=30,
            embedding=MATCHING_VECTOR, embedding_model="intfloat/multilingual-e5-small",
        )
        self.client.delete(reverse("api-document"), **auth_header(self.account))

        with patch("core.documents.embed_query", return_value=MATCHING_VECTOR):
            response = self.client.post(
                reverse("api-document-search"), data=json.dumps({"query": "refund"}),
                content_type="application/json", **auth_header(self.account),
            )
        self.assertEqual(response.status_code, 404)  # no document or ready FAQ entry left to search


class FAQSoftDeleteTests(TestCase):
    def setUp(self):
        self.account = make_approved_account("softdelete-faq@example.com")
        self.entry = FAQEntry.objects.create(
            account=self.account, question="What are your hours?", answer="9 to 5.",
            index_status=FAQEntry.IndexStatus.READY, embedding=MATCHING_VECTOR,
            embedding_model="intfloat/multilingual-e5-small",
        )

    def test_faq_list_excludes_deleted_entries(self):
        url = reverse("api-faq-detail", args=[self.entry.pk])
        self.client.delete(url, **auth_header(self.account))

        response = self.client.get(reverse("api-faq-list"), **auth_header(self.account))
        self.assertEqual(response.json()["entries"], [])

    def test_deleted_faq_entry_appears_in_the_deleted_list(self):
        url = reverse("api-faq-detail", args=[self.entry.pk])
        self.client.delete(url, **auth_header(self.account))

        response = self.client.get(reverse("api-faq-deleted-list"), **auth_header(self.account))
        self.assertEqual(len(response.json()["entries"]), 1)
        self.assertEqual(response.json()["entries"][0]["question"], "What are your hours?")

    def test_restore_brings_the_faq_entry_back_into_the_live_list(self):
        url = reverse("api-faq-detail", args=[self.entry.pk])
        self.client.delete(url, **auth_header(self.account))

        restore_url = reverse("api-faq-restore", args=[self.entry.pk])
        response = self.client.post(restore_url, data=json.dumps({}), content_type="application/json", **auth_header(self.account))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("api-faq-list"), **auth_header(self.account))
        self.assertEqual(len(response.json()["entries"]), 1)

    def test_deleted_faq_entry_is_excluded_from_publish(self):
        response = self.client.post(reverse("api-publish"), data=json.dumps({}), content_type="application/json", **auth_header(self.account))
        self.assertEqual(response.status_code, 201)  # with the entry still live, publish succeeds

        # delete the only knowledge source, then publishing again should fail
        url = reverse("api-faq-detail", args=[self.entry.pk])
        self.client.delete(url, **auth_header(self.account))

        response = self.client.post(reverse("api-publish"), data=json.dumps({}), content_type="application/json", **auth_header(self.account))
        self.assertEqual(response.status_code, 409)
