"""Enhanced RAG pipeline: LangGraph-orchestrated intent classification, wide retrieval,
cross-encoder reranking, evidence grading with query rewriting, then generation reusing
the same prompt layers as the baseline pipeline for a fair comparison.

Simplifications vs. a full production build, noted for honesty:
- No LangGraph Postgres checkpointer — the graph runs once per message, synchronously,
  the same way the baseline pipeline does. Conversation history is still passed in and
  used, same as baseline; there's just no resumable mid-graph state across requests.
- classify_intent and rewrite_query use the configured LLM when a real provider is
  active; with the "fake" (no-AI) provider they fall back to simple local heuristics,
  since the demo provider can't meaningfully follow a classification instruction.
"""
import logging
import re
from typing import Optional, TypedDict

from django.conf import settings
from typing_extensions import NotRequired

from . import llm
from .injection_guard import is_suspicious
from .rag import (
    NO_ANSWER,
    SNIPPET_CHARS,
    TONE_INSTRUCTIONS,
    build_messages,
    build_smalltalk_messages,
    extract_citations,
    is_smalltalk,
    retrieve,
)
from .reranker import rerank

logger = logging.getLogger(__name__)

RETRIEVE_WIDE_K = int(getattr(settings, "RAG_RETRIEVE_WIDE_K", 20))
RERANK_KEEP = int(getattr(settings, "RAG_RERANK_KEEP", 5))
RERANK_MIN_SIMILARITY = float(getattr(settings, "RAG_RERANK_MIN_SIMILARITY", 0.5))
MAX_QUERY_REWRITES = int(getattr(settings, "RAG_MAX_QUERY_REWRITES", 2))

_HUMAN_REQUEST_RE = re.compile(
    r"\b(talk to|speak (to|with)|connect me|human|agent|representative|real person|someone)\b", re.IGNORECASE
)


class GraphState(TypedDict):
    question: str
    rewritten_question: NotRequired[str]
    intent: NotRequired[str]
    injection_flagged: NotRequired[bool]
    passages: NotRequired[list]
    evidence_sufficient: NotRequired[bool]
    rewrite_count: int


def _llm_complete(provider, messages):
    """Collects a full (non-streamed) response from the LLM for a classification/rewrite call."""
    if provider["id"] == "fake":
        return ""
    full = ""
    try:
        for event in llm.stream_chat(provider, messages):
            if "text" in event:
                full += event["text"]
    except llm.LLMError:
        return ""
    return full.strip()


def _classify_intent_node(state, provider):
    text = state["question"]
    if is_suspicious(text):
        return {**state, "injection_flagged": True, "intent": "out_of_scope"}

    if provider["id"] == "fake":
        if is_smalltalk(text):
            intent = "small_talk"
        elif _HUMAN_REQUEST_RE.search(text):
            intent = "human_request"
        else:
            intent = "question"
        return {**state, "injection_flagged": False, "intent": intent}

    messages = [
        {
            "role": "system",
            "content": (
                "Classify the user's message into exactly one label: QUESTION, SMALL_TALK, "
                "HUMAN_REQUEST, or OUT_OF_SCOPE. Reply with only the label word."
            ),
        },
        {"role": "user", "content": text[:1000]},
    ]
    label = _llm_complete(provider, messages).strip().upper()
    mapping = {"QUESTION": "question", "SMALL_TALK": "small_talk", "HUMAN_REQUEST": "human_request", "OUT_OF_SCOPE": "out_of_scope"}
    intent = mapping.get(label.split()[0] if label else "", "question")
    return {**state, "injection_flagged": False, "intent": intent}

def _retrieve_and_rerank(account, document, published_version, question):
    candidates = retrieve(account, document, question, published_version=published_version, top_k=RETRIEVE_WIDE_K)
    # retrieve() already returns numbered/labelled passages; rerank needs the raw text field, which it has.
    reranked = rerank(question, candidates, keep=RERANK_KEEP)
    for number, passage in enumerate(reranked, start=1):
        passage["n"] = number
        passage["score"] = round(passage["rerank_score"], 3)
    return reranked


def run_graph(account, document, published_version, question, provider):
    """Runs the pre-generation graph synchronously and returns the final state."""
    from langgraph.graph import END, StateGraph

    def classify_node(state):
        return _classify_intent_node(state, provider)

    def retrieve_node(state):
        q = state.get("rewritten_question", state["question"])
        passages = _retrieve_and_rerank(account, document, published_version, q)
        return {**state, "passages": passages}

    def grade_node(state):
        passages = state.get("passages") or []
        top = passages[0]["rerank_score"] if passages else 0.0
        return {**state, "evidence_sufficient": top >= RERANK_MIN_SIMILARITY}

    def rewrite_node(state):
        # the rewrite count MUST increment even on the "fake" provider path, or should_rewrite
        # never sees it reach MAX_QUERY_REWRITES and the graph loops until the recursion limit.
        next_count = state["rewrite_count"] + 1
        if provider["id"] == "fake":
            return {**state, "rewrite_count": next_count}
        messages = [
            {
                "role": "system",
                "content": "Rewrite the user's question to be clearer and more specific for a document search. Reply with only the rewritten question.",
            },
            {"role": "user", "content": state["question"][:1000]},
        ]
        rewritten = _llm_complete(provider, messages)
        update = {**state, "rewrite_count": next_count}
        if rewritten:
            update["rewritten_question"] = rewritten
        return update

    def should_rewrite(state):
        if state["intent"] in ("small_talk", "human_request", "out_of_scope"):
            return "done"
        if state["evidence_sufficient"]:
            return "done"
        if state["rewrite_count"] >= MAX_QUERY_REWRITES:
            return "done"
        return "rewrite"

    graph = StateGraph(dict)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("rewrite", rewrite_node)

    def after_classify(state):
        if state.get("injection_flagged") or state["intent"] in ("small_talk", "human_request"):
            return "done"
        return "retrieve"

    graph.set_entry_point("classify")
    graph.add_conditional_edges("classify", after_classify, {"done": END, "retrieve": "retrieve"})
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", should_rewrite, {"done": END, "rewrite": "rewrite"})
    graph.add_edge("rewrite", "retrieve")

    app = graph.compile()
    return app.invoke({"question": question, "rewrite_count": 0})


def stream_answer_enhanced(account, document, history, question, provider, bot_settings, published_version=None):
    """Same event shapes as the baseline stream_answer: {"type": "token"/"final", ...}."""
    from langgraph.graph import END, StateGraph  # noqa: F401 (imported above too; kept for clarity if moved)

    # Run the graph. Pass provider through state since the graph's compiled nodes are closures here.
    state = run_graph(account, document, published_version, question, provider)

    def _final_fallback(reason, tokens_in=0, tokens_out=0):
        return {
            "type": "final",
            "text": bot_settings.active_fallback,
            "citations": [],
            "is_fallback": True,
            "fallback_reason": reason,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    if state.get("injection_flagged"):
        yield _final_fallback("input_blocked")
        return

    intent = state.get("intent", "question")

    if intent == "human_request":
        yield _final_fallback("human_requested")
        return

    if intent == "small_talk":
        messages = build_smalltalk_messages(bot_settings, history, question)
        full = ""
        tokens_in = tokens_out = 0
        for event in llm.stream_chat(provider, messages):
            if "usage" in event:
                tokens_in, tokens_out = event["usage"]
                continue
            full += event["text"]
            yield {"type": "token", "text": event["text"]}
        tokens_in = tokens_in or sum(len(m["content"]) for m in messages) // 4
        tokens_out = tokens_out or len(full) // 4
        yield {
            "type": "final", "text": full.strip(), "citations": [], "is_fallback": False,
            "fallback_reason": "", "tokens_in": tokens_in, "tokens_out": tokens_out,
        }
        return

    passages = state.get("passages", [])
    if not passages or not state.get("evidence_sufficient"):
        yield _final_fallback("weak_evidence")
        return

    messages = build_messages(passages, history, question, bot_settings)
    full = ""
    decided = False
    no_answer = False
    tokens_in = tokens_out = 0

    stream = llm.stream_chat(provider, messages)
    for event in stream:
        if "usage" in event:
            tokens_in, tokens_out = event["usage"]
            continue
        full += event["text"]
        if decided:
            yield {"type": "token", "text": event["text"]}
            continue
        head = full.lstrip()
        if len(head) < len(NO_ANSWER) and NO_ANSWER.startswith(head.upper()):
            continue
        decided = True
        if head.upper().startswith(NO_ANSWER):
            no_answer = True
            if hasattr(stream, "close"):
                stream.close()
            break
        yield {"type": "token", "text": full}

    if not decided:
        head = full.strip()
        if not head:
            raise llm.LLMError("The AI model returned an empty reply. Try again, or pick another model.")
        if head.upper().startswith(NO_ANSWER):
            no_answer = True
        else:
            yield {"type": "token", "text": full}

    tokens_in = tokens_in or sum(len(m["content"]) for m in messages) // 4
    tokens_out = tokens_out or len(full) // 4

    if no_answer:
        yield _final_fallback("no_answer", tokens_in, tokens_out)
        return

    yield {
        "type": "final",
        "text": full.strip(),
        "citations": extract_citations(full, passages) if bot_settings.show_citations else [],
        "is_fallback": False,
        "fallback_reason": "",
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }