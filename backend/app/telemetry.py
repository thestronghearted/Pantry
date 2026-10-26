"""Tracing, structured JSON logging with trace correlation, and PII redaction."""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Keys that must never reach telemetry, whatever the caller passes in `extra`.
SENSITIVE_KEYS = {
    "password", "email", "cookie", "set-cookie", "authorization", "token", "secret",
    "weight", "weight_kg", "age", "height", "height_cm", "body", "session",
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "taskName"}


def redact_text(text: str) -> str:
    return EMAIL_RE.sub("[email]", text)


class RedactionFilter(logging.Filter):
    """Drops sensitive extras and masks e-mail addresses in messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if key.lower() in SENSITIVE_KEYS:
                record.__dict__[key] = "[redacted]"
        record.msg = redact_text(str(record.getMessage()))
        record.args = ()
        return True


def current_trace_ids() -> tuple[str | None, str | None]:
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None, None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = current_trace_ids()
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id,
            "span_id": span_id,
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").disabled = True  # replaced by our own request log with trace ids


def setup_tracing(service_name: str, otlp_endpoint: str | None, environment: str) -> TracerProvider:
    """Always installs a provider (so trace ids exist for logs/headers); exports only if an endpoint is set."""
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name, "deployment.environment": environment})
    )
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint.rstrip("/") + "/v1/traces")))
        _setup_otlp_logs(service_name, otlp_endpoint, environment)
    trace.set_tracer_provider(provider)
    return provider


def _setup_otlp_logs(service_name: str, endpoint: str, environment: str) -> None:
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    provider = LoggerProvider(resource=Resource.create({"service.name": service_name, "deployment.environment": environment}))
    provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint.rstrip("/") + "/v1/logs")))
    set_logger_provider(provider)
    handler = LoggingHandler(level=logging.INFO, logger_provider=provider)
    handler.addFilter(RedactionFilter())
    logging.getLogger().addHandler(handler)
