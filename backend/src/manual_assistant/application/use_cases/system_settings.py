"""Configurações alteradas pelos administradores na tela, sem reiniciar a API.

Toda operação recebe quem está agindo: a regra "só administradores" vive aqui.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import PermissionDeniedError
from manual_assistant.application.ports.settings_repository import (
    ModelPriceRepository,
    SystemSettingsRepository,
)
from manual_assistant.application.ports.usage_repository import UsageRepository
from manual_assistant.domain.system_settings import SystemSettings
from manual_assistant.domain.usage import ModelPrice, validate_model_name
from manual_assistant.domain.user import User

logger = logging.getLogger(__name__)


def _require_admin(actor: User) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Apenas administradores podem alterar as configurações")


class GetSystemSettingsUseCase:
    def __init__(self, settings: SystemSettingsRepository) -> None:
        self._settings = settings

    async def execute(self, actor: User) -> SystemSettings:
        _require_admin(actor)
        return await self._settings.get()


class UpdateSystemSettingsUseCase:
    def __init__(self, settings: SystemSettingsRepository, clock: Clock = utc_now) -> None:
        self._settings = settings
        self._clock = clock

    async def execute(
        self, actor: User, *, usage_retention_months: int | None = None
    ) -> SystemSettings:
        """Só os campos informados mudam; os demais ficam como estão."""
        _require_admin(actor)
        current = await self._settings.get()
        updated = SystemSettings(
            usage_retention_months=(
                current.usage_retention_months
                if usage_retention_months is None
                else usage_retention_months
            ),
            updated_at=self._clock(),
            updated_by=actor.display_name or actor.username,
        )
        await self._settings.save(updated)
        logger.info("Configurações alteradas por %s", actor.username)
        return updated


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Um modelo que aparece no consumo ou tem preço cadastrado; ``price`` None = sem preço."""

    model: str
    price: ModelPrice | None


class ListModelPricesUseCase:
    def __init__(self, *, prices: ModelPriceRepository, usage: UsageRepository) -> None:
        self._prices = prices
        self._usage = usage

    async def execute(self, actor: User) -> Sequence[ModelPricing]:
        """Os modelos já usados (com ou sem preço) e os que só têm preço, por nome."""
        _require_admin(actor)
        prices = {price.model: price for price in await self._prices.list_all()}
        models = sorted(set(prices) | set(await self._usage.models()))
        return [ModelPricing(model, prices.get(model)) for model in models]


class SetModelPriceUseCase:
    def __init__(self, prices: ModelPriceRepository) -> None:
        self._prices = prices

    async def execute(
        self,
        actor: User,
        *,
        model: str,
        input_per_million: Decimal,
        output_per_million: Decimal,
    ) -> ModelPrice:
        _require_admin(actor)
        price = ModelPrice(
            model=model.strip(),
            input_per_million=input_per_million,
            output_per_million=output_per_million,
        )
        await self._prices.save(price)
        logger.info("Preço do modelo %s alterado por %s", price.model, actor.username)
        return price


class DeleteModelPriceUseCase:
    def __init__(self, prices: ModelPriceRepository) -> None:
        self._prices = prices

    async def execute(self, actor: User, *, model: str) -> None:
        _require_admin(actor)
        await self._prices.delete(validate_model_name(model.strip()))


class PurgeOldUsageUseCase:
    """Apaga o consumo mais antigo que a retenção configurada na tela."""

    def __init__(
        self,
        *,
        usage: UsageRepository,
        settings: SystemSettingsRepository,
        clock: Clock = utc_now,
    ) -> None:
        self._usage = usage
        self._settings = settings
        self._clock = clock

    async def execute(self) -> int:
        cutoff = (await self._settings.get()).usage_cutoff(self._clock())
        if cutoff is None:
            return 0
        removed = await self._usage.delete_before(cutoff)
        if removed:
            logger.info("Registros de consumo antigos apagados: %d", removed)
        return removed
