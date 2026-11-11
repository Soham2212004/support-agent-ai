"""Turns text into embeddings (lists of numbers that capture meaning) with a local model.

The model is loaded once per server process, the first time it is needed.
"""
import threading

from django.conf import settings

_models = {}
_load_lock = threading.Lock()
_encode_lock = threading.Lock()  # one batch at a time, so a search never waits behind a whole document


def get_model(model_name=None):
    model_name = model_name or settings.EMBEDDING_MODEL
    if model_name not in _models:
        with _load_lock:
            if model_name not in _models:
                from sentence_transformers import SentenceTransformer

                _models[model_name] = SentenceTransformer(model_name, device="cpu")
    return _models[model_name]


def _prefix(kind, model_name=None):
    # E5 models were trained with "query: " and "passage: " in front of the text
    if "e5" in (model_name or settings.EMBEDDING_MODEL).lower():
        return f"{kind}: "
    return ""


def _encode(texts, kind, batch_size, model_name=None):
    model = get_model(model_name)
    prefix = _prefix(kind, model_name)
    vectors = []
    for start in range(0, len(texts), batch_size):
        batch = [prefix + text for text in texts[start : start + batch_size]]
        with _encode_lock:
            result = model.encode(
                batch, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False
            )
        vectors.extend(vector.tolist() for vector in result)
    return vectors


def embed_passages(texts, batch_size=16):
    return _encode(texts, "passage", batch_size)


def embed_query(text, model_name=None):
    return _encode([text], "query", 1, model_name)[0]