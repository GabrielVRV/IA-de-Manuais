from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from manual_assistant.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from manual_assistant.infrastructure.persistence.migrate import upgrade_to_head
from manual_assistant.infrastructure.settings import Settings

# Mesma imagem usada no docker-compose: PostgreSQL com a extensão pgvector.
PGVECTOR_IMAGE = "pgvector/pgvector:pg17"


@pytest.fixture(scope="session")
def postgres_settings() -> Iterator[Settings]:
    """Sobe um PostgreSQL descartável (uma vez por execução) e aplica as migrações."""
    with PostgresContainer(PGVECTOR_IMAGE, driver=None) as container:
        settings = Settings(
            _env_file=None,
            environment="test",
            db_host=container.get_container_host_ip(),
            db_port=int(container.get_exposed_port(5432)),
            db_name=container.dbname,
            db_user=container.username,
            db_password=container.password,
            gemini_api_key="chave-de-teste",  # create_app exige; nenhum teste chama a IA real
        )
        upgrade_to_head(settings.database_url)
        yield settings


@pytest.fixture
async def engine(postgres_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_database_engine(postgres_settings.database_url)
    yield engine
    # Isola os testes: cada um começa com o banco vazio.
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE manuals, chunks CASCADE"))
    await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)
