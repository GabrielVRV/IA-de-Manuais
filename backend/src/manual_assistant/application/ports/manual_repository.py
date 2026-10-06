from collections.abc import Sequence
from typing import Protocol

from manual_assistant.domain.manual import Manual, ManualId


class ManualRepository(Protocol):
    """Persistência dos manuais cadastrados (metadados e status, não o conteúdo)."""

    async def save(self, manual: Manual) -> None:
        """Insere o manual ou atualiza o existente com o mesmo id."""
        ...

    async def get(self, manual_id: ManualId) -> Manual | None: ...

    async def list_all(self) -> Sequence[Manual]:
        """Todos os manuais, do mais recente para o mais antigo."""
        ...

    async def delete(self, manual_id: ManualId) -> None: ...
