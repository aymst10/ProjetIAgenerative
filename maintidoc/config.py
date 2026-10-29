"""Configuration lue depuis l'environnement. Aucun secret n'est codé en dur pour la production."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_secret: str
    storage_backend: str
    database_url: str
    qdrant_url: str
    qdrant_collection: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    mcp_url: str
    mlflow_tracking_uri: str
    use_heavy_models: bool
    use_vlm: bool
    embedding_model: str
    vision_encoder: str
    vlm_model: str
    index_version: str
    reranker_mode: str
    reranker_weights: str
    user_daily_quota: int
    max_mcp_calls: int
    max_model_calls: int
    max_processing_seconds: int
    max_image_bytes: int
    max_context_chars: int
    max_output_tokens: int
    api_url: str
    root: Path = ROOT

    @property
    def local_mode(self) -> bool:
        return self.storage_backend.strip().lower() != "external"

    @classmethod
    def from_env(cls) -> "Settings":
        secret = os.environ.get("APP_SECRET", "").strip()
        if not secret:
            secret = "dev-only-insecure-secret"
        data_dir = ROOT / "data"
        default_db = "sqlite:///" + str(data_dir / "maintidoc.db")
        return cls(
            app_secret=secret,
            storage_backend=os.environ.get("STORAGE_BACKEND", "local"),
            database_url=os.environ.get("DATABASE_URL", default_db),
            qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
            qdrant_collection=os.environ.get("QDRANT_COLLECTION", "maintidoc"),
            minio_endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
            minio_access_key=os.environ.get("MINIO_ACCESS_KEY", "maintidoc"),
            minio_secret_key=os.environ.get("MINIO_SECRET_KEY", "maintidoc-demo-secret"),
            minio_bucket=os.environ.get("MINIO_BUCKET", "maintidoc"),
            minio_secure=_env_bool("MINIO_SECURE", False),
            mcp_url=os.environ.get("MCP_URL", "http://localhost:8001/mcp"),
            mlflow_tracking_uri=os.environ.get("MLFLOW_TRACKING_URI", ""),
            use_heavy_models=_env_bool("USE_HEAVY_MODELS", False),
            use_vlm=_env_bool("USE_VLM", False),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "hashing-multilingual-v1"),
            vision_encoder=os.environ.get("VISION_ENCODER", "colorhist-v1"),
            vlm_model=os.environ.get("VLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"),
            index_version=os.environ.get("INDEX_VERSION", "idx-synth-v1"),
            reranker_mode=os.environ.get("RERANKER_MODE", "original"),
            reranker_weights=os.environ.get("RERANKER_WEIGHTS", "models/reranker_adapted.json"),
            user_daily_quota=_env_int("USER_DAILY_QUOTA", 30),
            max_mcp_calls=_env_int("MAX_MCP_CALLS", 3),
            max_model_calls=_env_int("MAX_MODEL_CALLS", 6),
            max_processing_seconds=_env_int("MAX_PROCESSING_SECONDS", 60),
            max_image_bytes=_env_int("MAX_IMAGE_BYTES", 5_000_000),
            max_context_chars=_env_int("MAX_CONTEXT_CHARS", 6000),
            max_output_tokens=_env_int("MAX_OUTPUT_TOKENS", 800),
            api_url=os.environ.get("API_URL", "http://localhost:8000"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def reset_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
