"""Verifies the handoff state machine: waiting -> replied -> resolved/expired, the
10-minute reminder, the 30-minute auto-expiry, and the 24-hour auto-resolve.
"""
import json

from django.core import signing
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import tasks
from .public_api import VISITOR_TOKEN_SALT
from .tests_tenant_isolation import auth_header, make_approved_account
from .models import AllowedWebsite, HandoffRequest, PublicChatMessage, PublicChatSession, PublishedBotVersion


class HandoffStateMachineTests(TestCase):
    def setUp(self):
        self.account = make_approved_account("client@example.com")
        self.version = PublishedBotVersion.objects.create(
            account=self.account,
            version=1,
            document_name="doc.pdf",
            embedding_model="intfloat/multilingual-e5-small",
            settings_snapshot={"display_name": "Bot", "greeting": "Hi", "tone": "friendly", "custom_instructions": "", "fallback_message": "Sorry."},
        )
        AllowedWebsite.objects.create(account=self.account, origin="https://clientsite.com")
        self.session = PublicChatSession.objects.create(
            account=self.account,
            version=self.version,
            visitor_name="Visitor",
            visitor_email="visitor@example.com",
            origin="https://clientsite.com",
            expires_at=timezone.now() + timezone.timedelta(minutes=30),
        )
        self.visitor_token = signing.dumps(
            {"session": str(self.session.token_id), "version": self.version.pk}, salt=VISITOR_TOKEN_SALT
        )

    def _visitor_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.visitor_token}", "HTTP_ORIGIN": "https://clientsite.com"}

    # ---- Creation ----
    def test_requesting_a_human_sets_session_to_waiting_and_emails_the_client(self):
        response = self.client.post(
            reverse("public-handoff"), data=json.dumps({"reason": "Need help with billing"}),
            content_type="application/json", **self._visitor_headers(),
        )
        self.assertEqual(response.status_code, 201)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, PublicChatSession.Status.WAITING_HUMAN)

        handoff = HandoffRequest.objects.get(session=self.session)
        self.assertEqual(handoff.status, HandoffRequest.Status.WAITING)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Need help with billing", mail.outbox[0].body)

    def test_requesting_a_human_twice_does_not_create_a_second_open_request(self):
        self.client.post(reverse("public-handoff"), data=json.dumps({}), content_type="application/json", **self._visitor_headers())
        self.client.post(reverse("public-handoff"), data=json.dumps({}), content_type="application/json", **self._visitor_headers())
        self.assertEqual(HandoffRequest.objects.filter(session=self.session).count(), 1)

    # ---- Reply ----
    def test_client_reply_moves_session_to_human_replied(self):
        handoff = HandoffRequest.objects.create(session=self.session, account=self.account)
        PublicChatSession.objects.filter(pk=self.session.pk).update(status=PublicChatSession.Status.WAITING_HUMAN)

        url = reverse("api-handoff-reply", args=[handoff.pk])
        response = self.client.post(
            url, data=json.dumps({"content": "I'll help you with that."}),
            content_type="application/json", **auth_header(self.account),
        )
        self.assertEqual(response.status_code, 201)

        handoff.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(handoff.status, HandoffRequest.Status.REPLIED)
        self.assertIsNotNone(handoff.replied_at)
        self.assertEqual(self.session.status, PublicChatSession.Status.HUMAN_REPLIED)

        human_message = PublicChatMessage.objects.filter(session=self.session, role=PublicChatMessage.Role.HUMAN).first()
        self.assertIsNotNone(human_message)
        self.assertEqual(human_message.content, "I'll help you with that.")

    def test_reply_to_already_resolved_handoff_fails(self):
        handoff = HandoffRequest.objects.create(
            session=self.session, account=self.account, status=HandoffRequest.Status.RESOLVED, resolved_at=timezone.now()
        )
        url = reverse("api-handoff-reply", args=[handoff.pk])
        response = self.client.post(
            url, data=json.dumps({"content": "Too late"}), content_type="application/json", **auth_header(self.account)
        )
        self.assertEqual(response.status_code, 404)

    # ---- Resolve ----
    def test_resolving_a_handoff_returns_session_to_active(self):
        handoff = HandoffRequest.objects.create(session=self.session, account=self.account)
        PublicChatSession.objects.filter(pk=self.session.pk).update(status=PublicChatSession.Status.WAITING_HUMAN)

        url = reverse("api-handoff-resolve", args=[handoff.pk])
        response = self.client.post(url, data=json.dumps({}), content_type="application/json", **auth_header(self.account))
        self.assertEqual(response.status_code, 200)

        handoff.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(handoff.status, HandoffRequest.Status.RESOLVED)
        self.assertEqual(self.session.status, PublicChatSession.Status.ACTIVE)

    # ---- Bot stays silent while a handoff is open ----
    def test_bot_does_not_answer_while_waiting_for_human(self):
        PublicChatSession.objects.filter(pk=self.session.pk).update(status=PublicChatSession.Status.WAITING_HUMAN)
        response = self.client.post(
            reverse("public-chat"), data=json.dumps({"content": "Are you still there?"}),
            content_type="application/json", **self._visitor_headers(),
        )
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode()
        self.assertIn("waiting_human", body)
        self.assertTrue(
            PublicChatMessage.objects.filter(session=self.session, role=PublicChatMessage.Role.USER, content="Are you still there?").exists()
        )

    # ---- Timers ----
    def test_reminder_is_sent_after_ten_minutes(self):
        handoff = HandoffRequest.objects.create(session=self.session, account=self.account)
        HandoffRequest.objects.filter(pk=handoff.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=11))

        tasks.check_handoff_timers()

        handoff.refresh_from_db()
        self.assertIsNotNone(handoff.reminder_sent_at)
        self.assertEqual(handoff.status, HandoffRequest.Status.WAITING)
        self.assertTrue(any("still waiting" in m.subject for m in mail.outbox))

    def test_reminder_is_not_sent_twice(self):
        handoff = HandoffRequest.objects.create(session=self.session, account=self.account)
        HandoffRequest.objects.filter(pk=handoff.pk).update(
            created_at=timezone.now() - timezone.timedelta(minutes=11), reminder_sent_at=timezone.now()
        )
        tasks.check_handoff_timers()
        self.assertEqual(len([m for m in mail.outbox if "still waiting" in m.subject]), 0)

    def test_handoff_expires_after_thirty_minutes_and_bot_resumes(self):
        handoff = HandoffRequest.objects.create(session=self.session, account=self.account)
        PublicChatSession.objects.filter(pk=self.session.pk).update(status=PublicChatSession.Status.WAITING_HUMAN)
        HandoffRequest.objects.filter(pk=handoff.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=31))

        tasks.check_handoff_timers()

        handoff.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(handoff.status, HandoffRequest.Status.EXPIRED)
        self.assertEqual(self.session.status, PublicChatSession.Status.ACTIVE)

        system_message = PublicChatMessage.objects.filter(session=self.session, role=PublicChatMessage.Role.SYSTEM).first()
        self.assertIsNotNone(system_message)

    def test_replied_handoff_auto_resolves_after_twenty_four_hours(self):
        handoff = HandoffRequest.objects.create(
            session=self.session, account=self.account, status=HandoffRequest.Status.REPLIED, replied_at=timezone.now()
        )
        PublicChatSession.objects.filter(pk=self.session.pk).update(status=PublicChatSession.Status.HUMAN_REPLIED)
        HandoffRequest.objects.filter(pk=handoff.pk).update(replied_at=timezone.now() - timezone.timedelta(hours=25))

        tasks.check_handoff_timers()

        handoff.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(handoff.status, HandoffRequest.Status.RESOLVED)
        self.assertEqual(self.session.status, PublicChatSession.Status.ACTIVE)

    def test_recently_replied_handoff_is_not_auto_resolved_early(self):
        handoff = HandoffRequest.objects.create(
            session=self.session, account=self.account, status=HandoffRequest.Status.REPLIED, replied_at=timezone.now()
        )
        tasks.check_handoff_timers()
        handoff.refresh_from_db()
        self.assertEqual(handoff.status, HandoffRequest.Status.REPLIED)
