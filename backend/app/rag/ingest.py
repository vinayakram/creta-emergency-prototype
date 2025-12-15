from __future__ import annotations

import argparse
import os
import uuid
from typing import List

from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.rag.chunking import simple_char_chunks
from app.rag.embeddings import FastEmbedder
from app.rag.qdrant_db import get_client, get_qdrant_config
from app.rag.pdf_ocr import extract_pages_ocr


# ---------------------------------------------------------
# CONFIG: Validated Emergency Situations page range
# (PDF page numbers, 1-based, inclusive)
# ---------------------------------------------------------
EMERGENCY_SECTION = {
    "name": "emergency_situations",
    "start_page": 388,  # inclusive
    "end_page": 412,    # inclusive
}


def _clean(text: str) -> str:
    """Normalize OCR text."""
    return " ".join((text or "").replace("\u00a0", " ").split())


def deterministic_uuid(text_id: str) -> str:
    """Stable UUID so re-ingestion does not create duplicates."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text_id))


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
    # OCR EXTRACTION (SOURCE OF TRUTH)
    # -----------------------------------------------------
    raw_text = extract_pages_ocr(
        pdf_path=pdf_path,
        start_page=EMERGENCY_SECTION["start_page"],
        end_page=EMERGENCY_SECTION["end_page"],
    )

    cleaned_text = _clean(raw_text)

    if not cleaned_text:
        raise RuntimeError("OCR extraction returned empty text")

    # -----------------------------------------------------
    # CHUNKING
    # -----------------------------------------------------
    chunks = simple_char_chunks(
        cleaned_text,
        chunk_size=1100,
        overlap=200,
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
    # DEBUG SAMPLE (DO NOT REMOVE WHILE TESTING)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to Creta manual PDF",
    )
    parser.add_argument(
        "--collection",
        default=settings.qdrant_collection,
    )
    parser.add_argument(
        "--embed-model",
        default=settings.embed_model,
    )

    args = parser.parse_args()

    ingest_pdf(
        pdf_path=args.pdf,
        collection_name=args.collection,
        embed_model=args.embed_model,
    )


if __name__ == "__main__":
    main()
