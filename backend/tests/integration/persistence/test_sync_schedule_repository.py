from datetime import time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.sync_schedule import SyncSchedule
from manual_assistant.infrastructure.persistence.sync_schedule_repository import (
    SqlAlchemySyncScheduleRepository,
)
from tests.factories import FIXED_NOW

pytestmark = [pytest.mark.db, pytest.mark.anyio]


async def test_starts_disabled_and_keeps_what_is_saved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySyncScheduleRepository(session_factory)

    assert await repository.get() == SyncSchedule()

    configured = SyncSchedule().change(
        enabled=True,
        time_of_day=time(23, 30),
        now=FIXED_NOW,
        author="Ana Admin",
        describe_figures=True,
    )
    await repository.save(configured)
    ran = configured.triggered(FIXED_NOW + timedelta(days=1), error="pasta vazia")
    await repository.save(ran)

    assert await repository.get() == ran
