from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from manual_assistant.application.errors import PermissionDeniedError
from manual_assistant.application.use_cases.sync_manuals import (
    ManualSyncService,
    SyncNotConfiguredError,
)
from manual_assistant.application.use_cases.sync_schedule import (
    SCHEDULED_BY,
    GetSyncScheduleUseCase,
    RunScheduledSyncUseCase,
    UpdateSyncScheduleUseCase,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.sync_schedule import SyncSchedule
from manual_assistant.domain.user import UserRole
from tests.fakes import InMemorySyncScheduleRepository
from tests.security import make_user
from tests.unit.application.test_sync_manuals import Context as SyncContext

pytestmark = pytest.mark.anyio

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
admin = make_user("admin", role=UserRole.ADMIN)
maria = make_user("maria")


def local(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=SAO_PAULO)


class Context:
    def __init__(self, *, sync_configured: bool = True) -> None:
        self.now = local(5, 10)
        self.folder = SyncContext()
        self.sync = (
            self.folder.service if sync_configured else ManualSyncService(plan=None, apply=None)
        )
        self.schedules = InMemorySyncScheduleRepository()
        self.get = GetSyncScheduleUseCase(
            schedules=self.schedules, sync=self.sync, timezone=SAO_PAULO, clock=self.clock
        )
        self.update = UpdateSyncScheduleUseCase(
            schedules=self.schedules, sync=self.sync, timezone=SAO_PAULO, clock=self.clock
        )
        self.run = RunScheduledSyncUseCase(
            schedules=self.schedules, sync=self.sync, timezone=SAO_PAULO, clock=self.clock
        )

    def clock(self) -> datetime:
        return self.now

    async def schedule_daily(self, at: str = "00:00") -> None:
        await self.update.execute(admin, enabled=True, time_of_day=at)


class TestConfigure:
    async def test_admin_turns_on_the_daily_sync_and_sees_the_next_run(self) -> None:
        ctx = Context()

        view = await ctx.update.execute(admin, enabled=True, time_of_day="00:00")

        assert view.schedule.enabled
        assert view.schedule.time_of_day == time(0, 0)
        assert view.schedule.updated_by == admin.display_name
        assert view.next_run == local(6, 0)
        assert view.timezone == "America/Sao_Paulo"
        assert (await ctx.get.execute(admin)).schedule == ctx.schedules.schedule

    async def test_turning_off_keeps_the_time(self) -> None:
        ctx = Context()
        await ctx.schedule_daily("06:30")

        view = await ctx.update.execute(admin, enabled=False, time_of_day="06:30")

        assert not view.schedule.enabled
        assert view.next_run is None

    async def test_cannot_turn_on_without_the_folder_configured(self) -> None:
        ctx = Context(sync_configured=False)

        with pytest.raises(SyncNotConfiguredError):
            await ctx.update.execute(admin, enabled=True, time_of_day="00:00")
        await ctx.update.execute(admin, enabled=False, time_of_day="00:00")  # desligar pode

    async def test_rejects_an_invalid_time(self) -> None:
        with pytest.raises(InvalidValueError):
            await Context().update.execute(admin, enabled=True, time_of_day="25:00")

    async def test_only_admins_see_or_change_the_schedule(self) -> None:
        ctx = Context()

        with pytest.raises(PermissionDeniedError):
            await ctx.get.execute(maria)
        with pytest.raises(PermissionDeniedError):
            await ctx.update.execute(maria, enabled=True, time_of_day="00:00")


class TestRunScheduledSync:
    async def test_starts_the_sync_at_the_scheduled_time_once(self) -> None:
        ctx = Context()
        ctx.folder.source.put("ARMAZENAGEM/95000001-00P.pdf")
        await ctx.schedule_daily()

        ctx.now = local(5, 23, 59)
        assert not await ctx.run.execute()

        ctx.now = local(6, 0, 0)
        assert await ctx.run.execute()
        await ctx.sync.wait()

        assert ctx.sync.last_run is not None
        assert ctx.sync.last_run.started_by == SCHEDULED_BY
        assert len(ctx.folder.repository.manuals) == 1
        assert ctx.schedules.schedule.last_triggered_at == local(6, 0)

        ctx.now = local(6, 0, 1)
        assert not await ctx.run.execute()

    async def test_the_scheduled_sync_follows_the_figure_option(self) -> None:
        ctx = Context()
        ctx.folder.source.put("ARMAZENAGEM/95000001-00P.pdf")
        await ctx.update.execute(admin, enabled=True, time_of_day="00:00", describe_figures=True)
        assert ctx.schedules.schedule.describe_figures

        ctx.now = local(6, 0)
        assert await ctx.run.execute()
        await ctx.sync.wait()

        assert ctx.sync.last_run is not None
        assert ctx.sync.last_run.describe_figures
        # Registrar a execução não pode apagar a opção.
        assert ctx.schedules.schedule.describe_figures

    async def test_does_nothing_while_disabled(self) -> None:
        ctx = Context()
        ctx.schedules.schedule = SyncSchedule(enabled=False)

        ctx.now = local(6, 0)

        assert not await ctx.run.execute()
        assert ctx.sync.last_run is None

    async def test_records_why_the_scheduled_sync_did_not_start(self) -> None:
        ctx = Context()  # pasta vazia: a sincronização se recusa a começar
        await ctx.schedule_daily()
        ctx.now = local(6, 0)

        assert not await ctx.run.execute()

        schedule = ctx.schedules.schedule
        assert schedule.last_triggered_at == local(6, 0)
        assert "vazia" in (schedule.last_trigger_error or "")
        ctx.now = local(6, 0, 1)
        assert not await ctx.run.execute()  # não tenta de novo a cada minuto
