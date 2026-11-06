import logging
from collections.abc import Sequence

from manual_assistant.application.errors import (
    ExternalServiceError,
    ManualNotFoundError,
    StoredFileNotFoundError,
    UnreadableDocumentError,
)
from manual_assistant.application.figures import (
    FigureDescriber,
    content_hash,
    figure_chunk_text,
)
from manual_assistant.application.ports.document_parser import DocumentParser
from manual_assistant.application.ports.embedding_provider import EmbeddingProvider
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.ports.text_chunker import TextChunker, TextFragment
from manual_assistant.application.ports.vector_store import EmbeddedChunk, VectorStore
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.chunk import Chunk, ChunkKind
from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.manual import Manual, ManualId
from manual_assistant.domain.pages import Page, PageRange

logger = logging.getLogger(__name__)


class IndexManualUseCase:
    """Lê o PDF de um manual, divide em trechos, gera embeddings e indexa.

    Pode ser executado de novo para reprocessar um manual: os trechos antigos são
    substituídos. Nunca deixa o manual travado em "processando": qualquer falha é
    registrada no próprio manual.

    Com ``figures``, as descrições de figuras já pagas desta versão do arquivo voltam
    para o índice; quem pede a indexação escolhe (``describe_figures``) se as páginas que
    faltam também são descritas pela IA (ADR 0014).
    """

    def __init__(
        self,
        *,
        repository: ManualRepository,
        storage: FileStorage,
        parser: DocumentParser,
        chunker: TextChunker,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        figures: FigureDescriber | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._parser = parser
        self._chunker = chunker
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._figures = figures

    async def execute(self, manual_id: ManualId, *, describe_figures: bool = False) -> Manual:
        return await self.run(await self.prepare(manual_id), describe_figures=describe_figures)

    async def prepare(self, manual_id: ManualId) -> Manual:
        """Etapa rápida e síncrona: valida e marca como "processando".

        Separada de ``run`` para que a API responda na hora (404, 409) e deixe o
        trabalho pesado em segundo plano.

        Raises:
            ManualNotFoundError: se o manual não existir.
            InvalidStateTransitionError: se ele já estiver em processamento.
        """
        manual = await self._repository.get(manual_id)
        if manual is None:
            raise ManualNotFoundError(manual_id)
        manual.start_processing()
        await self._repository.save(manual)
        return manual

    async def run(self, manual: Manual, *, describe_figures: bool = False) -> Manual:
        """Etapa demorada: indexa um manual já preparado e registra o resultado nele.

        ``describe_figures``: envia à IA as páginas com figuras ainda não descritas (uma
        chamada por página). Sem ele, só as descrições já guardadas entram no índice.
        """
        describe = describe_figures and self._figures is not None
        # Captura tudo de propósito: o resultado, sucesso ou falha, precisa ficar no manual.
        try:
            page_count, chunk_count, figure_count = await self._index(manual, describe)
        except Exception as error:
            manual.mark_failed(_failure_reason(error))
            logger.warning(
                "Falha ao indexar o manual %s: %s", manual.id, manual.failure_reason, exc_info=True
            )
        else:
            manual.mark_indexed(
                page_count=page_count, chunk_count=chunk_count, figure_count=figure_count
            )
            logger.info(
                "Manual %s indexado: %d trechos, %d páginas com figuras",
                manual.id,
                chunk_count,
                figure_count,
            )

        await self._repository.save(manual)
        return manual

    async def _index(self, manual: Manual, describe: bool) -> tuple[int, int, int]:
        content = await self._storage.read(original_file_key(manual.id))
        pages = await self._parser.parse(content)
        fragments = self._chunker.split(pages)
        version = content_hash(content)
        figures = [
            d
            for d in await self._figure_descriptions(
                manual, content, pages, version, fragments, describe=describe
            )
            if d.has_content
        ]
        if not fragments and not figures:
            raise UnreadableDocumentError(_no_content_message(describe))

        chunks = [
            Chunk.create(manual=manual, text=fragment.text, pages=fragment.pages, position=index)
            for index, fragment in enumerate(fragments)
        ] + figure_chunks(manual, figures)
        embeddings = await self._embeddings.embed_documents([c.embedding_text for c in chunks])
        if len(embeddings) != len(chunks):
            raise ExternalServiceError(
                f"O provedor retornou {len(embeddings)} embeddings para {len(chunks)} trechos"
            )

        # Os embeddings são gerados antes de apagar os trechos antigos: se o provedor
        # falhar, o índice anterior continua intacto.
        await self._vector_store.delete_by_manual(manual.id)
        await self._vector_store.upsert(
            [
                EmbeddedChunk(chunk, embedding)
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
        )
        if self._figures is not None:
            await self._figures.discard_other_versions(manual.id, version)
        return len(pages), len(fragments), len(figures)

    async def _figure_descriptions(
        self,
        manual: Manual,
        content: bytes,
        pages: Sequence[Page],
        version: str,
        fragments: Sequence[TextFragment],
        *,
        describe: bool,
    ) -> list[FigureDescription]:
        if self._figures is None:
            return []
        if not describe:
            return await self._figures.cached(manual.id, version)
        try:
            return await self._figures.describe(manual, content, pages, version=version)
        except ExternalServiceError:
            # Sem texto (escaneado), as figuras são tudo o que há: a falha é do manual.
            if not fragments:
                raise
            # Com texto, o manual é indexado mesmo assim; as figuras que faltaram ficam
            # para o botão "Descrever figuras" ou para o próximo reprocessamento.
            logger.warning(
                "Falha ao descrever as figuras do manual %s; indexando só o texto",
                manual.id,
                exc_info=True,
            )
            return await self._figures.cached(manual.id, version)


def _no_content_message(described: bool) -> str:
    if described:
        return "O PDF não contém texto nem figuras aproveitáveis"
    return (
        "O PDF não contém texto selecionável. Se for um documento escaneado, clique em "
        "Descrever figuras para a IA ler as páginas"
    )


def figure_chunks(manual: Manual, figures: Sequence[FigureDescription]) -> list[Chunk]:
    """Um trecho por página com figuras descritas, citado pela própria página."""
    with_content = [description for description in figures if description.has_content]
    return [
        Chunk.create(
            manual=manual,
            text=figure_chunk_text(description),
            pages=PageRange.single(description.page),
            position=index,
            kind=ChunkKind.FIGURE,
        )
        for index, description in enumerate(with_content)
    ]


def _failure_reason(error: Exception) -> str:
    """Mensagem que o administrador verá no manual (sem detalhes técnicos internos)."""
    if isinstance(error, UnreadableDocumentError | StoredFileNotFoundError):
        return str(error)
    if isinstance(error, ExternalServiceError):
        return "Falha em um serviço externo (IA ou banco de dados). Tente reprocessar o manual."
    return "Erro inesperado durante a indexação. Tente reprocessar o manual."
