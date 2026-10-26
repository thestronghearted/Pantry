"""Database-backed feature flags, cached briefly so every instance converges within seconds."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .models import FeatureFlag

KNOWN_FLAGS = {
    "shopping_list_v2": "Use the 'faster' shopping-list aggregation (ships with a regression on cup units; incident drill).",
}
CACHE_SECONDS = 5.0


class Flags:
    def __init__(self, factory: sessionmaker[Session], ttl: float = CACHE_SECONDS):
        self._factory = factory
        self._ttl = ttl
        self._cache: dict[str, bool] = {}
        self._loaded_at = 0.0

    def ensure_defaults(self) -> None:
        with self._factory() as s:
            existing = {f.name for f in s.scalars(select(FeatureFlag))}
            for name, desc in KNOWN_FLAGS.items():
                if name not in existing:
                    s.add(FeatureFlag(name=name, enabled=False, description=desc))
            s.commit()

    def _refresh(self) -> None:
        with self._factory() as s:
            self._cache = {f.name: f.enabled for f in s.scalars(select(FeatureFlag))}
        self._loaded_at = time.monotonic()

    def enabled(self, name: str) -> bool:
        if time.monotonic() - self._loaded_at > self._ttl:
            self._refresh()
        return self._cache.get(name, False)

    def all(self) -> list[dict]:
        with self._factory() as s:
            return [
                {"name": f.name, "enabled": f.enabled, "description": f.description}
                for f in s.scalars(select(FeatureFlag).order_by(FeatureFlag.name))
            ]

    def set(self, name: str, enabled: bool) -> bool:
        if name not in KNOWN_FLAGS:
            return False
        with self._factory() as s:
            flag = s.get(FeatureFlag, name)
            if flag is None:
                flag = FeatureFlag(name=name, description=KNOWN_FLAGS[name])
                s.add(flag)
            flag.enabled = enabled
            flag.updated_at = datetime.now(timezone.utc)
            s.commit()
        self._refresh()
        return True
