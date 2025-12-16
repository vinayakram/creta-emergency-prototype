from __future__ import annotations

import re
from typing import Dict, List

from app.rag.retriever import RetrievedChunk


# ---------------------------------------------------------
# Tool keywords (kept conservative, no hallucination)
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
    "Jump Starting",
    "Hazard Warning Flasher",
    "Flat Tyre",
    "Engine Does Not Start"
]


# ---------------------------------------------------------
# Query-aware filtering (CRITICAL FIX)
# ---------------------------------------------------------
def _filter_relevant_blocks(text: str, query: str) -> str:
    """
    From a structured manual chunk, keep only blocks
    relevant to the query intent.

    Works well for TXT manuals with headings + steps.
    """
    q_terms = [t for t in query.lower().split() if len(t) > 2]

    # Split on blank lines or headings
    blocks = re.split(r"\n\s*\n", text)
    relevant: List[str] = []

    for block in blocks:
        b = block.lower()
        if any(term in b for term in q_terms):
            relevant.append(block.strip())

    # Fallback: return original text if filtering removed everything
    return "\n\n".join(relevant) if relevant else text


# ---------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------
def _extract_numbered_steps(text: str) -> List[str]:
    """
    Extract numbered procedural steps.
    """
    steps: List[str] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for ln in lines:
        if re.match(r"^\d+\.\s+", ln):
            # Remove leading "1. "
            steps.append(re.sub(r"^\d+\.\s+", "", ln))

    return steps


def _extract_warning_lines(text: str) -> List[str]:
    warnings: List[str] = []

    for ln in text.splitlines():
        u = ln.strip().upper()
        if u.startswith("WARNING") or u.startswith("CAUTION") or u.startswith("NOTICE"):
            warnings.append(ln.strip())

    # Deduplicate
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
        if kw.lower() in haystack:
            found.append(kw)

    # Deduplicate while preserving order
    seen = set()
    out = []
    for t in found:
        if t not in seen:
            seen.add(t)
            out.append(t)

    return out


# ---------------------------------------------------------
# Public answer builder
# ---------------------------------------------------------
def build_answer(query: str, chunks: List[RetrievedChunk]) -> Dict:
    """
    Build a precise, non-hallucinated answer from retrieved chunks.
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
    # 1. Filter chunk text by query intent (KEY FIX)
    # -----------------------------------------------------
    filtered_texts: List[str] = []
    for c in chunks:
        filtered = _filter_relevant_blocks(c.text, query)
        if filtered:
            filtered_texts.append(filtered)

    # Use the best-matching filtered text for steps
    primary_text = filtered_texts[0]

    # -----------------------------------------------------
    # 2. Extract structured outputs
    # -----------------------------------------------------
    steps = _extract_numbered_steps(primary_text)
    warnings = _extract_warning_lines(primary_text)
    tools = _extract_tools(filtered_texts)

    # -----------------------------------------------------
    # 3. Sources (do not filter aggressively – transparency)
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
