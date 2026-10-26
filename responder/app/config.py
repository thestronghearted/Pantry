"""Responder configuration, from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or default


@dataclass(frozen=True)
class Settings:
    app_url: str = field(default_factory=lambda: _env("APP_URL", "http://app:8000"))
    prometheus_url: str = field(default_factory=lambda: _env("PROMETHEUS_URL", "http://prometheus:9090"))
    loki_url: str = field(default_factory=lambda: _env("LOKI_URL", "http://loki:3100"))
    admin_token: str | None = field(default_factory=lambda: _env("ADMIN_TOKEN"))
    probe_email: str | None = field(default_factory=lambda: _env("PROBE_EMAIL"))
    probe_password: str | None = field(default_factory=lambda: _env("PROBE_PASSWORD"))
    anthropic_api_key: str | None = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: _env("RESPONDER_MODEL", "claude-sonnet-5-5"))
    max_steps: int = field(default_factory=lambda: int(_env("MAX_STEPS", "12")))
    report_dir: Path = field(default_factory=lambda: Path(_env("REPORT_DIR", "/reports")))
    github_token: str | None = field(default_factory=lambda: _env("GITHUB_TOKEN"))
    github_repository: str | None = field(default_factory=lambda: _env("GITHUB_REPOSITORY"))
    cooldown_seconds: int = field(default_factory=lambda: int(_env("COOLDOWN_SECONDS", "600")))
    probe_week: str = "2020-01-06"  # the synthetic household's fixed week (see backend/app/seeding.py)
    probe_retries: int = field(default_factory=lambda: int(_env("PROBE_RETRIES", "6")))
    probe_wait_seconds: float = field(default_factory=lambda: float(_env("PROBE_WAIT_SECONDS", "2")))
