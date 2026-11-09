"""Turns text into embeddings (lists of numbers that capture meaning) with a local model.

The model is loaded once per server process, the first time it is needed.
"""
import threading

from django.conf import settings

_model = None
_load_lock = threading.Lock()
_encode_lock = threading.Lock()  # one batch at a time, so a search never waits behind a whole document


def get_model():
    global _model
    if _model is None:
        with _load_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")
    return _model


def _prefix(kind):
    # E5 models were trained with "query: " and "passage: " in front of the text
    if "e5" in settings.EMBEDDING_MODEL.lower():
        return f"{kind}: "
    return ""


def _encode(texts, kind, batch_size):
    model = get_model()
    prefix = _prefix(kind)
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


def embed_query(text):
    return _encode([text], "query", 1)[0]