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
from manual_assistant.application.use_cases.assistant_access import (
    ListAccessPoliciesUseCase,
    ListMyAssistantsUseCase,
    ListUserAccessUseCase,
    SetUserAccessUseCase,
    UpdateAccessPolicyUseCase,
)
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
from manual_assistant.application.use_cases.sync_manuals import (
    ApplyManualSyncUseCase,
    ManualSyncService,
    PlanManualSyncUseCase,
)
from manual_assistant.application.use_cases.sync_schedule import (
    GetSyncScheduleUseCase,
    RunScheduledSyncUseCase,
    UpdateSyncScheduleUseCase,
)
from manual_assistant.application.use_cases.system_settings import (
    DeleteModelPriceUseCase,
    GetSystemSettingsUseCase,
    ListModelPricesUseCase,
    PurgeOldUsageUseCase,
    SetModelPriceUseCase,
    UpdateSystemSettingsUseCase,
)
from manual_assistant.application.use_cases.usage_report import GetUsageReportUseCase
from manual_assistant.domain.conversation import RetentionPolicy
from manual_assistant.domain.session import SessionPolicy
from manual_assistant.infrastructure.active_directory.ldap_credential_verifier import (
    ActiveDirectoryConfig,
    LdapCredentialVerifier,
)
from manual_assistant.infrastructure.ai.factory import AiProviders, build_ai_providers
from manual_assistant.infrastructure.documents.line_chunker import LineChunker
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from manual_assistant.infrastructure.persistence.assistant_access_repository import (
    SqlAlchemyAssistantAccessRepository,
)
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
from manual_assistant.infrastructure.persistence.settings_repository import (
    SqlAlchemyModelPriceRepository,
    SqlAlchemySystemSettingsRepository,
)
from manual_assistant.infrastructure.persistence.sync_schedule_repository import (
    SqlAlchemySyncScheduleRepository,
)
from manual_assistant.infrastructure.persistence.usage_repository import SqlAlchemyUsageRepository
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from manual_assistant.infrastructure.persistence.vector_store import PgVectorStore
from manual_assistant.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from manual_assistant.infrastructure.settings import Settings
from manual_assistant.infrastructure.source.folder_manual_source import FolderManualSource
from manual_assistant.infrastructure.storage.local_file_storage import LocalFileStorage
from manual_assistant.presentation.http.app import create_http_app
from manual_assistant.presentation.http.dependencies import UseCases

logger = logging.getLogger(__name__)

# De quanto em quanto tempo as conversas e o consumo além do prazo de retenção são apagados.
PURGE_INTERVAL = timedelta(hours=6)
# De quanto em quanto tempo o agendamento da sincronização é conferido.
SCHEDULE_CHECK_INTERVAL = timedelta(minutes=1)


def create_app(
    settings: Settings | None = None,
    *,
    ai_providers: AiProviders | None = None,
    password_hasher: PasswordHasher | None = None,
    directory: CredentialVerifier | None = None,
) -> FastAPI:
    """``ai_providers``, ``password_hasher`` e ``directory`` permitem que os testes usem
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
    usage = SqlAlchemyUsageRepository(session_factory)
    system_settings = SqlAlchemySystemSettingsRepository(session_factory)
    model_prices = SqlAlchemyModelPriceRepository(session_factory)
    assistant_access = SqlAlchemyAssistantAccessRepository(session_factory)
    hasher = password_hasher or Argon2PasswordHasher()
    sessions = SessionManager(
        SqlAlchemySessionRepository(session_factory),
        policy=SessionPolicy(
            idle_timeout=timedelta(days=settings.auth_session_idle_days),
            max_age=timedelta(days=settings.auth_session_max_days),
        ),
    )
    if directory is None:
        directory = _build_directory(settings)

    register_manual = RegisterManualUseCase(
        repository, storage, max_bytes=settings.max_upload_bytes
    )
    index_manual = IndexManualUseCase(
        repository=repository,
        storage=storage,
        parser=PdfiumDocumentParser(),
        chunker=LineChunker(),
        embeddings=ai.embeddings,
        vector_store=vector_store,
    )
    delete_manual = DeleteManualUseCase(
        repository=repository, vector_store=vector_store, storage=storage
    )
    manual_sync = ManualSyncService(plan=None, apply=None)
    if settings.sync_source_dir:
        source = FolderManualSource(
            settings.sync_source_dir, catalog_file=settings.sync_catalog_file
        )
        manual_sync = ManualSyncService(
            plan=PlanManualSyncUseCase(
                source=source, repository=repository, languages=settings.sync_languages
            ),
            apply=ApplyManualSyncUseCase(
                source=source,
                repository=repository,
                storage=storage,
                register_manual=register_manual,
                index_manual=index_manual,
                delete_manual=delete_manual,
            ),
        )

    schedules = SqlAlchemySyncScheduleRepository(session_factory)
    use_cases = UseCases(
        check_health=CheckHealthUseCase(indicators=[DatabaseHealthIndicator(engine)]),
        register_manual=register_manual,
        index_manual=index_manual,
        list_manuals=ListManualsUseCase(repository),
        get_manual=GetManualUseCase(repository),
        get_manual_file=GetManualFileUseCase(repository, storage, assistant_access),
        delete_manual=delete_manual,
        manual_sync=manual_sync,
        get_sync_schedule=GetSyncScheduleUseCase(
            schedules=schedules, sync=manual_sync, timezone=settings.zone
        ),
        update_sync_schedule=UpdateSyncScheduleUseCase(
            schedules=schedules, sync=manual_sync, timezone=settings.zone
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
            usage=usage,
            settings=system_settings,
            access=assistant_access,
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
            directory=directory,
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
        usage_report=GetUsageReportUseCase(
            usage=usage, users=users, prices=model_prices, timezone=settings.zone
        ),
        get_settings=GetSystemSettingsUseCase(system_settings),
        update_settings=UpdateSystemSettingsUseCase(system_settings),
        list_my_assistants=ListMyAssistantsUseCase(assistant_access),
        list_access_policies=ListAccessPoliciesUseCase(assistant_access),
        update_access_policy=UpdateAccessPolicyUseCase(assistant_access),
        list_user_access=ListUserAccessUseCase(assistant_access),
        set_user_access=SetUserAccessUseCase(access=assistant_access, users=users),
        list_model_prices=ListModelPricesUseCase(prices=model_prices, usage=usage),
        set_model_price=SetModelPriceUseCase(model_prices),
        delete_model_price=DeleteModelPriceUseCase(model_prices),
    )
    recover_interrupted = RecoverInterruptedIndexingUseCase(repository)
    retention_days = settings.conversation_retention_days
    purge_conversations = PurgeIdleConversationsUseCase(
        conversations,
        RetentionPolicy(timedelta(days=retention_days) if retention_days else None),
    )
    purge_usage = PurgeOldUsageUseCase(usage=usage, settings=system_settings)
    run_scheduled_sync = RunScheduledSyncUseCase(
        schedules=schedules, sync=manual_sync, timezone=settings.zone
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await recover_interrupted.execute()
        except ExternalServiceError:
            # Banco fora do ar na partida: a API sobe mesmo assim e o health check acusa.
            logger.warning("Não foi possível verificar indexações interrompidas", exc_info=True)
        tasks = [
            asyncio.create_task(_purge_periodically(purge_conversations, purge_usage)),
            asyncio.create_task(_run_scheduled_sync_periodically(run_scheduled_sync)),
        ]
        yield
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        await manual_sync.stop()
        await engine.dispose()

    return create_http_app(
        title=settings.app_name,
        version=__version__,
        cors_origins=settings.cors_origins,
        use_cases=use_cases,
        cookie_secure=settings.auth_cookie_secure,
        lifespan=lifespan,
    )


async def _purge_periodically(
    conversations: PurgeIdleConversationsUseCase, usage: PurgeOldUsageUseCase
) -> None:
    """Aplica a retenção do histórico e do consumo na partida e depois a cada intervalo."""
    while True:
        try:
            await conversations.execute()
        except ExternalServiceError:
            logger.warning("Não foi possível apagar as conversas antigas", exc_info=True)
        try:
            await usage.execute()
        except ExternalServiceError:
            logger.warning("Não foi possível apagar o consumo antigo", exc_info=True)
        await asyncio.sleep(PURGE_INTERVAL.total_seconds())


async def _run_scheduled_sync_periodically(run: RunScheduledSyncUseCase) -> None:
    """Confere o agendamento da sincronização a cada intervalo."""
    while True:
        try:
            await run.execute()
        except ExternalServiceError:
            logger.warning("Não foi possível conferir a sincronização agendada", exc_info=True)
        await asyncio.sleep(SCHEDULE_CHECK_INTERVAL.total_seconds())


def _build_directory(settings: Settings) -> CredentialVerifier | None:
    """Login pelo AD (ADR 0011), ou None quando não configurado."""
    if not settings.ad_server_urls or not settings.ad_domain or not settings.ad_base_dn:
        logger.info("APP_AD_SERVER_URLS vazia: só usuários locais conseguem entrar")
        return None
    if not settings.ad_start_tls and any(
        not url.lower().startswith("ldaps://") for url in settings.ad_server_urls
    ):
        logger.warning(
            "Login pelo AD sem criptografia: as senhas de rede trafegam abertas. "
            "Use ldaps:// ou APP_AD_START_TLS=true"
        )
    return LdapCredentialVerifier(
        ActiveDirectoryConfig(
            server_urls=settings.ad_server_urls,
            domain=settings.ad_domain,
            base_dn=settings.ad_base_dn,
            required_group_dn=settings.ad_required_group_dn,
            start_tls=settings.ad_start_tls,
            ca_cert_file=settings.ad_ca_cert_file,
            timeout_seconds=settings.ad_timeout_seconds,
        )
    )
