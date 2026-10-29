"""Jetons HMAC. Le secret vient de l'environnement et n'est pas journalisé."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from maintidoc.config import get_settings


def _secret() -> str:
    return get_settings().app_secret


def sign(payload: dict, secret: str | None = None) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    signature = hmac.new((secret or _secret()).encode(), body.encode(), hashlib.sha256).hexdigest()
    blob = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return f"{blob}.{signature}"


def unsign(token: str, secret: str | None = None) -> dict:
    try:
        blob, signature = token.rsplit(".", 1)
    except ValueError as exc:
        raise PermissionError("access_denied") from exc
    padded = blob + "=" * (-len(blob) % 4)
    try:
        body = base64.urlsafe_b64decode(padded.encode()).decode()
    except Exception as exc:
        raise PermissionError("access_denied") from exc
    expected = hmac.new((secret or _secret()).encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise PermissionError("access_denied")
    return json.loads(body)


def session_token(user_id: str, groups: list[str], ttl_seconds: int = 8 * 3600) -> str:
    payload = {
        "kind": "session",
        "user_id": user_id,
        "groups": sorted(groups),
        "exp": int(time.time()) + ttl_seconds,
    }
    return sign(payload)


def read_session(token: str) -> dict:
    payload = unsign(token)
    if payload.get("kind") != "session" or int(payload.get("exp", 0)) < int(time.time()):
        raise PermissionError("access_denied")
    return payload


def approval_token(user_id: str, equipment_id: str, title: str, description: str) -> str:
    payload = {
        "kind": "approval",
        "user_id": user_id,
        "equipment_id": equipment_id,
        "title": title,
        "description": description,
    }
    return sign(payload)


def read_approval(token: str) -> dict:
    payload = unsign(token)
    if payload.get("kind") != "approval":
        raise PermissionError("access_denied")
    return payload
