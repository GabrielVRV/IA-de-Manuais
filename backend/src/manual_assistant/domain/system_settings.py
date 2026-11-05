"""Configurações que os administradores alteram pela tela, sem reiniciar a API."""

import calendar
from dataclasses import dataclass
from datetime import datetime

from manual_assistant.domain.errors import InvalidValueError

DEFAULT_USAGE_RETENTION_MONTHS = 12
USAGE_RETENTION_MAX_MONTHS = 120


@dataclass(kw_only=True, slots=True)
class SystemSettings:
    # Por quantos meses o consumo de cada usuário é guardado. 0 = para sempre.
    usage_retention_months: int = DEFAULT_USAGE_RETENTION_MONTHS
    updated_at: datetime | None = None
    updated_by: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.usage_retention_months <= USAGE_RETENTION_MAX_MONTHS:
            raise InvalidValueError(
                f"A retenção do consumo precisa estar entre 0 e {USAGE_RETENTION_MAX_MONTHS} meses"
            )

    def usage_cutoff(self, now: datetime) -> datetime | None:
        """Consumo registrado antes desta data já pode ser apagado; None = guardar sempre."""
        if not self.usage_retention_months:
            return None
        return months_before(now, self.usage_retention_months)


def months_before(moment: datetime, months: int) -> datetime:
    """Mesmo dia, ``months`` meses antes; no último dia do mês quando ele não existe
    (31/03 menos um mês = 28 ou 29/02)."""
    month_index = moment.year * 12 + moment.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)
