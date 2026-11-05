"""Agendamento da sincronização com a pasta da Engenharia (ADR 0009), configurado pela tela.

Um laço na API chama ``RunScheduledSyncUseCase`` a cada minuto; no horário, ele dispara
a mesma sincronização do botão "Sincronizar", em segundo plano.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import ApplicationError, PermissionDeniedError
from manual_assistant.application.ports.sync_schedule_repository import SyncScheduleRepository
from manual_assistant.application.use_cases.sync_manuals import (
    ManualSyncService,
    SyncNotConfiguredError,
)
from manual_assistant.domain.sync_schedule import SyncSchedule, parse_time_of_day
from manual_assistant.domain.user import User

logger = logging.getLogger(__name__)

SCHEDULED_BY = "Agendamento automático"


def _require_admin(actor: User) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Apenas administradores podem agendar a sincronização")


@dataclass(frozen=True, slots=True)
class SyncScheduleView:
    schedule: SyncSchedule
    next_run: datetime | None
    timezone: str


class _ScheduleUseCase:
    def __init__(
        self,
        *,
        schedules: SyncScheduleRepository,
        sync: ManualSyncService,
        timezone: ZoneInfo,
        clock: Clock = utc_now,
    ) -> None:
        self._schedules = schedules
        self._sync = sync
        self._timezone = timezone
        self._clock = clock

    def _view(self, schedule: SyncSchedule) -> SyncScheduleView:
        return SyncScheduleView(
            schedule=schedule,
            next_run=schedule.next_run(self._clock(), self._timezone),
            timezone=self._timezone.key,
        )


class GetSyncScheduleUseCase(_ScheduleUseCase):
    async def execute(self, actor: User) -> SyncScheduleView:
        _require_admin(actor)
        return self._view(await self._schedules.get())


class UpdateSyncScheduleUseCase(_ScheduleUseCase):
    async def execute(self, actor: User, *, enabled: bool, time_of_day: str) -> SyncScheduleView:
        """
        Raises:
            SyncNotConfiguredError: ao ligar sem a pasta de manuais configurada.
            InvalidValueError: horário fora do formato HH:MM.
        """
        _require_admin(actor)
        if enabled and not self._sync.enabled:
            raise SyncNotConfiguredError()
        current = await self._schedules.get()
        updated = current.change(
            enabled=enabled,
            time_of_day=parse_time_of_day(time_of_day),
            now=self._clock(),
            author=actor.display_name or actor.username,
        )
        await self._schedules.save(updated)
        logger.info(
            "Sincronização agendada %s por %s (%s)",
            "ligada" if enabled else "desligada",
            actor.username,
            time_of_day,
        )
        return self._view(updated)


class RunScheduledSyncUseCase(_ScheduleUseCase):
    async def execute(self) -> bool:
        """Dispara a sincronização se chegou o horário. Devolve se ela começou.

        O horário é marcado como executado mesmo quando a sincronização não consegue
        começar (pasta fora do ar, outra sincronização rodando): a falha fica registrada
        e não se repete a cada minuto; a próxima tentativa é no horário do dia seguinte.
        """
        now = self._clock()
        schedule = await self._schedules.get()
        if not schedule.is_due(now, self._timezone):
            return False
        try:
            await self._sync.start(started_by=SCHEDULED_BY)
        except ApplicationError as error:
            logger.warning("A sincronização agendada não começou: %s", error)
            await self._schedules.save(schedule.triggered(now, error=str(error)))
            return False
        await self._schedules.save(schedule.triggered(now))
        logger.info("Sincronização agendada iniciada")
        return True
