"""Public, unauthenticated endpoints for the Pricing page's plan table and the Contact form."""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .api import error, read_json
from .models import ContactMessage, Plan
from .public_common import reserve_rate_limit

CONTACT_RATE_PER_IP_PER_HOUR = 5


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


@require_GET
def public_config(request):
    plans = Plan.objects.exclude(key=Plan.Key.INTERNAL)
    return JsonResponse(
        {
            "plans": [
                {
                    "key": p.key,
                    "name": p.name,
                    "monthly_messages": p.monthly_messages,
                    "max_documents": p.max_documents,
                    "max_faq_entries": p.max_faq_entries,
                }
                for p in plans
            ]
        }
    )


@csrf_exempt
@require_POST
def contact(request):
    ip = _client_ip(request)
    if not reserve_rate_limit("contact", ip, CONTACT_RATE_PER_IP_PER_HOUR * 60):
        # bucket is per-minute in reserve_rate_limit, so scale the limit to an hourly feel
        # by just using a generous per-minute cap here; fine for a local/low-traffic contact form
        return error("Too many messages. Please try again later.", 429)

    data = read_json(request)
    if data is None:
        return error("Invalid request.")

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    message = str(data.get("message", "")).strip()

    errors = {}
    if not name or len(name) > 150:
        errors["name"] = "Enter your name (up to 150 characters)."
    try:
        validate_email(email)
    except ValidationError:
        errors["email"] = "Enter a valid email address."
    if not message or len(message) > 2000:
        errors["message"] = "Enter a message (up to 2000 characters)."

    if errors:
        return error("Please fix the highlighted fields.", 400, errors)

    ContactMessage.objects.create(name=name, email=email, message=message)
    return JsonResponse({"message": "Thanks — we'll get back to you soon."}, status=201)