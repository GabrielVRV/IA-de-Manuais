from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from manual_assistant.application.errors import PermissionDeniedError
from manual_assistant.application.use_cases.usage_report import (
    REPORT_MAX_DAYS,
    GetUsageReportUseCase,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.usage import ModelPrice, QuestionUsage
from manual_assistant.domain.user import User, UserRole
from tests.factories import FIXED_NOW
from tests.fakes import (
    InMemoryModelPriceRepository,
    InMemoryUsageRepository,
    InMemoryUserRepository,
)
from tests.security import make_user

pytestmark = pytest.mark.anyio

SAO_PAULO = ZoneInfo("America/Sao_Paulo")  # FIXED_NOW (12:00 UTC) = 09:00 em São Paulo
TODAY = date(2026, 10, 6)


class Context:
    def __init__(self) -> None:
        self.usage = InMemoryUsageRepository()
        self.users = InMemoryUserRepository()
        self.prices = InMemoryModelPriceRepository()
        self.report = GetUsageReportUseCase(
            usage=self.usage,
            users=self.users,
            prices=self.prices,
            timezone=SAO_PAULO,
            clock=lambda: FIXED_NOW,
        )
        self.admin = self.user("admin", role=UserRole.ADMIN)
        self.maria = self.user("maria")
        self.joao = self.user("joao")

    def user(self, username: str, *, role: UserRole = UserRole.USER) -> User:
        user = make_user(username, role=role)
        self.users.users[user.id] = user
        return user

    def spend(
        self,
        user: User,
        *,
        at: datetime = FIXED_NOW,
        model: str | None = "gpt-4.1-mini",
        tokens: tuple[int, int] = (1000, 200),
    ) -> None:
        input_tokens, output_tokens = tokens if model else (0, 0)
        self.usage.records.append(QuestionUsage(user.id, at, model, input_tokens, output_tokens))


async def test_sums_the_period_and_ranks_who_spent_the_most_tokens() -> None:
    ctx = Context()
    ctx.spend(ctx.maria, tokens=(1000, 200))
    ctx.spend(ctx.joao, tokens=(5000, 500))
    ctx.spend(ctx.joao, tokens=(3000, 300))

    report = await ctx.report.execute(ctx.admin, days=30)

    assert (report.totals.questions, report.totals.input_tokens, report.totals.output_tokens) == (
        3,
        9000,
        1000,
    )
    assert [(u.username, u.totals.questions, u.totals.total_tokens) for u in report.by_user] == [
        ("joao", 2, 8800),
        ("maria", 1, 1200),
    ]


async def test_lists_every_day_of_the_period_including_days_without_use() -> None:
    ctx = Context()
    ctx.spend(ctx.maria, at=FIXED_NOW - timedelta(days=2))

    report = await ctx.report.execute(ctx.admin, days=3)

    assert (report.first_day, report.last_day) == (TODAY - timedelta(days=2), TODAY)
    assert [(d.day, d.totals.questions) for d in report.by_day] == [
        (TODAY - timedelta(days=2), 1),
        (TODAY - timedelta(days=1), 0),
        (TODAY, 0),
    ]


async def test_days_follow_the_company_clock_not_utc() -> None:
    ctx = Context()
    # 01:00 UTC do dia 6 ainda é dia 5 em São Paulo (22:00).
    ctx.spend(ctx.maria, at=datetime(2026, 10, 6, 1, 0, tzinfo=UTC))

    report = await ctx.report.execute(ctx.admin, days=2)

    assert [(d.day, d.totals.questions) for d in report.by_day] == [
        (date(2026, 10, 5), 1),
        (TODAY, 0),
    ]


async def test_ignores_usage_before_the_period() -> None:
    ctx = Context()
    # Dia 4, 23:59 em São Paulo: fora de um período de 2 dias (5 e 6).
    ctx.spend(ctx.maria, at=datetime(2026, 10, 5, 2, 59, tzinfo=UTC))

    report = await ctx.report.execute(ctx.admin, days=2)

    assert report.totals.questions == 0
    assert report.by_user == []


async def test_calculates_the_cost_with_the_price_of_each_model() -> None:
    ctx = Context()
    ctx.prices.prices["gpt-4.1-mini"] = ModelPrice("gpt-4.1-mini", Decimal("0.40"), Decimal("1.60"))
    ctx.spend(ctx.maria, tokens=(1_000_000, 500_000))

    report = await ctx.report.execute(ctx.admin, days=1)

    assert report.totals.cost == Decimal("1.20")
    assert report.totals.cost_is_partial is False
    assert report.unpriced_models == []


async def test_flags_a_partial_cost_when_a_model_has_no_price() -> None:
    ctx = Context()
    ctx.prices.prices["gpt-4.1-mini"] = ModelPrice("gpt-4.1-mini", Decimal(1), Decimal(1))
    ctx.spend(ctx.maria, model="gpt-4.1-mini", tokens=(1_000_000, 0))
    ctx.spend(ctx.joao, model="gemini-3.5-flash", tokens=(1_000_000, 0))

    report = await ctx.report.execute(ctx.admin, days=1)

    assert report.totals.cost == Decimal(1)
    assert report.totals.cost_is_partial is True
    assert report.unpriced_models == ["gemini-3.5-flash"]
    by_user = {u.username: u.totals for u in report.by_user}
    assert by_user["maria"].cost_is_partial is False
    assert by_user["joao"].cost_is_partial is True


async def test_questions_answered_without_the_model_count_but_cost_nothing() -> None:
    ctx = Context()
    ctx.spend(ctx.maria, model=None)

    report = await ctx.report.execute(ctx.admin, days=1)

    assert report.totals.questions == 1
    assert report.totals.total_tokens == 0
    assert report.totals.cost_is_partial is False
    assert report.by_model == []


async def test_only_admins_see_the_usage() -> None:
    ctx = Context()

    with pytest.raises(PermissionDeniedError):
        await ctx.report.execute(ctx.maria, days=30)


@pytest.mark.parametrize("days", [0, REPORT_MAX_DAYS + 1])
async def test_rejects_periods_out_of_range(days: int) -> None:
    ctx = Context()

    with pytest.raises(InvalidValueError):
        await ctx.report.execute(ctx.admin, days=days)
