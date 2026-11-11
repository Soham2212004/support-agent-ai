"""Shared validation and metering helpers for the public chatbot API."""
import hashlib
import hmac
import ipaddress
import re
from urllib.parse import urlsplit

from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone

from .models import (
    AllowedWebsite,
    ClientApiKey,
    PublicMonthlyUsage,
    PublicRateLimitBucket,
)

MONTHLY_MESSAGE_LIMIT = 1000
VISITOR_MESSAGE_RATE = 10
TOKEN_REQUEST_RATE = 10


def normalize_origin(value):
    """Return a canonical scheme/host/port origin; paths and credentials are not allowed."""
    try:
        parsed = urlsplit(str(value).strip())
        if (
            parsed.scheme.lower() not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            return None
        hostname = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parsed.port
    except (UnicodeError, ValueError):
        return None

    if not hostname or len(hostname) > 253 or port == 0:
        return None
    try:
        hostname = ipaddress.ip_address(hostname).compressed
    except ValueError:
        labels = hostname.split(".")
        if any(
            not label or len(label) > 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
            for label in labels
        ):
            return None
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    default_port = (parsed.scheme.lower() == "https" and port == 443) or (
        parsed.scheme.lower() == "http" and port == 80
    )
    suffix = f":{port}" if port and not default_port else ""
    return f"{parsed.scheme.lower()}://{hostname}{suffix}"


def api_key_from_request(request):
    raw_key = request.headers.get("X-API-Key", "").strip()
    if not raw_key or len(raw_key) > 200:
        return None
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key = ClientApiKey.objects.select_related("account").filter(key_hash=digest).first()
    if key is None or not hmac.compare_digest(key.key_hash, digest) or not key.usable:
        return None
    if key.account.status != key.account.Status.APPROVED:
        return None
    return key


def origin_is_allowed(account, origin):
    return AllowedWebsite.objects.filter(account=account, origin=origin).exists()


def reserve_rate_limit(scope, key, limit):
    """Atomically count one request in the current UTC minute."""
    now = timezone.now()
    minute = now.replace(second=0, microsecond=0)
    try:
        PublicRateLimitBucket.objects.get_or_create(scope=scope, key=str(key), minute=minute)
    except IntegrityError:
        pass
    return (
        PublicRateLimitBucket.objects.filter(
            scope=scope, key=str(key), minute=minute, count__lt=limit
        ).update(count=F("count") + 1)
        == 1
    )


def current_month():
    return timezone.localdate().replace(day=1)


def reserve_monthly_message(account):
    month = current_month()
    try:
        PublicMonthlyUsage.objects.get_or_create(account=account, month=month)
    except IntegrityError:
        pass
    return (
        PublicMonthlyUsage.objects.filter(
            account=account, month=month, count__lt=MONTHLY_MESSAGE_LIMIT
        ).update(count=F("count") + 1)
        == 1
    )


def release_monthly_message(account):
    PublicMonthlyUsage.objects.filter(account=account, month=current_month(), count__gt=0).update(
        count=F("count") - 1
    )


def monthly_usage(account):
    row = PublicMonthlyUsage.objects.filter(account=account, month=current_month()).first()
    return {"used": row.count if row else 0, "limit": MONTHLY_MESSAGE_LIMIT}
