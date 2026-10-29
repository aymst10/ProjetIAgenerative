"""Les trois modes de reranker restent dans le corpus autorisé."""

import json

from maintidoc.config import ROOT
from maintidoc.retrieval.search import search_corpus


def test_modes_keep_the_pump_manual_visible():
    question = "Que signifie le voyant orange du panneau POMPE-A ?"
    for mode in ("none", "original", "adapted"):
        outcome = search_corpus(
            question,
            ["pompes"],
            equipment_id="POMPE-A",
            top_k=5,
            reranker_mode=mode,
        )
        documents = {hit.document_id for hit in outcome.hits}
        assert "manuel_pompe_a" in documents or "schema_pompe_a_panneau" in documents
        assert all(hit.family == "pompes" for hit in outcome.hits)


def test_adapted_weights_exist_and_have_five_features():
    payload = json.loads((ROOT / "models" / "reranker_adapted.json").read_text(encoding="utf-8"))
    assert len(payload["weights"]) == 5
    assert payload["train_examples"] >= 800


def test_scenario_catalog_covers_the_brief():
    scenarios = json.loads((ROOT / "eval" / "scenarios.json").read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for item in scenarios:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    assert len(scenarios) == 150
    assert counts["text"] == 40
    assert counts["image"] == 30
    assert counts["mcp"] == 20
    assert counts["uncertainty"] == 20
    assert counts["access"] == 20
    assert counts["injection"] == 20
