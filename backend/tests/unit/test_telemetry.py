"""Telemetry must carry trace ids and must never carry personal data (spec F7.1)."""
import io
import json
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.telemetry import JsonFormatter, RedactionFilter, redact_text


def make_logger(stream):
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    logger = logging.getLogger("test.telemetry")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger


def test_log_line_is_json_with_trace_and_span_ids():
    stream = io.StringIO()
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("op") as span:
        make_logger(stream).info("hello", extra={"journey": "shopping_list"})
        expected = format(span.get_span_context().trace_id, "032x")
    line = json.loads(stream.getvalue())
    assert line["trace_id"] == expected
    assert len(line["span_id"]) == 16
    assert line["journey"] == "shopping_list"
    assert line["message"] == "hello"


def test_sensitive_fields_and_emails_never_appear():
    stream = io.StringIO()
    make_logger(stream).info(
        "signup for jane.doe@example.com",
        extra={"password": "hunter2hunter2", "email": "jane.doe@example.com", "weight_kg": 91.5, "age": 41,
               "cookie": "pantry_session=abc", "authorization": "Bearer abc", "household_id": 7},
    )
    raw = stream.getvalue()
    for secret in ("hunter2hunter2", "jane.doe@example.com", "91.5", "pantry_session=abc", "Bearer abc"):
        assert secret not in raw
    line = json.loads(raw)
    assert line["household_id"] == 7  # opaque ids are allowed
    assert line["password"] == "[redacted]"
    assert "[email]" in line["message"]


def test_exception_text_is_redacted():
    stream = io.StringIO()
    logger = make_logger(stream)
    try:
        raise ValueError("bad value for sam@example.org")
    except ValueError:
        logger.exception("failed")
    assert "sam@example.org" not in stream.getvalue()


def test_redact_text():
    assert redact_text("a@b.co and c.d+e@f.org") == "[email] and [email]"


def test_no_trace_ids_outside_a_span():
    stream = io.StringIO()
    make_logger(stream).info("plain")
    line = json.loads(stream.getvalue())
    assert line["trace_id"] is None
