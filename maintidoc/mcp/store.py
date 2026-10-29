"""Historique et tickets fictifs. La clé d'idempotence est le jeton d'approbation."""

from __future__ import annotations

import json
from threading import Lock

from maintidoc.config import ROOT

SEED = ROOT / "corpus" / "maintenance_seed.json"


class MaintenanceStore:
    def __init__(self, history: list[dict], open_tickets: list[dict]) -> None:
        self.history = history
        self.open_tickets = open_tickets
        self.created: dict[str, dict] = {}
        self._counter = 200
        self._lock = Lock()

    @classmethod
    def from_seed(cls) -> "MaintenanceStore":
        payload = json.loads(SEED.read_text(encoding="utf-8"))
        return cls(list(payload["history"]), list(payload["open_tickets"]))

    def history_for(self, equipment_id: str) -> list[dict]:
        return [item for item in self.history if item["equipment_id"] == equipment_id]

    def tickets_for(self, equipment_id: str) -> list[dict]:
        opened = [item for item in self.open_tickets if item["equipment_id"] == equipment_id]
        created = [
            item for item in self.created.values() if item["equipment_id"] == equipment_id and item["status"] == "open"
        ]
        return opened + created

    def create(self, equipment_id: str, title: str, description: str, approval_token: str, user_id: str) -> dict:
        with self._lock:
            existing = self.created.get(approval_token)
            if existing is not None:
                return {**existing, "idempotent": True}
            self._counter += 1
            ticket = {
                "ticket_id": f"T-{self._counter}",
                "equipment_id": equipment_id,
                "title": title,
                "description": description,
                "status": "open",
                "user_id": user_id,
                "approval_token": approval_token,
                "idempotent": False,
            }
            self.created[approval_token] = ticket
            return dict(ticket)


_STORE: MaintenanceStore | None = None


def get_store() -> MaintenanceStore:
    global _STORE
    if _STORE is None:
        _STORE = MaintenanceStore.from_seed()
    return _STORE


def reset_store() -> MaintenanceStore:
    global _STORE
    _STORE = MaintenanceStore.from_seed()
    return _STORE
