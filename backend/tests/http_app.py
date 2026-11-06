"""Monta a API HTTP com fakes em memória (sem banco nem IA reais)."""

from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from manual_assistant import __version__
from manual_assistant.application.figures import FigureDescriber
from manual_assistant.application.ports.health_indicator import HealthIndicator
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
    RenameConversationUseCase,
)
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.describe_figures import (
    DescribeFiguresUseCase,
    FigureDescriptionService,
)
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
    UpdateSyncScheduleUseCase,
)
from manual_assistant.application.use_cases.system_settings import (
    DeleteModelPriceUseCase,
    GetSystemSettingsUseCase,
    ListModelPricesUseCase,
    SetModelPriceUseCase,
    UpdateSystemSettingsUseCase,
)
from manual_assistant.application.use_cases.usage_report import GetUsageReportUseCase
from manual_assistant.domain.user import User, UserRole
from manual_assistant.infrastructure.documents.line_chunker import LineChunker
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from manual_assistant.presentation.http.app import create_http_app
from manual_assistant.presentation.http.dependencies import UseCases
from tests.fakes import (
    FakeDirectory,
    FakeEmbeddingProvider,
    FakeLanguageModel,
    FakeManualSource,
    FakePageRenderer,
    InMemoryAssistantAccessRepository,
    InMemoryConversationRepository,
    InMemoryFigureDescriptionRepository,
    InMemoryFileStorage,
    InMemoryLoginAttemptRepository,
    InMemoryManualRepository,
    InMemoryModelPriceRepository,
    InMemorySessionRepository,
    InMemorySyncScheduleRepository,
    InMemorySystemSettingsRepository,
    InMemoryUsageRepository,
    InMemoryUserRepository,
    InMemoryVectorStore,
)
from tests.security import DEFAULT_PASSWORD, fast_hasher, make_user, session_manager

FRONTEND_ORIGIN = "http://servidor-interno"
TIMEZONE = ZoneInfo("America/Sao_Paulo")


@dataclass
class FakeBackend:
    """Dependências em memória, expostas para os testes inspecionarem o resultado."""

    repository: InMemoryManualRepository = field(default_factory=InMemoryManualRepository)
    storage: InMemoryFileStorage = field(default_factory=InMemoryFileStorage)
    embeddings: FakeEmbeddingProvider = field(default_factory=FakeEmbeddingProvider)
    vector_store: InMemoryVectorStore = field(default_factory=InMemoryVectorStore)
    language_model: FakeLanguageModel = field(default_factory=FakeLanguageModel)
    users: InMemoryUserRepository = field(default_factory=InMemoryUserRepository)
    sessions: InMemorySessionRepository = field(default_factory=InMemorySessionRepository)
    login_attempts: InMemoryLoginAttemptRepository = field(
        default_factory=InMemoryLoginAttemptRepository
    )
    directory: FakeDirectory = field(default_factory=FakeDirectory)
    conversations: InMemoryConversationRepository = field(
        default_factory=InMemoryConversationRepository
    )
    usage: InMemoryUsageRepository = field(default_factory=InMemoryUsageRepository)
    system_settings: InMemorySystemSettingsRepository = field(
        default_factory=InMemorySystemSettingsRepository
    )
    model_prices: InMemoryModelPriceRepository = field(default_factory=InMemoryModelPriceRepository)
    sync_schedule: InMemorySyncScheduleRepository = field(
        default_factory=InMemorySyncScheduleRepository
    )
    assistant_access: InMemoryAssistantAccessRepository = field(
        default_factory=InMemoryAssistantAccessRepository
    )
    health_indicators: list[HealthIndicator] = field(default_factory=list)
    max_upload_bytes: int = 1024 * 1024
    # None = pasta de manuais não configurada (sincronização desligada).
    manual_source: FakeManualSource | None = field(default_factory=FakeManualSource)
    manual_sync: ManualSyncService | None = None  # montado em build_app
    # Descrição das figuras (ADR 0014): páginas com figuras e modelo com visão simulados.
    figure_renderer: FakePageRenderer = field(default_factory=FakePageRenderer)
    figure_model: FakeLanguageModel = field(
        default_factory=lambda: FakeLanguageModel(answer="Motor M1 com polia de 200 mm.")
    )
    figure_repository: InMemoryFigureDescriptionRepository = field(
        default_factory=InMemoryFigureDescriptionRepository
    )
    figure_descriptions: FigureDescriptionService | None = None  # montado em build_app

    def build_app(self) -> FastAPI:
        hasher, sessions = fast_hasher(), session_manager(self.sessions)
        register_manual = RegisterManualUseCase(
            self.repository, self.storage, max_bytes=self.max_upload_bytes
        )
        figures = FigureDescriber(
            renderer=self.figure_renderer,
            model=self.figure_model,
            repository=self.figure_repository,
        )
        index_manual = IndexManualUseCase(
            repository=self.repository,
            storage=self.storage,
            parser=PdfiumDocumentParser(),  # real: os PDFs dos testes são gerados
            chunker=LineChunker(),
            embeddings=self.embeddings,
            vector_store=self.vector_store,
            figures=figures,
        )
        self.figure_descriptions = FigureDescriptionService(
            use_case=DescribeFiguresUseCase(
                repository=self.repository,
                storage=self.storage,
                parser=PdfiumDocumentParser(),
                figures=figures,
                embeddings=self.embeddings,
                vector_store=self.vector_store,
            ),
            repository=self.repository,
        )
        delete_manual = DeleteManualUseCase(
            repository=self.repository, vector_store=self.vector_store, storage=self.storage
        )
        self.manual_sync = ManualSyncService(plan=None, apply=None)
        if self.manual_source is not None:
            self.manual_sync = ManualSyncService(
                plan=PlanManualSyncUseCase(
                    source=self.manual_source, repository=self.repository, languages=["P"]
                ),
                apply=ApplyManualSyncUseCase(
                    source=self.manual_source,
                    repository=self.repository,
                    storage=self.storage,
                    register_manual=register_manual,
                    index_manual=index_manual,
                    delete_manual=delete_manual,
                ),
            )
        use_cases = UseCases(
            check_health=CheckHealthUseCase(self.health_indicators),
            register_manual=register_manual,
            index_manual=index_manual,
            list_manuals=ListManualsUseCase(self.repository),
            get_manual=GetManualUseCase(self.repository),
            get_manual_file=GetManualFileUseCase(
                self.repository, self.storage, self.assistant_access
            ),
            delete_manual=delete_manual,
            manual_sync=self.manual_sync,
            figure_descriptions=self.figure_descriptions,
            get_sync_schedule=GetSyncScheduleUseCase(
                schedules=self.sync_schedule, sync=self.manual_sync, timezone=TIMEZONE
            ),
            update_sync_schedule=UpdateSyncScheduleUseCase(
                schedules=self.sync_schedule, sync=self.manual_sync, timezone=TIMEZONE
            ),
            chat=ChatUseCase(
                conversations=self.conversations,
                ask_question=AskQuestionUseCase(
                    embeddings=self.embeddings,
                    vector_store=self.vector_store,
                    language_model=self.language_model,
                ),
                usage=self.usage,
                settings=self.system_settings,
                access=self.assistant_access,
            ),
            list_conversations=ListConversationsUseCase(self.conversations),
            get_conversation=GetConversationUseCase(self.conversations),
            rename_conversation=RenameConversationUseCase(self.conversations),
            delete_conversation=DeleteConversationUseCase(self.conversations),
            authenticate_user=AuthenticateUserUseCase(
                users=self.users,
                attempts=self.login_attempts,
                hasher=hasher,
                sessions=sessions,
                directory=self.directory,
            ),
            resolve_session=ResolveSessionUseCase(users=self.users, sessions=sessions),
            logout=LogoutUseCase(sessions),
            change_password=ChangePasswordUseCase(users=self.users, hasher=hasher),
            create_user=CreateUserUseCase(users=self.users, hasher=hasher),
            list_users=ListUsersUseCase(self.users),
            reset_user_password=ResetUserPasswordUseCase(users=self.users, hasher=hasher),
            update_user=UpdateUserUseCase(self.users),
            usage_report=GetUsageReportUseCase(
                usage=self.usage, users=self.users, prices=self.model_prices, timezone=TIMEZONE
            ),
            get_settings=GetSystemSettingsUseCase(self.system_settings),
            update_settings=UpdateSystemSettingsUseCase(self.system_settings),
            list_model_prices=ListModelPricesUseCase(prices=self.model_prices, usage=self.usage),
            set_model_price=SetModelPriceUseCase(self.model_prices),
            delete_model_price=DeleteModelPriceUseCase(self.model_prices),
            list_my_assistants=ListMyAssistantsUseCase(self.assistant_access),
            list_access_policies=ListAccessPoliciesUseCase(self.assistant_access),
            update_access_policy=UpdateAccessPolicyUseCase(self.assistant_access),
            list_user_access=ListUserAccessUseCase(self.assistant_access),
            set_user_access=SetUserAccessUseCase(access=self.assistant_access, users=self.users),
        )
        return create_http_app(
            title="test",
            version=__version__,
            cors_origins=[FRONTEND_ORIGIN],
            use_cases=use_cases,
        )

    def add_user(
        self,
        username: str = "maria",
        *,
        role: UserRole = UserRole.USER,
        must_change_password: bool = False,
    ) -> User:
        user = make_user(username, role=role, must_change_password=must_change_password)
        self.users.users[user.id] = user
        return user

    def client_logged_in_as(
        self, username: str = "admin", *, role: UserRole = UserRole.ADMIN
    ) -> TestClient:
        """Cliente com o cookie de sessão de um usuário recém-criado."""
        self.add_user(username, role=role)
        client = TestClient(self.build_app())
        login(client, username)
        return client


def login(client: TestClient, username: str, password: str = DEFAULT_PASSWORD) -> None:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
