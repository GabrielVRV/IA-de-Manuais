import re
from dataclasses import dataclass
from typing import Self

# Padrão de nome da Engenharia: código-revisãoIdioma.pdf (ex.: 95007003-01P.pdf).
_FILE_NAME = re.compile(r"(?P<number>\d+)-(?P<revision>\d+)(?P<language>[A-Za-z])\.pdf", re.I)
# Variante usada em parte dos secadores: código-vRevisão-modelo.pdf (ex.: 95021401-v2-ca10.pdf).
# Não tem letra de idioma: são manuais em português (a planilha lista 95021401-02P).
_VERSIONED_FILE_NAME = re.compile(r"(?P<number>\d+)-v(?P<revision>\d+)(?:-[^.]*)?\.pdf", re.I)
VERSIONED_LANGUAGE = "P"


@dataclass(frozen=True, slots=True)
class ManualCode:
    """Código de um manual da Engenharia, lido do nome do arquivo.

    O mesmo manual muda de revisão ao longo do tempo (-00, -01...), e cada idioma
    (P = português, E = inglês...) é um documento à parte.
    """

    number: str
    revision: int
    language: str

    @classmethod
    def from_file_name(cls, file_name: str) -> Self | None:
        """None quando o nome não segue o padrão (não é um manual de produto)."""
        name = file_name.strip()
        if match := _FILE_NAME.fullmatch(name):
            language = match["language"].upper()
        elif match := _VERSIONED_FILE_NAME.fullmatch(name):
            language = VERSIONED_LANGUAGE
        else:
            return None
        return cls(number=match["number"], revision=int(match["revision"]), language=language)

    @property
    def key(self) -> str:
        """Identifica o manual em qualquer revisão: código + idioma (ex.: "95007003P")."""
        return f"{self.number}{self.language}"

    @property
    def catalog_code(self) -> str:
        """Como o manual aparece na planilha da Engenharia (ex.: "95021401-02P")."""
        return f"{self.number}-{self.revision:02d}{self.language}"
