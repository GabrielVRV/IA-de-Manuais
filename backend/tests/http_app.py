"""Monta a API HTTP com fakes em memória (sem banco nem IA reais)."""

from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.testclient import TestClient

from manual_assistant import __version__
from manual_assistant.application.ports.health_indicator import HealthIndicator
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.application.use_cases.authenticate_user import AuthenticateUserUseCase
from manual_assistant.application.use_cases.change_password import ChangePasswordUseCase
from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
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
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.application.use_cases.resolve_session import ResolveSessionUseCase
from manual_assistant.domain.user import User, UserRole
from manual_assistant.infrastructure.documents.line_chunker import LineChunker
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from manual_assistant.presentation.http.app import create_http_app
from manual_assistant.presentation.http.dependencies import UseCases
from tests.fakes import (
    FakeEmbeddingProvider,
    FakeLanguageModel,
    InMemoryFileStorage,
    InMemoryManualRepository,
    InMemoryUserRepository,
    InMemoryVectorStore,
)
from tests.security import DEFAULT_PASSWORD, fast_hasher, make_user, token_service

FRONTEND_ORIGIN = "http://servidor-interno"


@dataclass
class FakeBackend:
    """Dependências em memória, expostas para os testes inspecionarem o resultado."""

    repository: InMemoryManualRepository = field(default_factory=InMemoryManualRepository)
    storage: InMemoryFileStorage = field(default_factory=InMemoryFileStorage)
    embeddings: FakeEmbeddingProvider = field(default_factory=FakeEmbeddingProvider)
    vector_store: InMemoryVectorStore = field(default_factory=InMemoryVectorStore)
    language_model: FakeLanguageModel = field(default_factory=FakeLanguageModel)
    users: InMemoryUserRepository = field(default_factory=InMemoryUserRepository)
    health_indicators: list[HealthIndicator] = field(default_factory=list)
    max_upload_bytes: int = 1024 * 1024

    def build_app(self) -> FastAPI:
        hasher, tokens = fast_hasher(), token_service()
        use_cases = UseCases(
            check_health=CheckHealthUseCase(self.health_indicators),
            register_manual=RegisterManualUseCase(
                self.repository, self.storage, max_bytes=self.max_upload_bytes
            ),
            index_manual=IndexManualUseCase(
                repository=self.repository,
                storage=self.storage,
                parser=PdfiumDocumentParser(),  # real: os PDFs dos testes são gerados
                chunker=LineChunker(),
                embeddings=self.embeddings,
                vector_store=self.vector_store,
            ),
            list_manuals=ListManualsUseCase(self.repository),
            get_manual=GetManualUseCase(self.repository),
            get_manual_file=GetManualFileUseCase(self.repository, self.storage),
            delete_manual=DeleteManualUseCase(
                repository=self.repository, vector_store=self.vector_store, storage=self.storage
            ),
            ask_question=AskQuestionUseCase(
                embeddings=self.embeddings,
                vector_store=self.vector_store,
                language_model=self.language_model,
            ),
            authenticate_user=AuthenticateUserUseCase(
                users=self.users, hasher=hasher, tokens=tokens
            ),
            resolve_session=ResolveSessionUseCase(users=self.users, tokens=tokens),
            change_password=ChangePasswordUseCase(users=self.users, hasher=hasher),
            create_user=CreateUserUseCase(users=self.users, hasher=hasher),
            list_users=ListUsersUseCase(self.users),
            reset_user_password=ResetUserPasswordUseCase(users=self.users, hasher=hasher),
            update_user=UpdateUserUseCase(self.users),
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
