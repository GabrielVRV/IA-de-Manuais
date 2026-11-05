from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.application.ports.usage_repository import UsageAggregate
from manual_assistant.domain.usage import QuestionUsage
from manual_assistant.domain.user import UserId
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import QuestionUsageRecord


class SqlAlchemyUsageRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, usage: QuestionUsage) -> None:
        statement = insert(QuestionUsageRecord).values(
            user_id=usage.user_id,
            asked_at=usage.asked_at,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        async with (
            translate_database_errors("registrar o consumo"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)

    async def aggregate(
        self, *, since: datetime, until: datetime, timezone: ZoneInfo
    ) -> Sequence[UsageAggregate]:
        record = QuestionUsageRecord
        # O dia no relógio da empresa, e não em UTC. Calculado numa subconsulta para o
        # GROUP BY usar a coluna pronta (o parâmetro do fuso não se repete).
        rows = (
            select(
                record.user_id,
                record.model,
                func.date(func.timezone(timezone.key, record.asked_at)).label("day"),
                record.input_tokens,
                record.output_tokens,
            )
            .where(record.asked_at >= since, record.asked_at < until)
            .subquery()
        )
        statement = select(
            rows.c.user_id,
            rows.c.model,
            rows.c.day,
            func.count(),
            func.sum(rows.c.input_tokens),
            func.sum(rows.c.output_tokens),
        ).group_by(rows.c.user_id, rows.c.model, rows.c.day)
        async with (
            translate_database_errors("consultar o consumo"),
            self._session_factory() as db,
        ):
            result = (await db.execute(statement)).all()
        return [
            UsageAggregate(
                user_id=UserId(user_id),
                model=model,
                day=day,
                questions=questions,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
            )
            for user_id, model, day, questions, input_tokens, output_tokens in result
        ]

    async def models(self) -> Sequence[str]:
        statement = (
            select(QuestionUsageRecord.model)
            .where(QuestionUsageRecord.model.is_not(None))
            .distinct()
            .order_by(QuestionUsageRecord.model)
        )
        async with (
            translate_database_errors("listar os modelos usados"),
            self._session_factory() as db,
        ):
            return [model for model in (await db.scalars(statement)).all() if model]

    async def delete_before(self, cutoff: datetime) -> int:
        statement = (
            delete(QuestionUsageRecord)
            .where(QuestionUsageRecord.asked_at < cutoff)
            .returning(QuestionUsageRecord.id)
        )
        async with (
            translate_database_errors("apagar o consumo antigo"),
            self._session_factory.begin() as db,
        ):
            return len((await db.scalars(statement)).all())
