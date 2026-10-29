"""Suivi MLflow optionnel. Aucun texte de question, de document ou de ticket n'est envoyé."""

from __future__ import annotations

from maintidoc.config import get_settings
from maintidoc.logging_utils import log_event
from maintidoc.schemas import RunEnvelope


def log_run(envelope: RunEnvelope, elapsed_seconds: float) -> None:
    settings = get_settings()
    if not settings.mlflow_tracking_uri:
        return
    try:
        import mlflow

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        with mlflow.start_run(run_name=envelope.run_id):
            mlflow.log_param("status", envelope.output.status)
            mlflow.log_param("reranker", envelope.versions.reranker)
            mlflow.log_param("index", envelope.versions.index)
            mlflow.log_metric("tool_calls", len(envelope.tool_trace))
            mlflow.log_metric("elapsed_seconds", float(elapsed_seconds))
    except Exception:
        log_event("mlflow_skipped", reason="unavailable", backend="mlflow")
