"""Raiz de composição: o único lugar que conhece todas as camadas e as conecta.

Execução: ``uvicorn --factory manual_assistant.main:create_app``
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from manual_assistant import __version__
from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.get_manual import GetManualUseCase
from manual_assistant.application.use_cases.get_manual_file import GetManualFileUseCase
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.list_manuals import ListManualsUseCase
from manual_assistant.application.use_cases.recover_interrupted_indexing import (
    RecoverInterruptedIndexingUseCase,
)
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.infrastructure.ai.factory import AiProviders, build_ai_providers
from manual_assistant.infrastructure.documents.line_chunker import LineChunker
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from manual_assistant.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from manual_assistant.infrastructure.persistence.health import DatabaseHealthIndicator
from manual_assistant.infrastructure.persistence.manual_repository import (
    SqlAlchemyManualRepository,
)
from manual_assistant.infrastructure.persistence.models import EMBEDDING_DIMENSIONS
from manual_assistant.infrastructure.persistence.vector_store import PgVectorStore
from manual_assistant.infrastructure.settings import Settings
from manual_assistant.infrastructure.storage.local_file_storage import LocalFileStorage
from manual_assistant.presentation.http.app import create_http_app
from manual_assistant.presentation.http.dependencies import UseCases

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    ai_providers: AiProviders | None = None,
) -> FastAPI:
    """``ai_providers`` permite que os testes substituam a IA real por fakes."""
    # Sem argumentos, o pydantic-settings lê os valores obrigatórios do ambiente.
    settings = settings or Settings()
    ai = ai_providers or build_ai_providers(settings, embedding_dimensions=EMBEDDING_DIMENSIONS)

    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    repository = SqlAlchemyManualRepository(session_factory)
    vector_store = PgVectorStore(session_factory, dimensions=EMBEDDING_DIMENSIONS)
    storage = LocalFileStorage(settings.storage_dir)

    use_cases = UseCases(
        check_health=CheckHealthUseCase(indicators=[DatabaseHealthIndicator(engine)]),
        register_manual=RegisterManualUseCase(
            repository, storage, max_bytes=settings.max_upload_bytes
        ),
        index_manual=IndexManualUseCase(
            repository=repository,
            storage=storage,
            parser=PdfiumDocumentParser(),
            chunker=LineChunker(),
            embeddings=ai.embeddings,
            vector_store=vector_store,
        ),
        list_manuals=ListManualsUseCase(repository),
        get_manual=GetManualUseCase(repository),
        get_manual_file=GetManualFileUseCase(repository, storage),
        delete_manual=DeleteManualUseCase(
            repository=repository, vector_store=vector_store, storage=storage
        ),
        ask_question=AskQuestionUseCase(
            embeddings=ai.embeddings,
            vector_store=vector_store,
            language_model=ai.language_model,
            top_k=settings.rag_top_k,
            min_score=settings.rag_min_score,
        ),
    )
    recover_interrupted = RecoverInterruptedIndexingUseCase(repository)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await recover_interrupted.execute()
        except ExternalServiceError:
            # Banco fora do ar na partida: a API sobe mesmo assim e o health check acusa.
            logger.warning("Não foi possível verificar indexações interrompidas", exc_info=True)
        yield
        await engine.dispose()

    return create_http_app(
        title=settings.app_name,
        version=__version__,
        cors_origins=settings.cors_origins,
        use_cases=use_cases,
        lifespan=lifespan,
    )
