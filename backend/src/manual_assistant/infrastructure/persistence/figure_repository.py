from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.manual import ManualId
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import FigureDescriptionRecord


class SqlAlchemyFigureDescriptionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list(self, manual_id: ManualId, content_hash: str) -> Sequence[FigureDescription]:
        statement = (
            select(FigureDescriptionRecord)
            .where(FigureDescriptionRecord.manual_id == manual_id)
            .where(FigureDescriptionRecord.content_hash == content_hash)
            .order_by(FigureDescriptionRecord.page)
        )
        async with (
            translate_database_errors("buscar as descrições de figuras"),
            self._session_factory() as session,
        ):
            records = (await session.scalars(statement)).all()
        return [
            FigureDescription(
                page=record.page,
                text=record.text,
                model=record.model,
                described_at=record.described_at,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
            )
            for record in records
        ]

    async def add(
        self, manual_id: ManualId, content_hash: str, description: FigureDescription
    ) -> None:
        values = {
            "manual_id": manual_id,
            "page": description.page,
            "content_hash": content_hash,
            "text": description.text,
            "model": description.model,
            "input_tokens": description.input_tokens,
            "output_tokens": description.output_tokens,
            "described_at": description.described_at,
        }
        statement = insert(FigureDescriptionRecord).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[FigureDescriptionRecord.manual_id, FigureDescriptionRecord.page],
            set_={
                column: statement.excluded[column]
                for column in values
                if column not in ("manual_id", "page")
            },
        )
        async with (
            translate_database_errors("salvar a descrição de figuras"),
            self._session_factory.begin() as session,
        ):
            await session.execute(statement)

    async def delete_other_versions(self, manual_id: ManualId, content_hash: str) -> int:
        statement = (
            delete(FigureDescriptionRecord)
            .where(FigureDescriptionRecord.manual_id == manual_id)
            .where(FigureDescriptionRecord.content_hash != content_hash)
        )
        async with (
            translate_database_errors("apagar descrições de figuras antigas"),
            self._session_factory.begin() as session,
        ):
            result = await session.execute(statement)
        return int(getattr(result, "rowcount", 0) or 0)
