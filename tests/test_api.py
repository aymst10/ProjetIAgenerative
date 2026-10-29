"""Authentification, quota et téléchargement."""

import os

from fastapi.testclient import TestClient

from maintidoc.api.main import app, reset_quotas
from maintidoc.config import reset_settings


def test_login_ask_and_document_acl():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.post("/auth/login", json={"user_id": "alice", "password": "mauvais"}).status_code == 401
    login = client.post("/auth/login", json={"user_id": "alice", "password": "alice-demo"})
    assert login.status_code == 200
    assert "password" not in login.json()
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    asked = client.post(
        "/ask",
        data={"question": "Que signifie le voyant orange du panneau POMPE-A ?", "equipment_id": "POMPE-A"},
        headers=headers,
    )
    assert asked.status_code == 200
    assert asked.json()["output"]["status"] == "answered"
    assert any(item["element_id"] == "para_18_1" for item in asked.json()["output"]["citations"])
    assert client.get("/documents/manuel_pompe_a", headers=headers).status_code == 200
    assert client.get("/documents/manuel_comp_a", headers=headers).status_code == 403
    assert client.post("/runs/absent/decision", json={"approved": True}, headers=headers).status_code == 404


def test_daily_quota():
    os.environ["USER_DAILY_QUOTA"] = "1"
    reset_settings()
    reset_quotas()
    client = TestClient(app)
    token = client.post("/auth/login", json={"user_id": "alice", "password": "alice-demo"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/ask", data={"question": "joint POMPE-A", "equipment_id": "POMPE-A"}, headers=headers)
    second = client.post("/ask", data={"question": "joint POMPE-A", "equipment_id": "POMPE-A"}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 429
    os.environ.pop("USER_DAILY_QUOTA", None)
    reset_settings()
    reset_quotas()
