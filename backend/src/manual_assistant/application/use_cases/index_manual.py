import logging

from manual_assistant.application.errors import (
    ExternalServiceError,
    ManualNotFoundError,
    StoredFileNotFoundError,
    UnreadableDocumentError,
)
from manual_assistant.application.ports.document_parser import DocumentParser
from manual_assistant.application.ports.embedding_provider import EmbeddingProvider
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.ports.text_chunker import TextChunker
from manual_assistant.application.ports.vector_store import EmbeddedChunk, VectorStore
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.chunk import Chunk
from manual_assistant.domain.manual import Manual, ManualId

logger = logging.getLogger(__name__)


class IndexManualUseCase:
    """Lê o PDF de um manual, divide em trechos, gera embeddings e indexa.

    Pode ser executado de novo para reprocessar um manual: os trechos antigos são
    substituídos. Nunca deixa o manual travado em "processando": qualquer falha é
    registrada no próprio manual.
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
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._parser = parser
        self._chunker = chunker
        self._embeddings = embeddings
        self._vector_store = vector_store

    async def execute(self, manual_id: ManualId) -> Manual:
        return await self.run(await self.prepare(manual_id))

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

    async def run(self, manual: Manual) -> Manual:
        """Etapa demorada: indexa um manual já preparado e registra o resultado nele."""
        # Captura tudo de propósito: o resultado, sucesso ou falha, precisa ficar no manual.
        try:
            page_count, chunk_count = await self._index(manual)
        except Exception as error:
            manual.mark_failed(_failure_reason(error))
            logger.warning(
                "Falha ao indexar o manual %s: %s", manual.id, manual.failure_reason, exc_info=True
            )
        else:
            manual.mark_indexed(page_count=page_count, chunk_count=chunk_count)
            logger.info("Manual %s indexado: %d trechos", manual.id, chunk_count)

        await self._repository.save(manual)
        return manual

    async def _index(self, manual: Manual) -> tuple[int, int]:
        content = await self._storage.read(original_file_key(manual.id))
        pages = await self._parser.parse(content)
        fragments = self._chunker.split(pages)
        if not fragments:
            raise UnreadableDocumentError("O documento não contém texto aproveitável")

        embeddings = await self._embeddings.embed_documents([f.text for f in fragments])
        if len(embeddings) != len(fragments):
            raise ExternalServiceError(
                f"O provedor retornou {len(embeddings)} embeddings para {len(fragments)} trechos"
            )

        chunks = [
            Chunk.create(manual=manual, text=fragment.text, pages=fragment.pages, position=index)
            for index, fragment in enumerate(fragments)
        ]
        # Os embeddings são gerados antes de apagar os trechos antigos: se o provedor
        # falhar, o índice anterior continua intacto.
        await self._vector_store.delete_by_manual(manual.id)
        await self._vector_store.upsert(
            [
                EmbeddedChunk(chunk, embedding)
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
        )
        return len(pages), len(chunks)


def _failure_reason(error: Exception) -> str:
    """Mensagem que o administrador verá no manual (sem detalhes técnicos internos)."""
    if isinstance(error, UnreadableDocumentError | StoredFileNotFoundError):
        return str(error)
    if isinstance(error, ExternalServiceError):
        return "Falha em um serviço externo (IA ou banco de dados). Tente reprocessar o manual."
    return "Erro inesperado durante a indexação. Tente reprocessar o manual."
