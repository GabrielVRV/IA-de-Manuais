"""Assistentes do chat e quem pode usar cada um (ADR 0013).

Cada assistente tem um acesso padrão (liberado para todos ou só para quem for liberado)
e cada usuário pode ter uma exceção ao padrão. Administradores usam todos.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import User

REQUEST_INSTRUCTIONS_MAX_LENGTH = 300
DEFAULT_REQUEST_INSTRUCTIONS = "Peça o acesso a um administrador do sistema."


class AssistantId(StrEnum):
    ENGINEERING = "engenharia"


@dataclass(frozen=True, slots=True)
class Assistant:
    id: AssistantId
    name: str
    topic: str  # do que ele trata, em poucas palavras


# Os assistentes existentes. Um novo (ex.: o da TI) entra aqui e no AssistantId.
ASSISTANTS: tuple[Assistant, ...] = (
    Assistant(AssistantId.ENGINEERING, "Assistente de Engenharia", "Manuais técnicos"),
)


def get_assistant(assistant_id: AssistantId) -> Assistant:
    return next(assistant for assistant in ASSISTANTS if assistant.id is assistant_id)


class DefaultAccess(StrEnum):
    """Quem usa o assistente quando o usuário não tem exceção."""

    OPEN = "open"  # todos os usuários ativos
    RESTRICTED = "restricted"  # só quem for liberado


class UserAccess(StrEnum):
    """Exceção ao acesso padrão, para um usuário."""

    GRANTED = "granted"
    DENIED = "denied"


@dataclass(kw_only=True, slots=True)
class AccessPolicy:
    assistant_id: AssistantId
    default_access: DefaultAccess = DefaultAccess.OPEN
    # Como pedir acesso (ex.: "Abra um chamado no GLPI"). None = mensagem padrão.
    request_instructions: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None

    def __post_init__(self) -> None:
        if self.request_instructions is not None:
            self.request_instructions = self.request_instructions.strip() or None
        if (
            self.request_instructions is not None
            and len(self.request_instructions) > REQUEST_INSTRUCTIONS_MAX_LENGTH
        ):
            raise InvalidValueError(
                "As instruções para pedir acesso podem ter no máximo "
                f"{REQUEST_INSTRUCTIONS_MAX_LENGTH} caracteres"
            )

    @property
    def instructions(self) -> str:
        return self.request_instructions or DEFAULT_REQUEST_INSTRUCTIONS

    def allows(self, user: User, exception: UserAccess | None) -> bool:
        """Administradores usam todos; senão vale a exceção do usuário, ou o padrão."""
        if user.is_admin:
            return True
        if exception is not None:
            return exception is UserAccess.GRANTED
        return self.default_access is DefaultAccess.OPEN

    def denial_message(self) -> str:
        return (
            f"Você não tem acesso ao {get_assistant(self.assistant_id).name}. {self.instructions}"
        )
