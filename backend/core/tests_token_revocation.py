"""Verifies that changing a password, resetting a password, or explicitly logging out
everywhere actually invalidates previously issued tokens, rather than just looking like
it does on the surface.
"""
import json

from django.core import signing
from django.test import TestCase
from django.urls import reverse

from .api import TOKEN_SALT, make_token
from .tests_tenant_isolation import auth_header, make_approved_account


class TokenRevocationTests(TestCase):
    def setUp(self):
        self.account = make_approved_account("tokenuser@example.com")
        self.account.set_password("originalpass123")
        self.account.save()

    def test_a_fresh_token_is_accepted(self):
        response = self.client.get(reverse("api-me"), **auth_header(self.account))
        self.assertEqual(response.status_code, 200)

    def test_token_signed_with_wrong_version_is_rejected(self):
        # Simulate an old token issued before any token_version bump, by hand-crafting
        # one with a stale version number instead of the account's current one.
        stale_token = signing.dumps({"id": self.account.pk, "tv": self.account.token_version - 1 or 999}, salt=TOKEN_SALT)
        response = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {stale_token}")
        self.assertEqual(response.status_code, 401)

    def test_change_password_invalidates_the_old_token_but_issues_a_new_one(self):
        old_token = make_token(self.account)

        response = self.client.post(
            reverse("api-change-password"),
            data=json.dumps({"current_password": "originalpass123", "new_password": "newpassword456"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {old_token}",
        )
        self.assertEqual(response.status_code, 200)
        new_token = response.json()["token"]
        self.assertNotEqual(old_token, new_token)

        # the old token must now be rejected everywhere
        old_response = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {old_token}")
        self.assertEqual(old_response.status_code, 401)

        # the new token issued by the same call must work
        new_response = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {new_token}")
        self.assertEqual(new_response.status_code, 200)

    def test_change_password_with_wrong_current_password_does_not_revoke_anything(self):
        old_token = make_token(self.account)

        response = self.client.post(
            reverse("api-change-password"),
            data=json.dumps({"current_password": "wrongpassword", "new_password": "newpassword456"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {old_token}",
        )
        self.assertEqual(response.status_code, 400)

        # the original token must still work, since nothing should have changed
        still_valid = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {old_token}")
        self.assertEqual(still_valid.status_code, 200)

    def test_logout_everywhere_invalidates_every_existing_token(self):
        token_a = make_token(self.account)
        token_b = make_token(self.account)  # a "second device" session

        response = self.client.post(
            reverse("api-logout-everywhere"), data=json.dumps({}), content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_a}",
        )
        self.assertEqual(response.status_code, 200)

        for token in (token_a, token_b):
            result = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
            self.assertEqual(result.status_code, 401)

    def test_password_reset_confirmation_invalidates_existing_tokens(self):
        from .api import PASSWORD_RESET_SALT

        old_token = make_token(self.account)
        reset_token = signing.dumps({"id": self.account.pk}, salt=PASSWORD_RESET_SALT)

        response = self.client.post(
            reverse("api-password-reset-confirm"),
            data=json.dumps({"token": reset_token, "password": "brandnewpassword789"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        result = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {old_token}")
        self.assertEqual(result.status_code, 401)

        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password("brandnewpassword789"))
