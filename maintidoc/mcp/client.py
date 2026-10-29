"""Client des outils. Le transport local appelle le même service que le serveur."""

from __future__ import annotations

import os

import httpx

from maintidoc.budgets import Budget, BudgetError
from maintidoc.config import get_settings
from maintidoc.mcp import service


class MaintenanceClient:
    def __init__(self, session_token: str, budget: Budget) -> None:
        self.session_token = session_token
        self.budget = budget
        self.trace: list[dict[str, str]] = []

    def _record(self, tool: str, equipment_id: str) -> None:
        self.budget.consume_mcp()
        self.trace.append({"tool": tool, "equipment_id": equipment_id})

    def _post(self, path: str, payload: dict) -> dict:
        settings = get_settings()
        response = httpx.post(
            settings.mcp_url.rstrip("/") + path,
            json=payload,
            headers={"Authorization": f"Bearer {self.session_token}"},
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()

    def get_equipment_history(self, equipment_id: str) -> dict:
        self._record("get_equipment_history", equipment_id)
        if os.environ.get("MCP_TRANSPORT") == "http":
            return self._post("/tools/get_equipment_history", {"equipment_id": equipment_id})
        return service.get_equipment_history(equipment_id, self.session_token)

    def get_open_tickets(self, equipment_id: str) -> dict:
        self._record("get_open_tickets", equipment_id)
        if os.environ.get("MCP_TRANSPORT") == "http":
            return self._post("/tools/get_open_tickets", {"equipment_id": equipment_id})
        return service.get_open_tickets(equipment_id, self.session_token)

    def create_ticket(self, equipment_id: str, title: str, description: str, approval_token: str) -> dict:
        self._record("create_ticket", equipment_id)
        payload = {
            "equipment_id": equipment_id,
            "title": title,
            "description": description,
            "approval_token": approval_token,
        }
        if os.environ.get("MCP_TRANSPORT") == "http":
            return self._post("/tools/create_ticket", payload)
        return service.create_ticket(equipment_id, title, description, approval_token, self.session_token)


def needs_maintenance_tools(question: str) -> bool:
    lowered = question.lower()
    markers = ("historique", "intervention", "ticket", "derniere", "dernière")
    return any(marker in lowered for marker in markers)
