"""Descreve as figuras de manuais já indexados, sem refazer os trechos de texto (ADR 0014)."""

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field

from manual_assistant.application.errors import (
    ApplicationError,
    ExternalServiceError,
    ManualNotFoundError,
)
from manual_assistant.application.figures import FigureDescriber, content_hash
from manual_assistant.application.ports.document_parser import DocumentParser
from manual_assistant.application.ports.embedding_provider import EmbeddingProvider
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.ports.vector_store import EmbeddedChunk, VectorStore
from manual_assistant.application.use_cases.index_manual import figure_chunks
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.chunk import ChunkKind
from manual_assistant.domain.errors import DomainError
from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.manual import Manual, ManualId, ManualStatus

logger = logging.getLogger(__name__)


class ManualNotIndexedError(ApplicationError):
    def __init__(self, manual: Manual) -> None:
        super().__init__(
            f"'{manual.title}' não está indexado (status: {manual.status}); "
            "reprocesse o manual pela tela"
        )


@dataclass(frozen=True, slots=True)
class FigurePlanItem:
    manual: Manual
    with_figures: int  # páginas com figuras
    pending: int  # ainda sem descrição: cada uma é uma chamada ao modelo com visão


@dataclass(frozen=True, slots=True)
class FigureResult:
    manual: Manual
    described: list[FigureDescription]  # descritas nesta execução
    figure_count: int  # trechos de figuras do manual agora

    @property
    def input_tokens(self) -> int:
        return sum(d.input_tokens for d in self.described)

    @property
    def output_tokens(self) -> int:
        return sum(d.output_tokens for d in self.described)


class DescribeFiguresUseCase:
    """Completa as figuras de um manual indexado.

    Os trechos de texto ficam como estão (sem gerar embeddings de novo); só os trechos
    de figuras do manual são refeitos, a partir das descrições guardadas.
    """

    def __init__(
        self,
        *,
        repository: ManualRepository,
        storage: FileStorage,
        parser: DocumentParser,
        figures: FigureDescriber,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._parser = parser
        self._figures = figures
        self._embeddings = embeddings
        self._vector_store = vector_store

    async def plan(self, manual: Manual) -> FigurePlanItem:
        """Quantas páginas têm figuras e quantas faltam. Não chama a IA.

        Vale para qualquer manual com arquivo, inclusive um que falhou (ex.: escaneado),
        para estimar o custo antes de reprocessá-lo descrevendo as figuras.

        Raises:
            StoredFileNotFoundError, UnreadableDocumentError.
        """
        content = await self._storage.read(original_file_key(manual.id))
        pages = await self._figures.pages(manual.id, content, content_hash(content))
        return FigurePlanItem(manual, len(pages.with_figures), len(pages.pending))

    async def execute(
        self,
        manual: Manual,
        *,
        on_page: Callable[[FigureDescription], None] | None = None,
    ) -> FigureResult:
        """
        Raises:
            ManualNotIndexedError, StoredFileNotFoundError, UnreadableDocumentError,
            ExternalServiceError (o que já foi descrito fica guardado para a próxima vez).
        """
        _ensure_indexed(manual)
        content = await self._storage.read(original_file_key(manual.id))
        version = content_hash(content)
        pages = await self._parser.parse(content)

        described: list[FigureDescription] = []

        def collect(description: FigureDescription) -> None:
            described.append(description)
            if on_page is not None:
                on_page(description)

        descriptions = await self._figures.describe(
            manual, content, pages, version=version, on_page=collect
        )
        chunks = figure_chunks(manual, descriptions)
        embeddings = await self._embeddings.embed_documents([c.embedding_text for c in chunks])
        if len(embeddings) != len(chunks):
            raise ExternalServiceError(
                f"O provedor retornou {len(embeddings)} embeddings para {len(chunks)} trechos"
            )

        # O manual pode ter sido reprocessado durante as chamadas à IA: só grava sobre
        # a mesma versão do arquivo, ainda indexada.
        current = await self._repository.get(manual.id)
        if current is None or current.status is not ManualStatus.INDEXED:
            raise ManualNotIndexedError(current or manual)
        stored = await self._storage.read(original_file_key(manual.id))
        if content_hash(stored) != version:
            raise ExternalServiceError(
                f"O arquivo de '{manual.title}' mudou durante a descrição; rode de novo"
            )

        await self._vector_store.delete_by_manual(manual.id, kind=ChunkKind.FIGURE)
        await self._vector_store.upsert(
            [EmbeddedChunk(c, e) for c, e in zip(chunks, embeddings, strict=True)]
        )
        current.record_figures(len(chunks))
        await self._repository.save(current)
        logger.info(
            "Figuras do manual %s: %d descritas agora, %d no índice",
            manual.id,
            len(described),
            len(chunks),
        )
        return FigureResult(current, described, len(chunks))


def _ensure_indexed(manual: Manual) -> None:
    if manual.status is not ManualStatus.INDEXED:
        raise ManualNotIndexedError(manual)


class FiguresAlreadyRunningError(ApplicationError):
    def __init__(self, manual: Manual) -> None:
        super().__init__(f"As figuras de '{manual.title}' já estão sendo descritas")


@dataclass(slots=True)
class FigureJob:
    """Andamento da descrição das figuras de um manual, disparada pela tela."""

    running: bool = True
    described: int = 0  # páginas descritas até agora
    error: str | None = None  # por que parou (o que já foi descrito fica guardado)


@dataclass(slots=True)
class FigureDescriptionService:
    """Descrever as figuras de um manual indexado pela tela, em segundo plano.

    Um pedido por manual de cada vez. O andamento fica em memória (a API roda num
    processo só): reiniciar a API apaga o andamento, não as descrições já gravadas.
    """

    use_case: DescribeFiguresUseCase
    repository: ManualRepository
    _jobs: dict[ManualId, FigureJob] = field(default_factory=dict)
    _tasks: dict[ManualId, asyncio.Task[None]] = field(default_factory=dict)

    def job(self, manual_id: ManualId) -> FigureJob | None:
        return self._jobs.get(manual_id)

    async def plan(self, manual_id: ManualId) -> FigurePlanItem:
        """
        Raises:
            ManualNotFoundError, StoredFileNotFoundError, UnreadableDocumentError.
        """
        return await self.use_case.plan(await self._get(manual_id))

    async def start(self, manual_id: ManualId) -> Manual:
        """Valida e devolve na hora; a descrição continua em segundo plano.

        Raises:
            ManualNotFoundError, ManualNotIndexedError, FiguresAlreadyRunningError.
        """
        manual = await self._get(manual_id)
        _ensure_indexed(manual)
        current = self._jobs.get(manual_id)
        if current is not None and current.running:
            raise FiguresAlreadyRunningError(manual)
        job = FigureJob()
        self._jobs[manual_id] = job
        self._tasks[manual_id] = asyncio.create_task(self._run(manual, job))
        return manual

    async def wait(self) -> None:
        """Espera as descrições em andamento terminarem (usado nos testes)."""
        for task in list(self._tasks.values()):
            with suppress(asyncio.CancelledError):
                await task

    async def stop(self) -> None:
        """Interrompe as descrições em andamento (desligamento da API)."""
        for task in self._tasks.values():
            task.cancel()
        await self.wait()

    async def _run(self, manual: Manual, job: FigureJob) -> None:
        def count(_: FigureDescription) -> None:
            job.described += 1

        try:
            await self.use_case.execute(manual, on_page=count)
        except asyncio.CancelledError:
            job.error = "a API foi desligada no meio da descrição; peça de novo"
            raise
        except (ApplicationError, DomainError) as error:
            job.error = str(error)
            logger.warning("Falha ao descrever as figuras do manual %s: %s", manual.id, error)
        except Exception:
            job.error = "Erro inesperado ao descrever as figuras. Tente de novo."
            logger.exception("Falha ao descrever as figuras do manual %s", manual.id)
        finally:
            job.running = False
            self._tasks.pop(manual.id, None)

    async def _get(self, manual_id: ManualId) -> Manual:
        manual = await self.repository.get(manual_id)
        if manual is None:
            raise ManualNotFoundError(manual_id)
        return manual
