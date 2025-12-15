from __future__ import annotations

from typing import List


def simple_char_chunks(text: str, chunk_size: int = 1100, overlap: int = 200) -> List[str]:
    """Dependency-free chunker for MVP."""
    text = (text or "").strip()
    if not text:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be > overlap")

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]
