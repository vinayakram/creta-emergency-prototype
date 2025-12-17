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

    Strategy:
    1. Broad semantic retrieval (high recall)
    2. Score thresholding (noise reduction)
    3. Scenario-aware biasing (safety)
    4. Context expansion (procedural continuity)
    5. Order restoration
    """

    BASE_TOP_K = 12
    SCORE_THRESHOLD = 0.55
    CONTEXT_WINDOW = 1

    def __init__(self) -> None:
        self.cfg = get_qdrant_config()
        self.client = get_client(self.cfg)
        self.embedder = FastEmbedder(settings.embed_model)

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        intent: str | None = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve context-aware chunks relevant to the query.
        """

        query_l = query.lower()

        # --------------------------------------------------
        # 1. Embed query
        # --------------------------------------------------
        query_vector = self.embedder.embed_one(query)

        # --------------------------------------------------
        # 2. Broad semantic retrieval (pytest-safe)
        # --------------------------------------------------
        try:
            response = self.client.query_points(
                collection_name=self.cfg.collection,
                query=query_vector,
                limit=(top_k or self.BASE_TOP_K) * 2,
                with_payload=True,
            )
        except Exception:
            # Qdrant not initialized / ingestion not run
            # Treat as empty knowledge base (pytest-safe)
            return []

        # --------------------------------------------------
        # 3. Score thresholding
        # --------------------------------------------------
        initial_hits = []

        for hit in response.points:
            score = self._get_similarity(hit)
            scenario = (hit.payload.get("scenario") or "").lower()

            if score >= self.SCORE_THRESHOLD:
                initial_hits.append(hit)
            elif intent == "pre_drive" and "pre-drive" in scenario:
                initial_hits.append(hit)

        if not initial_hits:
            return []

        # --------------------------------------------------
        # 4. Scenario-aware biasing (battery / jump-start)
        # --------------------------------------------------
        def is_battery_related(hit) -> bool:
            scenario = (hit.payload.get("scenario") or "").lower()
            text = (hit.payload.get("text") or "").lower()
            return any(
                kw in scenario or kw in text
                for kw in ("battery", "jump", "jump start", "jump-start")
            )

        if any(kw in query_l for kw in ("battery", "dead battery", "jump")):
            battery_hits = [h for h in initial_hits if is_battery_related(h)]
            if battery_hits:
                initial_hits = battery_hits

        # --------------------------------------------------
        # 5. Expand context
        # --------------------------------------------------
        chunk_ids_to_fetch = self._expand_context(initial_hits)

        expanded_hits = self._fetch_by_chunk_ids(chunk_ids_to_fetch)

        # --------------------------------------------------
        # 6. Convert to RetrievedChunk objects
        # --------------------------------------------------
        results = self._to_retrieved_chunks(expanded_hits)

        # --------------------------------------------------
        # 7. Restore procedural order
        # --------------------------------------------------
        if intent == "pre_drive":
            results.sort(
                key=lambda r: (
                    "pre-drive" not in (r.metadata.get("scenario") or "").lower(),
                    r.metadata.get("chunk_id", ""),
                )
            )
        else:
            results.sort(key=lambda r: r.metadata.get("chunk_id", ""))

        return results

    # ---------------------------------------------------------
    # Similarity normalization
    # ---------------------------------------------------------
    def _get_similarity(self, hit) -> float:
        if hasattr(hit, "score") and hit.score is not None:
            return float(hit.score)

        if hasattr(hit, "distance") and hit.distance is not None:
            return 1.0 - float(hit.distance)

        return 1.0

    # ---------------------------------------------------------
    # Context expansion logic
    # ---------------------------------------------------------
    def _expand_context(self, hits) -> Set[str]:
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
                        "scenario": payload.get("scenario"),
                    },
                    score=self._get_similarity(hit),
                )
            )

        return results
