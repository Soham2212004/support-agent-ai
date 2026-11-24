"""Verifies that repeated login attempts are actually blocked, both per-IP and
per-account, rather than the rate limiter silently doing nothing.
"""
import json

from django.test import TestCase
from django.urls import reverse

from .api import LOGIN_RATE_PER_ACCOUNT_PER_15_MIN, LOGIN_RATE_PER_IP_PER_MINUTE
from .tests_tenant_isolation import make_approved_account


class LoginRateLimitTests(TestCase):
    def setUp(self):
        # A fresh, unique email and IP per test, so Redis-backed rate-limit buckets from one
        # test (which Django's transaction rollback does NOT clear, unlike Postgres state)
        # can never bleed into another test running in the same real-world minute.
        import uuid

        unique = uuid.uuid4().hex[:8]
        self.test_email = f"ratelimit-{unique}@example.com"
        self.test_ip = f"10.{int(unique[:2], 16) % 250}.{int(unique[2:4], 16) % 250}.1"
        self.account = make_approved_account(self.test_email)
        self.account.set_password("correctpassword123")
        self.account.save()

    def _attempt(self, email=None, password="wrongpassword", ip=None):
        return self.client.post(
            reverse("api-login"),
            data=json.dumps({"email": email or self.test_email, "password": password}),
            content_type="application/json",
            REMOTE_ADDR=ip or self.test_ip,
        )

    def test_failed_attempts_under_the_limit_return_401_not_429(self):
        for _ in range(LOGIN_RATE_PER_ACCOUNT_PER_15_MIN):
            response = self._attempt()
            self.assertEqual(response.status_code, 401)

    def test_the_attempt_past_the_per_account_limit_is_blocked_with_429(self):
        for _ in range(LOGIN_RATE_PER_ACCOUNT_PER_15_MIN):
            self._attempt()

        blocked_response = self._attempt()
        self.assertEqual(blocked_response.status_code, 429)

    def test_a_correct_password_is_also_blocked_once_the_account_is_rate_limited(self):
        # Rate limiting must apply before the credentials are even checked, so a correct
        # password submitted right after a flood of wrong ones is still blocked.
        for _ in range(LOGIN_RATE_PER_ACCOUNT_PER_15_MIN):
            self._attempt()

        response = self._attempt(password="correctpassword123")
        self.assertEqual(response.status_code, 429)

    def test_the_per_ip_limit_blocks_requests_regardless_of_which_account_is_targeted(self):
        shared_ip = f"{self.test_ip}-shared-a"
        for i in range(LOGIN_RATE_PER_IP_PER_MINUTE):
            self._attempt(email=f"nonexistent-{i}-{self.test_email}", ip=shared_ip)

        blocked_response = self._attempt(email=f"yet-another-{self.test_email}", ip=shared_ip)
        self.assertEqual(blocked_response.status_code, 429)

    def test_different_ips_do_not_share_the_per_ip_bucket(self):
        ip_one = f"{self.test_ip}-one"
        ip_two = f"{self.test_ip}-two"
        for i in range(LOGIN_RATE_PER_IP_PER_MINUTE):
            self._attempt(email=f"nonexistent-{i}-{self.test_email}", ip=ip_one)

        # a different IP should not be affected by the first IP's bucket
        response = self._attempt(email=f"fresh-{self.test_email}", ip=ip_two)
        self.assertNotEqual(response.status_code, 429)
