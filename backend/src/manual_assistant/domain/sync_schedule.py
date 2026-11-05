"""Sincronização automática com a pasta da Engenharia, uma vez por dia num horário.

O horário é o do relógio da empresa (fuso configurado na API). Se a API estiver fora
do ar no horário, a sincronização do dia roda assim que ela voltar.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Self

from manual_assistant.domain.errors import InvalidValueError

TRIGGER_ERROR_MAX_LENGTH = 500


@dataclass(kw_only=True, slots=True)
class SyncSchedule:
    enabled: bool = False
    time_of_day: time = time(0, 0)
    updated_at: datetime | None = None
    updated_by: str | None = None
    last_triggered_at: datetime | None = None
    # Por que a última execução agendada não começou (ex.: pasta inacessível).
    last_trigger_error: str | None = None

    def __post_init__(self) -> None:
        if self.time_of_day.tzinfo is not None:
            raise InvalidValueError("O horário da sincronização não leva fuso: é o da empresa")
        if self.time_of_day.second or self.time_of_day.microsecond:
            raise InvalidValueError("O horário da sincronização é em horas e minutos")

    def change(self, *, enabled: bool, time_of_day: time, now: datetime, author: str) -> Self:
        """Novo agendamento. Um horário que já passou hoje só vale a partir de amanhã."""
        return type(self)(
            enabled=enabled,
            time_of_day=time_of_day,
            updated_at=now,
            updated_by=author,
            last_triggered_at=self.last_triggered_at,
            last_trigger_error=self.last_trigger_error,
        )

    def is_due(self, now: datetime, zone: tzinfo) -> bool:
        """Chegou a hora: o horário de hoje (ou de ontem) passou e ainda não rodou."""
        if not self.enabled:
            return False
        occurrence = self._latest_occurrence(now, zone)
        handled = [moment for moment in (self.last_triggered_at, self.updated_at) if moment]
        return all(occurrence > moment for moment in handled)

    def next_run(self, now: datetime, zone: tzinfo) -> datetime | None:
        """Quando a próxima sincronização agendada vai começar; None se desligada."""
        if not self.enabled:
            return None
        latest = self._latest_occurrence(now, zone)
        return latest if self.is_due(now, zone) else self._at(latest.date() + timedelta(1), zone)

    def triggered(self, now: datetime, *, error: str | None = None) -> Self:
        """Registra a execução do horário, que não se repete mesmo se falhar ao começar."""
        return type(self)(
            enabled=self.enabled,
            time_of_day=self.time_of_day,
            updated_at=self.updated_at,
            updated_by=self.updated_by,
            last_triggered_at=now,
            last_trigger_error=error[:TRIGGER_ERROR_MAX_LENGTH] if error else None,
        )

    def _latest_occurrence(self, now: datetime, zone: tzinfo) -> datetime:
        today = self._at(now.astimezone(zone).date(), zone)
        return today if today <= now else self._at(today.date() - timedelta(1), zone)

    def _at(self, day: date, zone: tzinfo) -> datetime:
        return datetime.combine(day, self.time_of_day, tzinfo=zone)


def parse_time_of_day(text: str) -> time:
    """ "HH:MM", como vem da tela."""
    try:
        parsed = time.fromisoformat(text)
    except ValueError as error:
        raise InvalidValueError("Informe o horário como HH:MM (ex.: 00:00)") from error
    if len(text) != 5 or parsed.tzinfo is not None:
        raise InvalidValueError("Informe o horário como HH:MM (ex.: 00:00)")
    return parsed
