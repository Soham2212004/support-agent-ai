from datetime import timedelta

from django.utils import timezone

from .models import ClientAccount, PurgeHeartbeat

EXPECTED_PURGE_TASKS = ["purge_rejected_requests", "purge_public_chat_data"]
STALE_AFTER = timedelta(hours=25)  # the loop runs every 24h; 1h of slack before flagging it


def pending_requests(request):
    """Adds the number of pending client requests to admin pages (for the home-page banner)."""
    user = getattr(request, "user", None)
    if not request.path.startswith("/admin/") or not (user and user.is_authenticated and user.is_staff):
        return {}
    return {
        "pending_client_requests": ClientAccount.objects.filter(status=ClientAccount.Status.PENDING).count()
    }


def purge_health(request):
    """Flags cleanup background loops that haven't reported a heartbeat recently (dead or never started)."""
    user = getattr(request, "user", None)
    if not request.path.startswith("/admin/") or not (user and user.is_authenticated and user.is_staff):
        return {}

    seen = dict(PurgeHeartbeat.objects.values_list("task_name", "last_run_at"))
    cutoff = timezone.now() - STALE_AFTER
    stale = [name for name in EXPECTED_PURGE_TASKS if name not in seen or seen[name] < cutoff]
    return {"stale_purge_tasks": stale}