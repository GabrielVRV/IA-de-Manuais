"""Descrição, por IA, das figuras e desenhos de uma página (ADR 0014).

O texto do PDF não diz o que mostram as fotos, os diagramas e os desenhos técnicos.
Cada página com figuras é enviada como imagem a um modelo com visão, e a descrição vira
um trecho a mais do manual, pesquisável e citado pela página.
"""

from dataclasses import dataclass
from datetime import datetime

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.usage import validate_model_name


@dataclass(frozen=True, slots=True)
class FigureDescription:
    """O que a IA viu nas figuras de uma página.

    ``text`` vazio (None) quando a página só tem elementos sem informação técnica (logotipo,
    moldura): fica registrado para a página não ser enviada de novo.
    """

    page: int
    text: str | None
    model: str
    described_at: datetime
    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        if self.page < 1:
            raise InvalidValueError(f"A numeração de páginas começa em 1 (recebido: {self.page})")
        if self.text is not None and not self.text.strip():
            raise InvalidValueError("Use None para uma página sem conteúdo técnico nas figuras")
        validate_model_name(self.model)
        if self.described_at.tzinfo is None:
            raise InvalidValueError("A data da descrição precisa ter fuso horário")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise InvalidValueError("A quantidade de tokens não pode ser negativa")

    @property
    def has_content(self) -> bool:
        return self.text is not None
