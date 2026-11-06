"""Implementações em memória das portas, para testar casos de uso sem infraestrutura.

O mypy garante que cada fake segue o contrato da porta que substitui.
"""

import asyncio
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from manual_assistant.application.errors import StoredFileNotFoundError
from manual_assistant.application.ports.credential_verifier import (
    CredentialCheck,
    CredentialStatus,
)
from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.application.ports.language_model import (
    Completion,
    CompletionRequest,
    ImageInput,
    TokenUsage,
)
from manual_assistant.application.ports.manual_source import SourceDocument
from manual_assistant.application.ports.text_chunker import TextFragment
from manual_assistant.application.ports.usage_repository import UsageAggregate
from manual_assistant.application.ports.vector_store import EmbeddedChunk
from manual_assistant.domain.assistant import AccessPolicy, AssistantId, UserAccess
from manual_assistant.domain.chunk import ChunkKind, ScoredChunk
from manual_assistant.domain.conversation import (
    Conversation,
    ConversationId,
    ConversationSummary,
    Exchange,
)
from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.login_attempts import LoginAttempts
from manual_assistant.domain.manual import Manual, ManualId
from manual_assistant.domain.pages import Page, PageRange
from manual_assistant.domain.session import Session
from manual_assistant.domain.sync_schedule import SyncSchedule
from manual_assistant.domain.system_settings import SystemSettings
from manual_assistant.domain.usage import ModelPrice, QuestionUsage
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
    searched_manual_ids: list[set[ManualId] | None] = field(default_factory=list)

    async def upsert(self, items: Sequence[EmbeddedChunk]) -> None:
        for item in items:
            self.items.setdefault(item.chunk.manual_id, []).append(item)

    async def search(
        self,
        query: Embedding,
        *,
        limit: int,
        min_score: float = 0.0,
        manual_ids: Collection[ManualId] | None = None,
    ) -> Sequence[ScoredChunk]:
        self.searched_manual_ids.append(None if manual_ids is None else set(manual_ids))
        return [
            r
            for r in self.search_results
            if r.score >= min_score and (manual_ids is None or r.chunk.manual_id in manual_ids)
        ][:limit]

    async def delete_by_manual(self, manual_id: ManualId, *, kind: ChunkKind | None = None) -> None:
        if kind is None:
            self.items.pop(manual_id, None)
        else:
            kept = [i for i in self.items.get(manual_id, []) if i.chunk.kind is not kind]
            self.items[manual_id] = kept


@dataclass
class FakeLanguageModel:
    answer: str = "Resposta gerada."
    error: Exception | None = None
    requests: list[CompletionRequest] = field(default_factory=list)
    # Falha só a partir da chamada de número ``fail_from_call`` (1 = a primeira).
    fail_from_call: int | None = None
    # Respostas por chamada, em ordem; quando acabam, vale ``answer``.
    answers: list[str] = field(default_factory=list)

    async def complete(self, request: CompletionRequest) -> Completion:
        self.requests.append(request)
        if self.error is not None and (
            self.fail_from_call is None or len(self.requests) >= self.fail_from_call
        ):
            raise self.error
        if self.answers:
            return Completion(
                text=self.answers.pop(0),
                model="fake-model",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )
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
class FakeDirectory:
    """AD simulado: logins e senhas cadastrados em ``accounts``."""

    accounts: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    expired: set[str] = field(default_factory=set)
    blocked: set[str] = field(default_factory=set)  # conta bloqueada/desativada no AD
    outside_group: set[str] = field(default_factory=set)  # fora do grupo exigido
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
        if username in self.blocked:
            return CredentialCheck(CredentialStatus.BLOCKED)
        if self.accounts.get(username) != password:
            return CredentialCheck(CredentialStatus.INVALID)
        if username in self.outside_group:
            return CredentialCheck(CredentialStatus.NOT_ALLOWED)
        if username in self.expired:
            return CredentialCheck(CredentialStatus.EXPIRED)
        return CredentialCheck(CredentialStatus.VALID, display_name=self.names.get(username))


@dataclass
class FakeManualSource:
    """Pasta da Engenharia simulada: caminho -> (conteúdo, título na planilha)."""

    files: dict[str, tuple[bytes, str | None]] = field(default_factory=dict)
    versions: dict[str, int] = field(default_factory=dict)  # muda a "data" do arquivo
    reads: list[str] = field(default_factory=list)
    read_error: Exception | None = None  # lançado ao ler qualquer arquivo
    read_gate: asyncio.Event | None = None  # se definido, a leitura espera por ele

    def put(self, path: str, content: bytes = b"%PDF-1.4 v1", title: str | None = None) -> None:
        self.files[path] = (content, title)
        self.versions[path] = self.versions.get(path, 0) + 1

    async def list_documents(self) -> Sequence[SourceDocument]:
        return [
            SourceDocument(
                path=path,
                file_name=path.rsplit("/", 1)[-1],
                fingerprint=f"{len(content)}-{self.versions[path]}",
                title=title,
            )
            for path, (content, title) in self.files.items()
        ]

    async def read(self, path: str) -> bytes:
        self.reads.append(path)
        if self.read_gate is not None:
            await self.read_gate.wait()
        if self.read_error is not None:
            raise self.read_error
        return self.files[path][0]


@dataclass
class InMemoryConversationRepository:
    conversations: dict[ConversationId, Conversation] = field(default_factory=dict)

    async def add(self, conversation: Conversation) -> None:
        self.conversations[conversation.id] = _copy(conversation)

    async def get(self, conversation_id: ConversationId) -> Conversation | None:
        stored = self.conversations.get(conversation_id)
        return _copy(stored) if stored else None

    async def list_by_owner(self, owner_id: UserId) -> Sequence[ConversationSummary]:
        owned = [c for c in self.conversations.values() if c.owner_id == owner_id]
        return [
            ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                exchange_count=len(c.exchanges),
            )
            for c in sorted(owned, key=lambda c: c.updated_at, reverse=True)
        ]

    async def append(self, conversation: Conversation, exchange: Exchange) -> None:
        stored = self.conversations[conversation.id]
        stored.exchanges.append(exchange)
        stored.updated_at = conversation.updated_at

    async def rename(self, conversation_id: ConversationId, title: str) -> None:
        self.conversations[conversation_id].title = title

    async def delete(self, conversation_id: ConversationId) -> None:
        self.conversations.pop(conversation_id, None)

    async def delete_idle(self, *, updated_before: datetime) -> int:
        idle = [c.id for c in self.conversations.values() if c.updated_at < updated_before]
        for conversation_id in idle:
            del self.conversations[conversation_id]
        return len(idle)


@dataclass
class InMemoryUsageRepository:
    records: list[QuestionUsage] = field(default_factory=list)

    async def add(self, usage: QuestionUsage) -> None:
        self.records.append(usage)

    async def aggregate(
        self, *, since: datetime, until: datetime, timezone: ZoneInfo
    ) -> Sequence[UsageAggregate]:
        groups: dict[tuple[UserId, str | None, date], list[QuestionUsage]] = defaultdict(list)
        for usage in self.records:
            if since <= usage.asked_at < until:
                day = usage.asked_at.astimezone(timezone).date()
                groups[(usage.user_id, usage.model, day)].append(usage)
        return [
            UsageAggregate(
                user_id=user_id,
                model=model,
                day=day,
                questions=len(items),
                input_tokens=sum(u.input_tokens for u in items),
                output_tokens=sum(u.output_tokens for u in items),
            )
            for (user_id, model, day), items in groups.items()
        ]

    async def count_since(self, user_id: UserId, since: datetime) -> int:
        return sum(1 for u in self.records if u.user_id == user_id and u.asked_at >= since)

    async def models(self) -> Sequence[str]:
        return sorted({u.model for u in self.records if u.model is not None})

    async def delete_before(self, cutoff: datetime) -> int:
        kept = [u for u in self.records if u.asked_at >= cutoff]
        removed = len(self.records) - len(kept)
        self.records = kept
        return removed


@dataclass
class InMemorySystemSettingsRepository:
    settings: SystemSettings = field(default_factory=SystemSettings)

    async def get(self) -> SystemSettings:
        return replace(self.settings)

    async def save(self, settings: SystemSettings) -> None:
        self.settings = replace(settings)


@dataclass
class InMemorySyncScheduleRepository:
    schedule: SyncSchedule = field(default_factory=SyncSchedule)

    async def get(self) -> SyncSchedule:
        return replace(self.schedule)

    async def save(self, schedule: SyncSchedule) -> None:
        self.schedule = replace(schedule)


@dataclass
class InMemoryModelPriceRepository:
    prices: dict[str, ModelPrice] = field(default_factory=dict)

    async def list_all(self) -> Sequence[ModelPrice]:
        return [self.prices[model] for model in sorted(self.prices)]

    async def save(self, price: ModelPrice) -> None:
        self.prices[price.model] = price

    async def delete(self, model: str) -> None:
        self.prices.pop(model, None)


def _copy(conversation: Conversation) -> Conversation:
    """Cópia independente, como se viesse do banco: o teste não altera o "armazenado"."""
    return replace(conversation, exchanges=list(conversation.exchanges))


@dataclass
class InMemoryAssistantAccessRepository:
    policies: dict[AssistantId, AccessPolicy] = field(default_factory=dict)
    access: dict[UserId, dict[AssistantId, UserAccess]] = field(default_factory=dict)

    async def get_policy(self, assistant_id: AssistantId) -> AccessPolicy:
        policy = self.policies.get(assistant_id)
        return replace(policy) if policy else AccessPolicy(assistant_id=assistant_id)

    async def save_policy(self, policy: AccessPolicy) -> None:
        self.policies[policy.assistant_id] = replace(policy)

    async def user_access(self, user_id: UserId) -> Mapping[AssistantId, UserAccess]:
        return dict(self.access.get(user_id, {}))

    async def all_user_access(self) -> Mapping[UserId, Mapping[AssistantId, UserAccess]]:
        return {user_id: dict(items) for user_id, items in self.access.items() if items}

    async def set_user_access(
        self, user_id: UserId, assistant_id: AssistantId, access: UserAccess | None
    ) -> None:
        items = self.access.setdefault(user_id, {})
        if access is None:
            items.pop(assistant_id, None)
        else:
            items[assistant_id] = access


@dataclass
class FakePageRenderer:
    """Páginas com figuras definidas pelo teste; a "imagem" diz qual página é."""

    figure_pages: list[int] = field(default_factory=list)
    rendered: list[int] = field(default_factory=list)

    async def pages_with_figures(self, content: bytes) -> Sequence[int]:
        return list(self.figure_pages)

    async def render(self, content: bytes, pages: Sequence[int]) -> Sequence[ImageInput]:
        self.rendered.extend(pages)
        return [ImageInput(data=f"página {page}".encode()) for page in pages]


@dataclass
class InMemoryFigureDescriptionRepository:
    # manual -> página -> (hash do arquivo, descrição)
    rows: dict[ManualId, dict[int, tuple[str, FigureDescription]]] = field(default_factory=dict)

    async def list(self, manual_id: ManualId, content_hash: str) -> Sequence[FigureDescription]:
        pages = self.rows.get(manual_id, {})
        return [d for page, (h, d) in sorted(pages.items()) if h == content_hash]

    async def add(
        self, manual_id: ManualId, content_hash: str, description: FigureDescription
    ) -> None:
        self.rows.setdefault(manual_id, {})[description.page] = (content_hash, description)

    async def delete_other_versions(self, manual_id: ManualId, content_hash: str) -> int:
        pages = self.rows.get(manual_id, {})
        stale = [page for page, (h, _) in pages.items() if h != content_hash]
        for page in stale:
            del pages[page]
        return len(stale)
