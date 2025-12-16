from __future__ import annotations

import argparse
import os
import re
import uuid
from typing import List

import fitz
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.rag.embeddings import FastEmbedder
from app.rag.qdrant_db import get_client, get_qdrant_config
from app.rag.pdf_ocr import extract_pages_ocr


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
EMERGENCY_SECTION = {
    "name": "emergency_situations",
    "start_page": 388,
    "end_page": 412,
}


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------
def deterministic_uuid(text_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text_id))


def is_garbled(text: str) -> bool:
    if not text:
        return True
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    junk_patterns = ["\\", "ȿ", "ƌ", "ǿ"]
    return alpha_ratio < 0.5 or any(j in text for j in junk_patterns)


def clean_ocr_text(text: str) -> str:
    """
    Light OCR cleanup WITHOUT destroying structure.
    """
    lines = []
    for line in text.splitlines():
        line = line.strip()

        if len(set(line)) <= 3 and len(line) > 20:
            continue

        line = re.sub(r"\.{3,}", " ", line)
        line = re.sub(r"(.)\1{4,}", r"\1", line)

        if len(line) > 20:
            lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------
# Structural chunking (NO hardcoding)
# ---------------------------------------------------------
def split_structural_blocks(text: str) -> list[str]:
    """
    Split structured manuals into semantic blocks.

    New block starts when:
    - line is non-empty
    - line is NOT a numbered step
    - line starts with a capital letter

    Works for TXT, OCR, and PDF-extracted manuals.
    """
    blocks = []
    current = []

    for line in text.splitlines():
        line = line.rstrip()

        is_heading = (
            line
            and not re.match(r"^\d+\.", line)
            and line[0].isupper()
        )

        if is_heading and current:
            blocks.append("\n".join(current).strip())
            current = []

        if line:
            current.append(line)

    if current:
        blocks.append("\n".join(current).strip())

    return [b for b in blocks if len(b) > 80]


def extract_heading(block: str) -> str | None:
    """
    Extract the first non-numbered line as scenario title.
    """
    for line in block.splitlines():
        if line and not re.match(r"^\d+\.", line):
            return line.strip()
    return None


# ---------------------------------------------------------
# PDF extraction (hybrid native + OCR)
# ---------------------------------------------------------
def extract_part8_text(pdf_path: str, start_page: int, end_page: int) -> str:
    doc = fitz.open(pdf_path)
    pages: List[str] = []

    for page_num in range(start_page - 1, end_page):
        page = doc[page_num]
        native_text = page.get_text("text").strip()

        if len(native_text) < 200 or is_garbled(native_text):
            ocr_text = extract_pages_ocr(
                pdf_path=pdf_path,
                start_page=page_num + 1,
                end_page=page_num + 1,
            )
            combined = ocr_text
        else:
            combined = native_text

        combined = clean_ocr_text(combined)

        if combined:
            pages.append(combined)

    if not pages:
        raise RuntimeError("No usable text extracted from PDF")

    return "\n\n".join(pages)


# ---------------------------------------------------------
# Core ingestion helpers
# ---------------------------------------------------------
def _create_collection(client, collection_name: str, dim: int) -> None:
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=dim,
            distance=Distance.COSINE,
        ),
    )


def _upsert_chunks(
    chunks: list[str],
    collection_name: str,
    embed_model: str,
    prefix: str,
) -> None:
    embedder = FastEmbedder(embed_model)
    vectors = embedder.embed(chunks)
    dim = embedder.dim

    cfg = get_qdrant_config()
    cfg.collection = collection_name
    client = get_client(cfg)

    _create_collection(client, collection_name, dim)

    points: List[PointStruct] = []

    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        chunk_id = f"{prefix}-c{idx:04d}"
        point_id = deterministic_uuid(chunk_id)
        scenario = extract_heading(chunk)

        payload = {
            "chunk_id": chunk_id,
            "section": EMERGENCY_SECTION["name"],
            "scenario": scenario,
            "text": chunk,
        }

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        )

    print("\n=== INGESTION SANITY CHECK ===")
    print(points[0].payload["text"][:500])
    print("==============================")

    client.upsert(
        collection_name=collection_name,
        points=points,
        wait=True,
    )

    print(f"[SUCCESS] Ingested {len(points)} scenario chunks")
    print(f"[SUCCESS] Embedding model: {embed_model} (dim={dim})")


# ---------------------------------------------------------
# Public ingestion APIs
# ---------------------------------------------------------
def ingest_pdf(
    pdf_path: str,
    collection_name: str,
    embed_model: str,
) -> None:
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"PDF not found: {pdf_path}")

    print(
        f"[INFO] Ingesting emergency section from PDF "
        f"(pages {EMERGENCY_SECTION['start_page']}–{EMERGENCY_SECTION['end_page']})"
    )

    raw_text = extract_part8_text(
        pdf_path=pdf_path,
        start_page=EMERGENCY_SECTION["start_page"],
        end_page=EMERGENCY_SECTION["end_page"],
    )

    chunks = split_structural_blocks(raw_text)
    if not chunks:
        raise RuntimeError("No scenario blocks produced from PDF")

    _upsert_chunks(
        chunks=chunks,
        collection_name=collection_name,
        embed_model=embed_model,
        prefix="emergency-pdf",
    )


def ingest_txt_file(
    txt_path: str,
    collection_name: str,
    embed_model: str,
) -> None:
    if not os.path.exists(txt_path):
        raise RuntimeError(f"Text file not found: {txt_path}")

    with open(txt_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    raw_text = raw_text.replace("\u00a0", " ").strip()
    if not raw_text:
        raise RuntimeError("Text file is empty")

    chunks = split_structural_blocks(raw_text)
    if not chunks:
        raise RuntimeError("No scenario blocks produced from TXT")

    _upsert_chunks(
        chunks=chunks,
        collection_name=collection_name,
        embed_model=embed_model,
        prefix="emergency-txt",
    )


def ingest_source(
    path: str,
    collection_name: str,
    embed_model: str,
) -> None:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".txt":
        print("[INFO] Detected TXT source – using structural TXT ingestion")
        ingest_txt_file(path, collection_name, embed_model)

    elif ext == ".pdf":
        print("[INFO] Detected PDF source – using hybrid PDF ingestion")
        ingest_pdf(path, collection_name, embed_model)

    else:
        raise ValueError(f"Unsupported file type '{ext}'")


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--collection", default=settings.qdrant_collection)
    parser.add_argument("--embed-model", default=settings.embed_model)
    args = parser.parse_args()

    ingest_source(
        path=args.source,
        collection_name=args.collection,
        embed_model=args.embed_model,
    )


if __name__ == "__main__":
    main()
