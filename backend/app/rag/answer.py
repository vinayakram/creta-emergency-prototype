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
# Select BEST chunk for the query (CRITICAL FIX)
# ---------------------------------------------------------
def _best_chunk_for_query(query: str, chunks: List[RetrievedChunk]) -> RetrievedChunk:
    """
    Select the most relevant chunk for answering.
    Priority:
    1. Highest similarity score
    2. Explicit query phrase match in text
    """
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
    """
    Keep only the subsection relevant to the query.
    Works for structured manuals with headings + steps.
    """
    q_terms = [t for t in query.lower().split() if len(t) > 2]

    # Split by blank lines (structure preserved during ingestion)
    blocks = re.split(r"\n\s*\n", text)
    relevant: List[str] = []

    for block in blocks:
        b = block.lower()
        if any(term in b for term in q_terms):
            relevant.append(block.strip())

    return "\n\n".join(relevant) if relevant else text


# ---------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------
def _extract_numbered_steps(text: str) -> List[str]:
    """
    Extract numbered procedural steps cleanly.
    """
    steps: List[str] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for ln in lines:
        if re.match(r"^\d+\.\s+", ln):
            steps.append(re.sub(r"^\d+\.\s+", "", ln))

    return steps


def _extract_warning_lines(text: str) -> List[str]:
    warnings: List[str] = []

    for ln in text.splitlines():
        u = ln.strip().upper()
        if u.startswith("WARNING") or u.startswith("CAUTION") or u.startswith("NOTICE"):
            warnings.append(ln.strip())

    # Deduplicate while preserving order
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
    out = []
    for t in found:
        if t not in seen:
            seen.add(t)
            out.append(t)

    return out


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------
def build_answer(query: str, chunks: List[RetrievedChunk]) -> Dict:
    """
    Build a precise, scenario-correct answer from retrieved chunks.
    """
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
    # 1. Pick the BEST chunk for this query
    # -----------------------------------------------------
    best_chunk = _best_chunk_for_query(query, chunks)

    # -----------------------------------------------------
    # 2. Filter its content by query intent
    # -----------------------------------------------------
    focused_text = _filter_relevant_blocks(best_chunk.text, query)

    # -----------------------------------------------------
    # 3. Extract structured outputs
    # -----------------------------------------------------
    steps = _extract_numbered_steps(focused_text)
    warnings = _extract_warning_lines(focused_text)
    tools = _extract_tools([c.text for c in chunks])

    # -----------------------------------------------------
    # 4. Sources (transparent, unfiltered)
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
