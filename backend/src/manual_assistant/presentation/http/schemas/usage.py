from datetime import date
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field

from manual_assistant.application.use_cases.usage_report import UsageReport, UsageTotals


class UsageTotalsResponse(BaseModel):
    questions: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float = Field(description="Custo estimado, só dos modelos com preço cadastrado")
    cost_is_partial: bool = Field(description="Houve tokens de modelo sem preço cadastrado")

    @classmethod
    def from_totals(cls, totals: UsageTotals) -> Self:
        return cls(
            questions=totals.questions,
            input_tokens=totals.input_tokens,
            output_tokens=totals.output_tokens,
            total_tokens=totals.total_tokens,
            cost_usd=float(totals.cost),
            cost_is_partial=totals.cost_is_partial,
        )


class DayUsageResponse(BaseModel):
    day: date
    totals: UsageTotalsResponse


class UserUsageResponse(BaseModel):
    user_id: UUID
    username: str
    display_name: str
    totals: UsageTotalsResponse


class ModelUsageResponse(BaseModel):
    model: str
    priced: bool
    totals: UsageTotalsResponse


class UsageReportResponse(BaseModel):
    first_day: date
    last_day: date
    timezone: str
    totals: UsageTotalsResponse
    by_day: list[DayUsageResponse] = Field(description="Todos os dias do período")
    by_user: list[UserUsageResponse] = Field(description="De quem mais gastou para quem menos")
    by_model: list[ModelUsageResponse]
    unpriced_models: list[str] = Field(description="Modelos usados sem preço cadastrado")

    @classmethod
    def from_report(cls, report: UsageReport) -> Self:
        return cls(
            first_day=report.first_day,
            last_day=report.last_day,
            timezone=report.timezone,
            totals=UsageTotalsResponse.from_totals(report.totals),
            by_day=[
                DayUsageResponse(day=d.day, totals=UsageTotalsResponse.from_totals(d.totals))
                for d in report.by_day
            ],
            by_user=[
                UserUsageResponse(
                    user_id=u.user_id,
                    username=u.username,
                    display_name=u.display_name,
                    totals=UsageTotalsResponse.from_totals(u.totals),
                )
                for u in report.by_user
            ],
            by_model=[
                ModelUsageResponse(
                    model=m.model,
                    priced=m.priced,
                    totals=UsageTotalsResponse.from_totals(m.totals),
                )
                for m in report.by_model
            ],
            unpriced_models=report.unpriced_models,
        )
