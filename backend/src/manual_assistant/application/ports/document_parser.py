from collections.abc import Sequence
from typing import Protocol

from manual_assistant.domain.pages import Page


class DocumentParser(Protocol):
    """Extrai o texto de um documento, página a página."""

    async def parse(self, content: bytes) -> Sequence[Page]:
        """Retorna as páginas na ordem do documento.

        Raises:
            UnreadableDocumentError: se o conteúdo não puder ser lido.
        """
        ...
