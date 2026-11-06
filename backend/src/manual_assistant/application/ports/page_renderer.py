from collections.abc import Sequence
from typing import Protocol

from manual_assistant.application.ports.language_model import ImageInput


class PageRenderer(Protocol):
    """Encontra as páginas com figuras e as transforma em imagem para o modelo com visão."""

    async def pages_with_figures(self, content: bytes) -> Sequence[int]:
        """Números das páginas (a partir de 1) com fotos, diagramas ou desenhos técnicos.

        Raises:
            UnreadableDocumentError: se o documento não puder ser lido.
        """
        ...

    async def render(self, content: bytes, pages: Sequence[int]) -> Sequence[ImageInput]:
        """Uma imagem por página pedida, na mesma ordem.

        Raises:
            UnreadableDocumentError: se o documento não puder ser lido.
        """
        ...
