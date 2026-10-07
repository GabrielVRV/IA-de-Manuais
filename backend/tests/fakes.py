"""Implementações em memória das portas, para testar casos de uso sem infraestrutura.

O mypy garante que cada fake segue o contrato da porta que substitui.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from manual_assistant.application.errors import StoredFileNotFoundError
from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.application.ports.language_model import (
    Completion,
    CompletionRequest,
    TokenUsage,
)
from manual_assistant.application.ports.text_chunker import TextFragment
from manual_assistant.application.ports.vector_store import EmbeddedChunk
from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.manual import Manual, ManualId
from manual_assistant.domain.pages import Page, PageRange


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
