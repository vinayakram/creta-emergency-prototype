from __future__ import annotations

import re
from typing import Dict, List

from app.rag.retriever import RetrievedChunk


# ---------------------------------------------------------
# Conservative tool keywords (manual-faithful)
# ---------------------------------------------------------
TOOL_KEYWORDS = [
    "jack",
    "wheel spanner",
    "spanner",
    "tow hook",
    "towing",
    "jumper cable",
    "jumper cables",
    "battery cable",
    "warning triangle",
]


# ---------------------------------------------------------
# Intent classification (NO hardcoded scenarios)
# ---------------------------------------------------------
def classify_intent(query: str) -> str:
    """
    Classify user intent to prevent harmful instructions.
    """
    q = query.lower()

    harmful_verbs = {
        "make", "cause", "damage", "break",
        "puncture", "sabotage", "destroy"
    }
    vehicle_targets = {
        "tyre", "tire", "engine", "battery",
        "vehicle", "car"
    }

    if any(v in q for v in harmful_verbs) and any(t in q for t in vehicle_targets):
        return "malicious"

    return "assistance"


# ---------------------------------------------------------
# Safety redirect (contextual help)
# ---------------------------------------------------------
def safety_redirect_response(query: str) -> Dict:
    return {
        "query": query,
        "steps": [
            "I can’t help with damaging a vehicle.",
            "If you are dealing with a flat tyre unexpectedly, follow these safe steps:",
            "Reduce speed gradually and avoid sudden braking.",
            "Move the vehicle to a safe place away from traffic.",
            "Switch on the hazard warning flasher.",
            "Inspect the tyre only after the vehicle is safely stopped."
        ],
        "warnings": [
            "Intentionally damaging a vehicle can be dangerous and illegal."
        ],
        "tools": [],
        "sources": [],
        "disclaimer": (
            "This assistant provides safety guidance based on vehicle manuals. "
            "It does not support harmful or illegal actions."
        ),
    }


# ---------------------------------------------------------
# Select BEST chunk for the query
# ---------------------------------------------------------
def _best_chunk_for_query(query: str, chunks: List[RetrievedChunk]) -> RetrievedChunk:
    q = query.lower()

    def score_chunk(c: RetrievedChunk) -> float:
        score = c.score
        text = c.text.lower()

        if q in text:
            score += 1.5

        for term in q.split():
            if term in text:
                score += 0.2

        return score

    return max(chunks, key=score_chunk)


# ---------------------------------------------------------
# Query-aware text filtering
# ---------------------------------------------------------
def _filter_relevant_blocks(text: str, query: str) -> str:
    q_terms = [t for t in query.lower().split() if len(t) > 2]

    blocks = re.split(r"\n\s*\n", text)
    relevant: List[str] = []

    for block in blocks:
        if any(term in block.lower() for term in q_terms):
            relevant.append(block.strip())

    return "\n\n".join(relevant) if relevant else text


# ---------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------
def _extract_numbered_steps(text: str) -> List[str]:
    steps: List[str] = []

    for ln in text.splitlines():
        ln = ln.strip()
        if re.match(r"^\d+\.\s+", ln):
            steps.append(re.sub(r"^\d+\.\s+", "", ln))

    return steps


def _extract_warning_lines(text: str) -> List[str]:
    warnings: List[str] = []

    for ln in text.splitlines():
        u = ln.strip().upper()
        if u.startswith(("WARNING", "CAUTION", "NOTICE")):
            warnings.append(ln.strip())

    seen = set()
    out = []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            out.append(w)

    return out


def _extract_tools(texts: List[str]) -> List[str]:
    haystack = " ".join(texts).lower()
    found: List[str] = []

    for kw in TOOL_KEYWORDS:
        if kw in haystack:
            found.append(kw)

    seen = set()
    return [t for t in found if not (t in seen or seen.add(t))]


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------
def build_answer(query: str, chunks: List[RetrievedChunk]) -> Dict:
    """
    Build a precise, safe, scenario-correct answer.
    """
    # -----------------------------------------------------
    # 0. Intent safety gate
    # -----------------------------------------------------
    if classify_intent(query) == "malicious":
        return safety_redirect_response(query)

    if not chunks:
        return {
            "query": query,
            "steps": [],
            "warnings": [],
            "tools": [],
            "sources": [],
            "disclaimer": (
                "Prototype: information is retrieved from the owner’s manual excerpts. "
                "Always prioritize safety and your local regulations."
            ),
        }

    # -----------------------------------------------------
    # 1. Pick the BEST chunk
    # -----------------------------------------------------
    best_chunk = _best_chunk_for_query(query, chunks)

    # -----------------------------------------------------
    # 2. Filter content by query intent
    # -----------------------------------------------------
    focused_text = _filter_relevant_blocks(best_chunk.text, query)

    # -----------------------------------------------------
    # 3. Extract structured outputs
    # -----------------------------------------------------
    steps = _extract_numbered_steps(focused_text)
    warnings = _extract_warning_lines(focused_text)
    tools = _extract_tools([c.text for c in chunks])

    # -----------------------------------------------------
    # 4. Sources (transparent)
    # -----------------------------------------------------
    sources = [
        {
            "id": c.id,
            "page": int(c.metadata.get("page") or -1),
            "chunk_id": c.metadata.get("chunk_id"),
            "text": c.text,
            "score": c.score,
        }
        for c in chunks
    ]

    return {
        "query": query,
        "steps": steps,
        "warnings": warnings[:10],
        "tools": tools,
        "sources": sources,
        "disclaimer": (
            "Prototype: information is retrieved from the owner’s manual excerpts. "
            "Always prioritize safety and your local regulations. "
            "If you are in danger, contact emergency services or roadside assistance."
        ),
    }
