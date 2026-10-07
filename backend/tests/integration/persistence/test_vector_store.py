import math

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.application.ports.vector_store import EmbeddedChunk
from manual_assistant.domain.manual import Manual
from manual_assistant.domain.pages import PageRange
from manual_assistant.infrastructure.persistence.manual_repository import (
    SqlAlchemyManualRepository,
)
from manual_assistant.infrastructure.persistence.models import EMBEDDING_DIMENSIONS
from manual_assistant.infrastructure.persistence.vector_store import PgVectorStore
from tests.factories import make_chunk, make_manual

pytestmark = [pytest.mark.anyio, pytest.mark.db]


def vector(**weights: float) -> Embedding:
    """Vetor com pesos nos eixos informados, ex.: vector(a=1, b=1). Eixos: a=0, b=1, c=2."""
    values = [0.0] * EMBEDDING_DIMENSIONS
    for axis, weight in weights.items():
        values["abc".index(axis)] = weight
    return tuple(values)


@pytest.fixture
def store(session_factory: async_sessionmaker[AsyncSession]) -> PgVectorStore:
    return PgVectorStore(session_factory)


@pytest.fixture
def repository(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyManualRepository:
    return SqlAlchemyManualRepository(session_factory)


async def indexed_manual(repository: SqlAlchemyManualRepository, title: str) -> Manual:
    manual = make_manual(title)
    manual.start_processing()
    manual.mark_indexed(page_count=10, chunk_count=3)
    await repository.save(manual)
    return manual


async def test_returns_most_similar_chunks_first(
    store: PgVectorStore, repository: SqlAlchemyManualRepository
) -> None:
    manual = await indexed_manual(repository, "Manual da Prensa")
    exact = make_chunk(manual, text="exato", pages=PageRange(2, 3), position=0)
    close = make_chunk(manual, text="parecido", position=1)
    unrelated = make_chunk(manual, text="sem relação", position=2)
    await store.upsert(
        [
            EmbeddedChunk(unrelated, vector(c=1)),
            EmbeddedChunk(close, vector(a=1, b=1)),
            EmbeddedChunk(exact, vector(a=1)),
        ]
    )

    results = await store.search(vector(a=1), limit=3)

    assert [r.chunk.text for r in results] == ["exato", "parecido", "sem relação"]
    assert results[0].chunk == exact
    assert results[0].score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(math.cos(math.pi / 4))  # 45 graus
    assert results[2].score == pytest.approx(0.0)


async def test_respects_limit_and_minimum_score(
    store: PgVectorStore, repository: SqlAlchemyManualRepository
) -> None:
    manual = await indexed_manual(repository, "Manual")
    await store.upsert(
        [
            EmbeddedChunk(make_chunk(manual, text="a", position=0), vector(a=1)),
            EmbeddedChunk(make_chunk(manual, text="ab", position=1), vector(a=1, b=1)),
            EmbeddedChunk(make_chunk(manual, text="c", position=2), vector(c=1)),
        ]
    )

    assert [r.chunk.text for r in await store.search(vector(a=1), limit=1)] == ["a"]
    relevant = await store.search(vector(a=1), limit=10, min_score=0.5)
    assert [r.chunk.text for r in relevant] == ["a", "ab"]


async def test_ignores_manuals_that_are_not_indexed(
    store: PgVectorStore, repository: SqlAlchemyManualRepository
) -> None:
    ready = await indexed_manual(repository, "Pronto")
    in_progress = make_manual("Em processamento")
    in_progress.start_processing()
    await repository.save(in_progress)
    await store.upsert(
        [
            EmbeddedChunk(make_chunk(ready, text="pronto"), vector(a=1)),
            EmbeddedChunk(make_chunk(in_progress, text="parcial"), vector(a=1)),
        ]
    )

    results = await store.search(vector(a=1), limit=10)

    assert [r.chunk.manual_title for r in results] == ["Pronto"]


async def test_upsert_replaces_an_existing_chunk(
    store: PgVectorStore, repository: SqlAlchemyManualRepository
) -> None:
    manual = await indexed_manual(repository, "Manual")
    chunk = make_chunk(manual, text="texto")
    await store.upsert([EmbeddedChunk(chunk, vector(a=1))])

    await store.upsert([EmbeddedChunk(chunk, vector(b=1))])

    results = await store.search(vector(b=1), limit=10)
    assert len(results) == 1
    assert results[0].score == pytest.approx(1.0)


async def test_removes_chunks_by_manual_and_on_manual_deletion(
    store: PgVectorStore, repository: SqlAlchemyManualRepository
) -> None:
    first = await indexed_manual(repository, "Primeiro")
    second = await indexed_manual(repository, "Segundo")
    await store.upsert(
        [
            EmbeddedChunk(make_chunk(first), vector(a=1)),
            EmbeddedChunk(make_chunk(second), vector(a=1)),
        ]
    )

    await store.delete_by_manual(first.id)
    assert [r.chunk.manual_title for r in await store.search(vector(a=1), limit=10)] == ["Segundo"]

    await repository.delete(second.id)  # ON DELETE CASCADE
    assert await store.search(vector(a=1), limit=10) == []


async def test_rejects_embeddings_with_wrong_dimensions(store: PgVectorStore) -> None:
    with pytest.raises(ValueError, match="dimensões"):
        await store.upsert([EmbeddedChunk(make_chunk(), (1.0, 0.0))])
    with pytest.raises(ValueError, match="dimensões"):
        await store.search((1.0,), limit=1)


async def test_rejects_invalid_limit(store: PgVectorStore) -> None:
    with pytest.raises(ValueError, match="limite"):
        await store.search(vector(a=1), limit=0)


async def test_upserting_nothing_is_a_no_op(store: PgVectorStore) -> None:
    await store.upsert([])
