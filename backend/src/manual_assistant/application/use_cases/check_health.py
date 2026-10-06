import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from manual_assistant.application.ports.health_indicator import HealthIndicator

logger = logging.getLogger(__name__)


class HealthStatus(StrEnum):
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class HealthReport:
    status: HealthStatus
    components: Mapping[str, HealthStatus] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status is HealthStatus.UP


class CheckHealthUseCase:
    """Consolida a saúde da aplicação a partir dos indicadores registrados."""

    def __init__(self, indicators: Sequence[HealthIndicator] = ()) -> None:
        self._indicators = tuple(indicators)

    async def execute(self) -> HealthReport:
        components = {
            indicator.name: await self._probe(indicator) for indicator in self._indicators
        }
        overall = (
            HealthStatus.UP
            if all(status is HealthStatus.UP for status in components.values())
            else HealthStatus.DOWN
        )
        return HealthReport(status=overall, components=components)

    @staticmethod
    async def _probe(indicator: HealthIndicator) -> HealthStatus:
        # Um health check nunca pode derrubar a aplicação: qualquer falha vira DOWN.
        try:
            healthy = await indicator.is_healthy()
        except Exception:
            logger.exception("Falha ao verificar a saúde de '%s'", indicator.name)
            return HealthStatus.DOWN
        return HealthStatus.UP if healthy else HealthStatus.DOWN
