"""Journaux techniques. Le contenu brut des documents et des questions n'y entre pas."""

from __future__ import annotations

import json
import sys

SAFE_FIELDS = {
    "document_id",
    "page",
    "element_id",
    "user_id",
    "status",
    "tool",
    "count",
    "backend",
    "reason",
}


def log_event(event: str, **fields: object) -> None:
    payload: dict[str, object] = {"event": event}
    for key, value in fields.items():
        if key in SAFE_FIELDS and isinstance(value, (str, int)):
            payload[key] = value
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
