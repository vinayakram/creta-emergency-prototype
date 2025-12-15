from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.rag.retriever import RetrievedChunk

# MVP tool keyword list (extend later by reading the manual).
TOOL_KEYWORDS = [
    "jack",
    "wheel spanner",
    "spanner",
    "tow hook",
    "towing",
    "jumper cable",
    "jumper cables",
    "battery cable",
    "lug nut",
    "wheel nut",
    "spare tire",
    "spare tyre",
    "warning triangle",
    "reflective",
]


def _extract_warning_lines(text: str) -> List[str]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    out = []
    for ln in lines:
        u = ln.upper()
        if u.startswith("WARNING") or u.startswith("CAUTION") or u.startswith("NOTICE"):
            out.append(ln)
    # De-duplicate, keep order
    seen = set()
    dedup = []
    for w in out:
        if w not in seen:
            seen.add(w)
            dedup.append(w)
    return dedup


def _extract_numbered_steps(text: str) -> List[str]:
    # Look for numbered steps at start of lines: "1.", "2)", "3 -", etc.
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    steps = []
    for ln in lines:
        if re.match(r"^\d+\s*[\).:-]\s+\S+", ln):
            steps.append(ln)

    # If no explicit numbering, fall back to short sentences (first chunk)
    if not steps and text:
        sent = re.split(r"(?<=[.!?])\s+", text.strip())
        steps = [s.strip() for s in sent[:8] if len(s.strip()) > 0]
    return steps


def _extract_tools(texts: List[str]) -> List[str]:
    haystack = " ".join(texts).lower()
    found = []
    for kw in TOOL_KEYWORDS:
        if kw.lower() in haystack:
            found.append(kw)
    # Dedup
    seen = set()
    out = []
    for t in found:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def build_answer(query: str, chunks: List[RetrievedChunk]) -> Dict:
    context_texts = [c.text for c in chunks]

    warnings: List[str] = []
    for c in chunks:
        warnings.extend(_extract_warning_lines(c.text))

    # Steps from the best chunk
    steps = _extract_numbered_steps(chunks[0].text if chunks else "")

    tools = _extract_tools(context_texts)

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
        "warnings": warnings[:15],
        "tools": tools,
        "sources": sources,
        "disclaimer": (
            "Prototype: information is retrieved from the owner’s manual excerpts. "
            "Always prioritize safety and your local regulations. If you are in danger, contact emergency services / roadside assistance."
        ),
    }
