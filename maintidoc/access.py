"""Contrôle d'accès par groupe, avant recherche et à l'ouverture d'un fichier."""

from __future__ import annotations

from maintidoc.logging_utils import log_event

CORPUS_GROUPS = frozenset({"pompes", "compresseurs", "responsables"})


def intersects(allowed_groups: list[str] | tuple[str, ...], user_groups: list[str] | tuple[str, ...]) -> bool:
    return bool(set(allowed_groups) & set(user_groups))


def has_corpus_access(user_groups: list[str] | tuple[str, ...]) -> bool:
    return bool(set(user_groups) & CORPUS_GROUPS)


def equipment_allowed(equipment: dict | None, user_groups: list[str] | tuple[str, ...]) -> bool:
    if equipment is None:
        return True
    return intersects(equipment.get("allowed_groups", []), user_groups)


def deny(document_id: str, user_id: str = "") -> None:
    log_event("access_denied", document_id=document_id, user_id=user_id, reason="group")
