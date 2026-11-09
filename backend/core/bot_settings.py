"""Bot settings API: view and update chatbot personality, instructions, and fallback."""
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .api import client_required, error, read_json
from .models import BotSettings, DEFAULT_BOT_FALLBACK, DEFAULT_BOT_GREETING

logger = logging.getLogger(__name__)

MAX_NAME_CHARS = 100
MAX_GREETING_CHARS = 500
MAX_INSTRUCTIONS_CHARS = 1000
MAX_FALLBACK_CHARS = 500


def serialize_settings(settings):
    return {
        "name": settings.name or settings.display_name,
        "greeting": settings.active_greeting,
        "tone": settings.tone,
        "custom_instructions": settings.custom_instructions,
        "fallback_message": settings.active_fallback,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }


@csrf_exempt
@client_required(approved_only=True)
def bot_settings(request):
    account = request.client_account
    settings = BotSettings.get_for_account(account)

    if request.method == "GET":
        return JsonResponse(serialize_settings(settings))

    if request.method == "POST":
        data = read_json(request)
        if data is None:
            return error("Invalid JSON request body.", 400)

        errors = {}

        name = str(data.get("name", "")).strip()
        if len(name) > MAX_NAME_CHARS:
            errors["name"] = f"Bot name cannot exceed {MAX_NAME_CHARS} characters."

        greeting = str(data.get("greeting", "")).strip()
        if not greeting:
            greeting = DEFAULT_BOT_GREETING
        elif len(greeting) > MAX_GREETING_CHARS:
            errors["greeting"] = f"Greeting cannot exceed {MAX_GREETING_CHARS} characters."

        tone = str(data.get("tone", "")).strip().lower()
        if tone not in (BotSettings.Tone.FRIENDLY, BotSettings.Tone.PROFESSIONAL, BotSettings.Tone.CONCISE):
            errors["tone"] = "Please select a valid tone: friendly, professional, or concise."

        custom_instructions = str(data.get("custom_instructions", "")).strip()
        if len(custom_instructions) > MAX_INSTRUCTIONS_CHARS:
            errors["custom_instructions"] = f"Custom instructions cannot exceed {MAX_INSTRUCTIONS_CHARS} characters."

        fallback_message = str(data.get("fallback_message", "")).strip()
        if not fallback_message:
            fallback_message = DEFAULT_BOT_FALLBACK
        elif len(fallback_message) > MAX_FALLBACK_CHARS:
            errors["fallback_message"] = f"Fallback message cannot exceed {MAX_FALLBACK_CHARS} characters."

        if errors:
            return error("Please correct the errors before saving.", 400, errors)

        settings.name = name
        settings.greeting = greeting
        settings.tone = tone
        settings.custom_instructions = custom_instructions
        settings.fallback_message = fallback_message
        settings.save()

        return JsonResponse(
            {
                "message": "Bot settings saved successfully.",
                "settings": serialize_settings(settings),
            }
        )

    return error("Method not allowed.", 405)
