from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from manual_assistant.domain.usage import QuestionUsage
from manual_assistant.domain.user import UserId


@dataclass(frozen=True, slots=True)
class UsageAggregate:
    """Soma do consumo de um usuário com um modelo, num dia (no fuso da empresa)."""

    user_id: UserId
    model: str | None
    day: date
    questions: int
    input_tokens: int
    output_tokens: int


class UsageRepository(Protocol):
    """
    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def add(self, usage: QuestionUsage) -> None: ...

    async def aggregate(
        self, *, since: datetime, until: datetime, timezone: ZoneInfo
    ) -> Sequence[UsageAggregate]:
        """Consumo de ``since`` (inclusive) a ``until`` (exclusive), somado por usuário,
        modelo e dia; o dia é o do relógio em ``timezone``."""
        ...

    async def count_since(self, user_id: UserId, since: datetime) -> int:
        """Perguntas do usuário registradas a partir de ``since``."""
        ...

    async def models(self) -> Sequence[str]:
        """Modelos que já aparecem no consumo, em ordem alfabética."""
        ...

    async def delete_before(self, cutoff: datetime) -> int:
        """Apaga o consumo registrado antes de ``cutoff``; devolve quantos registros."""
        ...
