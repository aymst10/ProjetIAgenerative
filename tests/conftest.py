"""Réinitialise l'état partagé entre les tests."""

import os

import pytest

os.environ.setdefault("RERANKER_MODE", "original")
os.environ.setdefault("USER_DAILY_QUOTA", "30")
os.environ.setdefault("MAX_MCP_CALLS", "3")


@pytest.fixture(autouse=True)
def _isolated_state():
    from maintidoc.api.main import reset_quotas
    from maintidoc.config import reset_settings
    from maintidoc.mcp.store import reset_store
    from maintidoc.workflow.graph import reset_app

    reset_settings()
    reset_store()
    reset_app()
    reset_quotas()
    yield
    reset_settings()
    reset_store()
    reset_app()
    reset_quotas()
