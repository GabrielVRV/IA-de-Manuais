"""Relatório de consumo do modelo de linguagem para os administradores.

O custo é calculado na hora, com o preço de cada modelo cadastrado na tela de
configurações. Tokens de um modelo sem preço entram nos totais de tokens, mas não no
custo: o relatório avisa que o custo está incompleto.
"""

from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TypeVar
from zoneinfo import ZoneInfo

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import PermissionDeniedError
from manual_assistant.application.ports.settings_repository import ModelPriceRepository
from manual_assistant.application.ports.usage_repository import UsageAggregate, UsageRepository
from manual_assistant.application.ports.user_repository import UserRepository
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.usage import ModelPrice
from manual_assistant.domain.user import User, UserId

K = TypeVar("K", bound=Hashable)

REPORT_MAX_DAYS = 366
REMOVED_USER_NAME = "Usuário removido"


def require_admin(actor: User) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Apenas administradores podem ver o consumo")


@dataclass(frozen=True, slots=True)
class UsageTotals:
    questions: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: Decimal = Decimal(0)  # em dólares, só dos modelos com preço cadastrado
    cost_is_partial: bool = False  # houve tokens de modelo sem preço

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class UserUsage:
    user_id: UserId
    username: str
    display_name: str
    totals: UsageTotals


@dataclass(frozen=True, slots=True)
class DayUsage:
    day: date
    totals: UsageTotals


@dataclass(frozen=True, slots=True)
class ModelUsage:
    model: str
    totals: UsageTotals
    priced: bool


@dataclass(frozen=True, slots=True)
class UsageReport:
    first_day: date
    last_day: date
    timezone: str
    totals: UsageTotals
    by_day: Sequence[DayUsage]  # todos os dias do período, inclusive os sem uso
    by_user: Sequence[UserUsage]  # de quem mais gastou tokens para quem menos gastou
    by_model: Sequence[ModelUsage]

    @property
    def unpriced_models(self) -> list[str]:
        return [m.model for m in self.by_model if not m.priced]


class GetUsageReportUseCase:
    def __init__(
        self,
        *,
        usage: UsageRepository,
        users: UserRepository,
        prices: ModelPriceRepository,
        timezone: ZoneInfo,
        clock: Clock = utc_now,
    ) -> None:
        self._usage = usage
        self._users = users
        self._prices = prices
        self._timezone = timezone
        self._clock = clock

    async def execute(self, actor: User, *, days: int) -> UsageReport:
        """Consumo dos últimos ``days`` dias, contando hoje."""
        require_admin(actor)
        if not 1 <= days <= REPORT_MAX_DAYS:
            raise InvalidValueError(f"O período precisa ter de 1 a {REPORT_MAX_DAYS} dias")

        last_day = self._clock().astimezone(self._timezone).date()
        first_day = last_day - timedelta(days=days - 1)
        rows = await self._usage.aggregate(
            since=self._midnight(first_day),
            until=self._midnight(last_day + timedelta(days=1)),
            timezone=self._timezone,
        )
        prices = {price.model: price for price in await self._prices.list_all()}
        users = {user.id: user for user in await self._users.list_all()}

        by_day = _group(rows, key=lambda row: row.day, prices=prices)
        by_user = _group(rows, key=lambda row: row.user_id, prices=prices)
        by_model = _group(
            [row for row in rows if row.model is not None],
            key=lambda row: row.model or "",
            prices=prices,
        )
        return UsageReport(
            first_day=first_day,
            last_day=last_day,
            timezone=self._timezone.key,
            totals=_sum(rows, prices),
            by_day=[
                DayUsage(day, by_day.get(day, UsageTotals()))
                for day in (first_day + timedelta(days=n) for n in range(days))
            ],
            by_user=sorted(
                (_user_usage(uid, users.get(uid), totals) for uid, totals in by_user.items()),
                key=lambda u: (-u.totals.total_tokens, -u.totals.questions, u.display_name),
            ),
            by_model=[
                ModelUsage(model, totals, priced=model in prices)
                for model, totals in sorted(by_model.items())
            ],
        )

    def _midnight(self, day: date) -> datetime:
        return datetime.combine(day, time(), tzinfo=self._timezone)


def _group(
    rows: Iterable[UsageAggregate],
    *,
    key: Callable[[UsageAggregate], K],
    prices: Mapping[str, ModelPrice],
) -> dict[K, UsageTotals]:
    groups: dict[K, list[UsageAggregate]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    return {group: _sum(members, prices) for group, members in groups.items()}


def _sum(rows: Iterable[UsageAggregate], prices: Mapping[str, ModelPrice]) -> UsageTotals:
    questions = input_tokens = output_tokens = 0
    cost = Decimal(0)
    partial = False
    for row in rows:
        questions += row.questions
        input_tokens += row.input_tokens
        output_tokens += row.output_tokens
        if row.model is None or not (row.input_tokens or row.output_tokens):
            continue
        price = prices.get(row.model)
        if price is None:
            partial = True
        else:
            cost += price.cost(input_tokens=row.input_tokens, output_tokens=row.output_tokens)
    return UsageTotals(questions, input_tokens, output_tokens, cost, partial)


def _user_usage(user_id: UserId, user: User | None, totals: UsageTotals) -> UserUsage:
    if user is None:
        return UserUsage(user_id, "", REMOVED_USER_NAME, totals)
    return UserUsage(user_id, user.username, user.display_name, totals)
