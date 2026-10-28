"""Crochet vision-langage. Inactif tant que USE_VLM n'est pas activé.

Le chargement utilise local_files_only : les poids ne sont pas téléchargés.
"""

from __future__ import annotations

from maintidoc.config import Settings
from maintidoc.logging_utils import log_event


def vlm_available(settings: Settings) -> bool:
    return bool(settings.use_vlm)


def describe_with_vlm(image_path: str | None, question: str, settings: Settings) -> str | None:
    """Retourne une observation du VLM, ou None si le modèle n'est pas chargé localement."""
    if not settings.use_vlm or not image_path:
        return None
    try:
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
    except Exception:
        log_event("vlm_unavailable", reason="package", backend="transformers")
        return None
    try:
        AutoProcessor.from_pretrained(settings.vlm_model, local_files_only=True)
        Qwen2_5_VLForConditionalGeneration.from_pretrained(settings.vlm_model, local_files_only=True)
    except Exception:
        log_event("vlm_unavailable", reason="weights", backend=settings.vlm_model)
        return None
    log_event("vlm_loaded", backend=settings.vlm_model)
    return None
