from __future__ import annotations

import argparse
import os
import uuid
from typing import List, Optional, Tuple

from pypdf import PdfReader
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.rag.chunking import simple_char_chunks
from app.rag.embeddings import FastEmbedder
from app.rag.qdrant_db import get_client, get_qdrant_config


def _clean(text: str) -> str:
    return " ".join((text or "").replace("\u00a0", " ").split())


def find_part8_range(reader: PdfReader) -> Tuple[int, int]:
    """Best-effort: find start page of 'PART 8' and stop at 'PART 9' if present.
    If we fail, ingest whole PDF.
    """
    start = 0
    end = len(reader.pages)

    for i, page in enumerate(reader.pages):
        t = (page.extract_text() or "").upper()
        if "PART 8" in t and ("EMERGENCY" in t or "EMERGENC" in t):
            start = i
            break

    for i in range(start + 1, len(reader.pages)):
        t = (reader.pages[i].extract_text() or "").upper()
        if "PART 9" in t:
            end = i
            break

    return start, end


def deterministic_uuid(text_id: str) -> str:
    # Qdrant supports UUID IDs; UUID5 gives stable IDs across re-ingest.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text_id))


def ingest_pdf(
    pdf_path: str,
    collection_name: str,
    embed_model: str,
    force_page_start: Optional[int] = None,
    force_page_end: Optional[int] = None,
) -> None:
    reader = PdfReader(pdf_path)
    if force_page_start is not None and force_page_end is not None:
        start, end = force_page_start, force_page_end
    else:
        start, end = find_part8_range(reader)

    embedder = FastEmbedder(embed_model)
    dim = embedder.dim

    cfg = get_qdrant_config()
    cfg.collection = collection_name
    client = get_client(cfg)

    # Recreate collection for a clean MVP run
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    points: List[PointStruct] = []

    for page_idx in range(start, end):
        page = reader.pages[page_idx]
        cleaned = _clean(page.extract_text() or "")
        if not cleaned:
            continue

        chunks = simple_char_chunks(cleaned, chunk_size=1100, overlap=200)
        if not chunks:
            continue

        vectors = embedder.embed(chunks)

        for chunk_idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            chunk_id = f"p{page_idx+1:04d}-c{chunk_idx:03d}"
            point_id = deterministic_uuid(chunk_id)
            payload = {"chunk_id": chunk_id, "page": page_idx + 1, "text": chunk}
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))

    if not points:
        raise RuntimeError("No text extracted from PDF. Try a different PDF parser or check the file.")

    client.upsert(collection_name=collection_name, points=points, wait=True)

    print(f"Ingested {len(points)} chunks into Qdrant collection '{collection_name}'.")
    print(f"Embedding model: {embed_model} (dim={dim})")
    print(f"Page range used: start={start+1} end={end} (end is exclusive).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="Path to Creta manual PDF")
    parser.add_argument("--collection", default=settings.qdrant_collection)
    parser.add_argument("--embed-model", default=settings.embed_model)
    parser.add_argument("--page-start", type=int, default=None, help="1-indexed start page override")
    parser.add_argument("--page-end", type=int, default=None, help="1-indexed end page override (exclusive)")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        raise SystemExit(f"PDF not found: {args.pdf}")

    ps = args.page_start - 1 if args.page_start else None
    pe = args.page_end - 1 if args.page_end else None

    ingest_pdf(
        pdf_path=args.pdf,
        collection_name=args.collection,
        embed_model=args.embed_model,
        force_page_start=ps,
        force_page_end=pe,
    )


if __name__ == "__main__":
    main()
