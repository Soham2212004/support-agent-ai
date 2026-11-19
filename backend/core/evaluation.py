"""Metrics for scoring a pipeline against a question dataset. See management/commands/run_evaluation.py."""
import statistics


def retrieval_hit(expected_source, passages):
    if not expected_source:
        return None  # no expected source recorded for this question
    expected = expected_source.lower()
    return any(expected in (p.get("label", "") + " " + p.get("text", "")).lower() for p in passages)


def correct_decline(answerable, is_fallback):
    if answerable:
        return None  # only meaningful for unanswerable questions
    return is_fallback  # correct decline = it WAS unanswerable and the bot DID fall back


def summarize(rows):
    def pct(key):
        values = [r[key] for r in rows if r.get(key) is not None]
        return round(sum(1 for v in values if v) / len(values) * 100, 1) if values else None

    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    tokens_in = sum(r.get("tokens_in", 0) for r in rows)
    tokens_out = sum(r.get("tokens_out", 0) for r in rows)

    return {
        "question_count": len(rows),
        "retrieval_hit_rate": pct("retrieval_hit"),
        "correct_decline_rate": pct("correct_decline"),
        "median_latency_ms": round(statistics.median(latencies)) if latencies else None,
        "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18]) if len(latencies) >= 20 else (
            round(max(latencies)) if latencies else None
        ),
        "total_tokens_in": tokens_in,
        "total_tokens_out": tokens_out,
        "avg_tokens_per_answer": round((tokens_in + tokens_out) / len(rows)) if rows else 0,
    }