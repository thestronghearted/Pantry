"""Integration fixtures. Needs TEST_DATABASE_URL (a Postgres URL in CI and in `dev.py test`).

For quick local iteration without Docker you may point it at SQLite, e.g.
    TEST_DATABASE_URL=sqlite+pysqlite:///:memory:
but the Postgres run is the one that counts.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings
from app.db import Base, make_engine
from app.main import create_app

ADMIN_TOKEN = "test-admin-token"
PROBE_EMAIL = "probe@example.com"
PROBE_PASSWORD = "probe-password-for-tests"
MONDAY = "2026-11-02"


def _database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL is not set. Run `py scripts/dev.py test` (starts Postgres in Docker) "
            "or export TEST_DATABASE_URL.",
            returncode=2,
        )
    return url


def _reset(url: str) -> None:
    if url.startswith("sqlite"):
        return  # in-memory databases are fresh per engine
    engine = make_engine(url)
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()


def make_settings(**overrides) -> Settings:
    base = dict(
        database_url=_database_url(),
        session_secret="test-secret",
        admin_token=ADMIN_TOKEN,
        probe_email=PROBE_EMAIL,
        probe_password=PROBE_PASSWORD,
        rate_limit_per_minute=10,
        environment="test",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def app():
    settings = make_settings()
    _reset(settings.database_url)
    app = create_app(settings)
    yield app
    app.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_client(app):
    """Extra independent clients (separate cookie jars) against the same app, e.g. a second household."""
    clients = []

    def _make():
        c = TestClient(app)
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.close()


def signup(c: TestClient, email="family@example.com", name="The Smiths", password="correct-horse-battery"):
    r = c.post("/api/auth/signup", json={"household_name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


ADULT = dict(name="Alex", sex="male", age=40, height_cm=180, weight_kg=95, activity="light", goal="lose", kg_per_week=0.5)
PARTNER = dict(name="Sam", sex="female", age=38, height_cm=168, weight_kg=72, activity="light", goal="lose", kg_per_week=0.4)
CHILD = dict(name="Kit", sex="male", age=10, height_cm=140, weight_kg=34, activity="active", goal="custom", custom_kcal=1900)


def add_member(c: TestClient, **member):
    r = c.post("/api/members", json=member)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def family(client):
    """A signed-in household with two adults and a child."""
    signup(client)
    return client, [add_member(client, **m) for m in (ADULT, PARTNER, CHILD)]


def generate(c: TestClient, **overrides):
    body = {"week_start": MONDAY, "max_difficulty": "easy", "max_minutes_per_day": 120, "seed": 1}
    body.update(overrides)
    r = c.post("/api/plan/generate", json=body)
    assert r.status_code == 200, r.text
    return r.json()
