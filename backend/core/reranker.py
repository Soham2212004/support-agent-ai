"""Local cross-encoder reranker. Scores (question, passage) pairs more precisely than
embedding similarity alone, so the enhanced pipeline can keep only the best candidates.
"""
import math
import threading

from django.conf import settings

_model = None
_load_lock = threading.Lock()

RERANK_MODEL = getattr(settings, "RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")


def get_reranker():
    global _model
    if _model is None:
        with _load_lock:
            if _model is None:
                from sentence_transformers import CrossEncoder

                _model = CrossEncoder(RERANK_MODEL, device="cpu")
    return _model


def rerank(question, candidates, keep=5):
    """candidates: list of dicts with a 'text' key. Returns the best `keep`, each with a 'rerank_score' in 0..1."""
    if not candidates:
        return []
    model = get_reranker()
    pairs = [(question, c["text"]) for c in candidates]
    raw_scores = model.predict(pairs)
    for candidate, raw in zip(candidates, raw_scores):
        # Cross-encoder logits aren't bounded 0..1; squash with a sigmoid for a comparable threshold.
        candidate["rerank_score"] = 1 / (1 + math.exp(-float(raw)))
    candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
    return candidates[:keep]