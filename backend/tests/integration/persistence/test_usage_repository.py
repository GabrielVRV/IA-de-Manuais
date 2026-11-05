from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.system_settings import SystemSettings
from manual_assistant.domain.usage import ModelPrice, QuestionUsage
from manual_assistant.domain.user import User
from manual_assistant.infrastructure.persistence.settings_repository import (
    SqlAlchemyModelPriceRepository,
    SqlAlchemySystemSettingsRepository,
)
from manual_assistant.infrastructure.persistence.usage_repository import (
    SqlAlchemyUsageRepository,
)
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from tests.factories import FIXED_NOW
from tests.security import make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


@pytest.fixture
def usage(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyUsageRepository:
    return SqlAlchemyUsageRepository(session_factory)


async def saved_user(session_factory: async_sessionmaker[AsyncSession], username: str) -> User:
    user = make_user(username)
    await SqlAlchemyUserRepository(session_factory).save(user)
    return user


class TestUsageRepository:
    async def test_sums_by_user_model_and_day_in_the_company_timezone(
        self,
        usage: SqlAlchemyUsageRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        maria = await saved_user(session_factory, "maria")
        joao = await saved_user(session_factory, "joao")
        await usage.add(QuestionUsage(maria.id, FIXED_NOW, "gpt-4.1-mini", 100, 10))
        await usage.add(QuestionUsage(maria.id, FIXED_NOW, "gpt-4.1-mini", 200, 20))
        await usage.add(QuestionUsage(maria.id, FIXED_NOW, None))
        # 01:00 UTC do dia 6 = 22:00 do dia 5 em São Paulo.
        await usage.add(
            QuestionUsage(joao.id, datetime(2026, 10, 6, 1, 0, tzinfo=UTC), "gpt-4.1-mini", 5, 5)
        )

        rows = await usage.aggregate(
            since=FIXED_NOW - timedelta(days=2),
            until=FIXED_NOW + timedelta(seconds=1),
            timezone=SAO_PAULO,
        )

        summary = {
            (row.user_id, row.model, row.day): (row.questions, row.input_tokens, row.output_tokens)
            for row in rows
        }
        assert summary == {
            (maria.id, "gpt-4.1-mini", date(2026, 10, 6)): (2, 300, 30),
            (maria.id, None, date(2026, 10, 6)): (1, 0, 0),
            (joao.id, "gpt-4.1-mini", date(2026, 10, 5)): (1, 5, 5),
        }

    async def test_period_includes_the_start_and_excludes_the_end(
        self,
        usage: SqlAlchemyUsageRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        maria = await saved_user(session_factory, "maria")
        await usage.add(QuestionUsage(maria.id, FIXED_NOW, "gpt-4.1-mini", 1, 1))
        await usage.add(QuestionUsage(maria.id, FIXED_NOW + timedelta(hours=1), "gpt-4.1-mini"))

        rows = await usage.aggregate(
            since=FIXED_NOW, until=FIXED_NOW + timedelta(hours=1), timezone=SAO_PAULO
        )

        assert [row.questions for row in rows] == [1]

    async def test_counts_the_questions_of_one_user_since_a_moment(
        self,
        usage: SqlAlchemyUsageRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        maria = await saved_user(session_factory, "maria")
        joao = await saved_user(session_factory, "joao")
        await usage.add(QuestionUsage(maria.id, FIXED_NOW - timedelta(minutes=5), None))
        await usage.add(QuestionUsage(maria.id, FIXED_NOW - timedelta(seconds=30), None))
        await usage.add(QuestionUsage(maria.id, FIXED_NOW, "gpt-4.1-mini", 1, 1))
        await usage.add(QuestionUsage(joao.id, FIXED_NOW, "gpt-4.1-mini", 1, 1))

        assert await usage.count_since(maria.id, FIXED_NOW - timedelta(minutes=1)) == 2
        assert await usage.count_since(maria.id, FIXED_NOW - timedelta(hours=1)) == 3

    async def test_lists_the_models_already_used(
        self,
        usage: SqlAlchemyUsageRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        maria = await saved_user(session_factory, "maria")
        for model in ["gpt-4.1-mini", None, "gemini-3.5-flash", "gpt-4.1-mini"]:
            await usage.add(QuestionUsage(maria.id, FIXED_NOW, model))

        assert await usage.models() == ["gemini-3.5-flash", "gpt-4.1-mini"]

    async def test_deletes_only_usage_before_the_cutoff(
        self,
        usage: SqlAlchemyUsageRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        maria = await saved_user(session_factory, "maria")
        await usage.add(QuestionUsage(maria.id, FIXED_NOW - timedelta(days=400), "gpt-4.1-mini"))
        await usage.add(QuestionUsage(maria.id, FIXED_NOW, "gpt-4.1-mini"))

        removed = await usage.delete_before(FIXED_NOW - timedelta(days=365))

        assert removed == 1
        assert await usage.models() == ["gpt-4.1-mini"]
        rows = await usage.aggregate(
            since=FIXED_NOW - timedelta(days=500),
            until=FIXED_NOW + timedelta(days=1),
            timezone=SAO_PAULO,
        )
        assert sum(row.questions for row in rows) == 1


class TestSystemSettingsRepository:
    async def test_returns_the_defaults_until_saved(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlAlchemySystemSettingsRepository(session_factory)

        assert await repository.get() == SystemSettings()

        saved = SystemSettings(
            usage_retention_months=6,
            questions_per_minute=3,
            questions_per_day=0,
            updated_at=FIXED_NOW,
            updated_by="Admin",
        )
        await repository.save(saved)
        await repository.save(saved)  # salvar de novo atualiza a mesma linha

        assert await repository.get() == saved


class TestModelPriceRepository:
    async def test_saves_replaces_and_deletes_prices(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlAlchemyModelPriceRepository(session_factory)

        await repository.save(ModelPrice("gpt-4.1-mini", Decimal("0.4"), Decimal("1.6")))
        await repository.save(ModelPrice("gpt-4.1-mini", Decimal("0.5"), Decimal("2.0")))
        await repository.save(ModelPrice("a-model", Decimal("0.000123"), Decimal(0)))

        assert await repository.list_all() == [
            ModelPrice("a-model", Decimal("0.000123"), Decimal(0)),
            ModelPrice("gpt-4.1-mini", Decimal("0.5"), Decimal("2.0")),
        ]

        await repository.delete("a-model")

        assert [p.model for p in await repository.list_all()] == ["gpt-4.1-mini"]
