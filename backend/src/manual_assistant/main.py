"""Raiz de composição: o único lugar que conhece todas as camadas e as conecta.

Execução: ``uvicorn --factory manual_assistant.main:create_app``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from manual_assistant import __version__
from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
from manual_assistant.infrastructure.persistence.database import create_database_engine
from manual_assistant.infrastructure.persistence.health import DatabaseHealthIndicator
from manual_assistant.infrastructure.settings import Settings
from manual_assistant.presentation.http.app import create_http_app
from manual_assistant.presentation.http.dependencies import UseCases


def create_app(settings: Settings | None = None) -> FastAPI:
    # Sem argumentos, o pydantic-settings lê os valores obrigatórios do ambiente.
    settings = settings or Settings()

    engine = create_database_engine(settings.database_url)

    use_cases = UseCases(
        check_health=CheckHealthUseCase(indicators=[DatabaseHealthIndicator(engine)]),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    return create_http_app(
        title=settings.app_name,
        version=__version__,
        cors_origins=settings.cors_origins,
        use_cases=use_cases,
        lifespan=lifespan,
    )
