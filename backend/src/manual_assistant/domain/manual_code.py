import re
from dataclasses import dataclass
from typing import Self

# Padrão de nome da Engenharia: código-revisãoIdioma.pdf (ex.: 95007003-01P.pdf).
_FILE_NAME = re.compile(r"(?P<number>\d+)-(?P<revision>\d+)(?P<language>[A-Za-z])\.pdf", re.I)


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
        match = _FILE_NAME.fullmatch(file_name.strip())
        if match is None:
            return None
        return cls(
            number=match["number"],
            revision=int(match["revision"]),
            language=match["language"].upper(),
        )

    @property
    def key(self) -> str:
        """Identifica o manual em qualquer revisão: código + idioma (ex.: "95007003P")."""
        return f"{self.number}{self.language}"
