"""Tracks estimated daily LLM spend and exposes a kill-switch that pauses test/demo chat."""
from datetime import date
from decimal import Decimal

from django.conf import settings

from .models import LlmSpend

# $ per 1M tokens — rough, provider-agnostic estimate; override per-provider later if needed
PRICE_PER_MILLION_IN = Decimal(str(getattr(settings, "LLM_PRICE_IN", "0.15")))
PRICE_PER_MILLION_OUT = Decimal(str(getattr(settings, "LLM_PRICE_OUT", "0.60")))
DEFAULT_DAILY_BUDGET = Decimal(str(getattr(settings, "LLM_DAILY_BUDGET", "5.00")))


def _today_row():
    row, _ = LlmSpend.objects.get_or_create(
        date=date.today(), defaults={"budget_limit": DEFAULT_DAILY_BUDGET}
    )
    return row


def record_usage(tokens_in, tokens_out):
    """Call after every LLM response. Updates today's spend and the paused flag."""
    row = _today_row()
    cost = (Decimal(tokens_in) / 1_000_000 * PRICE_PER_MILLION_IN) + (
        Decimal(tokens_out) / 1_000_000 * PRICE_PER_MILLION_OUT
    )
    LlmSpend.objects.filter(pk=row.pk).update(
        input_tokens=models_f("input_tokens", tokens_in),
        output_tokens=models_f("output_tokens", tokens_out),
        estimated_cost=models_f("estimated_cost", cost),
    )
    row.refresh_from_db()
    if row.estimated_cost >= row.budget_limit and not row.paused:
        LlmSpend.objects.filter(pk=row.pk).update(paused=True)


def models_f(field, delta):
    from django.db.models import F

    return F(field) + delta


def is_budget_paused():
    row = LlmSpend.objects.filter(date=date.today()).first()
    return bool(row and row.paused)