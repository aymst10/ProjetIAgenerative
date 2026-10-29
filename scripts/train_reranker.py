"""Entraîne le petit reranker adapté et écrit ses poids."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maintidoc.ingest.pipeline import get_index
from maintidoc.rerank.apply import features
from maintidoc.rerank.features import tokens
from maintidoc.retrieval.search import Hit

HOLDOUT = {"manuel_comp_a", "fiche_comp_b_seuils", "graissage_pompes", "note_atelier_pompes"}
OUTPUT = ROOT / "models" / "reranker_adapted.json"


def _hit(element, score: float = 0.0) -> Hit:
    return Hit(
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


def examples(seed: int = 7) -> tuple[np.ndarray, np.ndarray, int]:
    rng = random.Random(seed)
    elements = [
        element
        for element in get_index().elements
        if not element.element_id.startswith("garde")
        and not element.injection
        and len(tokens(element.text)) >= 4
    ]
    rows: list[np.ndarray] = []
    labels: list[float] = []
    count = 0
    for element in elements:
        if element.document_id in HOLDOUT:
            continue
        words = tokens(element.text)
        questions = [" ".join(words[:5]), " ".join(list(reversed(words[:5])))]
        others = [item for item in elements if item.key != element.key]
        ranked = sorted(
            others,
            key=lambda item: len(set(tokens(questions[0])) & set(tokens(item.text))),
            reverse=True,
        )
        negatives = ranked[:14]
        rng.shuffle(others)
        negatives.extend(others[:6])
        for question in questions:
            pool = [_hit(element)] + [_hit(item) for item in negatives]
            matrix = features(question, pool, element.equipment_ids[0] if element.equipment_ids else None)
            rows.append(matrix[0])
            labels.append(1.0)
            for row in matrix[1:]:
                rows.append(row)
                labels.append(0.0)
            count += 1
    return np.asarray(rows, dtype=np.float64), np.asarray(labels, dtype=np.float64), count


def fit(features_matrix: np.ndarray, labels: np.ndarray, epochs: int = 500, lr: float = 0.4) -> np.ndarray:
    weights = np.array([1.0, 1.0, 0.4, 0.2, -0.4], dtype=np.float64)
    for _ in range(epochs):
        raw = np.clip(features_matrix @ weights, -20, 20)
        probs = 1.0 / (1.0 + np.exp(-raw))
        gradient = (probs - labels)[:, None] * features_matrix
        weights -= lr * gradient.mean(axis=0)
    return weights


def main() -> None:
    matrix, labels, positives = examples()
    weights = fit(matrix, labels)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "weights": [round(float(value), 6) for value in weights],
        "features": ["overlap", "bm25", "equipment", "typed", "bias"],
        "train_examples": int(len(labels)),
        "positives": positives,
        "holdout_documents": sorted(HOLDOUT),
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"examples={len(labels)} weights={payload['weights']}")


if __name__ == "__main__":
    main()
