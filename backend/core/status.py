"""Public, unauthenticated changelog feed for the /status page."""
from django.http import JsonResponse

from .models import ChangelogEntry


def changelog_list(request):
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed."}, status=405)
    entries = ChangelogEntry.objects.all()[:50]
    return JsonResponse(
        {
            "entries": [
                {"title": e.title, "body": e.body, "published_at": e.published_at.isoformat()}
                for e in entries
            ]
        }
    )