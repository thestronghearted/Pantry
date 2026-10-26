"""The migration is the source of truth for the deployed schema, so it must match the models."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db import Base


def test_migration_creates_every_model_table(app):
    tables = set(inspect(app.state.engine).get_table_names())
    assert set(Base.metadata.tables) <= tables
    assert "alembic_version" in tables


def test_models_and_migration_have_no_drift(app):
    with app.state.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models changed without a migration: {diff}"


def test_starting_twice_is_safe(app):
    """A second instance (or a restart) re-runs migrations and seeding without error or duplicates."""
    from sqlalchemy import func, select

    from app.config import Settings
    from app.main import create_app
    from app.models import Recipe

    settings = Settings(**{**app.state.settings.__dict__})
    with app.state.session_factory() as s:
        before = s.scalar(select(func.count()).select_from(Recipe))
    second = create_app(settings) if not settings.database_url.endswith(":memory:") else None
    if second is not None:
        with second.state.session_factory() as s:
            assert s.scalar(select(func.count()).select_from(Recipe)) == before
        second.state.engine.dispose()
