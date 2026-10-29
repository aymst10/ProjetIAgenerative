"""Réordonne les extraits : aucun reranker, BM25, ou régression logistique adaptée."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from maintidoc.config import ROOT, Settings, get_settings
from maintidoc.logging_utils import log_event
from maintidoc.rerank.features import bm25_scores, tokens
from maintidoc.retrieval.search import Hit

FEATURE_NAMES = ["overlap", "bm25", "equipment", "typed", "bias"]


def _overlap(query: str, text: str) -> float:
    query_tokens = set(tokens(query))
    if not query_tokens:
        return 0.0
    return len(query_tokens & set(tokens(text))) / len(query_tokens)


def features(query: str, hits: list[Hit], equipment_id: str | None) -> np.ndarray:
    lexical = bm25_scores(query, [hit.text for hit in hits])
    peak = max(lexical) if lexical else 1.0
    if peak <= 0:
        peak = 1.0
    rows = []
    for hit, bm25 in zip(hits, lexical):
        equipment = 1.0 if equipment_id and equipment_id in hit.equipment_ids else 0.0
        typed = 1.0 if hit.element_type in {"paragraph", "table"} else 0.0
        rows.append([_overlap(query, hit.text), bm25 / peak, equipment, typed, 1.0])
    return np.asarray(rows, dtype=np.float64)


def load_weights(settings: Settings | None = None) -> np.ndarray | None:
    settings = settings or get_settings()
    path = Path(settings.reranker_weights)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        log_event("reranker_fallback", backend="original", reason="weights_missing")
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return np.asarray(payload["weights"], dtype=np.float64)


def _order(hits: list[Hit], scores: list[float]) -> list[Hit]:
    ranked = sorted(zip(hits, scores), key=lambda pair: pair[1], reverse=True)
    return [
        Hit(
            document_id=hit.document_id,
            document_version=hit.document_version,
            title=hit.title,
            page=hit.page,
            element_id=hit.element_id,
            element_type=hit.element_type,
            family=hit.family,
            equipment_ids=list(hit.equipment_ids),
            allowed_groups=list(hit.allowed_groups),
            text=hit.text,
            image_path=hit.image_path,
            score=float(score),
            injection=hit.injection,
        )
        for hit, score in ranked
    ]


def rerank_hits(
    query: str,
    hits: list[Hit],
    mode: str | None = None,
    equipment_id: str | None = None,
    settings: Settings | None = None,
) -> list[Hit]:
    if len(hits) < 2:
        return hits
    settings = settings or get_settings()
    mode = (mode or settings.reranker_mode).strip().lower()
    if mode == "none":
        return hits
    matrix = features(query, hits, equipment_id)
    if mode == "adapted":
        weights = load_weights(settings)
        if weights is not None and weights.shape == (matrix.shape[1],):
            raw = matrix @ weights
            scores = 1.0 / (1.0 + np.exp(-np.clip(raw, -20, 20)))
            return _order(hits, scores.tolist())
        mode = "original"
    if mode == "original":
        return _order(hits, matrix[:, 1].tolist())
    return hits
