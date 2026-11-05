from typing import Protocol

from manual_assistant.domain.sync_schedule import SyncSchedule


class SyncScheduleRepository(Protocol):
    """
    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def get(self) -> SyncSchedule:
        """O agendamento salvo, ou um desligado se nunca foi configurado."""
        ...

    async def save(self, schedule: SyncSchedule) -> None: ...
