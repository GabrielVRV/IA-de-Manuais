from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import NewType, Self
from uuid import UUID, uuid4

from manual_assistant.domain.answer import Answer
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.question import Question
from manual_assistant.domain.user import UserId

ConversationId = NewType("ConversationId", UUID)

TITLE_MAX_LENGTH = 80
# O título automático é a primeira pergunta, encurtada para caber na lista do histórico.
AUTO_TITLE_LENGTH = 60


@dataclass(frozen=True, slots=True)
class Exchange:
    """Uma troca da conversa: a pergunta do usuário e a resposta do assistente."""

    question: str
    answer: Answer
    asked_at: datetime


@dataclass(eq=False, kw_only=True, slots=True)
class Conversation:
    """Conversa de um usuário com o assistente. Só o dono pode vê-la (ADR 0010)."""

    id: ConversationId
    owner_id: UserId
    title: str
    created_at: datetime
    updated_at: datetime
    exchanges: list[Exchange] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = validate_title(self.title)

    @classmethod
    def start(cls, owner_id: UserId, first_question: Question, now: datetime) -> Self:
        return cls(
            id=ConversationId(uuid4()),
            owner_id=owner_id,
            title=title_from(first_question),
            created_at=now,
            updated_at=now,
        )

    def is_owned_by(self, user_id: UserId) -> bool:
        return self.owner_id == user_id

    def rename(self, title: str) -> None:
        self.title = validate_title(title)

    def record(self, question: Question, answer: Answer, now: datetime) -> Exchange:
        exchange = Exchange(question=question.text, answer=answer, asked_at=now)
        self.exchanges.append(exchange)
        self.updated_at = now
        return exchange

    def recent(self, limit: int) -> tuple[Exchange, ...]:
        """As últimas trocas, da mais antiga para a mais nova: o contexto da próxima pergunta."""
        return tuple(self.exchanges[-limit:]) if limit > 0 else ()


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """O que a lista do histórico mostra, sem carregar as mensagens."""

    id: ConversationId
    title: str
    created_at: datetime
    updated_at: datetime
    exchange_count: int


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Conversas paradas há mais que ``max_idle`` são apagadas. ``None`` guarda para sempre."""

    max_idle: timedelta | None

    def cutoff(self, now: datetime) -> datetime | None:
        return None if self.max_idle is None else now - self.max_idle


def validate_title(title: str) -> str:
    title = " ".join(title.split())
    if not title:
        raise InvalidValueError("O título da conversa não pode ficar vazio")
    if len(title) > TITLE_MAX_LENGTH:
        raise InvalidValueError(f"O título pode ter no máximo {TITLE_MAX_LENGTH} caracteres")
    return title


def title_from(question: Question) -> str:
    """Primeira pergunta como título, cortada numa palavra inteira quando é longa."""
    text = " ".join(question.text.split())
    if len(text) <= AUTO_TITLE_LENGTH:
        return text
    cut = text[: AUTO_TITLE_LENGTH - 1].rsplit(" ", 1)[0].rstrip(" ,.;:?!")
    return f"{cut or text[: AUTO_TITLE_LENGTH - 1]}…"
