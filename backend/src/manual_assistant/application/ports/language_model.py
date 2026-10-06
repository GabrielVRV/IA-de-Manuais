from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    system_instruction: str
    prompt: str
    # Temperatura baixa: respostas técnicas precisam ser fiéis ao manual, não criativas.
    temperature: float = 0.2
    max_output_tokens: int = 1024


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    model: str
    usage: TokenUsage  # base para o controle de custos


class LanguageModel(Protocol):
    """Modelo de linguagem que gera respostas (Gemini, GPT...)."""

    async def complete(self, request: CompletionRequest) -> Completion:
        """
        Raises:
            ExternalServiceError: se o provedor falhar, recusar ou não responder.
        """
        ...
