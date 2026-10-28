"""Ingestion : extraction, métadonnées, index local."""

from __future__ import annotations

from functools import lru_cache

from maintidoc.config import ROOT, get_settings
from maintidoc.ingest.index import LocalIndex, sync_qdrant
from maintidoc.ingest.parse import load_elements
from maintidoc.logging_utils import log_event
from maintidoc.metadata import replace_elements


INDEX_DIR = ROOT / "data" / "index"


def publish_originals() -> None:
    settings = get_settings()
    if settings.local_mode:
        log_event("files_local", backend="filesystem", count=0)
        return
    try:
        from minio import Minio

        from maintidoc.corpus_data import CORPUS, documents

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
        count = 0
        for document in documents():
            path = CORPUS / document["file"]
            client.fput_object(settings.minio_bucket, document["file"], str(path))
            count += 1
        log_event("files_uploaded", backend="minio", count=count)
    except Exception:
        log_event("object_store_skipped", backend="filesystem", reason="unreachable")


def ingest() -> LocalIndex:
    settings = get_settings()
    elements = load_elements()
    index = LocalIndex.build(elements, settings)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    index.save(INDEX_DIR)
    replace_elements(elements)
    publish_originals()
    sync_qdrant(index, settings)
    log_event("ingest_complete", count=len(elements), backend="local")
    get_index.cache_clear()
    return index


@lru_cache(maxsize=1)
def get_index() -> LocalIndex:
    if (INDEX_DIR / "elements.json").exists():
        return LocalIndex.load(INDEX_DIR)
    return ingest()
