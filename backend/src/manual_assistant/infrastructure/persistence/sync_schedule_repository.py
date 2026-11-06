from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.sync_schedule import SyncSchedule
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import SyncScheduleRecord

_SINGLE_ROW_ID = 1


class SqlAlchemySyncScheduleRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self) -> SyncSchedule:
        async with (
            translate_database_errors("consultar o agendamento da sincronização"),
            self._session_factory() as db,
        ):
            record = await db.get(SyncScheduleRecord, _SINGLE_ROW_ID)
        if record is None:
            return SyncSchedule()
        return SyncSchedule(
            enabled=record.enabled,
            time_of_day=record.time_of_day,
            describe_figures=record.describe_figures,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
            last_triggered_at=record.last_triggered_at,
            last_trigger_error=record.last_trigger_error,
        )

    async def save(self, schedule: SyncSchedule) -> None:
        values: dict[str, Any] = {
            "enabled": schedule.enabled,
            "time_of_day": schedule.time_of_day,
            "describe_figures": schedule.describe_figures,
            "updated_at": schedule.updated_at,
            "updated_by": schedule.updated_by,
            "last_triggered_at": schedule.last_triggered_at,
            "last_trigger_error": schedule.last_trigger_error,
        }
        statement = insert(SyncScheduleRecord).values(id=_SINGLE_ROW_ID, **values)
        statement = statement.on_conflict_do_update(
            index_elements=[SyncScheduleRecord.id], set_=values
        )
        async with (
            translate_database_errors("salvar o agendamento da sincronização"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)
