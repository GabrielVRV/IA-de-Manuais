from datetime import timedelta
from decimal import Decimal

import pytest

from manual_assistant.application.errors import PermissionDeniedError
from manual_assistant.application.use_cases.system_settings import (
    DeleteModelPriceUseCase,
    GetSystemSettingsUseCase,
    ListModelPricesUseCase,
    PurgeOldUsageUseCase,
    SetModelPriceUseCase,
    UpdateSystemSettingsUseCase,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.system_settings import SystemSettings
from manual_assistant.domain.usage import ModelPrice, QuestionUsage
from manual_assistant.domain.user import UserRole
from tests.factories import FIXED_NOW
from tests.fakes import (
    InMemoryModelPriceRepository,
    InMemorySystemSettingsRepository,
    InMemoryUsageRepository,
)
from tests.security import make_user

pytestmark = pytest.mark.anyio

admin = make_user("admin", role=UserRole.ADMIN)
maria = make_user("maria")


class TestSettings:
    async def test_starts_with_the_defaults(self) -> None:
        settings = await GetSystemSettingsUseCase(InMemorySystemSettingsRepository()).execute(admin)

        assert settings == SystemSettings()

    async def test_admin_changes_the_retention_and_is_recorded_as_the_author(self) -> None:
        repository = InMemorySystemSettingsRepository()

        updated = await UpdateSystemSettingsUseCase(repository, clock=lambda: FIXED_NOW).execute(
            admin, usage_retention_months=6
        )

        assert updated.usage_retention_months == 6
        assert (updated.updated_at, updated.updated_by) == (FIXED_NOW, admin.display_name)
        assert repository.settings == updated

    async def test_admin_changes_the_question_limits(self) -> None:
        repository = InMemorySystemSettingsRepository()

        updated = await UpdateSystemSettingsUseCase(repository).execute(
            admin, questions_per_minute=5, questions_per_day=0
        )

        assert (updated.questions_per_minute, updated.questions_per_day) == (5, 0)
        assert updated.usage_retention_months == SystemSettings().usage_retention_months

    async def test_fields_not_sent_stay_as_they_are(self) -> None:
        repository = InMemorySystemSettingsRepository(SystemSettings(usage_retention_months=3))

        updated = await UpdateSystemSettingsUseCase(repository).execute(admin)

        assert updated.usage_retention_months == 3

    async def test_rejects_an_invalid_retention(self) -> None:
        with pytest.raises(InvalidValueError):
            await UpdateSystemSettingsUseCase(InMemorySystemSettingsRepository()).execute(
                admin, usage_retention_months=-1
            )

    async def test_only_admins_see_or_change_the_settings(self) -> None:
        repository = InMemorySystemSettingsRepository()

        with pytest.raises(PermissionDeniedError):
            await GetSystemSettingsUseCase(repository).execute(maria)
        with pytest.raises(PermissionDeniedError):
            await UpdateSystemSettingsUseCase(repository).execute(maria, usage_retention_months=1)


class TestModelPrices:
    async def test_lists_the_models_already_used_even_without_a_price(self) -> None:
        prices = InMemoryModelPriceRepository()
        prices.prices["gpt-4.1-mini"] = ModelPrice("gpt-4.1-mini", Decimal(1), Decimal(2))
        usage = InMemoryUsageRepository()
        usage.records.append(QuestionUsage(maria.id, FIXED_NOW, "gemini-3.5-flash", 10, 10))
        usage.records.append(QuestionUsage(maria.id, FIXED_NOW, "gpt-4.1-mini", 10, 10))

        listed = await ListModelPricesUseCase(prices=prices, usage=usage).execute(admin)

        assert [(p.model, p.price is not None) for p in listed] == [
            ("gemini-3.5-flash", False),
            ("gpt-4.1-mini", True),
        ]

    async def test_sets_replaces_and_removes_the_price_of_a_model(self) -> None:
        prices = InMemoryModelPriceRepository()
        set_price = SetModelPriceUseCase(prices)

        await set_price.execute(
            admin,
            model=" gpt-4.1-mini ",
            input_per_million=Decimal(1),
            output_per_million=Decimal(2),
        )
        await set_price.execute(
            admin, model="gpt-4.1-mini", input_per_million=Decimal(3), output_per_million=Decimal(4)
        )

        assert prices.prices == {"gpt-4.1-mini": ModelPrice("gpt-4.1-mini", Decimal(3), Decimal(4))}

        await DeleteModelPriceUseCase(prices).execute(admin, model="gpt-4.1-mini")

        assert prices.prices == {}

    async def test_rejects_a_negative_price(self) -> None:
        with pytest.raises(InvalidValueError):
            await SetModelPriceUseCase(InMemoryModelPriceRepository()).execute(
                admin,
                model="gpt-4.1-mini",
                input_per_million=Decimal(-1),
                output_per_million=Decimal(1),
            )

    async def test_only_admins_manage_prices(self) -> None:
        prices, usage = InMemoryModelPriceRepository(), InMemoryUsageRepository()

        with pytest.raises(PermissionDeniedError):
            await ListModelPricesUseCase(prices=prices, usage=usage).execute(maria)
        with pytest.raises(PermissionDeniedError):
            await SetModelPriceUseCase(prices).execute(
                maria, model="x", input_per_million=Decimal(1), output_per_million=Decimal(1)
            )
        with pytest.raises(PermissionDeniedError):
            await DeleteModelPriceUseCase(prices).execute(maria, model="x")


class TestPurgeOldUsage:
    def usage_at(self, *ages_in_days: int) -> InMemoryUsageRepository:
        usage = InMemoryUsageRepository()
        for age in ages_in_days:
            usage.records.append(
                QuestionUsage(maria.id, FIXED_NOW - timedelta(days=age), "gpt-4.1-mini", 1, 1)
            )
        return usage

    async def test_removes_usage_older_than_the_retention(self) -> None:
        usage = self.usage_at(10, 40)
        settings = InMemorySystemSettingsRepository(SystemSettings(usage_retention_months=1))

        removed = await PurgeOldUsageUseCase(
            usage=usage, settings=settings, clock=lambda: FIXED_NOW
        ).execute()

        assert removed == 1
        assert [FIXED_NOW - u.asked_at for u in usage.records] == [timedelta(days=10)]

    async def test_keeps_everything_when_the_retention_is_zero(self) -> None:
        usage = self.usage_at(10, 4000)
        settings = InMemorySystemSettingsRepository(SystemSettings(usage_retention_months=0))

        removed = await PurgeOldUsageUseCase(
            usage=usage, settings=settings, clock=lambda: FIXED_NOW
        ).execute()

        assert removed == 0
        assert len(usage.records) == 2
