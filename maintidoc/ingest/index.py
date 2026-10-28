"""Index vectoriel local, avec envoi optionnel vers Qdrant."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from maintidoc.config import ROOT, Settings
from maintidoc.ingest.elements import Element
from maintidoc.ingest.embeddings import HIST_DIM, color_histogram, embed_texts
from maintidoc.logging_utils import log_event


@dataclass
class LocalIndex:
    elements: list[Element]
    text_vectors: np.ndarray
    image_vectors: np.ndarray
    image_mask: np.ndarray
    meta: dict

    @classmethod
    def build(cls, elements: list[Element], settings: Settings) -> "LocalIndex":
        sources = [
            " ".join(element.equipment_ids)
            + " "
            + element.family
            + " "
            + element.text
            + " "
            + element.ocr_text
            for element in elements
        ]
        text_vectors = embed_texts(sources, settings)
        image_vectors = np.zeros((len(elements), HIST_DIM), dtype=np.float32)
        mask = np.zeros(len(elements), dtype=bool)
        figures = ROOT / "corpus"
        for index, element in enumerate(elements):
            if not element.image_path:
                continue
            image_vectors[index] = color_histogram(str(figures / element.image_path))
            mask[index] = True
        meta = {
            "count": len(elements),
            "embedding_model": settings.embedding_model,
            "vision_encoder": settings.vision_encoder,
            "index_version": settings.index_version,
        }
        return cls(elements, text_vectors, image_vectors, mask, meta)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        payload = [element.to_dict() for element in self.elements]
        (directory / "elements.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        (directory / "meta.json").write_text(
            json.dumps(self.meta, ensure_ascii=False),
            encoding="utf-8",
        )
        np.savez_compressed(
            directory / "vectors.npz",
            text=self.text_vectors,
            image=self.image_vectors,
            mask=self.image_mask,
        )

    @classmethod
    def load(cls, directory: Path) -> "LocalIndex":
        payload = json.loads((directory / "elements.json").read_text(encoding="utf-8"))
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        arrays = np.load(directory / "vectors.npz")
        return cls(
            [Element.from_dict(item) for item in payload],
            arrays["text"],
            arrays["image"],
            arrays["mask"],
            meta,
        )


def sync_qdrant(index: LocalIndex, settings: Settings) -> None:
    if settings.local_mode:
        return
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams

        client = QdrantClient(url=settings.qdrant_url, timeout=3)
        name = settings.qdrant_collection
        dim = int(index.text_vectors.shape[1])
        if not client.collection_exists(name):
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        points = []
        for index_row, element in enumerate(index.elements):
            points.append(
                PointStruct(
                    id=index_row,
                    vector=index.text_vectors[index_row].tolist(),
                    payload={
                        "document_id": element.document_id,
                        "page": element.page,
                        "element_id": element.element_id,
                        "allowed_groups": element.allowed_groups,
                        "key": element.key,
                    },
                )
            )
        if points:
            client.upsert(collection_name=name, points=points)
        log_event("qdrant_upsert", count=len(points), backend="qdrant")
    except Exception:
        log_event("qdrant_skipped", backend="local", reason="unreachable")
