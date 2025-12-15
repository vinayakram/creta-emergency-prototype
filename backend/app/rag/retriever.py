from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from app.config import settings
from app.rag.embeddings import FastEmbedder
from app.rag.qdrant_db import get_client, get_qdrant_config


@dataclass
class RetrievedChunk:
    id: str
    text: str
    metadata: Dict[str, Any]
    score: float


class Retriever:
    def __init__(self) -> None:
        self.cfg = get_qdrant_config()
        self.client = get_client(self.cfg)
        self.embedder = FastEmbedder(settings.embed_model)

    def retrieve(self, query: str, top_k: int = 4) -> List[RetrievedChunk]:
        """
        Perform semantic vector search against Qdrant.

        Uses query_points(), which is the stable API across:
        - local mode
        - embedded Qdrant
        - HTTP server mode
        """
        query_vector = self.embedder.embed_one(query)

        # Canonical Qdrant 1.x search API
        response = self.client.query_points(
            collection_name=self.cfg.collection,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        hits = response.points

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
                    },
                    score=float(hit.score),
                )
            )

        return results
