from collections.abc import Sequence
from typing import Protocol

from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.manual import ManualId


class FigureDescriptionRepository(Protocol):
    """Descrições de figuras já pagas, por manual e versão do arquivo (hash do conteúdo).

    Ficam separadas dos trechos: reindexar o texto não joga fora o que a IA já descreveu.

    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def list(self, manual_id: ManualId, content_hash: str) -> Sequence[FigureDescription]:
        """Descrições desta versão do arquivo, por número de página."""
        ...

    async def add(
        self, manual_id: ManualId, content_hash: str, description: FigureDescription
    ) -> None:
        """Grava (ou substitui) a descrição de uma página."""
        ...

    async def delete_other_versions(self, manual_id: ManualId, content_hash: str) -> int:
        """Apaga as descrições de outras versões do arquivo; devolve quantas."""
        ...
