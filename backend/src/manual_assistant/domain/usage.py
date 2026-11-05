"""Consumo do modelo de linguagem: quanto cada pergunta gastou e quanto isso custa.

Só números são guardados (usuário, data, modelo, tokens): o texto da pergunta fica
apenas no histórico de conversas, que tem retenção própria (ADR 0010).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import UserId

MODEL_NAME_MAX_LENGTH = 100
TOKENS_PER_PRICE_UNIT = 1_000_000  # os provedores cobram por milhão de tokens
PRICE_MAX = Decimal(10_000)


@dataclass(frozen=True, slots=True)
class QuestionUsage:
    """O que uma pergunta respondida gastou do modelo de linguagem."""

    user_id: UserId
    asked_at: datetime
    # None quando nada foi enviado ao modelo (nenhum trecho encontrado): não gastou tokens.
    model: str | None
    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        if self.asked_at.tzinfo is None:
            raise InvalidValueError("A data da pergunta precisa ter fuso horário")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise InvalidValueError("A quantidade de tokens não pode ser negativa")
        if self.model is not None:
            validate_model_name(self.model)
        elif self.input_tokens or self.output_tokens:
            raise InvalidValueError("Tokens gastos precisam informar o modelo")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Preço de um modelo em dólares por milhão de tokens, informado pelo administrador.

    O preço é por modelo: trocar de modelo não altera o custo calculado do que já passou.
    """

    model: str
    input_per_million: Decimal
    output_per_million: Decimal

    def __post_init__(self) -> None:
        validate_model_name(self.model)
        for price in (self.input_per_million, self.output_per_million):
            if not price.is_finite() or price < 0 or price > PRICE_MAX:
                raise InvalidValueError(f"O preço precisa estar entre 0 e {PRICE_MAX} dólares")

    def cost(self, *, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            self.input_per_million * input_tokens + self.output_per_million * output_tokens
        ) / TOKENS_PER_PRICE_UNIT


def validate_model_name(model: str) -> str:
    if not model.strip():
        raise InvalidValueError("O nome do modelo é obrigatório")
    if len(model) > MODEL_NAME_MAX_LENGTH:
        raise InvalidValueError(f"O nome do modelo excede {MODEL_NAME_MAX_LENGTH} caracteres")
    return model
