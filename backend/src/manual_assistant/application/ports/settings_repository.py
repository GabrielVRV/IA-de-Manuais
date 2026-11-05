from collections.abc import Sequence
from typing import Protocol

from manual_assistant.domain.system_settings import SystemSettings
from manual_assistant.domain.usage import ModelPrice


class SystemSettingsRepository(Protocol):
    """
    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def get(self) -> SystemSettings:
        """As configurações salvas, ou as padrão se nunca foram alteradas."""
        ...

    async def save(self, settings: SystemSettings) -> None: ...


class ModelPriceRepository(Protocol):
    """
    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def list_all(self) -> Sequence[ModelPrice]:
        """Preços cadastrados, em ordem alfabética de modelo."""
        ...

    async def save(self, price: ModelPrice) -> None:
        """Insere ou substitui o preço do modelo."""
        ...

    async def delete(self, model: str) -> None: ...
