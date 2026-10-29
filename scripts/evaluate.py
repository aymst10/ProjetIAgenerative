"""Compare les rerankers et vérifie les scénarios de sécurité."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maintidoc.corpus_data import user_by_id
from maintidoc.retrieval.search import search_corpus
from maintidoc.workflow.graph import run_question

SCENARIOS = ROOT / "eval" / "scenarios.json"
REPORT = ROOT / "eval" / "report.json"


def _dcg(flags: list[int], k: int) -> float:
    return sum(flag / math.log2(index + 2) for index, flag in enumerate(flags[:k]))


def retrieval_metrics(mode: str, scenarios: list[dict]) -> dict[str, float]:
    ndcg_scores = []
    mrr_scores = []
    recall_scores = []
    for scenario in scenarios:
        relevant = set(scenario["relevant_documents"])
        if not relevant:
            continue
        user = user_by_id(scenario["user"])
        image = str(ROOT / "corpus" / scenario["image"]) if scenario.get("image") else None
        outcome = search_corpus(
            scenario["question"],
            user["groups"],
            image_path=image,
            equipment_id=scenario.get("equipment_id"),
            top_k=10,
            user_id=user["user_id"],
            reranker_mode=mode,
        )
        ranked = [hit.document_id for hit in outcome.hits]
        flags = [1 if document in relevant else 0 for document in ranked]
        ideal = _dcg(sorted(flags, reverse=True), 5)
        ndcg_scores.append(0.0 if ideal == 0 else _dcg(flags, 5) / ideal)
        rank = next((index + 1 for index, flag in enumerate(flags) if flag), None)
        mrr_scores.append(0.0 if rank is None or rank > 10 else 1 / rank)
        recall_scores.append(1.0 if any(flags[:5]) else 0.0)
    size = max(len(ndcg_scores), 1)
    return {
        "n": len(ndcg_scores),
        "ndcg_at_5": round(sum(ndcg_scores) / size, 4),
        "mrr_at_10": round(sum(mrr_scores) / size, 4),
        "recall_at_5": round(sum(recall_scores) / size, 4),
    }


def workflow_checks(scenarios: list[dict]) -> dict:
    failures = []
    leaks = 0
    unapproved = 0
    for scenario in scenarios:
        if scenario["category"] in {"text", "image"} and scenario.get("expect_status") not in {
            "needs_clarification",
            "abstained",
            "access_denied",
        }:
            continue
        user = user_by_id(scenario["user"])
        image = str(ROOT / "corpus" / scenario["image"]) if scenario.get("image") else None
        envelope = run_question(
            scenario["question"],
            user,
            equipment_id=scenario.get("equipment_id"),
            image_path=image,
        )
        output = envelope.output
        tools = [item.tool for item in envelope.tool_trace]
        if scenario.get("expect_status") and output.status != scenario["expect_status"]:
            failures.append({"category": scenario["category"], "question": scenario["question"], "status": output.status})
        if scenario.get("answer_contains") and scenario["answer_contains"].lower() not in output.answer.lower():
            failures.append({"category": scenario["category"], "question": scenario["question"], "missing": scenario["answer_contains"]})
        for forbidden in scenario.get("answer_excludes", []):
            if forbidden.lower() in output.answer.lower():
                leaks += 1
                failures.append({"category": scenario["category"], "leak": forbidden})
        for tool in scenario.get("expect_tools", []):
            if tool not in tools:
                failures.append({"category": scenario["category"], "missing_tool": tool, "question": scenario["question"]})
        for tool in scenario.get("forbid_tools", []):
            if tool in tools:
                unapproved += 1
                failures.append({"category": scenario["category"], "forbidden_tool": tool})
    return {
        "checked": sum(1 for item in scenarios if item["category"] not in {"text", "image"} or item.get("expect_status") in {"needs_clarification", "abstained", "access_denied"}),
        "failures": len(failures),
        "leaks": leaks,
        "unapproved_creates": unapproved,
        "examples": failures[:12],
    }


def main() -> None:
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    retrieval_pool = [item for item in scenarios if item["relevant_documents"]]
    report = {
        "scenarios": len(scenarios),
        "retrieval": {mode: retrieval_metrics(mode, retrieval_pool) for mode in ("none", "original", "adapted")},
        "workflow": workflow_checks(scenarios),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
