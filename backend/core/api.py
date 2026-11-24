"""JSON API used by the React website: register, sign in, and "who am I".

Authentication is a signed bearer token (no cookies), so it never clashes with the
Django admin session and does not need CSRF protection.
"""
import json
import logging
import os
from functools import wraps

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import ClientAccount

logger = logging.getLogger(__name__)

TOKEN_SALT = "support-agent-ai.client"
TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # sign-in lasts 7 days

EMAIL_VERIFY_SALT = "support-agent-ai.email-verify"
EMAIL_VERIFY_MAX_AGE = 60 * 60 * 24  # 24 hours

PASSWORD_RESET_SALT = "support-agent-ai.password-reset"
PASSWORD_RESET_MAX_AGE = 60 * 60  # 1 hour
# Common disposable/throwaway email providers. A local, free check — no external service.
DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com", "tempmail.com", "temp-mail.org", "10minutemail.com",
    "guerrillamail.com", "throwawaymail.com", "yopmail.com", "trashmail.com",
    "fakeinbox.com", "sharklasers.com", "getnada.com", "dispostable.com",
    "maildrop.cc", "mintemail.com", "mailnesia.com",
}


def make_verification_token(account):
    return signing.dumps({"id": account.pk}, salt=EMAIL_VERIFY_SALT)


def send_verification_email(account):
    token = make_verification_token(account)
    frontend_base = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")
    link = f"{frontend_base}/verify-email?token={token}"
    try:
        send_mail(
            subject="Verify your email — Support Agent AI",
            message=(
                f"Hi {account.name},\n\n"
                f"Click the link below to verify your email and move your request to review:\n\n"
                f"{link}\n\n"
                f"This link expires in 24 hours. If you didn't request this, ignore this email."
            ),
            from_email=None,
            recipient_list=[account.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Could not send verification email to %s", account.email)


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

def client_required(approved_only=False, allow_suspended_read=False):
    """Decorator for dashboard API views. Use approved_only=True for anything beyond basic account info.

    allow_suspended_read=True lets a suspended account's GET requests through (read-only access and
    data export stay available while suspended). Writes always require full approval.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            account = account_from_request(request)
            if account is None:
                return error("Please sign in.", 401)
            if approved_only and account.status != ClientAccount.Status.APPROVED:
                if allow_suspended_read and account.status == ClientAccount.Status.SUSPENDED and request.method == "GET":
                    pass  # read-only access stays available while suspended
                elif account.status == ClientAccount.Status.SUSPENDED:
                    return error("Your account is suspended. You can still export your data.", 403)
                elif account.status == ClientAccount.Status.UNVERIFIED:
                    return error("Please verify your email first.", 403)
                else:
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
        else:
            domain = cleaned["email"].rsplit("@", 1)[-1]
            if domain in DISPOSABLE_EMAIL_DOMAINS:
                errors["email"] = "Please use a permanent email address, not a disposable one."

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

    send_verification_email(account)
    return JsonResponse({"message": "Check your email to verify your account."}, status=201)


@csrf_exempt
@require_POST
def verify_email(request):
    data = read_json(request)
    if data is None:
        return error("Invalid request.")
    token = str(data.get("token", "")).strip()
    if not token:
        return error("A verification code is required.", 400)
    try:
        payload = signing.loads(token, salt=EMAIL_VERIFY_SALT, max_age=EMAIL_VERIFY_MAX_AGE)
    except signing.BadSignature:
        return error("This verification link is invalid or has expired.", 400)

    account = ClientAccount.objects.filter(pk=payload.get("id")).first()
    if account is None:
        return error("This verification link is invalid or has expired.", 400)

    if account.status == ClientAccount.Status.UNVERIFIED:
        account.status = ClientAccount.Status.PENDING
        account.email_verified_at = timezone.now()
        account.save()

    return JsonResponse(
        {
            "message": "Email verified. Your request is now pending approval.",
            "token": make_token(account),
            "account": serialize(account),
        }
    )


@csrf_exempt
@require_POST
def resend_verification(request):
    data = read_json(request)
    if data is None:
        return error("Invalid request.")
    email = str(data.get("email", "")).strip().lower()
    account = ClientAccount.objects.filter(email=email, status=ClientAccount.Status.UNVERIFIED).first()
    if account:
        send_verification_email(account)
    # Same response whether or not the account exists or is already verified, so this endpoint
    # never reveals account state to a caller who doesn't already know the password.
    return JsonResponse({"message": "If that email needs verifying, a new link has been sent."})


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



@csrf_exempt
@require_POST
def request_password_reset(request):
    data = read_json(request)
    if data is None:
        return error("Invalid request.")
    email = str(data.get("email", "")).strip().lower()

    account = ClientAccount.objects.filter(email=email).first()
    if account is not None:
        token = signing.dumps({"id": account.pk}, salt=PASSWORD_RESET_SALT)
        frontend_base = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")
        link = f"{frontend_base}/reset-password?token={token}"
        try:
            send_mail(
                subject="Reset your password — Support Agent AI",
                message=(
                    f"Hi {account.name},\n\n"
                    f"Click the link below to set a new password:\n\n"
                    f"{link}\n\n"
                    f"This link expires in 1 hour. If you didn't request this, ignore this email."
                ),
                from_email=None,
                recipient_list=[account.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Could not send password reset email to %s", account.email)

    # Same response whether or not the account exists, so this endpoint never reveals
    # which emails are registered.
    return JsonResponse({"message": "If that email is registered, a reset link has been sent."})


@csrf_exempt
@require_POST
def confirm_password_reset(request):
    data = read_json(request)
    if data is None:
        return error("Invalid request.")
    token = str(data.get("token", "")).strip()
    new_password = str(data.get("password", ""))

    if not token:
        return error("A reset code is required.", 400)
    if len(new_password) < 8:
        return error("Use at least 8 characters.", 400, {"password": "Use at least 8 characters."})
    if len(new_password) > 128:
        return error("Password is too long.", 400, {"password": "Password is too long."})

    try:
        payload = signing.loads(token, salt=PASSWORD_RESET_SALT, max_age=PASSWORD_RESET_MAX_AGE)
    except signing.BadSignature:
        return error("This reset link is invalid or has expired.", 400)

    account = ClientAccount.objects.filter(pk=payload.get("id")).first()
    if account is None:
        return error("This reset link is invalid or has expired.", 400)

    account.set_password(new_password)
    account.save(update_fields=["password"])

    return JsonResponse({"message": "Your password has been reset. You can now sign in."})