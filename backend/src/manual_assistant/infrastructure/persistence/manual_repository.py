from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.manual import Manual, ManualId, ManualStatus, SourceFile
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import ManualRecord

# Campos que nunca mudam depois do cadastro.
_IMMUTABLE_COLUMNS = frozenset({"id", "created_at"})


class SqlAlchemyManualRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, manual: Manual) -> None:
        values = _to_row(manual)
        statement = insert(ManualRecord).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[ManualRecord.id],
            set_={
                **{
                    column: statement.excluded[column]
                    for column in values
                    if column not in _IMMUTABLE_COLUMNS
                },
                "updated_at": func.now(),
            },
        )
        async with (
            translate_database_errors("salvar o manual"),
            self._session_factory.begin() as session,
        ):
            await session.execute(statement)

    async def get(self, manual_id: ManualId) -> Manual | None:
        async with translate_database_errors("buscar o manual"), self._session_factory() as session:
            record = await session.get(ManualRecord, manual_id)
        return _to_entity(record) if record else None

    async def list_all(self) -> Sequence[Manual]:
        statement = select(ManualRecord).order_by(ManualRecord.created_at.desc())
        async with (
            translate_database_errors("listar os manuais"),
            self._session_factory() as session,
        ):
            records = (await session.scalars(statement)).all()
        return [_to_entity(record) for record in records]

    async def delete(self, manual_id: ManualId) -> None:
        statement = delete(ManualRecord).where(ManualRecord.id == manual_id)
        async with (
            translate_database_errors("excluir o manual"),
            self._session_factory.begin() as session,
        ):
            await session.execute(statement)


def _to_row(manual: Manual) -> dict[str, Any]:
    return {
        "id": manual.id,
        "title": manual.title,
        "file_name": manual.file_name,
        "status": manual.status.value,
        "page_count": manual.page_count,
        "chunk_count": manual.chunk_count,
        "failure_reason": manual.failure_reason,
        "source_key": manual.source.key if manual.source else None,
        "source_fingerprint": manual.source.fingerprint if manual.source else None,
        "source_content_hash": manual.source.content_hash if manual.source else None,
        "created_at": manual.created_at,
    }


def _to_entity(record: ManualRecord) -> Manual:
    return Manual(
        id=ManualId(record.id),
        title=record.title,
        file_name=record.file_name,
        created_at=record.created_at,
        status=ManualStatus(record.status),
        page_count=record.page_count,
        chunk_count=record.chunk_count,
        failure_reason=record.failure_reason,
        source=_source_of(record),
    )


def _source_of(record: ManualRecord) -> SourceFile | None:
    # A regra source_complete do banco garante que os três vêm juntos.
    if record.source_key is None or record.source_fingerprint is None:
        return None
    if record.source_content_hash is None:
        return None
    return SourceFile(
        key=record.source_key,
        fingerprint=record.source_fingerprint,
        content_hash=record.source_content_hash,
    )
