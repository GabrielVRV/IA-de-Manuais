from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.domain.manual import Manual, ManualId, ManualStatus, SourceFile
from manual_assistant.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from manual_assistant.infrastructure.persistence.manual_repository import (
    SqlAlchemyManualRepository,
)
from tests.factories import FIXED_NOW, make_manual

pytestmark = [pytest.mark.anyio, pytest.mark.db]


@pytest.fixture
def repository(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyManualRepository:
    return SqlAlchemyManualRepository(session_factory)


async def test_saves_and_restores_every_field(repository: SqlAlchemyManualRepository) -> None:
    manual = make_manual()
    manual.start_processing()
    manual.mark_failed("PDF protegido por senha")

    await repository.save(manual)
    restored = await repository.get(manual.id)

    assert restored is not None
    assert (
        restored.id,
        restored.title,
        restored.file_name,
        restored.created_at,
        restored.status,
        restored.failure_reason,
    ) == (
        manual.id,
        manual.title,
        manual.file_name,
        manual.created_at,
        ManualStatus.FAILED,
        "PDF protegido por senha",
    )


async def test_saving_again_updates_the_manual(repository: SqlAlchemyManualRepository) -> None:
    manual = make_manual()
    await repository.save(manual)

    manual.start_processing()
    manual.mark_indexed(page_count=42, chunk_count=130)
    await repository.save(manual)

    restored = await repository.get(manual.id)
    assert restored is not None
    assert restored.status is ManualStatus.INDEXED
    assert (restored.page_count, restored.chunk_count) == (42, 130)


async def test_returns_none_for_unknown_manual(repository: SqlAlchemyManualRepository) -> None:
    assert await repository.get(ManualId(uuid4())) is None


async def test_lists_newest_first(repository: SqlAlchemyManualRepository) -> None:
    older = Manual.register(title="Antigo", file_name="a.pdf", now=FIXED_NOW)
    newer = Manual.register(title="Novo", file_name="b.pdf", now=FIXED_NOW + timedelta(days=1))
    await repository.save(older)
    await repository.save(newer)

    assert [m.title for m in await repository.list_all()] == ["Novo", "Antigo"]


async def test_saves_and_restores_the_source_file(repository: SqlAlchemyManualRepository) -> None:
    source = SourceFile(key="95007003P", fingerprint="1024-1700000000", content_hash="a" * 64)
    manual = Manual.register(title="Incubadora", file_name="95007003-01P.pdf", now=FIXED_NOW)
    manual.update_from_source(title="Incubadora", file_name="95007003-01P.pdf", source=source)
    uploaded = make_manual()

    await repository.save(manual)
    await repository.save(uploaded)

    restored, restored_uploaded = await repository.get(manual.id), await repository.get(uploaded.id)
    assert restored is not None
    assert restored_uploaded is not None
    assert restored.source == source
    assert restored_uploaded.source is None


async def test_deletes_the_manual(repository: SqlAlchemyManualRepository) -> None:
    manual = make_manual()
    await repository.save(manual)

    await repository.delete(manual.id)

    assert await repository.get(manual.id) is None


async def test_translates_connection_failures() -> None:
    unreachable = URL.create(
        "postgresql+asyncpg", username="x", password="x", host="127.0.0.1", port=1, database="x"
    )
    engine = create_database_engine(unreachable)
    repository = SqlAlchemyManualRepository(create_session_factory(engine))

    with pytest.raises(ExternalServiceError):
        await repository.list_all()
    await engine.dispose()
