"""Recherche textuelle et visuelle limitée au corpus autorisé."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from maintidoc.access import equipment_allowed, has_corpus_access, intersects
from maintidoc.corpus_data import CORPUS, document_by_id, equipment_by_id
from maintidoc.ingest.elements import Element
from maintidoc.ingest.embeddings import embed_image, embed_texts, image_signals
from maintidoc.ingest.index import LocalIndex
from maintidoc.ingest.pipeline import get_index
from maintidoc.logging_utils import log_event
from maintidoc.retrieval.rrf import reciprocal_rank_fusion


@dataclass
class Hit:
    document_id: str
    document_version: str
    title: str
    page: int
    element_id: str
    element_type: str
    family: str
    equipment_ids: list[str]
    allowed_groups: list[str]
    text: str
    image_path: str | None
    score: float
    injection: bool

    @classmethod
    def from_element(cls, element: Element, score: float) -> "Hit":
        return cls(
            document_id=element.document_id,
            document_version=element.document_version,
            title=element.title,
            page=element.page,
            element_id=element.element_id,
            element_type=element.element_type,
            family=element.family,
            equipment_ids=list(element.equipment_ids),
            allowed_groups=list(element.allowed_groups),
            text=element.text,
            image_path=element.image_path,
            score=score,
            injection=element.injection,
        )


@dataclass
class SearchOutcome:
    hits: list[Hit]
    access_denied: bool


def _allowed_rows(index: LocalIndex, user_groups: list[str]) -> list[int]:
    return [
        row
        for row, element in enumerate(index.elements)
        if intersects(element.allowed_groups, user_groups)
    ]


def _topk(matrix: np.ndarray, query: np.ndarray, rows: list[int], k: int) -> list[int]:
    if not rows or matrix.size == 0:
        return []
    scores = matrix[rows] @ query
    order = np.argsort(-scores)
    return [rows[int(position)] for position in order[:k]]


def filter_visible(hits: list[Hit], user_groups: list[str]) -> list[Hit]:
    """Second contrôle, au moment d'afficher les extraits."""
    return [hit for hit in hits if intersects(hit.allowed_groups, user_groups)]


def search_corpus(
    query: str,
    user_groups: list[str],
    image_path: str | None = None,
    equipment_id: str | None = None,
    top_k: int = 5,
    user_id: str = "",
    index: LocalIndex | None = None,
) -> SearchOutcome:
    equipment = equipment_by_id(equipment_id)
    if not has_corpus_access(user_groups) or not equipment_allowed(equipment, user_groups):
        log_event("access_denied", user_id=user_id, document_id=equipment_id or "", reason="search")
        return SearchOutcome(hits=[], access_denied=True)

    index = index or get_index()
    from maintidoc.config import get_settings

    settings = get_settings()
    rows = _allowed_rows(index, user_groups)
    rankings: list[list[int]] = []
    if query.strip():
        query_vector = embed_texts([query], settings)[0]
        rankings.append(_topk(index.text_vectors, query_vector, rows, k=20))
    if image_path and image_signals(image_path)["readable"]:
        image_vector = embed_image(image_path, settings)
        if image_vector.shape[0] == index.image_vectors.shape[1]:
            image_rows = [row for row in rows if bool(index.image_mask[row])]
            rankings.append(_topk(index.image_vectors, image_vector, image_rows, k=10))
    fused = reciprocal_rank_fusion([ranking for ranking in rankings if ranking])
    boosted: list[tuple[int, float]] = []
    for row, score in fused:
        element = index.elements[row]
        if equipment_id and equipment_id in element.equipment_ids:
            score *= 1.25
        boosted.append((row, score))
    boosted.sort(key=lambda pair: pair[1], reverse=True)
    hits = [
        Hit.from_element(index.elements[row], score)
        for row, score in boosted[:top_k]
        if intersects(index.elements[row].allowed_groups, user_groups)
    ]
    return SearchOutcome(hits=filter_visible(hits, user_groups), access_denied=False)


def read_document(document_id: str, user_groups: list[str], user_id: str = "") -> bytes:
    document = document_by_id(document_id)
    if document is None or not intersects(document["allowed_groups"], user_groups):
        log_event("access_denied", document_id=document_id, user_id=user_id, reason="open")
        raise PermissionError("access_denied")
    return (CORPUS / document["file"]).read_bytes()


def read_figure(
    document_id: str,
    element_id: str,
    user_groups: list[str],
    user_id: str = "",
) -> bytes:
    document = document_by_id(document_id)
    if document is None or not intersects(document["allowed_groups"], user_groups):
        log_event("access_denied", document_id=document_id, user_id=user_id, reason="open_figure")
        raise PermissionError("access_denied")
    for page in document["pages"]:
        for element in page["elements"]:
            if element["element_id"] == element_id and element.get("image"):
                return (CORPUS / element["image"]).read_bytes()
    log_event("access_denied", document_id=document_id, element_id=element_id, user_id=user_id, reason="missing")
    raise PermissionError("access_denied")
