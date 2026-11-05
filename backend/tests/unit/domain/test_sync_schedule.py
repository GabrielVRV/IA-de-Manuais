from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.sync_schedule import (
    TRIGGER_ERROR_MAX_LENGTH,
    SyncSchedule,
    parse_time_of_day,
)

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def local(day: int, hour: int, minute: int = 0) -> datetime:
    """Novembro de 2026, no horário de São Paulo."""
    return datetime(2026, 11, day, hour, minute, tzinfo=SAO_PAULO)


def configured_at(moment: datetime, *, at: time = time(0, 0)) -> SyncSchedule:
    return SyncSchedule().change(enabled=True, time_of_day=at, now=moment, author="Ana")


class TestIsDue:
    def test_disabled_schedule_never_runs(self) -> None:
        schedule = SyncSchedule(enabled=False, updated_at=local(1, 10))

        assert not schedule.is_due(local(3, 0, 5), SAO_PAULO)

    def test_runs_at_the_time_on_the_company_clock(self) -> None:
        schedule = configured_at(local(5, 10))

        assert not schedule.is_due(local(5, 23, 59), SAO_PAULO)
        assert schedule.is_due(local(6, 0, 0), SAO_PAULO)
        # 03:00 UTC é meia-noite em São Paulo: o fuso decide, não o relógio do servidor.
        assert schedule.is_due(datetime(2026, 11, 6, 3, 0, tzinfo=UTC), SAO_PAULO)
        assert not schedule.is_due(datetime(2026, 11, 6, 2, 59, tzinfo=UTC), SAO_PAULO)

    def test_a_time_already_past_today_waits_until_tomorrow(self) -> None:
        schedule = configured_at(local(5, 10), at=time(8, 0))

        assert not schedule.is_due(local(5, 10, 1), SAO_PAULO)
        assert schedule.is_due(local(6, 8, 0), SAO_PAULO)

    def test_a_time_later_today_runs_today(self) -> None:
        schedule = configured_at(local(5, 10), at=time(18, 30))

        assert schedule.is_due(local(5, 18, 30), SAO_PAULO)

    def test_runs_once_per_day(self) -> None:
        schedule = configured_at(local(5, 10)).triggered(local(6, 0, 0))

        assert not schedule.is_due(local(6, 0, 1), SAO_PAULO)
        assert not schedule.is_due(local(6, 23, 59), SAO_PAULO)
        assert schedule.is_due(local(7, 0, 0), SAO_PAULO)

    def test_catches_up_when_the_api_was_down_at_the_time(self) -> None:
        schedule = configured_at(local(4, 10)).triggered(local(5, 0, 0))

        # Fora do ar à meia-noite do dia 6; volta às 8h.
        assert schedule.is_due(local(6, 8, 0), SAO_PAULO)

    def test_a_failed_start_is_not_retried_every_minute(self) -> None:
        schedule = configured_at(local(5, 10)).triggered(local(6, 0, 0), error="pasta vazia")

        assert schedule.last_trigger_error == "pasta vazia"
        assert not schedule.is_due(local(6, 0, 1), SAO_PAULO)


class TestNextRun:
    def test_is_the_next_occurrence_of_the_time(self) -> None:
        schedule = configured_at(local(5, 10))

        assert schedule.next_run(local(5, 10, 1), SAO_PAULO) == local(6, 0)

    def test_is_none_when_disabled(self) -> None:
        assert SyncSchedule().next_run(local(5, 10), SAO_PAULO) is None


class TestTriggered:
    def test_success_clears_the_previous_error(self) -> None:
        failed = configured_at(local(4, 10)).triggered(local(5, 0), error="pasta vazia")

        succeeded = failed.triggered(local(6, 0))

        assert (succeeded.last_triggered_at, succeeded.last_trigger_error) == (local(6, 0), None)
        assert (succeeded.enabled, succeeded.updated_by) == (True, "Ana")

    def test_long_errors_are_cut(self) -> None:
        schedule = SyncSchedule().triggered(local(5, 0), error="x" * 2000)

        assert len(schedule.last_trigger_error or "") == TRIGGER_ERROR_MAX_LENGTH


class TestTimeOfDay:
    def test_parses_hours_and_minutes(self) -> None:
        assert parse_time_of_day("00:00") == time(0, 0)
        assert parse_time_of_day("23:59") == time(23, 59)

    @pytest.mark.parametrize("text", ["", "24:00", "7:00", "07:00:00", "07h00", "07:00+03:00"])
    def test_rejects_other_formats(self, text: str) -> None:
        with pytest.raises(InvalidValueError):
            parse_time_of_day(text)

    def test_rejects_seconds_and_timezones(self) -> None:
        with pytest.raises(InvalidValueError):
            SyncSchedule(time_of_day=time(0, 0, 30))
        with pytest.raises(InvalidValueError):
            SyncSchedule(time_of_day=time(0, 0, tzinfo=UTC))

    def test_change_keeps_the_last_execution(self) -> None:
        ran = configured_at(local(4, 10)).triggered(local(5, 0))

        changed = ran.change(enabled=False, time_of_day=time(6, 0), now=local(5, 9), author="Bia")

        assert changed.last_triggered_at == local(5, 0)
        assert (changed.updated_at, changed.updated_by) == (local(5, 9), "Bia")
        assert changed.next_run(local(5, 9) + timedelta(minutes=1), SAO_PAULO) is None
