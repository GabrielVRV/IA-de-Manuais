from dataclasses import dataclass

from manual_assistant.domain.errors import InvalidValueError

QUESTION_MIN_LENGTH = 3
# Limita o custo por pergunta e evita que colem um manual inteiro como "pergunta".
QUESTION_MAX_LENGTH = 2000


@dataclass(frozen=True, slots=True)
class Question:
    text: str

    def __post_init__(self) -> None:
        text = self.text.strip()
        if len(text) < QUESTION_MIN_LENGTH:
            raise InvalidValueError(
                f"A pergunta precisa ter ao menos {QUESTION_MIN_LENGTH} caracteres"
            )
        if len(text) > QUESTION_MAX_LENGTH:
            raise InvalidValueError(f"A pergunta excede {QUESTION_MAX_LENGTH} caracteres")
        object.__setattr__(self, "text", text)
