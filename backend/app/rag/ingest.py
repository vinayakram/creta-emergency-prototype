from __future__ import annotations

import argparse
import os
import uuid
from typing import List

from pypdf import PdfReader
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.rag.chunking import simple_char_chunks
from app.rag.embeddings import FastEmbedder
from app.rag.qdrant_db import get_client, get_qdrant_config


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
    """Normalize extracted PDF text."""
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

    reader = PdfReader(pdf_path)

    # Convert to 0-based indices for PdfReader
    start = EMERGENCY_SECTION["start_page"] - 1
    end = EMERGENCY_SECTION["end_page"]

    if start < 0 or end > len(reader.pages):
        raise RuntimeError(
            f"Configured page range {start+1}-{end} "
            f"is outside PDF page count ({len(reader.pages)})"
        )

    print(
        f"[INFO] Ingesting section '{EMERGENCY_SECTION['name']}' "
        f"from PDF pages {start+1} to {end}"
    )

    embedder = FastEmbedder(embed_model)
    dim = embedder.dim

    cfg = get_qdrant_config()
    cfg.collection = collection_name
    client = get_client(cfg)

    # Always recreate collection for clean MVP runs
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=dim,
            distance=Distance.COSINE,
        ),
    )

    points: List[PointStruct] = []

    for page_idx in range(start, end):
        page = reader.pages[page_idx]
        cleaned_text = _clean(page.extract_text() or "")

        if not cleaned_text:
            continue

        chunks = simple_char_chunks(
            cleaned_text,
            chunk_size=1100,
            overlap=200,
        )

        vectors = embedder.embed(chunks)

        for chunk_idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            chunk_id = f"p{page_idx+1:04d}-c{chunk_idx:03d}"
            point_id = deterministic_uuid(chunk_id)

            payload = {
                "chunk_id": chunk_id,
                "page": page_idx + 1,
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

    if not points:
        raise RuntimeError("No text chunks extracted. Check PDF encoding.")

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
