import logging

from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.domain.manual import ManualStatus

logger = logging.getLogger(__name__)

INTERRUPTED_REASON = "A indexação foi interrompida (o servidor reiniciou). Reprocesse o manual."


class RecoverInterruptedIndexingUseCase:
    """Executado ao iniciar a API: nenhuma indexação sobrevive a um reinício.

    Sem isso, um manual que estava sendo processado quando o container caiu ficaria
    "processando" para sempre e não poderia nem ser reprocessado.
    Pressupõe uma única instância da API (o cenário deste projeto).
    """

    def __init__(self, repository: ManualRepository) -> None:
        self._repository = repository

    async def execute(self) -> int:
        recovered = 0
        for manual in await self._repository.list_all():
            if manual.status is ManualStatus.PROCESSING:
                manual.mark_failed(INTERRUPTED_REASON)
                await self._repository.save(manual)
                recovered += 1
        if recovered:
            logger.warning("%d indexação(ões) interrompida(s) marcada(s) como falha", recovered)
        return recovered
