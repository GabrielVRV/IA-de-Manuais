from collections.abc import Sequence

from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.domain.manual import Manual


class ListManualsUseCase:
    def __init__(self, repository: ManualRepository) -> None:
        self._repository = repository

    async def execute(self) -> Sequence[Manual]:
        return await self._repository.list_all()
