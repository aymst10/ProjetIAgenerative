"""Schéma de sortie validé par Pydantic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    page: int
    element_id: str


class ProposedAction(BaseModel):
    type: Literal["create_ticket"] = "create_ticket"
    equipment_id: str
    title: str
    description: str


OutputStatus = Literal[
    "answered",
    "needs_clarification",
    "abstained",
    "access_denied",
    "awaiting_approval",
    "ticket_created",
    "rejected",
    "budget_exceeded",
]


class AssistantOutput(BaseModel):
    status: OutputStatus
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    proposed_action: ProposedAction | None = None


class VersionInfo(BaseModel):
    model: str
    prompts: dict[str, str]
    reranker: str
    index: str


class ToolTrace(BaseModel):
    tool: str
    equipment_id: str


class RunEnvelope(BaseModel):
    run_id: str
    output: AssistantOutput
    versions: VersionInfo
    ticket_id: str | None = None
    tool_trace: list[ToolTrace] = Field(default_factory=list)
