from .models import ClientAccount


def pending_requests(request):
    """Adds the number of pending client requests to admin pages (for the home-page banner)."""
    user = getattr(request, "user", None)
    if not request.path.startswith("/admin/") or not (user and user.is_authenticated and user.is_staff):
        return {}
    return {
        "pending_client_requests": ClientAccount.objects.filter(status=ClientAccount.Status.PENDING).count()
    }