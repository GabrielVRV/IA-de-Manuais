"""Descrição das figuras por IA: na indexação e para manuais já indexados (ADR 0014)."""

import pytest

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.figures import (
    NO_FIGURES_MARKER,
    FigureDescriber,
    content_hash,
)
from manual_assistant.application.use_cases.describe_figures import (
    DescribeFiguresUseCase,
    ManualNotIndexedError,
)
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.chunk import ChunkKind
from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.manual import Manual, ManualStatus
from manual_assistant.domain.pages import Page, PageRange
from tests.factories import FIXED_NOW, make_manual
from tests.fakes import (
    FakeDocumentParser,
    FakeEmbeddingProvider,
    FakeLanguageModel,
    FakePageRenderer,
    InMemoryFigureDescriptionRepository,
    InMemoryFileStorage,
    InMemoryManualRepository,
    InMemoryVectorStore,
    OnePagePerFragmentChunker,
)

pytestmark = pytest.mark.anyio

CONTENT = b"%PDF- manual"


class Context:
    def __init__(self) -> None:
        self.repository = InMemoryManualRepository()
        self.storage = InMemoryFileStorage()
        self.parser = FakeDocumentParser(
            pages=[Page(1, "Introdução"), Page(2, "Montagem do motor"), Page(3, "Fim")]
        )
        self.embeddings = FakeEmbeddingProvider()
        self.vector_store = InMemoryVectorStore()
        self.renderer = FakePageRenderer(figure_pages=[2, 3])
        self.model = FakeLanguageModel(answer="Motor M1 com polia de 200 mm.")
        self.descriptions = InMemoryFigureDescriptionRepository()
        self.figures = FigureDescriber(
            renderer=self.renderer,
            model=self.model,
            repository=self.descriptions,
            clock=lambda: FIXED_NOW,
        )

    def index_use_case(self) -> IndexManualUseCase:
        return IndexManualUseCase(
            repository=self.repository,
            storage=self.storage,
            parser=self.parser,
            chunker=OnePagePerFragmentChunker(),
            embeddings=self.embeddings,
            vector_store=self.vector_store,
            figures=self.figures,
        )

    def describe_use_case(self) -> DescribeFiguresUseCase:
        return DescribeFiguresUseCase(
            repository=self.repository,
            storage=self.storage,
            parser=self.parser,
            figures=self.figures,
            embeddings=self.embeddings,
            vector_store=self.vector_store,
        )

    async def registered_manual(self) -> Manual:
        manual = make_manual()
        await self.repository.save(manual)
        self.storage.files[original_file_key(manual.id)] = CONTENT
        return manual

    async def indexed_manual(self) -> Manual:
        """Indexado só com o texto, como os manuais de antes desta funcionalidade."""
        manual = await self.registered_manual()
        indexed = await self.index_use_case().execute(manual.id)
        self.embeddings.embedded_texts.clear()
        return indexed

    def chunks(self, manual: Manual, kind: ChunkKind) -> list[tuple[str, PageRange, int]]:
        return [
            (item.chunk.text, item.chunk.pages, item.chunk.position)
            for item in self.vector_store.items.get(manual.id, [])
            if item.chunk.kind is kind
        ]


@pytest.fixture
def ctx() -> Context:
    return Context()


def described(page: int, text: str | None = "Figura") -> FigureDescription:
    return FigureDescription(page=page, text=text, model="fake-model", described_at=FIXED_NOW)


class TestFigureDescriber:
    async def test_sends_each_page_image_with_its_text_and_saves_the_description(
        self, ctx: Context
    ) -> None:
        manual = await ctx.registered_manual()

        result = await ctx.figures.describe(
            manual, CONTENT, ctx.parser.pages, version=content_hash(CONTENT)
        )

        assert [(d.page, d.text) for d in result] == [
            (2, "Motor M1 com polia de 200 mm."),
            (3, "Motor M1 com polia de 200 mm."),
        ]
        request = ctx.model.requests[0]
        assert request.images[0].data == "página 2".encode()
        assert "Página: 2" in request.prompt
        assert "Montagem do motor" in request.prompt
        assert manual.title in request.prompt
        assert len(await ctx.descriptions.list(manual.id, content_hash(CONTENT))) == 2

    async def test_only_describes_pages_not_yet_described(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        await ctx.descriptions.add(manual.id, content_hash(CONTENT), described(2))

        result = await ctx.figures.describe(
            manual, CONTENT, ctx.parser.pages, version=content_hash(CONTENT)
        )

        assert ctx.renderer.rendered == [3]
        assert len(ctx.model.requests) == 1
        assert [d.page for d in result] == [2, 3]

    async def test_a_new_version_of_the_file_is_described_again(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        await ctx.descriptions.add(manual.id, "versão-antiga", described(2))

        await ctx.figures.describe(manual, CONTENT, ctx.parser.pages, version="versão-nova")

        assert ctx.renderer.rendered == [2, 3]

    async def test_pages_without_technical_content_are_kept_without_text(
        self, ctx: Context
    ) -> None:
        manual = await ctx.registered_manual()
        ctx.model.answers = [NO_FIGURES_MARKER, "Diagrama elétrico"]

        result = await ctx.figures.describe(
            manual, CONTENT, ctx.parser.pages, version=content_hash(CONTENT)
        )

        assert [(d.page, d.text) for d in result] == [(2, None), (3, "Diagrama elétrico")]

    async def test_what_was_described_before_a_failure_is_kept(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        ctx.model.error = ExternalServiceError("cota excedida")
        ctx.model.fail_from_call = 2

        with pytest.raises(ExternalServiceError):
            await ctx.figures.describe(
                manual, CONTENT, ctx.parser.pages, version=content_hash(CONTENT)
            )

        saved = await ctx.descriptions.list(manual.id, content_hash(CONTENT))
        assert [d.page for d in saved] == [2]


class TestIndexing:
    async def test_describes_figures_and_indexes_them_with_the_text(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()

        result = await ctx.index_use_case().execute(manual.id, describe_figures=True)

        assert result.status is ManualStatus.INDEXED
        assert (result.chunk_count, result.figure_count) == (3, 2)
        assert [
            (pages, position) for _, pages, position in ctx.chunks(manual, ChunkKind.FIGURE)
        ] == [
            (PageRange.single(2), 0),
            (PageRange.single(3), 1),
        ]
        text, _, _ = ctx.chunks(manual, ChunkKind.FIGURE)[0]
        assert text.startswith("[Figuras da página 2, descritas por IA")
        assert "Motor M1" in text

    async def test_reindexing_reuses_the_descriptions_already_paid(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        await ctx.index_use_case().execute(manual.id, describe_figures=True)
        calls = len(ctx.model.requests)

        result = await ctx.index_use_case().execute(manual.id, describe_figures=True)

        assert len(ctx.model.requests) == calls
        assert result.figure_count == 2

    async def test_with_description_off_only_reuses_what_was_described(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        await ctx.descriptions.add(manual.id, content_hash(CONTENT), described(3))

        result = await ctx.index_use_case().execute(manual.id)

        assert ctx.model.requests == []
        assert result.figure_count == 1

    async def test_indexes_a_scanned_manual_from_its_figures(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        ctx.parser.pages = [Page(1, ""), Page(2, "")]
        ctx.renderer.figure_pages = [1, 2]

        result = await ctx.index_use_case().execute(manual.id, describe_figures=True)

        assert result.status is ManualStatus.INDEXED
        assert (result.chunk_count, result.figure_count) == (0, 2)
        assert "(nenhum: a página parece escaneada)" in ctx.model.requests[0].prompt

    async def test_a_scanned_manual_fails_when_the_model_fails(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        ctx.parser.pages = [Page(1, "")]
        ctx.renderer.figure_pages = [1]
        ctx.model.error = ExternalServiceError("fora do ar")

        result = await ctx.index_use_case().execute(manual.id, describe_figures=True)

        assert result.status is ManualStatus.FAILED

    async def test_indexes_the_text_when_describing_figures_fails(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        ctx.model.error = ExternalServiceError("cota excedida")
        ctx.model.fail_from_call = 2

        result = await ctx.index_use_case().execute(manual.id, describe_figures=True)

        assert result.status is ManualStatus.INDEXED
        assert (result.chunk_count, result.figure_count) == (3, 1)

    async def test_discards_descriptions_of_previous_versions(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()
        await ctx.descriptions.add(manual.id, "versão-antiga", described(1))

        await ctx.index_use_case().execute(manual.id, describe_figures=True)

        assert await ctx.descriptions.list(manual.id, "versão-antiga") == []


class TestDescribeIndexedManual:
    async def test_adds_figures_without_embedding_the_text_again(self, ctx: Context) -> None:
        manual = await ctx.indexed_manual()
        text_chunks = ctx.chunks(manual, ChunkKind.TEXT)
        pages: list[int] = []

        result = await ctx.describe_use_case().execute(
            manual, on_page=lambda d: pages.append(d.page)
        )

        assert pages == [2, 3]
        assert result.figure_count == 2
        assert (result.input_tokens, result.output_tokens) == (2, 2)
        # Só as figuras vão para o embedding, cada uma com o título do manual na frente.
        assert all(
            text.startswith(f"{manual.title}\n[Figuras") for text in ctx.embeddings.embedded_texts
        )
        assert ctx.chunks(manual, ChunkKind.TEXT) == text_chunks
        assert len(ctx.chunks(manual, ChunkKind.FIGURE)) == 2
        stored = await ctx.repository.get(manual.id)
        assert stored is not None
        assert (stored.chunk_count, stored.figure_count) == (3, 2)

    async def test_running_again_does_not_duplicate_figures(self, ctx: Context) -> None:
        manual = await ctx.indexed_manual()
        await ctx.describe_use_case().execute(manual)

        result = await ctx.describe_use_case().execute(manual)

        assert result.described == []
        assert len(ctx.chunks(manual, ChunkKind.FIGURE)) == 2

    async def test_plan_counts_pending_pages_without_calling_the_model(self, ctx: Context) -> None:
        manual = await ctx.indexed_manual()
        await ctx.descriptions.add(manual.id, content_hash(CONTENT), described(2))

        plan = await ctx.describe_use_case().plan(manual)

        assert (plan.with_figures, plan.pending) == (2, 1)
        assert ctx.model.requests == []

    async def test_requires_an_indexed_manual(self, ctx: Context) -> None:
        manual = await ctx.registered_manual()

        with pytest.raises(ManualNotIndexedError):
            await ctx.describe_use_case().execute(manual)

    async def test_does_not_touch_a_manual_reprocessed_meanwhile(self, ctx: Context) -> None:
        manual = await ctx.indexed_manual()
        stored = await ctx.repository.get(manual.id)
        assert stored is not None
        stored.start_processing()

        with pytest.raises(ManualNotIndexedError):
            await ctx.describe_use_case().execute(manual)

        assert ctx.chunks(manual, ChunkKind.FIGURE) == []
