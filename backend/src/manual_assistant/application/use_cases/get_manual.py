from manual_assistant.application.errors import ManualNotFoundError
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.domain.manual import Manual, ManualId


class GetManualUseCase:
    def __init__(self, repository: ManualRepository) -> None:
        self._repository = repository

    async def execute(self, manual_id: ManualId) -> Manual:
        manual = await self._repository.get(manual_id)
        if manual is None:
            raise ManualNotFoundError(manual_id)
        return manual
