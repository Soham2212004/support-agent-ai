from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import PublicChatSession, PurgeHeartbeat

TRANSCRIPT_RETENTION_DAYS = 90
TASK_NAME = "purge_public_chat_data"


class Command(BaseCommand):
    help = "Delete public visitor transcripts older than 90 days. Rate-limit buckets live in Redis with their own TTL."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=TRANSCRIPT_RETENTION_DAYS)
        old_sessions = PublicChatSession.objects.filter(created_at__lt=cutoff)
        session_count = old_sessions.count()
        old_sessions.delete()

        result = f"Purged {session_count} public visitor transcript(s) older than {TRANSCRIPT_RETENTION_DAYS} days."
        PurgeHeartbeat.objects.update_or_create(
            task_name=TASK_NAME, defaults={"last_run_at": timezone.now(), "last_result": result}
        )
        self.stdout.write(result)