"""JSON API used by the React website: register, sign in, and "who am I".

Authentication is a signed bearer token (no cookies), so it never clashes with the
Django admin session and does not need CSRF protection.
"""
import json
from functools import wraps

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import ClientAccount

TOKEN_SALT = "support-agent-ai.client"
TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # sign-in lasts 7 days


# ---------------------------------------------------------------- helpers
def error(message, status=400, errors=None):
    return JsonResponse({"message": message, "errors": errors or {}}, status=status)


def read_json(request):
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def make_token(account):
    return signing.dumps({"id": account.pk}, salt=TOKEN_SALT)


def account_from_request(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        payload = signing.loads(header[7:].strip(), salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:  # includes expired tokens
        return None
    return ClientAccount.objects.filter(pk=payload.get("id")).first()


def serialize(account):
    return {
        "name": account.name,
        "email": account.email,
        "company_name": account.company_name,
        "role": account.role,
        "status": account.status,
    }


def client_required(approved_only=False):
    """Decorator for future API views. Use approved_only=True for dashboard data."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            account = account_from_request(request)
            if account is None:
                return error("Please sign in.", 401)
            if approved_only and account.status != ClientAccount.Status.APPROVED:
                return error("Your request has not been approved.", 403)
            request.client_account = account
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------- views
@csrf_exempt
@require_POST
def register(request):
    data = read_json(request)
    if data is None:
        return error("Invalid request.")

    cleaned, errors = {}, {}

    def text(field, label, max_len):
        value = str(data.get(field, "")).strip()
        if not value:
            errors[field] = f"{label} is required."
        elif len(value) > max_len:
            errors[field] = f"{label} is too long (maximum {max_len} characters)."
        cleaned[field] = value

    text("name", "Name", 150)
    text("email", "Email", 254)
    text("company_name", "Company name", 200)
    text("role", "Your role", 150)
    text("company_description", "Company description", 1000)
    text("website", "Company website", 300)
    text("reason", "This answer", 1000)

    # email
    if "email" not in errors:
        cleaned["email"] = cleaned["email"].lower()
        try:
            validate_email(cleaned["email"])
        except ValidationError:
            errors["email"] = "Enter a valid email address."

    # website (add https:// if the person left it out)
    if "website" not in errors:
        site = cleaned["website"]
        if not site.lower().startswith(("http://", "https://")):
            site = "https://" + site
        try:
            URLValidator(schemes=["http", "https"])(site)
            cleaned["website"] = site
        except ValidationError:
            errors["website"] = "Enter a valid website address, like https://example.com."

    # password
    password = str(data.get("password", ""))
    confirm = str(data.get("confirm_password", ""))
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 8:
        errors["password"] = "Use at least 8 characters."
    elif len(password) > 128:
        errors["password"] = "Password is too long."
    if not confirm:
        errors["confirm_password"] = "Please confirm your password."
    elif password and confirm != password:
        errors["confirm_password"] = "Passwords do not match."

    # duplicate email
    if "email" not in errors:
        existing = ClientAccount.objects.filter(email=cleaned["email"]).first()
        if existing:
            if existing.status == ClientAccount.Status.REJECTED:
                errors["email"] = "A request with this email was rejected. Please try again after a few months."
            else:
                errors["email"] = "An account with this email already exists. Please sign in."

    if errors:
        return error("Please fix the highlighted fields.", 400, errors)

    account = ClientAccount(**cleaned)
    account.set_password(password)
    try:
        account.save()
    except IntegrityError:
        return error("Please fix the highlighted fields.", 400, {"email": "An account with this email already exists."})

    return JsonResponse({"message": "Request received."}, status=201)


@csrf_exempt
@require_POST
def login(request):
    data = read_json(request)
    if data is None:
        return error("Invalid request.")

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    account = ClientAccount.objects.filter(email=email).first()
    if account is None or not account.check_password(password):
        return error("Invalid email or password.", 401)

    return JsonResponse({"token": make_token(account), "account": serialize(account)})


@require_GET
def me(request):
    account = account_from_request(request)
    if account is None:
        return error("Please sign in.", 401)
    return JsonResponse({"account": serialize(account)})