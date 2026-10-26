"""Prometheus metrics for the user journeys, with trace-id exemplars."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager

from fastapi import HTTPException
from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client.openmetrics.exposition import generate_latest as generate_openmetrics

from .telemetry import current_trace_ids

log = logging.getLogger("pantry.journey")

REGISTRY = CollectorRegistry()

JOURNEY_REQUESTS = Counter(
    "journey_requests_total",
    "User-journey requests by outcome (error = server-side failure, client_error = bad request).",
    ["journey", "outcome", "synthetic"],
    registry=REGISTRY,
)
JOURNEY_DURATION = Histogram(
    "journey_duration_seconds",
    "User-journey latency in seconds.",
    ["journey"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    registry=REGISTRY,
)
PLAN_DAYS_OFF_TARGET = Counter(
    "plan_days_off_target_total",
    "Generated plan days where at least one member missed the +/-10% calorie band.",
    registry=REGISTRY,
)


def render_metrics(openmetrics: bool) -> tuple[bytes, str]:
    if openmetrics:
        return generate_openmetrics(REGISTRY), "application/openmetrics-text; version=1.0.0; charset=utf-8"
    from prometheus_client import generate_latest

    return generate_latest(REGISTRY), "text/plain; version=0.0.4; charset=utf-8"


@contextmanager
def journey(name: str, *, synthetic: bool = False, household_id: int | None = None):
    """Record outcome, latency (with exemplar) and one structured log line for a journey request."""
    start = time.perf_counter()
    outcome = "success"
    try:
        yield
    except HTTPException as exc:
        outcome = "error" if exc.status_code >= 500 else "client_error"
        raise
    except Exception:
        outcome = "error"
        raise
    finally:
        elapsed = time.perf_counter() - start
        trace_id, _ = current_trace_ids()
        exemplar = {"trace_id": trace_id} if trace_id else None
        JOURNEY_REQUESTS.labels(name, outcome, str(synthetic).lower()).inc(exemplar=exemplar)
        JOURNEY_DURATION.labels(name).observe(elapsed, exemplar=exemplar)
        log.log(
            logging.ERROR if outcome == "error" else logging.INFO,
            "journey finished",
            extra={
                "journey": name,
                "outcome": outcome,
                "synthetic": synthetic,
                "duration_ms": round(elapsed * 1000, 1),
                "household_id": household_id,
            },
        )
