"""Budgets d'une demande : appels MCP, appels modèle, temps hors attente humaine."""

from __future__ import annotations

import time
from dataclasses import dataclass

from maintidoc.config import Settings, get_settings


class BudgetError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Budget:
    max_mcp_calls: int
    max_model_calls: int
    max_seconds: int
    mcp_calls: int = 0
    model_calls: int = 0
    auto_seconds: float = 0.0
    last_mark: float = 0.0

    @classmethod
    def start(cls, settings: Settings | None = None) -> "Budget":
        settings = settings or get_settings()
        now = time.monotonic()
        return cls(
            max_mcp_calls=settings.max_mcp_calls,
            max_model_calls=settings.max_model_calls,
            max_seconds=settings.max_processing_seconds,
            last_mark=now,
        )

    def tick(self) -> None:
        now = time.monotonic()
        self.auto_seconds += now - self.last_mark
        self.last_mark = now
        if self.auto_seconds > self.max_seconds:
            raise BudgetError("time")

    def consume_mcp(self) -> None:
        self.tick()
        if self.mcp_calls >= self.max_mcp_calls:
            raise BudgetError("mcp")
        self.mcp_calls += 1

    def consume_model(self) -> None:
        self.tick()
        if self.model_calls >= self.max_model_calls:
            raise BudgetError("model")
        self.model_calls += 1

    def pause(self) -> None:
        """Oublie le temps passé à attendre un humain."""
        self.tick()

    def resume(self) -> None:
        self.last_mark = time.monotonic()

    def as_state(self) -> dict[str, float | int]:
        return {
            "mcp_calls": self.mcp_calls,
            "model_calls": self.model_calls,
            "auto_seconds": self.auto_seconds,
            "last_mark": self.last_mark,
            "max_mcp_calls": self.max_mcp_calls,
            "max_model_calls": self.max_model_calls,
            "max_seconds": self.max_seconds,
        }

    @classmethod
    def from_state(cls, state: dict) -> "Budget":
        return cls(
            max_mcp_calls=int(state["max_mcp_calls"]),
            max_model_calls=int(state["max_model_calls"]),
            max_seconds=int(state["max_seconds"]),
            mcp_calls=int(state["mcp_calls"]),
            model_calls=int(state["model_calls"]),
            auto_seconds=float(state["auto_seconds"]),
            last_mark=float(state["last_mark"]),
        )
