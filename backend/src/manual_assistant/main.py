"""Raiz de composição: o único lugar que conhece todas as camadas e as conecta.

Execução: ``uvicorn --factory manual_assistant.main:create_app``
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

from fastapi import FastAPI

from manual_assistant import __version__
from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.credential_verifier import CredentialVerifier
from manual_assistant.application.ports.security import PasswordHasher
from manual_assistant.application.sessions import SessionManager
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.application.use_cases.authenticate_user import AuthenticateUserUseCase
from manual_assistant.application.use_cases.change_password import ChangePasswordUseCase
from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
from manual_assistant.application.use_cases.conversations import (
    ChatUseCase,
    DeleteConversationUseCase,
    GetConversationUseCase,
    ListConversationsUseCase,
    PurgeIdleConversationsUseCase,
    RenameConversationUseCase,
)
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.get_manual import GetManualUseCase
from manual_assistant.application.use_cases.get_manual_file import GetManualFileUseCase
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.list_manuals import ListManualsUseCase
from manual_assistant.application.use_cases.manage_users import (
    CreateUserUseCase,
    ListUsersUseCase,
    ResetUserPasswordUseCase,
    UpdateUserUseCase,
)
from manual_assistant.application.use_cases.recover_interrupted_indexing import (
    RecoverInterruptedIndexingUseCase,
)
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.application.use_cases.resolve_session import (
    LogoutUseCase,
    ResolveSessionUseCase,
)
from manual_assistant.domain.conversation import RetentionPolicy
from manual_assistant.domain.session import SessionPolicy
from manual_assistant.infrastructure.ai.factory import AiProviders, build_ai_providers
from manual_assistant.infrastructure.documents.line_chunker import LineChunker
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from manual_assistant.infrastructure.persistence.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from manual_assistant.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from manual_assistant.infrastructure.persistence.health import DatabaseHealthIndicator
from manual_assistant.infrastructure.persistence.login_attempt_repository import (
    SqlAlchemyLoginAttemptRepository,
)
from manual_assistant.infrastructure.persistence.manual_repository import (
    SqlAlchemyManualRepository,
)
from manual_assistant.infrastructure.persistence.models import EMBEDDING_DIMENSIONS
from manual_assistant.infrastructure.persistence.session_repository import (
    SqlAlchemySessionRepository,
)
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from manual_assistant.infrastructure.persistence.vector_store import PgVectorStore
from manual_assistant.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from manual_assistant.infrastructure.settings import Settings
from manual_assistant.infrastructure.storage.local_file_storage import LocalFileStorage
from manual_assistant.infrastructure.totvs.datasul_credential_verifier import (
    DatasulCredentialVerifier,
)
from manual_assistant.presentation.http.app import create_http_app
from manual_assistant.presentation.http.dependencies import UseCases

logger = logging.getLogger(__name__)

# De quanto em quanto tempo as conversas paradas além do prazo de retenção são apagadas.
CONVERSATION_PURGE_INTERVAL = timedelta(hours=6)


def create_app(
    settings: Settings | None = None,
    *,
    ai_providers: AiProviders | None = None,
    password_hasher: PasswordHasher | None = None,
    totvs: CredentialVerifier | None = None,
) -> FastAPI:
    """``ai_providers``, ``password_hasher`` e ``totvs`` permitem que os testes usem
    versões rápidas ou simuladas."""
    # Sem argumentos, o pydantic-settings lê os valores obrigatórios do ambiente.
    settings = settings or Settings()
    ai = ai_providers or build_ai_providers(settings, embedding_dimensions=EMBEDDING_DIMENSIONS)

    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    repository = SqlAlchemyManualRepository(session_factory)
    vector_store = PgVectorStore(session_factory, dimensions=EMBEDDING_DIMENSIONS)
    storage = LocalFileStorage(settings.storage_dir)
    users = SqlAlchemyUserRepository(session_factory)
    conversations = SqlAlchemyConversationRepository(session_factory)
    hasher = password_hasher or Argon2PasswordHasher()
    sessions = SessionManager(
        SqlAlchemySessionRepository(session_factory),
        policy=SessionPolicy(
            idle_timeout=timedelta(days=settings.auth_session_idle_days),
            max_age=timedelta(days=settings.auth_session_max_days),
        ),
    )
    if totvs is None and settings.totvs_login_url:
        totvs = DatasulCredentialVerifier(
            settings.totvs_login_url, timeout_seconds=settings.totvs_timeout_seconds
        )
    if totvs is None:
        logger.info("APP_TOTVS_LOGIN_URL vazia: só usuários locais conseguem entrar")

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
        chat=ChatUseCase(
            conversations=conversations,
            ask_question=AskQuestionUseCase(
                embeddings=ai.embeddings,
                vector_store=vector_store,
                language_model=ai.language_model,
                top_k=settings.rag_top_k,
                min_score=settings.rag_min_score,
            ),
        ),
        list_conversations=ListConversationsUseCase(conversations),
        get_conversation=GetConversationUseCase(conversations),
        rename_conversation=RenameConversationUseCase(conversations),
        delete_conversation=DeleteConversationUseCase(conversations),
        authenticate_user=AuthenticateUserUseCase(
            users=users,
            attempts=SqlAlchemyLoginAttemptRepository(session_factory),
            hasher=hasher,
            sessions=sessions,
            totvs=totvs,
            max_failed_attempts=settings.auth_max_failed_attempts,
            lockout=timedelta(minutes=settings.auth_lockout_minutes),
        ),
        resolve_session=ResolveSessionUseCase(users=users, sessions=sessions),
        logout=LogoutUseCase(sessions),
        change_password=ChangePasswordUseCase(users=users, hasher=hasher),
        create_user=CreateUserUseCase(users=users, hasher=hasher),
        list_users=ListUsersUseCase(users),
        reset_user_password=ResetUserPasswordUseCase(users=users, hasher=hasher),
        update_user=UpdateUserUseCase(users),
    )
    recover_interrupted = RecoverInterruptedIndexingUseCase(repository)
    retention_days = settings.conversation_retention_days
    purge_conversations = PurgeIdleConversationsUseCase(
        conversations,
        RetentionPolicy(timedelta(days=retention_days) if retention_days else None),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await recover_interrupted.execute()
        except ExternalServiceError:
            # Banco fora do ar na partida: a API sobe mesmo assim e o health check acusa.
            logger.warning("Não foi possível verificar indexações interrompidas", exc_info=True)
        purge_task = asyncio.create_task(_purge_periodically(purge_conversations))
        yield
        purge_task.cancel()
        with suppress(asyncio.CancelledError):
            await purge_task
        await engine.dispose()

    return create_http_app(
        title=settings.app_name,
        version=__version__,
        cors_origins=settings.cors_origins,
        use_cases=use_cases,
        cookie_secure=settings.auth_cookie_secure,
        lifespan=lifespan,
    )


async def _purge_periodically(purge: PurgeIdleConversationsUseCase) -> None:
    """Aplica a retenção do histórico na partida e depois a cada intervalo."""
    while True:
        try:
            await purge.execute()
        except ExternalServiceError:
            logger.warning("Não foi possível apagar as conversas antigas", exc_info=True)
        await asyncio.sleep(CONVERSATION_PURGE_INTERVAL.total_seconds())
