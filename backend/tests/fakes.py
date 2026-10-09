"""Implementações em memória das portas, para testar casos de uso sem infraestrutura.

O mypy garante que cada fake segue o contrato da porta que substitui.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime

from manual_assistant.application.errors import StoredFileNotFoundError
from manual_assistant.application.ports.credential_verifier import (
    CredentialCheck,
    CredentialStatus,
)
from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.application.ports.language_model import (
    Completion,
    CompletionRequest,
    TokenUsage,
)
from manual_assistant.application.ports.text_chunker import TextFragment
from manual_assistant.application.ports.vector_store import EmbeddedChunk
from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.login_attempts import LoginAttempts
from manual_assistant.domain.manual import Manual, ManualId
from manual_assistant.domain.pages import Page, PageRange
from manual_assistant.domain.session import Session
from manual_assistant.domain.user import User, UserId


@dataclass
class FakeHealthIndicator:
    name: str
    healthy: bool = True
    error: Exception | None = None

    async def is_healthy(self) -> bool:
        if self.error is not None:
            raise self.error
        return self.healthy


@dataclass
class InMemoryManualRepository:
    manuals: dict[ManualId, Manual] = field(default_factory=dict)
    error_on_save: Exception | None = None
    error_on_list: Exception | None = None
    saved_statuses: list[str] = field(default_factory=list)

    async def save(self, manual: Manual) -> None:
        if self.error_on_save is not None:
            raise self.error_on_save
        self.manuals[manual.id] = manual
        self.saved_statuses.append(manual.status.value)

    async def get(self, manual_id: ManualId) -> Manual | None:
        return self.manuals.get(manual_id)

    async def list_all(self) -> Sequence[Manual]:
        if self.error_on_list is not None:
            raise self.error_on_list
        return sorted(self.manuals.values(), key=lambda m: m.created_at, reverse=True)

    async def delete(self, manual_id: ManualId) -> None:
        self.manuals.pop(manual_id, None)


@dataclass
class InMemoryFileStorage:
    files: dict[str, bytes] = field(default_factory=dict)

    async def save(self, key: str, content: bytes) -> None:
        self.files[key] = content

    async def read(self, key: str) -> bytes:
        if key not in self.files:
            raise StoredFileNotFoundError(f"Arquivo não encontrado: {key}")
        return self.files[key]

    async def delete(self, key: str) -> None:
        self.files.pop(key, None)


@dataclass
class FakeDocumentParser:
    pages: list[Page] = field(default_factory=lambda: [Page(1, "Conteúdo do manual")])
    error: Exception | None = None

    async def parse(self, content: bytes) -> Sequence[Page]:
        if self.error is not None:
            raise self.error
        return self.pages


class OnePagePerFragmentChunker:
    """Um fragmento por página não vazia: previsível para os testes."""

    def split(self, pages: Sequence[Page]) -> Sequence[TextFragment]:
        return [
            TextFragment(text=page.text, pages=PageRange.single(page.number))
            for page in pages
            if not page.is_blank
        ]


@dataclass
class FakeEmbeddingProvider:
    dimensions: int = 3
    error: Exception | None = None
    drop_last: bool = False  # simula um provedor que devolve menos vetores
    embedded_texts: list[str] = field(default_factory=list)

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Embedding]:
        if self.error is not None:
            raise self.error
        self.embedded_texts.extend(texts)
        vectors = [self._vector(text) for text in texts]
        return vectors[:-1] if self.drop_last else vectors

    async def embed_query(self, text: str) -> Embedding:
        if self.error is not None:
            raise self.error
        return self._vector(text)

    def _vector(self, text: str) -> Embedding:
        return tuple(float(len(text) + i) for i in range(self.dimensions))


@dataclass
class InMemoryVectorStore:
    items: dict[ManualId, list[EmbeddedChunk]] = field(default_factory=dict)
    search_results: list[ScoredChunk] = field(default_factory=list)

    async def upsert(self, items: Sequence[EmbeddedChunk]) -> None:
        for item in items:
            self.items.setdefault(item.chunk.manual_id, []).append(item)

    async def search(
        self, query: Embedding, *, limit: int, min_score: float = 0.0
    ) -> Sequence[ScoredChunk]:
        return [r for r in self.search_results if r.score >= min_score][:limit]

    async def delete_by_manual(self, manual_id: ManualId) -> None:
        self.items.pop(manual_id, None)


@dataclass
class FakeLanguageModel:
    answer: str = "Resposta gerada."
    error: Exception | None = None
    requests: list[CompletionRequest] = field(default_factory=list)

    async def complete(self, request: CompletionRequest) -> Completion:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return Completion(
            text=self.answer, model="fake-model", usage=TokenUsage(input_tokens=1, output_tokens=1)
        )


@dataclass
class InMemoryUserRepository:
    users: dict[UserId, User] = field(default_factory=dict)

    async def save(self, user: User) -> None:
        self.users[user.id] = user

    async def get(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self.users.values() if u.username == username), None)

    async def list_all(self) -> Sequence[User]:
        return sorted(self.users.values(), key=lambda u: u.display_name)


@dataclass
class InMemorySessionRepository:
    sessions: dict[str, Session] = field(default_factory=dict)
    touches: int = 0

    async def add(self, session: Session) -> None:
        self.sessions[session.token_hash] = replace(session)

    async def get(self, token_hash: str) -> Session | None:
        session = self.sessions.get(token_hash)
        return replace(session) if session else None

    async def touch(self, token_hash: str, last_seen_at: datetime) -> None:
        self.touches += 1
        if token_hash in self.sessions:
            self.sessions[token_hash].last_seen_at = last_seen_at

    async def delete(self, token_hash: str) -> None:
        self.sessions.pop(token_hash, None)

    async def delete_expired(self, *, last_seen_before: datetime, created_before: datetime) -> None:
        self.sessions = {
            key: s
            for key, s in self.sessions.items()
            if s.last_seen_at >= last_seen_before and s.created_at >= created_before
        }


@dataclass
class InMemoryLoginAttemptRepository:
    attempts: dict[str, LoginAttempts] = field(default_factory=dict)

    async def get(self, username: str) -> LoginAttempts:
        stored = self.attempts.get(username)
        return replace(stored) if stored else LoginAttempts(username=username)

    async def save(self, attempts: LoginAttempts) -> None:
        self.attempts[attempts.username] = replace(attempts)

    async def clear(self, username: str) -> None:
        self.attempts.pop(username, None)


@dataclass
class FakeTotvs:
    """TOTVS simulado: logins e senhas cadastrados em ``accounts``."""

    accounts: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    expired: set[str] = field(default_factory=set)
    error: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def add(self, username: str, password: str, name: str | None = None) -> None:
        self.accounts[username] = password
        if name:
            self.names[username] = name

    async def verify(self, username: str, password: str) -> CredentialCheck:
        self.calls.append(username)
        if self.error is not None:
            raise self.error
        if self.accounts.get(username) != password:
            return CredentialCheck(CredentialStatus.INVALID)
        if username in self.expired:
            return CredentialCheck(CredentialStatus.EXPIRED)
        return CredentialCheck(CredentialStatus.VALID, display_name=self.names.get(username))
