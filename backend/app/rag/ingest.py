from __future__ import annotations

import argparse
import os
import uuid
import fitz
import re
from typing import List

from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.rag.chunking import simple_char_chunks
from app.rag.embeddings import FastEmbedder
from app.rag.qdrant_db import get_client, get_qdrant_config
from app.rag.pdf_ocr import extract_pages_ocr


# ---------------------------------------------------------
# CONFIG: Validated Emergency Situations page range
# ---------------------------------------------------------
EMERGENCY_SECTION = {
    "name": "emergency_situations",
    "start_page": 388,
    "end_page": 412,
}


def _clean(text: str) -> str:
    return " ".join((text or "").replace("\u00a0", " ").split())


def deterministic_uuid(text_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text_id))


def is_garbled(text: str) -> bool:
    if not text:
        return True
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    junk_patterns = ["\\", "ȿ", "ƌ", "ǿ"]
    return alpha_ratio < 0.5 or any(j in text for j in junk_patterns)


def clean_ocr_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()

        # Drop lines that are mostly repeated chars
        if len(set(line)) <= 3 and len(line) > 20:
            continue

        # Remove dot leaders like "......"
        line = re.sub(r"\.{3,}", " ", line)

        # Collapse repeated letters (eeeeeee → e)
        line = re.sub(r"(.)\1{4,}", r"\1", line)

        if len(line) > 30:
            lines.append(line)

    return " ".join(lines)


def extract_part8_text(pdf_path: str, start_page: int, end_page: int) -> str:
    doc = fitz.open(pdf_path)
    collected_pages = []

    for page_num in range(start_page - 1, end_page):
        page = doc[page_num]

        native_text = page.get_text("text").strip()

        # 🔥 NEW: detect garbled text
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
            collected_pages.append(combined)

    if not collected_pages:
        raise RuntimeError("Hybrid extraction produced no usable text")

    return "\n\n".join(collected_pages)


def ingest_pdf(
    pdf_path: str,
    collection_name: str,
    embed_model: str,
) -> None:
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"PDF not found: {pdf_path}")

    print(
        f"[INFO] Ingesting section '{EMERGENCY_SECTION['name']}' "
        f"from PDF pages {EMERGENCY_SECTION['start_page']} "
        f"to {EMERGENCY_SECTION['end_page']}"
    )

    # -----------------------------------------------------
    # HYBRID EXTRACTION (FIX)
    # -----------------------------------------------------
    raw_text = extract_part8_text(
        pdf_path=pdf_path,
        start_page=EMERGENCY_SECTION["start_page"],
        end_page=EMERGENCY_SECTION["end_page"],
    )

    if not raw_text:
        raise RuntimeError("Extraction returned empty text")

    # -----------------------------------------------------
    # CHUNKING (unchanged for now)
    # -----------------------------------------------------
    chunks = simple_char_chunks(
        raw_text,
        chunk_size=300,
        overlap=20,
    )

    if not chunks:
        raise RuntimeError("Chunking produced no chunks")

    print(f"[INFO] Created {len(chunks)} text chunks")

    # -----------------------------------------------------
    # EMBEDDINGS
    # -----------------------------------------------------
    embedder = FastEmbedder(embed_model)
    vectors = embedder.embed(chunks)
    dim = embedder.dim

    # -----------------------------------------------------
    # QDRANT SETUP
    # -----------------------------------------------------
    cfg = get_qdrant_config()
    cfg.collection = collection_name
    client = get_client(cfg)

    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=dim,
            distance=Distance.COSINE,
        ),
    )

    # -----------------------------------------------------
    # POINT CONSTRUCTION
    # -----------------------------------------------------
    points: List[PointStruct] = []

    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        chunk_id = f"emergency-c{idx:04d}"
        point_id = deterministic_uuid(chunk_id)

        payload = {
            "chunk_id": chunk_id,
            "section": EMERGENCY_SECTION["name"],
            "text": chunk,
        }

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        )

    # -----------------------------------------------------
    # DEBUG SAMPLE
    # -----------------------------------------------------
    print("\n=== INGESTION SANITY CHECK ===")
    print(points[0].payload["text"][:500])
    print("==============================")

    # -----------------------------------------------------
    # UPSERT
    # -----------------------------------------------------
    client.upsert(
        collection_name=collection_name,
        points=points,
        wait=True,
    )

    print(f"[SUCCESS] Ingested {len(points)} chunks")
    print(f"[SUCCESS] Embedding model: {embed_model} (dim={dim})")


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

    chunks = simple_char_chunks(
        raw_text,
        chunk_size=300,
        overlap=20,
    )

    if not chunks:
        raise RuntimeError("Chunking produced no chunks")

    print(f"[INFO] Created {len(chunks)} text chunks")

    embedder = FastEmbedder(embed_model)
    vectors = embedder.embed(chunks)
    dim = embedder.dim

    cfg = get_qdrant_config()
    cfg.collection = collection_name
    client = get_client(cfg)

    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=dim,
            distance=Distance.COSINE,
        ),
    )

    points = []
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        chunk_id = f"emergency-txt-c{idx:04d}"
        point_id = deterministic_uuid(chunk_id)

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "chunk_id": chunk_id,
                    "section": "emergency_situations",
                    "text": chunk,
                },
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

    print(f"[SUCCESS] Ingested {len(points)} chunks from TXT")


def ingest_source(
    path: str,
    collection_name: str,
    embed_model: str,
) -> None:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".txt":
        print("[INFO] Detected TXT source – using text ingestion")
        ingest_txt_file(
            txt_path=path,
            collection_name=collection_name,
            embed_model=embed_model,
        )

    elif ext == ".pdf":
        print("[INFO] Detected PDF source – using PDF ingestion")
        ingest_pdf(
            pdf_path=path,
            collection_name=collection_name,
            embed_model=embed_model,
        )

    else:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            "Only .pdf and .txt are supported."
        )


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
