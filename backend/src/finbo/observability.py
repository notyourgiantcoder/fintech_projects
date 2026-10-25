"""Tracing to Langfuse (free cloud tier) over OpenTelemetry.

Microsoft Agent Framework emits OpenTelemetry spans for every agent run, model call and
tool call. When LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set, those spans are sent
to Langfuse's OTLP endpoint. Prompt and answer text is excluded unless
LANGFUSE_CAPTURE_CONTENT=1, because it contains the user's financial details.
"""

from __future__ import annotations

import base64
import logging
import os

log = logging.getLogger(__name__)
_configured = False


def langfuse_exporter_settings() -> tuple[str, dict[str, str]] | None:
    public = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not (public and secret):
        return None
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
    token = base64.b64encode(f"{public}:{secret}".encode()).decode()
    return f"{host}/api/public/otel/v1/traces", {"Authorization": f"Basic {token}"}


def configure_tracing() -> bool:
    """Idempotent. Returns True when spans will be exported."""
    global _configured
    if _configured:
        return True
    settings = langfuse_exporter_settings()
    if settings is None:
        return False
    try:
        from agent_framework.observability import configure_otel_providers
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError:
        log.warning("Langfuse keys are set but OpenTelemetry packages are missing.")
        return False
    endpoint, headers = settings
    configure_otel_providers(
        service_name="finbo",
        exporters=[OTLPSpanExporter(endpoint=endpoint, headers=headers)],
        enable_sensitive_data=os.getenv("LANGFUSE_CAPTURE_CONTENT") == "1",
    )
    _configured = True
    return True
