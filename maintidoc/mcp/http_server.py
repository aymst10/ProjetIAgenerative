"""Serveur HTTP des outils de maintenance, et serveur MCP si le paquet est présent."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from maintidoc.mcp import service

app = FastAPI(title="MaintiDoc maintenance", version="0.1.0")


def _token(authorization: str = Header()) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="access_denied")
    return authorization.removeprefix("Bearer ").strip()


class EquipmentBody(BaseModel):
    equipment_id: str


class TicketBody(BaseModel):
    equipment_id: str
    title: str
    description: str
    approval_token: str


def _denied(exc: PermissionError) -> HTTPException:
    return HTTPException(status_code=403, detail="access_denied")


@app.post("/tools/get_equipment_history")
def history(body: EquipmentBody, token: str = Depends(_token)) -> dict:
    try:
        return service.get_equipment_history(body.equipment_id, token)
    except PermissionError as exc:
        raise _denied(exc) from exc


@app.post("/tools/get_open_tickets")
def tickets(body: EquipmentBody, token: str = Depends(_token)) -> dict:
    try:
        return service.get_open_tickets(body.equipment_id, token)
    except PermissionError as exc:
        raise _denied(exc) from exc


@app.post("/tools/create_ticket")
def create(body: TicketBody, token: str = Depends(_token)) -> dict:
    try:
        return service.create_ticket(
            body.equipment_id,
            body.title,
            body.description,
            body.approval_token,
            token,
        )
    except PermissionError as exc:
        raise _denied(exc) from exc


def build_mcp():
    """Serveur MCP officiel. Les outils relaient le service déjà contrôlé."""
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        return None
    mcp = FastMCP("maintidoc-maintenance")

    @mcp.tool()
    def get_equipment_history(equipment_id: str, session_token: str) -> str:
        import json

        return json.dumps(service.get_equipment_history(equipment_id, session_token), ensure_ascii=False)

    @mcp.tool()
    def get_open_tickets(equipment_id: str, session_token: str) -> str:
        import json

        return json.dumps(service.get_open_tickets(equipment_id, session_token), ensure_ascii=False)

    @mcp.tool()
    def create_ticket(equipment_id: str, title: str, description: str, approval_token: str, session_token: str) -> str:
        import json

        payload = service.create_ticket(equipment_id, title, description, approval_token, session_token)
        return json.dumps(payload, ensure_ascii=False)

    return mcp
