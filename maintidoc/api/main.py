"""API FastAPI : authentification, quota et délégation au workflow."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from maintidoc.config import get_settings
from maintidoc.corpus_data import authenticate, user_by_id
from maintidoc.mcp.tokens import read_session, session_token
from maintidoc.retrieval.search import read_document, read_figure
from maintidoc.workflow.graph import get_app, run_question, submit_decision

app = FastAPI(title="MaintiDoc", version="0.1.0")

_quota_day = ""
_quota_use: dict[str, int] = {}


class LoginBody(BaseModel):
    user_id: str
    password: str


class DecisionBody(BaseModel):
    approved: bool
    title: str | None = None
    description: str | None = None


def reset_quotas() -> None:
    global _quota_day
    _quota_day = ""
    _quota_use.clear()


def charge_quota(user_id: str) -> None:
    global _quota_day
    today = date.today().isoformat()
    if _quota_day != today:
        _quota_use.clear()
        _quota_day = today
    limit = get_settings().user_daily_quota
    used = _quota_use.get(user_id, 0)
    if used >= limit:
        raise HTTPException(status_code=429, detail="budget_exceeded")
    _quota_use[user_id] = used + 1


def current_user(authorization: str = Header()) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="access_denied")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = read_session(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="access_denied") from exc
    user = user_by_id(payload["user_id"])
    if user is None or sorted(user["groups"]) != list(payload["groups"]):
        raise HTTPException(status_code=401, detail="access_denied")
    return user


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/login")
def login(body: LoginBody) -> dict:
    user = authenticate(body.user_id, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="access_denied")
    return {
        "token": session_token(user["user_id"], user["groups"]),
        "user_id": user["user_id"],
        "display_name": user["display_name"],
        "groups": user["groups"],
    }


@app.post("/ask")
async def ask(
    question: str = Form(),
    equipment_id: str | None = Form(None),
    image: UploadFile | None = File(None),
    user: dict = Depends(current_user),
) -> dict:
    charge_quota(user["user_id"])
    image_path = None
    if image is not None and image.filename:
        payload = await image.read()
        if len(payload) > get_settings().max_image_bytes:
            raise HTTPException(status_code=413, detail="budget_exceeded")
        folder = get_settings().root / "data" / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{uuid.uuid4().hex}.bin"
        target.write_bytes(payload)
        image_path = str(target)
    chosen = equipment_id or None
    if chosen == "":
        chosen = None
    envelope = run_question(question, user, equipment_id=chosen, image_path=image_path)
    return envelope.model_dump()


@app.post("/runs/{run_id}/decision")
def decide(run_id: str, body: DecisionBody, user: dict = Depends(current_user)) -> dict:
    snapshot = get_app().get_state({"configurable": {"thread_id": run_id}})
    values = snapshot.values or {}
    if "user_id" not in values:
        raise HTTPException(status_code=404, detail="missing")
    if values.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="access_denied")
    envelope = submit_decision(run_id, body.approved, title=body.title, description=body.description)
    return envelope.model_dump()


@app.get("/documents/{document_id}")
def download_document(document_id: str, user: dict = Depends(current_user)) -> Response:
    try:
        blob = read_document(document_id, user["groups"], user["user_id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="access_denied") from exc
    return Response(content=blob, media_type="application/pdf")


@app.get("/figures/{document_id}/{element_id}")
def download_figure(document_id: str, element_id: str, user: dict = Depends(current_user)) -> Response:
    try:
        blob = read_figure(document_id, element_id, user["groups"], user["user_id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="access_denied") from exc
    return Response(content=blob, media_type="image/png")
