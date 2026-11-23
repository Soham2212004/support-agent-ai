"""Verifies that per-plan limits are enforced, and that concurrent requests can't
double-count or bypass the monthly/daily usage caps.
"""
from concurrent.futures import ThreadPoolExecutor

from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from . import chat
from .models import ChatUsage, Plan, PublicMonthlyUsage
from .public_common import current_month, monthly_message_limit, reserve_monthly_message
from .tests_tenant_isolation import make_approved_account


class PlanAssignmentTests(TestCase):
    def test_new_account_defaults_to_the_free_plan(self):
        account = make_approved_account("newclient@example.com")
        self.assertEqual(account.plan.key, Plan.Key.FREE)

    def test_monthly_message_limit_reads_from_the_assigned_plan(self):
        pro = Plan.objects.get(key=Plan.Key.PRO)
        account = make_approved_account("pro-client@example.com")
        account.plan = pro
        account.save(update_fields=["plan"])
        self.assertEqual(monthly_message_limit(account), pro.monthly_messages)


class MonthlyUsageLimitTests(TestCase):
    def setUp(self):
        self.account = make_approved_account("usage@example.com")
        free = Plan.objects.get(key=Plan.Key.FREE)
        free.monthly_messages = 3
        free.save(update_fields=["monthly_messages"])
        self.account.plan = free
        self.account.save(update_fields=["plan"])

    def test_reservation_succeeds_until_the_limit_then_blocks(self):
        for _ in range(3):
            self.assertTrue(reserve_monthly_message(self.account))
        self.assertFalse(reserve_monthly_message(self.account))

        usage = PublicMonthlyUsage.objects.get(account=self.account, month=current_month())
        self.assertEqual(usage.count, 3)


class MonthlyUsageConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.account = make_approved_account("race@example.com")
        free = Plan.objects.get(key=Plan.Key.FREE)
        free.monthly_messages = 5
        free.save(update_fields=["monthly_messages"])
        self.account.plan = free
        self.account.save(update_fields=["plan"])

    def test_concurrent_reservations_never_exceed_the_limit(self):
        import django.db

        def attempt():
            try:
                return reserve_monthly_message(self.account)
            finally:
                django.db.connection.close()

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(lambda _: attempt(), range(20)))

        successes = sum(1 for r in results if r)
        self.assertEqual(successes, 5)

        usage = PublicMonthlyUsage.objects.get(account=self.account, month=current_month())
        self.assertEqual(usage.count, 5)


class DailyTestMessageLimitTests(TestCase):
    def setUp(self):
        self.account = make_approved_account("daily@example.com")
        free = Plan.objects.get(key=Plan.Key.FREE)
        free.daily_test_messages = 2
        free.save(update_fields=["daily_test_messages"])
        self.account.plan = free
        self.account.save(update_fields=["plan"])

    def test_daily_limit_reflects_the_assigned_plan(self):
        self.assertEqual(chat.daily_limit(self.account), 2)

    def test_reserve_message_blocks_once_the_daily_cap_is_reached(self):
        self.assertTrue(chat.reserve_message(self.account))
        self.assertTrue(chat.reserve_message(self.account))
        self.assertFalse(chat.reserve_message(self.account))

        usage = ChatUsage.objects.get(account=self.account, day=timezone.now().date())
        self.assertEqual(usage.count, 2)
