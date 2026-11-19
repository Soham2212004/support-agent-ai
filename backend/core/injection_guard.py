"""Flags visitor input that looks like it's trying to override the system prompt.

Uses a real Hugging Face classifier if INJECTION_MODEL is set (downloaded on first use);
otherwise falls back to a local, free, zero-download heuristic. Both run entirely offline.
"""
import logging
import re
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

_classifier = None
_load_lock = threading.Lock()

INJECTION_MODEL = getattr(settings, "INJECTION_MODEL", "")

_HEURISTIC_PATTERNS = [
    r"ignore (all |the )?(previous|prior|above) instructions",
    r"disregard (all |the )?(previous|prior|above)",
    r"you are now",
    r"new instructions?:",
    r"system prompt",
    r"reveal (your|the) (instructions|prompt|rules)",
    r"act as (if|a)",
    r"pretend (you are|to be)",
    r"\bDAN\b",
    r"jailbreak",
]
_HEURISTIC_RE = re.compile("|".join(_HEURISTIC_PATTERNS), re.IGNORECASE)


def _get_classifier():
    global _classifier
    if _classifier is None:
        with _load_lock:
            if _classifier is None:
                from transformers import pipeline

                _classifier = pipeline("text-classification", model=INJECTION_MODEL, device=-1)
    return _classifier


def is_suspicious(text):
    """Returns True if the text looks like a prompt-injection attempt."""
    if not text:
        return False

    if INJECTION_MODEL:
        try:
            result = _get_classifier()(text[:512])[0]
            label = str(result.get("label", "")).upper()
            return "INJECT" in label and result.get("score", 0) > 0.5
        except Exception:
            logger.exception("Injection classifier failed; falling back to heuristic for this message.")

    return bool(_HEURISTIC_RE.search(text))