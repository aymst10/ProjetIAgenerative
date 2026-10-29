"""Outils de maintenance. Les groupes sont relus côté serveur à chaque appel."""

from __future__ import annotations

from maintidoc.access import equipment_allowed
from maintidoc.corpus_data import equipment_by_id, user_by_id
from maintidoc.logging_utils import log_event
from maintidoc.mcp.store import get_store
from maintidoc.mcp.tokens import read_approval, read_session


def _user(session_token: str) -> dict:
    payload = read_session(session_token)
    user = user_by_id(payload["user_id"])
    if user is None or sorted(user["groups"]) != list(payload["groups"]):
        log_event("access_denied", user_id=payload.get("user_id", ""), reason="mcp_session")
        raise PermissionError("access_denied")
    return user


def _guard(equipment_id: str, user: dict) -> None:
    equipment = equipment_by_id(equipment_id)
    if equipment is None or not equipment_allowed(equipment, user["groups"]):
        log_event("access_denied", user_id=user["user_id"], document_id=equipment_id, reason="mcp_tool")
        raise PermissionError("access_denied")


def get_equipment_history(equipment_id: str, session_token: str) -> dict:
    user = _user(session_token)
    _guard(equipment_id, user)
    events = get_store().history_for(equipment_id)
    log_event("mcp_call", tool="get_equipment_history", user_id=user["user_id"], document_id=equipment_id, count=len(events))
    return {"equipment_id": equipment_id, "events": events}


def get_open_tickets(equipment_id: str, session_token: str) -> dict:
    user = _user(session_token)
    _guard(equipment_id, user)
    tickets = [
        {key: value for key, value in ticket.items() if key != "approval_token"}
        for ticket in get_store().tickets_for(equipment_id)
    ]
    log_event("mcp_call", tool="get_open_tickets", user_id=user["user_id"], document_id=equipment_id, count=len(tickets))
    return {"equipment_id": equipment_id, "tickets": tickets}


def create_ticket(
    equipment_id: str,
    title: str,
    description: str,
    approval_token: str,
    session_token: str,
) -> dict:
    user = _user(session_token)
    _guard(equipment_id, user)
    try:
        approval = read_approval(approval_token)
    except PermissionError:
        log_event("access_denied", user_id=user["user_id"], document_id=equipment_id, reason="approval")
        raise
    same = (
        approval["user_id"] == user["user_id"]
        and approval["equipment_id"] == equipment_id
        and approval["title"] == title
        and approval["description"] == description
    )
    if not same:
        log_event("access_denied", user_id=user["user_id"], document_id=equipment_id, reason="approval_mismatch")
        raise PermissionError("access_denied")
    ticket = get_store().create(equipment_id, title, description, approval_token, user["user_id"])
    log_event(
        "mcp_call",
        tool="create_ticket",
        user_id=user["user_id"],
        document_id=equipment_id,
        status="reused" if ticket["idempotent"] else "created",
    )
    return {
        "ticket_id": ticket["ticket_id"],
        "equipment_id": equipment_id,
        "status": ticket["status"],
        "idempotent": ticket["idempotent"],
    }
