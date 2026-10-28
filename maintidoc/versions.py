"""Versions de prompts, de modèle et d'index attachées à chaque exécution."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from maintidoc.config import ROOT, Settings
from maintidoc.schemas import VersionInfo


PROMPT_FILES = {
    "answer": "answer_v1.yaml",
    "visual_analysis": "visual_analysis_v1.yaml",
    "evidence_check": "evidence_check_v1.yaml",
    "ticket_draft": "ticket_draft_v1.yaml",
}


@lru_cache(maxsize=1)
def load_prompts() -> dict[str, dict]:
    prompts: dict[str, dict] = {}
    base = ROOT / "prompts"
    for role, name in PROMPT_FILES.items():
        path = base / name
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        data["_path"] = str(Path("prompts") / name)
        prompts[role] = data
    return prompts


def version_info(settings: Settings) -> VersionInfo:
    prompts = load_prompts()
    if settings.use_vlm:
        model = settings.vlm_model
    else:
        model = "deterministic-evidence-v1"
    return VersionInfo(
        model=model,
        prompts={role: str(item.get("version", role)) for role, item in prompts.items()},
        reranker=settings.reranker_mode,
        index=settings.index_version,
    )
