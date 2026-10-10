from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Um PDF encontrado na pasta de manuais da Engenharia."""

    path: str  # relativo à pasta de origem, com "/" (ex.: "PROTEÍNA/95007003-01P.pdf")
    file_name: str
    fingerprint: str  # muda quando o arquivo muda (tamanho e data de modificação)
    title: str | None = None  # descrição na planilha da Engenharia, se houver


class ManualSource(Protocol):
    """Pasta de onde os manuais são importados. SOMENTE LEITURA: a pasta pertence à
    Engenharia, e o sistema nunca cria, altera, move ou apaga nada nela.

    Raises (todos os métodos):
        ExternalServiceError: se a pasta não puder ser lida.
    """

    async def list_documents(self) -> Sequence[SourceDocument]: ...

    async def read(self, path: str) -> bytes:
        """Conteúdo de um documento devolvido por ``list_documents``."""
        ...
