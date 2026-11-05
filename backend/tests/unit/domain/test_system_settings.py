from datetime import UTC, datetime

import pytest

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.system_settings import (
    DEFAULT_USAGE_RETENTION_MONTHS,
    USAGE_RETENTION_MAX_MONTHS,
    SystemSettings,
    months_before,
)


def at(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 15, 30, tzinfo=UTC)


class TestUsageRetention:
    def test_keeps_a_year_of_usage_by_default(self) -> None:
        settings = SystemSettings()

        assert settings.usage_retention_months == DEFAULT_USAGE_RETENTION_MONTHS == 12
        assert settings.usage_cutoff(at(2026, 11, 5)) == at(2025, 11, 5)

    def test_zero_keeps_usage_forever(self) -> None:
        assert SystemSettings(usage_retention_months=0).usage_cutoff(at(2026, 11, 5)) is None

    @pytest.mark.parametrize("months", [-1, USAGE_RETENTION_MAX_MONTHS + 1])
    def test_rejects_retention_out_of_range(self, months: int) -> None:
        with pytest.raises(InvalidValueError):
            SystemSettings(usage_retention_months=months)


class TestMonthsBefore:
    @pytest.mark.parametrize(
        ("moment", "months", "expected"),
        [
            (at(2026, 11, 5), 1, at(2026, 10, 5)),
            (at(2026, 1, 15), 1, at(2025, 12, 15)),
            (at(2026, 3, 31), 1, at(2026, 2, 28)),  # fevereiro não tem dia 31
            (at(2028, 3, 31), 1, at(2028, 2, 29)),  # ano bissexto
            (at(2026, 11, 5), 24, at(2024, 11, 5)),
        ],
    )
    def test_goes_back_whole_calendar_months(
        self, moment: datetime, months: int, expected: datetime
    ) -> None:
        assert months_before(moment, months) == expected
