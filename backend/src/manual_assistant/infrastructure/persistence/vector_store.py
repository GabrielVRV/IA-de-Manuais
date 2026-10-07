from collections.abc import Sequence

from sqlalchemy import ColumnElement, Float, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.application.ports.vector_store import EmbeddedChunk
from manual_assistant.domain.chunk import Chunk, ChunkId, ScoredChunk
from manual_assistant.domain.manual import ManualId, ManualStatus
from manual_assistant.domain.pages import PageRange
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import (
    EMBEDDING_DIMENSIONS,
    ChunkRecord,
    ManualRecord,
)

_UPDATABLE_COLUMNS = ("position", "text", "page_start", "page_end", "embedding")


class PgVectorStore:
    """Índice vetorial no próprio PostgreSQL (extensão pgvector), por distância de cosseno."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        dimensions: int = EMBEDDING_DIMENSIONS,
    ) -> None:
        self._session_factory = session_factory
        self._dimensions = dimensions

    async def upsert(self, items: Sequence[EmbeddedChunk]) -> None:
        if not items:
            return
        rows = [self._to_row(item) for item in items]
        statement = insert(ChunkRecord)
        statement = statement.on_conflict_do_update(
            index_elements=[ChunkRecord.id],
            set_={column: statement.excluded[column] for column in _UPDATABLE_COLUMNS},
        )
        async with (
            translate_database_errors("indexar os trechos"),
            self._session_factory.begin() as session,
        ):
            await session.execute(statement, rows)

    async def search(
        self,
        query: Embedding,
        *,
        limit: int,
        min_score: float = 0.0,
    ) -> Sequence[ScoredChunk]:
        if limit < 1:
            raise ValueError("O limite de resultados deve ser ao menos 1")
        self._ensure_dimensions(query)

        distance = _cosine_distance(query)
        statement = (
            select(
                ChunkRecord.id,
                ChunkRecord.manual_id,
                ChunkRecord.position,
                ChunkRecord.text,
                ChunkRecord.page_start,
                ChunkRecord.page_end,
                ManualRecord.title,
                distance.label("distance"),
            )
            .join(ManualRecord, ManualRecord.id == ChunkRecord.manual_id)
            # Regra do domínio: só manuais indexados aparecem nas respostas.
            .where(ManualRecord.status == ManualStatus.INDEXED.value)
            .where(distance <= 1.0 - min_score)
            .order_by(distance)
            .limit(limit)
        )
        async with translate_database_errors("buscar trechos"), self._session_factory() as session:
            rows = (await session.execute(statement)).all()

        return [
            ScoredChunk(
                chunk=Chunk(
                    id=ChunkId(row.id),
                    manual_id=ManualId(row.manual_id),
                    manual_title=row.title,
                    text=row.text,
                    pages=PageRange(row.page_start, row.page_end),
                    position=row.position,
                ),
                score=_similarity(row.distance),
            )
            for row in rows
        ]

    async def delete_by_manual(self, manual_id: ManualId) -> None:
        statement = delete(ChunkRecord).where(ChunkRecord.manual_id == manual_id)
        async with (
            translate_database_errors("remover os trechos do manual"),
            self._session_factory.begin() as session,
        ):
            await session.execute(statement)

    def _to_row(self, item: EmbeddedChunk) -> dict[str, object]:
        self._ensure_dimensions(item.embedding)
        chunk = item.chunk
        return {
            "id": chunk.id,
            "manual_id": chunk.manual_id,
            "position": chunk.position,
            "text": chunk.text,
            "page_start": chunk.pages.start,
            "page_end": chunk.pages.end,
            "embedding": list(item.embedding),
        }

    def _ensure_dimensions(self, embedding: Embedding) -> None:
        if len(embedding) != self._dimensions:
            raise ValueError(
                f"Embedding com {len(embedding)} dimensões; o índice espera {self._dimensions}"
            )


def _cosine_distance(query: Embedding) -> ColumnElement[float]:
    """Operador <=> do pgvector: 0 = mesma direção, 1 = sem relação, 2 = opostos."""
    return ChunkRecord.embedding.op("<=>", return_type=Float)(list(query))


def _similarity(distance: float) -> float:
    """Converte distância de cosseno em relevância de 0 a 1 (negativos viram 0)."""
    return min(1.0, max(0.0, 1.0 - distance))
