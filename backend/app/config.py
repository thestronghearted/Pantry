"""Runtime configuration, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite+pysqlite:///./pantry.db"))
    session_secret: str = field(default_factory=lambda: os.environ.get("SESSION_SECRET", "dev-only-change-me"))
    admin_token: str | None = field(default_factory=lambda: os.environ.get("ADMIN_TOKEN") or None)
    environment: str = field(default_factory=lambda: os.environ.get("ENVIRONMENT", "local"))
    cookie_secure: bool = field(default_factory=lambda: _bool("COOKIE_SECURE", False))
    trust_proxy: bool = field(default_factory=lambda: _bool("TRUST_PROXY", False))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10")))
    probe_email: str | None = field(default_factory=lambda: os.environ.get("PROBE_EMAIL") or None)
    probe_password: str | None = field(default_factory=lambda: os.environ.get("PROBE_PASSWORD") or None)
    otlp_endpoint: str | None = field(default_factory=lambda: os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or None)
    service_name: str = field(default_factory=lambda: os.environ.get("OTEL_SERVICE_NAME", "pantry-api"))
    static_dir: Path = field(default_factory=lambda: Path(os.environ.get("STATIC_DIR", "static")))
    run_migrations: bool = field(default_factory=lambda: _bool("RUN_MIGRATIONS", True))

    @property
    def is_production_like(self) -> bool:
        return self.environment in {"dev", "prod", "production"}


def get_settings() -> Settings:
    return Settings()
