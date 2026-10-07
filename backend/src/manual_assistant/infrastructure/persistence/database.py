from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from manual_assistant.application.errors import ExternalServiceError

CONNECT_TIMEOUT_SECONDS = 5
COMMAND_TIMEOUT_SECONDS = 30


def create_database_engine(url: URL) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_pre_ping=True,  # descarta conexões derrubadas (ex.: reinício do banco)
        pool_size=5,
        max_overflow=5,
        connect_args={
            "timeout": CONNECT_TIMEOUT_SECONDS,
            "command_timeout": COMMAND_TIMEOUT_SECONDS,
        },
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def translate_database_errors(operation: str) -> AsyncIterator[None]:
    """Converte falhas do banco no erro da aplicação, escondendo o SQLAlchemy dos casos de uso."""
    try:
        yield
    except (SQLAlchemyError, OSError) as error:
        raise ExternalServiceError(f"Falha no banco de dados ao {operation}") from error
