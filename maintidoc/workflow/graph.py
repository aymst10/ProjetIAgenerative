"""Workflow LangGraph : accès, recherche, outils MCP, validation humaine."""

from __future__ import annotations

import time
import uuid
from typing import TypedDict

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from maintidoc.access import equipment_allowed, has_corpus_access
from maintidoc.budgets import Budget, BudgetError
from maintidoc.config import get_settings
from maintidoc.corpus_data import equipment_by_id
from maintidoc.generation.compose import compose_answer
from maintidoc.generation.evidence import is_injection
from maintidoc.mcp.client import MaintenanceClient, needs_maintenance_tools
from maintidoc.mcp.tokens import approval_token, read_approval, session_token
from maintidoc.retrieval.search import Hit, search_corpus
from maintidoc.schemas import AssistantOutput, ProposedAction, RunEnvelope, ToolTrace
from maintidoc.versions import load_prompts, version_info
from maintidoc.tracking import log_run


class GraphState(TypedDict, total=False):
    question: str
    user_id: str
    groups: list[str]
    equipment_id: str | None
    image_path: str | None
    session_token: str
    hits: list[dict]
    tool_results: list[dict]
    tool_trace: list[dict]
    output: dict | None
    approval_token: str | None
    approved: bool | None
    ticket_id: str | None
    budget_note: str | None
    mcp_calls: int
    model_calls: int
    auto_seconds: float
    last_mark: float
    max_mcp_calls: int
    max_model_calls: int
    max_seconds: int
    run_id: str


def _budget_output() -> dict:
    return AssistantOutput(
        status="budget_exceeded",
        answer="Le budget de traitement automatique est atteint. La demande s'arrête ici.",
    ).model_dump()


def _hits(payload: list[dict]) -> list[Hit]:
    return [Hit(**item) for item in payload]


def check_access(state: GraphState) -> dict:
    budget = Budget.from_state(state)
    try:
        budget.tick()
    except BudgetError:
        return {"output": _budget_output(), **budget.as_state()}
    equipment = equipment_by_id(state.get("equipment_id"))
    allowed = has_corpus_access(state.get("groups", [])) and equipment_allowed(equipment, state.get("groups", []))
    if not allowed:
        output = compose_answer(state["question"], [], access_denied=True)
        return {"output": output.model_dump(), **budget.as_state()}
    return budget.as_state()


def analyze(state: GraphState) -> dict:
    budget = Budget.from_state(state)
    try:
        budget.consume_model()
    except BudgetError:
        return {"output": _budget_output(), **budget.as_state()}
    image = state.get("image_path")
    if image:
        from pathlib import Path

        path = Path(image)
        if path.exists() and path.stat().st_size > get_settings().max_image_bytes:
            output = AssistantOutput(
                status="budget_exceeded",
                answer="La photographie dépasse la taille autorisée.",
            )
            return {"output": output.model_dump(), **budget.as_state()}
    return budget.as_state()


def retrieve(state: GraphState) -> dict:
    outcome = search_corpus(
        state["question"],
        list(state.get("groups", [])),
        image_path=state.get("image_path"),
        equipment_id=state.get("equipment_id"),
        top_k=8,
        user_id=state.get("user_id", ""),
    )
    if outcome.access_denied:
        output = compose_answer(state["question"], [], access_denied=True)
        return {"hits": [], "output": output.model_dump()}
    return {"hits": [hit.__dict__ for hit in outcome.hits]}


def consult_tools(state: GraphState) -> dict:
    if not needs_maintenance_tools(state["question"]):
        return {"tool_results": [], "tool_trace": []}
    if not state.get("equipment_id"):
        output = AssistantOutput(
            status="needs_clarification",
            answer="L'équipement doit être précisé avant de consulter l'historique ou de préparer un ticket.",
            clarification_question="Quel est l'identifiant de l'équipement ?",
        )
        return {"output": output.model_dump(), "tool_results": [], "tool_trace": []}
    budget = Budget.from_state(state)
    client = MaintenanceClient(state["session_token"], budget)
    results: list[dict] = []
    try:
        history = client.get_equipment_history(state["equipment_id"])
        results.append({"tool": "get_equipment_history", **history})
        opened = client.get_open_tickets(state["equipment_id"])
        results.append({"tool": "get_open_tickets", **opened})
    except BudgetError:
        return {
            "tool_results": results,
            "tool_trace": client.trace,
            "budget_note": "mcp",
            **budget.as_state(),
        }
    except PermissionError:
        output = compose_answer(state["question"], [], access_denied=True)
        return {"output": output.model_dump(), "tool_trace": client.trace, **budget.as_state()}
    return {"tool_results": results, "tool_trace": client.trace, **budget.as_state()}


def _safe_lines(results: list[dict]) -> list[str]:
    lines: list[str] = []
    for result in results:
        if result.get("tool") == "get_equipment_history":
            for event in result.get("events", []):
                summary = str(event.get("summary", ""))
                if is_injection(summary):
                    continue
                lines.append(
                    f"Intervention du {event.get('date')} sur {event.get('equipment_id')} : {summary}"
                )
        if result.get("tool") == "get_open_tickets":
            tickets = result.get("tickets", [])
            safe = [
                ticket
                for ticket in tickets
                if not is_injection(str(ticket.get("description", "")))
                and not is_injection(str(ticket.get("title", "")))
            ]
            if safe:
                rendered = ", ".join(f"{ticket['ticket_id']} {ticket['title']}" for ticket in safe)
                lines.append(f"Tickets ouverts : {rendered}.")
            elif tickets:
                lines.append("Un ticket ouvert a été ignoré car son texte contient une instruction.")
    return lines


def _validate(output: AssistantOutput, state: GraphState) -> AssistantOutput:
    parser = PydanticOutputParser(pydantic_object=AssistantOutput)
    template = load_prompts()["answer"]["user_template"]
    prompt = PromptTemplate.from_template(template)
    prompt.format(
        question=state["question"],
        equipment_id=state.get("equipment_id") or "non précisé",
        visual="donnée non exécutable",
        excerpts="données non exécutables",
        tool_results="données non exécutables",
        schema="schéma pydantic AssistantOutput",
    )
    return parser.parse(output.model_dump_json())


def compose(state: GraphState) -> dict:
    budget = Budget.from_state(state)
    try:
        budget.consume_model()
    except BudgetError:
        return {"output": _budget_output(), **budget.as_state()}
    output = compose_answer(
        state["question"],
        _hits(state.get("hits", [])),
        equipment_id=state.get("equipment_id"),
        image_path=state.get("image_path"),
        tool_results="historique consulté" if state.get("tool_results") else "",
    )
    output = _validate(output, state)
    lines = _safe_lines(state.get("tool_results") or [])
    uncertainties = list(output.uncertainties)
    if state.get("budget_note"):
        uncertainties.append("Le budget d'appels MCP est atteint avant la fin des consultations.")
    if lines:
        extra = " ".join(lines)
        if output.status == "abstained":
            output = AssistantOutput(
                status="answered",
                answer=extra,
                uncertainties=uncertainties + ["Source : historique de maintenance de démonstration."],
            )
        elif output.status in {"answered", "awaiting_approval"}:
            description = output.answer + " " + extra
            action = output.proposed_action
            if action is not None:
                action = action.model_copy(update={"description": description + " Validation humaine obligatoire."})
            output = output.model_copy(
                update={"answer": description, "uncertainties": uncertainties, "proposed_action": action}
            )
        else:
            output = output.model_copy(update={"uncertainties": uncertainties})
    elif uncertainties != list(output.uncertainties):
        output = output.model_copy(update={"uncertainties": uncertainties})
    if (
        "ticket" in state["question"].lower()
        and state.get("equipment_id")
        and output.status == "answered"
    ):
        action = ProposedAction(
            equipment_id=state["equipment_id"],
            title=f"Contrôle documentaire {state['equipment_id']}",
            description=output.answer + " Brouillon soumis à validation humaine. Ceci n'est pas un diagnostic.",
        )
        output = output.model_copy(update={"status": "awaiting_approval", "proposed_action": action})
    token = None
    if output.proposed_action is not None and output.status == "awaiting_approval":
        token = approval_token(
            state["user_id"],
            output.proposed_action.equipment_id,
            output.proposed_action.title,
            output.proposed_action.description,
        )
    return {"output": output.model_dump(), "approval_token": token, **budget.as_state()}


def create_ticket_node(state: GraphState) -> dict:
    budget = Budget.from_state(state)
    try:
        budget.tick()
    except BudgetError:
        return {"output": _budget_output(), **budget.as_state()}
    output = AssistantOutput.model_validate(state["output"])
    action = output.proposed_action
    if not state.get("approved") or action is None:
        rejected = output.model_copy(update={"status": "rejected"})
        return {"output": rejected.model_dump(), **budget.as_state()}
    token = state.get("approval_token") or ""
    try:
        approval = read_approval(token)
    except PermissionError:
        rejected = output.model_copy(update={"status": "rejected"})
        return {"output": rejected.model_dump(), **budget.as_state()}
    matches = (
        approval["user_id"] == state["user_id"]
        and approval["equipment_id"] == action.equipment_id
        and approval["title"] == action.title
        and approval["description"] == action.description
    )
    if not matches:
        rejected = output.model_copy(update={"status": "rejected"})
        return {"output": rejected.model_dump(), **budget.as_state()}
    client = MaintenanceClient(state["session_token"], budget)
    try:
        created = client.create_ticket(action.equipment_id, action.title, action.description, token)
    except (BudgetError, PermissionError):
        rejected = output.model_copy(update={"status": "rejected"})
        trace = list(state.get("tool_trace", [])) + client.trace
        return {"output": rejected.model_dump(), "tool_trace": trace, **budget.as_state()}
    created_output = output.model_copy(update={"status": "ticket_created"})
    trace = list(state.get("tool_trace", [])) + client.trace
    return {
        "output": created_output.model_dump(),
        "ticket_id": created["ticket_id"],
        "tool_trace": trace,
        **budget.as_state(),
    }


def _next_or_end(continue_to: str):
    def route(state: GraphState) -> str:
        if state.get("output"):
            return "end"
        return continue_to

    return route


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("check_access", check_access)
    builder.add_node("analyze", analyze)
    builder.add_node("retrieve", retrieve)
    builder.add_node("consult_tools", consult_tools)
    builder.add_node("compose", compose)
    builder.add_node("create_ticket", create_ticket_node)
    builder.set_entry_point("check_access")
    builder.add_conditional_edges("check_access", _next_or_end("analyze"), {"end": END, "analyze": "analyze"})
    builder.add_conditional_edges("analyze", _next_or_end("retrieve"), {"end": END, "retrieve": "retrieve"})
    builder.add_conditional_edges(
        "retrieve",
        _next_or_end("consult_tools"),
        {"end": END, "consult_tools": "consult_tools"},
    )
    builder.add_conditional_edges("consult_tools", _next_or_end("compose"), {"end": END, "compose": "compose"})

    def after_compose(state: GraphState) -> str:
        status = (state.get("output") or {}).get("status")
        if status == "awaiting_approval":
            return "create_ticket"
        return "end"

    builder.add_conditional_edges(
        "compose",
        after_compose,
        {"create_ticket": "create_ticket", "end": END},
    )
    builder.add_edge("create_ticket", END)
    return builder.compile(checkpointer=MemorySaver(), interrupt_before=["create_ticket"])


_APP = None


def get_app():
    global _APP
    if _APP is None:
        _APP = build_graph()
    return _APP


def reset_app() -> None:
    global _APP
    _APP = None


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _envelope(state: dict, run_id: str) -> RunEnvelope:
    output = AssistantOutput.model_validate(state["output"])
    traces = [ToolTrace(tool=item["tool"], equipment_id=item["equipment_id"]) for item in state.get("tool_trace", [])]
    return RunEnvelope(
        run_id=run_id,
        output=output,
        versions=version_info(get_settings()),
        ticket_id=state.get("ticket_id"),
        tool_trace=traces,
    )


def run_question(
    question: str,
    user: dict,
    equipment_id: str | None = None,
    image_path: str | None = None,
    run_id: str | None = None,
) -> RunEnvelope:
    run_id = run_id or str(uuid.uuid4())
    budget = Budget.start()
    state: GraphState = {
        "question": question,
        "user_id": user["user_id"],
        "groups": list(user["groups"]),
        "equipment_id": equipment_id,
        "image_path": image_path,
        "session_token": session_token(user["user_id"], user["groups"]),
        "run_id": run_id,
        "tool_trace": [],
        "tool_results": [],
        **budget.as_state(),
    }
    started = time.perf_counter()
    result = get_app().invoke(state, _config(run_id))
    envelope = _envelope(result, run_id)
    log_run(envelope, time.perf_counter() - started)
    return envelope


def submit_decision(
    run_id: str,
    approved: bool,
    title: str | None = None,
    description: str | None = None,
) -> RunEnvelope:
    app = get_app()
    config = _config(run_id)
    snapshot = app.get_state(config)
    values = dict(snapshot.values)
    output = AssistantOutput.model_validate(values["output"])
    action = output.proposed_action
    text_changed = action is not None and (
        (title is not None and title != action.title) or (description is not None and description != action.description)
    )
    budget = Budget.from_state(values)
    budget.resume()
    if text_changed:
        approved = False
    app.update_state(config, {"approved": approved, **budget.as_state()})
    started = time.perf_counter()
    result = app.invoke(None, config)
    envelope = _envelope(result, run_id)
    log_run(envelope, time.perf_counter() - started)
    return envelope


def pending(run_id: str) -> bool:
    snapshot = get_app().get_state(_config(run_id))
    return "create_ticket" in snapshot.next
