import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from manual_assistant.infrastructure.persistence.migrate import downgrade_to_base, upgrade_to_head
from manual_assistant.infrastructure.persistence.models import Base
from manual_assistant.infrastructure.settings import Settings

pytestmark = pytest.mark.db


def _pending_differences(connection: Connection) -> list[object]:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return list(compare_metadata(context, Base.metadata))


@pytest.mark.anyio
async def test_models_and_migrations_are_in_sync(engine: AsyncEngine) -> None:
    """Falha se alguém alterar models.py e esquecer de criar a migração."""
    async with engine.connect() as connection:
        differences = await connection.run_sync(_pending_differences)

    assert differences == []


def test_migrations_can_be_reverted_and_reapplied(postgres_settings: Settings) -> None:
    downgrade_to_base(postgres_settings.database_url)
    upgrade_to_head(postgres_settings.database_url)
