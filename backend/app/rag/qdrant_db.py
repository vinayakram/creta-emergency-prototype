from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from qdrant_client import QdrantClient

from app.config import settings


@dataclass
class QdrantConfig:
    collection: str
    path: Optional[str] = None
    url: Optional[str] = None
    api_key: Optional[str] = None


def get_qdrant_config() -> QdrantConfig:
    return QdrantConfig(
        collection=settings.qdrant_collection,
        path=settings.qdrant_path,
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )


def get_client(cfg: QdrantConfig) -> QdrantClient:
    # Prefer URL when provided; else local mode via path.
    if cfg.url:
        return QdrantClient(url=cfg.url, api_key=cfg.api_key)
    if not cfg.path:
        return QdrantClient(":memory:")
    return QdrantClient(path=cfg.path)
