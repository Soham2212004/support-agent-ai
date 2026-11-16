"""Celery tasks: wraps the existing indexing logic so it runs on a worker instead of a bare thread."""
from celery import shared_task

from .faq_indexing import index_faq_entry as _index_faq_entry_sync
from .indexing import index_document as _index_document_sync


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def index_document_task(self, document_id):
    _index_document_sync(document_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def index_faq_entry_task(self, entry_id):
    _index_faq_entry_sync(entry_id)


@shared_task
def check_handoff_timers():
    """Runs every minute (Celery beat): sends 10-minute reminders and expires handoffs after 30 minutes idle."""
    import logging

    from django.core.mail import send_mail
    from django.db.models import F
    from django.utils import timezone

    from .models import HandoffRequest, PublicChatMessage, PublicChatSession
    from .public_api import HANDOFF_EXPIRE_AFTER, HANDOFF_REMINDER_AFTER

    logger = logging.getLogger(__name__)
    now = timezone.now()

    # 10-minute reminder for still-waiting handoffs that haven't been reminded yet
    due_for_reminder = HandoffRequest.objects.filter(
        status=HandoffRequest.Status.WAITING,
        reminder_sent_at__isnull=True,
        created_at__lte=now - HANDOFF_REMINDER_AFTER,
    ).select_related("session", "account")
    for handoff in due_for_reminder:
        try:
            send_mail(
                subject=f"Reminder: a visitor is still waiting — {handoff.session.visitor_name}",
                message=(
                    f"{handoff.session.visitor_name} ({handoff.session.visitor_email}) has been waiting "
                    f"for a human for 10 minutes. Reply from your dashboard's Handoffs tab. "
                    f"If nobody replies within 30 minutes total, the bot will resume automatically."
                ),
                from_email=None,
                recipient_list=[handoff.account.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Could not send handoff reminder email for handoff %s", handoff.pk)
        HandoffRequest.objects.filter(pk=handoff.pk).update(reminder_sent_at=now)

    # 30-minute auto-expiry: tell the visitor, return the conversation to the bot
    due_for_expiry = HandoffRequest.objects.filter(
        status=HandoffRequest.Status.WAITING, created_at__lte=now - HANDOFF_EXPIRE_AFTER
    ).select_related("session")
    for handoff in due_for_expiry:
        session = handoff.session
        next_seq = (session.messages.order_by("-seq").values_list("seq", flat=True).first() or 0) + 1
        PublicChatMessage.objects.create(
            session=session,
            seq=next_seq,
            role=PublicChatMessage.Role.SYSTEM,
            content="Our team wasn't able to join in time — they'll follow up with you by email. You can keep chatting with the bot in the meantime.",
        )
        PublicChatSession.objects.filter(pk=session.pk).update(status=PublicChatSession.Status.ACTIVE, updated_at=now)
        HandoffRequest.objects.filter(pk=handoff.pk).update(status=HandoffRequest.Status.EXPIRED)

    # Auto-resolve a replied handoff nobody explicitly closed after 24 hours
    stale_replied = HandoffRequest.objects.filter(
        status=HandoffRequest.Status.REPLIED, replied_at__lte=now - timezone.timedelta(hours=24)
    )
    for handoff in stale_replied:
        PublicChatSession.objects.filter(pk=handoff.session_id).update(status=PublicChatSession.Status.ACTIVE)
    stale_replied.update(status=HandoffRequest.Status.RESOLVED, resolved_at=now)