from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Protocol

from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.domain.chunk import Chunk, ChunkKind, ScoredChunk
from manual_assistant.domain.manual import ManualId


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    chunk: Chunk
    embedding: Embedding


class VectorStore(Protocol):
    """Índice de trechos pesquisável por similaridade semântica.

    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def upsert(self, items: Sequence[EmbeddedChunk]) -> None: ...

    async def search(
        self,
        query: Embedding,
        *,
        limit: int,
        min_score: float = 0.0,
        manual_ids: Collection[ManualId] | None = None,
    ) -> Sequence[ScoredChunk]:
        """Trechos mais parecidos com a consulta, do mais para o menos relevante.

        Retorna apenas trechos de manuais indexados (``Manual.is_searchable``). Com
        ``manual_ids``, só trechos desses manuais.
        """
        ...

    async def search_codes(
        self,
        codes: Collection[str],
        *,
        limit: int,
        manual_ids: Collection[ManualId] | None = None,
    ) -> Sequence[ScoredChunk]:
        """Trechos que contêm literalmente algum dos códigos (``domain.codes.compact``:
        pontos, hífens e barras não contam), os que contêm mais códigos primeiro."""
        ...

    async def delete_by_manual(self, manual_id: ManualId, *, kind: ChunkKind | None = None) -> None:
        """Apaga os trechos do manual; com ``kind``, só os desse tipo."""
        ...
