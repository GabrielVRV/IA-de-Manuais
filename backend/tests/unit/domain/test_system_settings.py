from datetime import UTC, datetime, timedelta

import pytest

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.system_settings import (
    DEFAULT_USAGE_RETENTION_MONTHS,
    QUESTION_LIMIT_MAX,
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


class TestQuestionLimits:
    def test_limits_questions_per_minute_and_per_day_by_default(self) -> None:
        limits = SystemSettings().question_limits

        assert [(limit.max_questions, limit.window) for limit in limits] == [
            (10, timedelta(minutes=1)),
            (200, timedelta(hours=24)),
        ]

    def test_zero_turns_a_limit_off(self) -> None:
        settings = SystemSettings(questions_per_minute=0, questions_per_day=50)

        assert [limit.max_questions for limit in settings.question_limits] == [50]
        assert SystemSettings(questions_per_minute=0, questions_per_day=0).question_limits == ()

    def test_message_tells_the_limit_and_the_window(self) -> None:
        (_, per_day) = SystemSettings().question_limits

        assert per_day.message().startswith("Você atingiu o limite de 200 pergunta(s) em 24 horas")

    @pytest.mark.parametrize("field", ["questions_per_minute", "questions_per_day"])
    @pytest.mark.parametrize("value", [-1, QUESTION_LIMIT_MAX + 1])
    def test_rejects_limits_out_of_range(self, field: str, value: int) -> None:
        with pytest.raises(InvalidValueError):
            SystemSettings(**{field: value})  # type: ignore[arg-type]


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
