"""Lecture du manifeste d'accès et des comptes fictifs."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from maintidoc.config import ROOT


CORPUS = ROOT / "corpus"


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    return json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_users() -> list[dict]:
    payload = json.loads((CORPUS / "users.json").read_text(encoding="utf-8"))
    return list(payload["users"])


def clear_corpus_cache() -> None:
    load_manifest.cache_clear()
    load_users.cache_clear()


def documents() -> list[dict]:
    return list(load_manifest()["documents"])


def equipment_by_id(equipment_id: str | None) -> dict | None:
    if not equipment_id:
        return None
    for item in load_manifest()["equipment"]:
        if item["equipment_id"] == equipment_id:
            return item
    return None


def document_by_id(document_id: str) -> dict | None:
    for item in documents():
        if item["document_id"] == document_id:
            return item
    return None


def user_by_id(user_id: str) -> dict | None:
    for item in load_users():
        if item["user_id"] == user_id:
            return item
    return None


def authenticate(user_id: str, password: str) -> dict | None:
    user = user_by_id(user_id)
    if user is None or user.get("password") != password:
        return None
    return user


def corpus_path(relative: str) -> Path:
    path = (CORPUS / relative).resolve()
    if CORPUS.resolve() not in path.parents and path != CORPUS.resolve():
        raise PermissionError("access_denied")
    return path
