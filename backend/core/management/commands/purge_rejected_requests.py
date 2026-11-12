from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import REJECTED_RETENTION_DAYS, ClientAccount, PurgeHeartbeat

TASK_NAME = "purge_rejected_requests"


class Command(BaseCommand):
    help = "Delete client requests that were rejected more than ~6 months ago."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=REJECTED_RETENTION_DAYS)
        old = ClientAccount.objects.filter(status=ClientAccount.Status.REJECTED, rejected_at__lt=cutoff)
        count = old.count()
        old.delete()

        result = f"Purged {count} rejected request(s) older than {REJECTED_RETENTION_DAYS} days."
        PurgeHeartbeat.objects.update_or_create(
            task_name=TASK_NAME, defaults={"last_run_at": timezone.now(), "last_result": result}
        )
        self.stdout.write(result)