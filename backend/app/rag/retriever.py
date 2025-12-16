from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

from qdrant_client.models import Filter, FieldCondition, MatchAny

from app.config import settings
from app.rag.embeddings import FastEmbedder
from app.rag.qdrant_db import get_client, get_qdrant_config


# ---------------------------------------------------------
# Data model
# ---------------------------------------------------------
@dataclass
class RetrievedChunk:
    id: str
    text: str
    metadata: Dict[str, Any]
    score: float


# ---------------------------------------------------------
# Retriever
# ---------------------------------------------------------
class Retriever:
    """
    Generic, source-agnostic retriever for procedural manuals.

    Works for:
    - PDF ingestion
    - TXT ingestion
    - OCR / future sources

    Strategy:
    1. Broad semantic retrieval (high recall)
    2. Score thresholding (noise reduction)
    3. Context expansion (neighboring chunks)
    4. Order restoration (procedural coherence)
    """

    # Tunable knobs (safe defaults)
    BASE_TOP_K = 12
    SCORE_THRESHOLD = 0.55   # lower for TXT friendliness
    CONTEXT_WINDOW = 1       # chunks before/after

    def __init__(self) -> None:
        self.cfg = get_qdrant_config()
        self.client = get_client(self.cfg)
        self.embedder = FastEmbedder(settings.embed_model)

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def retrieve(self, query: str, top_k: int | None = None,intent: str | None = None,) -> List[RetrievedChunk]:
        """
        Retrieve context-aware chunks relevant to the query.
        """
        # 1. Embed query
        query_vector = self.embedder.embed_one(query)

        # 2. Broad semantic retrieval (NO metadata filters)
        response = self.client.query_points(
            collection_name=self.cfg.collection,
            query=query_vector,
            limit=top_k if top_k is not None else self.BASE_TOP_K,
            with_payload=True,
        )

        # 3. Score thresholding (Record-safe)
        #initial_hits = [
        #    hit
        #    for hit in response.points
        #    if self._get_similarity(hit) >= self.SCORE_THRESHOLD
        #]
        
        initial_hits = []
        
        for hit in response.points:
            score = self._get_similarity(hit)
            scenario = (hit.payload.get("scenario") or "").lower()
            
            if score >= self.SCORE_THRESHOLD:
                initial_hits.append(hit)
            elif intent == "pre_drive" and "pre_drive" in scenario:
                initial_hits.append(hit)

        if not initial_hits:
            return []

        # 4. Expand context generically
        chunk_ids_to_fetch = self._expand_context(initial_hits)

        # 5. Fetch expanded chunks by chunk_id
        expanded_hits = self._fetch_by_chunk_ids(chunk_ids_to_fetch)

        # 6. Convert to RetrievedChunk objects
        results = self._to_retrieved_chunks(expanded_hits)

        # 7. Restore procedural order
        #results.sort(key=lambda r: r.metadata.get("chunk_id", ""))
        
        if intent == "pre_drive":
            results.sort(key=lambda r:("pre-drive" not in (r.metadata.get("scenario") or "").lower(),r.metadata.get("chunk_id",""),))
        else:
            results.sort(key=lambda r: r.metadata.get("chunk_id", ""))

        return results

    # ---------------------------------------------------------
    # Similarity normalization (Qdrant-safe)
    # ---------------------------------------------------------
    def _get_similarity(self, hit) -> float:
        """
        Normalize similarity across Qdrant response types.

        - search() → ScoredPoint.score
        - query_points() → Record.distance (cosine distance)
        """
        # search() API
        if hasattr(hit, "score") and hit.score is not None:
            return float(hit.score)

        # query_points() API
        if hasattr(hit, "distance") and hit.distance is not None:
            # Cosine distance ∈ [0, 2], lower is better
            return 1.0 - float(hit.distance)

        # Fallback: trust semantic ranking
        return 1.0

    # ---------------------------------------------------------
    # Context expansion logic (GENERIC)
    # ---------------------------------------------------------
    def _expand_context(self, hits) -> Set[str]:
        """
        Expand context for ANY chunk_id format that ends with '-cXXXX'.

        Supported examples:
        - emergency-c0007
        - emergency-txt-c0007
        - manualA-section2-c0012
        """
        chunk_ids: Set[str] = set()

        for hit in hits:
            payload = hit.payload or {}
            cid = payload.get("chunk_id")
            if not cid or "-c" not in cid:
                continue

            prefix, idx_str = cid.rsplit("-c", 1)

            try:
                base_idx = int(idx_str)
            except ValueError:
                continue

            for offset in range(-self.CONTEXT_WINDOW, self.CONTEXT_WINDOW + 1):
                neighbor_idx = base_idx + offset
                if neighbor_idx < 0:
                    continue
                chunk_ids.add(f"{prefix}-c{neighbor_idx:04d}")

        return chunk_ids

    # ---------------------------------------------------------
    # Qdrant helpers
    # ---------------------------------------------------------
    def _fetch_by_chunk_ids(self, chunk_ids: Set[str]):
        """
        Fetch chunks directly by chunk_id.
        """
        if not chunk_ids:
            return []

        flt = Filter(
            must=[
                FieldCondition(
                    key="chunk_id",
                    match=MatchAny(any=list(chunk_ids)),
                )
            ]
        )

        points = []
        offset = None

        while True:
            batch, offset = self.client.scroll(
                collection_name=self.cfg.collection,
                scroll_filter=flt,
                limit=64,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            points.extend(batch)

            if offset is None:
                break

        return points

    # ---------------------------------------------------------
    # Conversion helpers
    # ---------------------------------------------------------
    def _to_retrieved_chunks(self, hits) -> List[RetrievedChunk]:
        """
        Convert Qdrant points to RetrievedChunk objects.
        """
        results: List[RetrievedChunk] = []

        print("[DEBUG] Qdrant collection:", settings.qdrant_collection)

        for hit in hits:
            payload = hit.payload or {}
            results.append(
                RetrievedChunk(
                    id=str(hit.id),
                    text=str(payload.get("text", "")),
                    metadata={
                        "page": payload.get("page"),       # PDF only
                        "chunk_id": payload.get("chunk_id"),
                        "section": payload.get("section"),
                    },
                    score=self._get_similarity(hit),
                )
            )

        print("[DEBUG] Retrieved chunks:", len(results))
        return results
