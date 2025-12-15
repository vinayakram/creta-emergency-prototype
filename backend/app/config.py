from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Qdrant: local mode path or server url
    qdrant_path: str | None = "data/qdrant"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "creta_part8"

    # Embeddings
    embed_model: str = "BAAI/bge-small-en-v1.5"
    top_k: int = 4

    allow_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
