"""Configurações que os administradores alteram pela tela, sem reiniciar a API."""

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta

from manual_assistant.domain.errors import InvalidValueError

DEFAULT_USAGE_RETENTION_MONTHS = 12
USAGE_RETENTION_MAX_MONTHS = 120
DEFAULT_QUESTIONS_PER_MINUTE = 10
DEFAULT_QUESTIONS_PER_DAY = 200
QUESTION_LIMIT_MAX = 100_000


@dataclass(frozen=True, slots=True)
class QuestionLimit:
    """No máximo ``max_questions`` perguntas por usuário dentro de ``window``."""

    max_questions: int
    window: timedelta
    description: str  # como a janela aparece na mensagem: "1 minuto", "24 horas"

    def message(self) -> str:
        return (
            f"Você atingiu o limite de {self.max_questions} pergunta(s) em {self.description}. "
            "Tente novamente mais tarde."
        )


@dataclass(kw_only=True, slots=True)
class SystemSettings:
    # Por quantos meses o consumo de cada usuário é guardado. 0 = para sempre.
    usage_retention_months: int = DEFAULT_USAGE_RETENTION_MONTHS
    # Perguntas por usuário, para proteger a cota da API de IA. 0 = sem limite.
    questions_per_minute: int = DEFAULT_QUESTIONS_PER_MINUTE
    questions_per_day: int = DEFAULT_QUESTIONS_PER_DAY  # nas últimas 24 horas
    updated_at: datetime | None = None
    updated_by: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.usage_retention_months <= USAGE_RETENTION_MAX_MONTHS:
            raise InvalidValueError(
                f"A retenção do consumo precisa estar entre 0 e {USAGE_RETENTION_MAX_MONTHS} meses"
            )
        for limit in (self.questions_per_minute, self.questions_per_day):
            if not 0 <= limit <= QUESTION_LIMIT_MAX:
                raise InvalidValueError(
                    f"O limite de perguntas precisa estar entre 0 e {QUESTION_LIMIT_MAX}"
                )

    def usage_cutoff(self, now: datetime) -> datetime | None:
        """Consumo registrado antes desta data já pode ser apagado; None = guardar sempre."""
        if not self.usage_retention_months:
            return None
        return months_before(now, self.usage_retention_months)

    @property
    def question_limits(self) -> tuple[QuestionLimit, ...]:
        """Os limites ligados, do de janela mais curta para o de mais longa."""
        limits = (
            QuestionLimit(self.questions_per_minute, timedelta(minutes=1), "1 minuto"),
            QuestionLimit(self.questions_per_day, timedelta(hours=24), "24 horas"),
        )
        return tuple(limit for limit in limits if limit.max_questions)


def months_before(moment: datetime, months: int) -> datetime:
    """Mesmo dia, ``months`` meses antes; no último dia do mês quando ele não existe
    (31/03 menos um mês = 28 ou 29/02)."""
    month_index = moment.year * 12 + moment.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)
