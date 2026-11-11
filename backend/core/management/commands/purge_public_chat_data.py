from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import PublicChatSession, PublicRateLimitBucket

TRANSCRIPT_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = "Delete public visitor transcripts older than 90 days and expired rate-limit buckets."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=TRANSCRIPT_RETENTION_DAYS)
        old_sessions = PublicChatSession.objects.filter(created_at__lt=cutoff)
        session_count = old_sessions.count()
        old_sessions.delete()

        old_buckets = PublicRateLimitBucket.objects.filter(minute__lt=timezone.now() - timedelta(days=1))
        bucket_count = old_buckets.count()
        old_buckets.delete()
        self.stdout.write(
            f"Purged {session_count} public visitor transcript(s) older than "
            f"{TRANSCRIPT_RETENTION_DAYS} days and {bucket_count} expired rate-limit bucket(s)."
        )
