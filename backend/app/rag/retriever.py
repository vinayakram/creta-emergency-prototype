from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

from app.config import settings
from app.rag.embeddings import FastEmbedder
from app.rag.qdrant_db import get_client, get_qdrant_config
from qdrant_client.models import Filter, FieldCondition, MatchAny



@dataclass
class RetrievedChunk:
    id: str
    text: str
    metadata: Dict[str, Any]
    score: float


class Retriever:
    """
    Keyword-free, context-aware retriever for procedural manuals.

    Strategy:
    1. Broad semantic retrieval (high recall)
    2. Score thresholding (noise reduction)
    3. Context expansion (adjacent chunks)
    4. Order restoration (procedural coherence)
    """

    # Tunable knobs (safe defaults)
    BASE_TOP_K = 12
    SCORE_THRESHOLD = 0.62
    CONTEXT_WINDOW = 1  # number of chunks before/after

    def __init__(self) -> None:
        self.cfg = get_qdrant_config()
        self.client = get_client(self.cfg)
        self.embedder = FastEmbedder(settings.embed_model)

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def retrieve(self, query: str,top_k: int | None = None) -> List[RetrievedChunk]:
        """
        Retrieve context-aware chunks relevant to the query.
        """
        # 1. Embed query
        query_vector = self.embedder.embed_one(query)

        # 2. Broad semantic retrieval
        response = self.client.query_points(
            collection_name=self.cfg.collection,
            query=query_vector,
            limit=top_k if top_k is not None else self.BASE_TOP_K,
            with_payload=True,
        )

        # 3. Score thresholding
        initial_hits = [
            hit for hit in response.points
            if hit.score is not None and hit.score >= self.SCORE_THRESHOLD
        ]

        if not initial_hits:
            return []

        # 4. Determine which neighboring chunks to include
        chunk_ids_to_fetch = self._expand_context(initial_hits)

        # 5. Fetch expanded set directly by IDs
        expanded_hits = self._fetch_by_chunk_ids(chunk_ids_to_fetch)

        # 6. Convert to RetrievedChunk
        results = self._to_retrieved_chunks(expanded_hits)

        # 7. Restore procedural order
        results.sort(key=lambda r: r.metadata.get("chunk_id", ""))

        return results

    # ---------------------------------------------------------
    # Context expansion logic
    # ---------------------------------------------------------
    def _expand_context(self, hits) -> Set[str]:
        """
        Given initial hits, compute neighboring chunk_ids to fetch.
        """
        chunk_ids: Set[str] = set()

        for hit in hits:
            payload = hit.payload or {}
            cid = payload.get("chunk_id")
            if not cid:
                continue

            try:
                # Expected format: emergency-c0007
                base_idx = int(cid.split("-c")[1])
            except (IndexError, ValueError):
                continue

            for offset in range(-self.CONTEXT_WINDOW, self.CONTEXT_WINDOW + 1):
                neighbor_idx = base_idx + offset
                if neighbor_idx < 0:
                    continue
                chunk_ids.add(f"emergency-c{neighbor_idx:04d}")

        return chunk_ids

    # ---------------------------------------------------------
    # Qdrant helpers
    # ---------------------------------------------------------
    def _fetch_by_chunk_ids(self, chunk_ids: set[str]):
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

        for hit in hits:
            payload = hit.payload or {}
            results.append(
                RetrievedChunk(
                    id=str(hit.id),
                    text=str(payload.get("text", "")),
                    metadata={
                        "page": payload.get("page"),
                        "chunk_id": payload.get("chunk_id"),
                        "section": payload.get("section"),
                    },
                    # Expanded chunks may not have a similarity score
                    score=float(hit.score) if hasattr(hit, "score") and hit.score is not None else 0.0,
                )
            )

        return results
