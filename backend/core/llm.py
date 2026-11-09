"""One OpenAI-compatible client for every AI provider.

Gemini, Grok, OpenAI and Ollama all speak the same API, so switching between them is
only configuration (see the AI section of the .env file).
"""
import itertools
import os
import re
import time

PROVIDERS = {
    "gemini": {
        "label": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-2.5-flash",
        "temperature": True,
    },
    "grok": {
        "label": "Grok",
        "base_url": "https://api.x.ai/v1",
        "key_env": "GROK_API_KEY",
        "model_env": "GROK_MODEL",
        "default_model": "grok-4.3",
        "temperature": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
        "temperature": False,  # some newer OpenAI models only accept the default temperature
    },
    "ollama": {
        "label": "Ollama (on your PC)",
        "base_url_env": "OLLAMA_BASE_URL",
        "default_base_url": "http://host.docker.internal:11434/v1",
        "model_env": "OLLAMA_MODEL",
        "default_model": "llama3.2",
        "no_key": True,
        "temperature": True,
        "timeout": 120,  # the first request can be slow while the model loads
    },
}
ORDER = ["gemini", "grok", "openai", "ollama"]
FAKE = {"id": "fake", "label": "Demo (no AI model)", "model": "demo", "base_url": "", "api_key": ""}


class LLMError(Exception):
    """An error whose message is safe to show to the user."""


def _env(name, default=""):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().strip('"').strip("'")


def _resolve(provider_id):
    """Return the provider's settings if it is configured, otherwise None."""
    spec = PROVIDERS.get(provider_id)
    if spec is None:
        return None

    if spec.get("no_key"):  # Ollama: shown unless OLLAMA_MODEL is set to an empty value
        model = _env(spec["model_env"], spec["default_model"])
        if not model:
            return None
        base_url = _env(spec["base_url_env"], spec["default_base_url"])
        return {"id": provider_id, "label": spec["label"], "model": model, "base_url": base_url, "api_key": ""}

    key = _env(spec["key_env"])
    if not key:
        return None
    model = _env(spec["model_env"]) or spec["default_model"]
    return {"id": provider_id, "label": spec["label"], "model": model, "base_url": spec["base_url"], "api_key": key}


def available_providers():
    """Configured providers in a fixed order, plus the always-available demo mode."""
    found = [p for p in (_resolve(pid) for pid in ORDER) if p]
    found.append(dict(FAKE))
    return found


def default_provider_id():
    wanted = _env("LLM_PROVIDER").lower()
    ids = [p["id"] for p in available_providers()]
    if wanted in ids:
        return wanted
    # not chosen (or not configured): prefer a provider with an API key, then the demo mode.
    # Ollama is only used by default when LLM_PROVIDER=ollama, because it may not be running.
    return [i for i in ids if i != "ollama"][0]


def get_provider(provider_id=None):
    provider_id = (provider_id or default_provider_id()).lower()
    for provider in available_providers():
        if provider["id"] == provider_id:
            return provider
    raise LLMError(
        f"The '{provider_id}' model isn't set up. Add its key to the .env file, "
        "then run: docker compose up -d"
    )


def stream_chat(provider, messages):
    """Yield {"text": "..."} pieces and, when the provider reports it, {"usage": (in, out)}."""
    if provider["id"] == "fake":
        yield from _fake_stream(messages)
        return

    try:
        import openai
    except ImportError as exc:
        raise LLMError("The openai package is missing. Rebuild with: docker compose up -d --build") from exc

    spec = PROVIDERS[provider["id"]]
    client = openai.OpenAI(
        base_url=provider["base_url"],
        api_key=provider["api_key"] or "ollama",
        timeout=spec.get("timeout", 45),
        max_retries=1,
    )
    params = {"model": provider["model"], "messages": messages, "stream": True}
    if spec.get("temperature"):
        params["temperature"] = 0.2

    try:
        stream = client.chat.completions.create(**params)
        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage:
                yield {"usage": (usage.prompt_tokens or 0, usage.completion_tokens or 0)}
            if chunk.choices:
                text = getattr(chunk.choices[0].delta, "content", None)
                if text:
                    yield {"text": text}
    except LLMError:
        raise
    except Exception as exc:  # turned into a readable message
        raise LLMError(_friendly_error(exc, provider, client)) from exc


def _friendly_error(exc, provider, client):
    import openai

    label = provider["label"]

    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return f"{label} rejected the API key. Check the key in your .env file, then run: docker compose up -d"

    if isinstance(exc, openai.NotFoundError):
        names = []
        try:
            names = [m.id.replace("models/", "") for m in itertools.islice(client.models.list(), 12)]
        except Exception:
            pass
        message = f"{label} doesn't have a model called '{provider['model']}'."
        if names:
            message += f" Models you can use: {', '.join(names)}."
        if provider["id"] == "ollama":
            message += f" To download it, run: ollama pull {provider['model']}."
        else:
            message += " Set the model name in your .env file."
        return message

    if isinstance(exc, openai.RateLimitError):
        return f"{label} says you've reached its rate or quota limit. Wait a minute, or pick another model."

    if isinstance(exc, openai.APIConnectionError):  # includes timeouts
        if provider["id"] == "ollama":
            return (
                "Can't reach Ollama. Make sure Ollama is running, and that it listens on all addresses: "
                "set the OLLAMA_HOST environment variable to 0.0.0.0 on your PC and restart Ollama."
            )
        return f"Couldn't reach {label}. Check your internet connection and try again."

    if isinstance(exc, openai.BadRequestError):
        return f"{label} rejected the request. Try another model."

    return f"{label} returned an error. Please try again, or pick another model."


def _fake_stream(messages):
    """Demo mode: no AI model. Quotes the best passage, so the chat can be tested without any key."""
    system = messages[0]["content"]
    match = re.search(r"\[1\] \([^)\n]*\)\n(.*?)(?:\n\n\[2\] |\Z)", system, re.S)
    passage = match.group(1).strip() if match else ""
    if len(passage) > 280:
        passage = passage[:280].rsplit(" ", 1)[0] + "..."
    answer = (
        "Demo mode (no AI model is connected). The most relevant passage in your document says: "
        f"{passage} [1]"
    )
    words = answer.split(" ")
    for index, word in enumerate(words):
        yield {"text": word if index == 0 else " " + word}
        time.sleep(0.02)
