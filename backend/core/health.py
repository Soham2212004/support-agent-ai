"""Unauthenticated health check: database and pgvector."""
from django.db import connection
from django.http import JsonResponse


def health(request):
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            checks["pgvector"] = "ok" if cursor.fetchone() else "not installed"
    except Exception as exc:
        checks["pgvector"] = f"error: {exc}"

    healthy = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if healthy else "degraded", "checks": checks}, status=200 if healthy else 503)