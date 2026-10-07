from uuid import uuid4

import pytest

from manual_assistant.application.errors import (
    ExternalServiceError,
    ManualNotFoundError,
    UnreadableDocumentError,
)
from manual_assistant.application.ports.vector_store import EmbeddedChunk
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.errors import InvalidStateTransitionError
from manual_assistant.domain.manual import Manual, ManualId, ManualStatus
from manual_assistant.domain.pages import Page, PageRange
from tests.factories import make_chunk, make_manual
from tests.fakes import (
    FakeDocumentParser,
    FakeEmbeddingProvider,
    InMemoryFileStorage,
    InMemoryManualRepository,
    InMemoryVectorStore,
    OnePagePerFragmentChunker,
)

pytestmark = pytest.mark.anyio


class Context:
    def __init__(self) -> None:
        self.repository = InMemoryManualRepository()
        self.storage = InMemoryFileStorage()
        self.parser = FakeDocumentParser(
            pages=[Page(1, "Introdução"), Page(2, "   "), Page(3, "Pressão: 180 bar")]
        )
        self.embeddings = FakeEmbeddingProvider()
        self.vector_store = InMemoryVectorStore()
        self.use_case = IndexManualUseCase(
            repository=self.repository,
            storage=self.storage,
            parser=self.parser,
            chunker=OnePagePerFragmentChunker(),
            embeddings=self.embeddings,
            vector_store=self.vector_store,
        )

    async def registered_manual(self) -> Manual:
        manual = make_manual()
        await self.repository.save(manual)
        self.storage.files[original_file_key(manual.id)] = b"%PDF-"
        self.repository.saved_statuses.clear()
        return manual


@pytest.fixture
def ctx() -> Context:
    return Context()


async def test_indexes_every_fragment_with_its_embedding(ctx: Context) -> None:
    manual = await ctx.registered_manual()

    result = await ctx.use_case.execute(manual.id)

    assert result.status is ManualStatus.INDEXED
    assert (result.page_count, result.chunk_count) == (3, 2)
    indexed = ctx.vector_store.items[manual.id]
    assert [(i.chunk.text, i.chunk.pages, i.chunk.position) for i in indexed] == [
        ("Introdução", PageRange.single(1), 0),
        ("Pressão: 180 bar", PageRange.single(3), 1),
    ]
    assert all(len(i.embedding) == ctx.embeddings.dimensions for i in indexed)
    # O status "processando" é salvo antes, para ficar visível durante a indexação.
    assert ctx.repository.saved_statuses == ["processing", "indexed"]


async def test_reindexing_replaces_previous_chunks(ctx: Context) -> None:
    manual = await ctx.registered_manual()
    stale = EmbeddedChunk(make_chunk(manual, text="versão antiga"), (0.0, 0.0, 0.0))
    await ctx.vector_store.upsert([stale])

    await ctx.use_case.execute(manual.id)

    texts = [i.chunk.text for i in ctx.vector_store.items[manual.id]]
    assert "versão antiga" not in texts


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (UnreadableDocumentError("PDF protegido por senha"), "PDF protegido por senha"),
        (ExternalServiceError("timeout"), "serviço externo"),
        (RuntimeError("bug"), "Erro inesperado"),
    ],
)
async def test_records_failures_on_the_manual(
    ctx: Context, error: Exception, expected_reason: str
) -> None:
    manual = await ctx.registered_manual()
    ctx.parser.error = error

    result = await ctx.use_case.execute(manual.id)

    assert result.status is ManualStatus.FAILED
    assert result.failure_reason is not None
    assert expected_reason in result.failure_reason
    assert ctx.repository.saved_statuses == ["processing", "failed"]


async def test_fails_when_the_original_file_is_missing(ctx: Context) -> None:
    manual = await ctx.registered_manual()
    ctx.storage.files.clear()

    result = await ctx.use_case.execute(manual.id)

    assert result.status is ManualStatus.FAILED
    assert result.failure_reason == "Arquivo não encontrado: " + original_file_key(manual.id)


async def test_fails_when_there_is_no_usable_text(ctx: Context) -> None:
    manual = await ctx.registered_manual()
    ctx.parser.pages = [Page(1, "  ")]

    result = await ctx.use_case.execute(manual.id)

    assert result.failure_reason == "O documento não contém texto aproveitável"


async def test_keeps_the_previous_index_when_embeddings_fail(ctx: Context) -> None:
    manual = await ctx.registered_manual()
    previous = EmbeddedChunk(make_chunk(manual, text="índice anterior"), (0.0, 0.0, 0.0))
    await ctx.vector_store.upsert([previous])
    ctx.embeddings.error = ExternalServiceError("cota excedida")

    result = await ctx.use_case.execute(manual.id)

    assert result.status is ManualStatus.FAILED
    assert ctx.vector_store.items[manual.id] == [previous]


async def test_fails_when_the_provider_returns_fewer_embeddings(ctx: Context) -> None:
    manual = await ctx.registered_manual()
    ctx.embeddings.drop_last = True

    result = await ctx.use_case.execute(manual.id)

    assert result.status is ManualStatus.FAILED
    assert manual.id not in ctx.vector_store.items


async def test_rejects_unknown_manual(ctx: Context) -> None:
    with pytest.raises(ManualNotFoundError):
        await ctx.use_case.execute(ManualId(uuid4()))


async def test_rejects_a_manual_already_being_processed(ctx: Context) -> None:
    manual = await ctx.registered_manual()
    manual.start_processing()

    with pytest.raises(InvalidStateTransitionError):
        await ctx.use_case.execute(manual.id)
