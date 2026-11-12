import logging
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .api import client_required, error, read_json
from .models import BotSettings, DEFAULT_BOT_FALLBACK, DEFAULT_BOT_GREETING

logger = logging.getLogger(__name__)

MAX_NAME_CHARS = 100
MAX_GREETING_CHARS = 500
MAX_INSTRUCTIONS_CHARS = 1000
MAX_FALLBACK_CHARS = 500
MIN_SIMILARITY = 0.3
MAX_SIMILARITY = 0.95
MAX_STARTER_QUESTIONS = 4
MAX_STARTER_QUESTION_CHARS = 150


def serialize_settings(settings):
    return {
        "name": settings.name or settings.display_name,
        "greeting": settings.active_greeting,
        "tone": settings.tone,
        "custom_instructions": settings.custom_instructions,
        "fallback_message": settings.active_fallback,
        "similarity_threshold": settings.similarity_threshold,
        "show_citations": settings.show_citations,
        "max_answer_length": settings.max_answer_length,
        "starter_questions": settings.starter_questions,
        "escalation_email": settings.escalation_email,
        "avatar_url": settings.avatar_url,
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

        try:
            similarity_threshold = float(data.get("similarity_threshold", settings.similarity_threshold))
        except (TypeError, ValueError):
            errors["similarity_threshold"] = "Enter a number."
        else:
            if not (MIN_SIMILARITY <= similarity_threshold <= MAX_SIMILARITY):
                errors["similarity_threshold"] = f"Choose a value between {MIN_SIMILARITY} and {MAX_SIMILARITY}."

        show_citations = bool(data.get("show_citations", True))

        max_answer_length = str(data.get("max_answer_length", "")).strip().lower()
        if not max_answer_length:
            max_answer_length = BotSettings.AnswerLength.STANDARD
        elif max_answer_length not in BotSettings.AnswerLength.values:
            errors["max_answer_length"] = "Please select a valid answer length."

        raw_questions = data.get("starter_questions", [])
        starter_questions = []
        if isinstance(raw_questions, list):
            for item in raw_questions[:MAX_STARTER_QUESTIONS]:
                text = str(item).strip()
                if not text:
                    continue
                if len(text) > MAX_STARTER_QUESTION_CHARS:
                    errors["starter_questions"] = (
                        f"Each starter question must be under {MAX_STARTER_QUESTION_CHARS} characters."
                    )
                    break
                starter_questions.append(text)

        escalation_email = str(data.get("escalation_email", "")).strip().lower()
        if escalation_email:
            try:
                validate_email(escalation_email)
            except ValidationError:
                errors["escalation_email"] = "Enter a valid email address."

        avatar_url = str(data.get("avatar_url", "")).strip()
        if avatar_url:
            try:
                URLValidator(schemes=["http", "https"])(avatar_url)
            except ValidationError:
                errors["avatar_url"] = "Enter a valid image URL, like https://example.com/avatar.png."

        if errors:
            return error("Please correct the errors before saving.", 400, errors)

        settings.name = name
        settings.greeting = greeting
        settings.tone = tone
        settings.custom_instructions = custom_instructions
        settings.fallback_message = fallback_message
        settings.similarity_threshold = similarity_threshold
        settings.show_citations = show_citations
        settings.max_answer_length = max_answer_length
        settings.starter_questions = starter_questions
        settings.escalation_email = escalation_email
        settings.avatar_url = avatar_url
        settings.save()

        return JsonResponse(
            {
                "message": "Bot settings saved successfully.",
                "settings": serialize_settings(settings),
            }
        )

    return error("Method not allowed.", 405)
