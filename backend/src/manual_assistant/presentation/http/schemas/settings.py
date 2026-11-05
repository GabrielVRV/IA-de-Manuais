from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field

from manual_assistant.application.use_cases.system_settings import ModelPricing
from manual_assistant.domain.system_settings import (
    QUESTION_LIMIT_MAX,
    USAGE_RETENTION_MAX_MONTHS,
    SystemSettings,
)
from manual_assistant.domain.usage import MODEL_NAME_MAX_LENGTH, PRICE_MAX


class SystemSettingsResponse(BaseModel):
    usage_retention_months: int = Field(description="0 = guardar o consumo para sempre")
    questions_per_minute: int = Field(description="Por usuário; 0 = sem limite")
    questions_per_day: int = Field(description="Por usuário, nas últimas 24 horas; 0 = sem limite")
    updated_at: datetime | None
    updated_by: str | None

    @classmethod
    def from_entity(cls, settings: SystemSettings) -> Self:
        return cls(
            usage_retention_months=settings.usage_retention_months,
            questions_per_minute=settings.questions_per_minute,
            questions_per_day=settings.questions_per_day,
            updated_at=settings.updated_at,
            updated_by=settings.updated_by,
        )


class UpdateSystemSettingsRequest(BaseModel):
    """Só os campos enviados mudam."""

    usage_retention_months: int | None = Field(default=None, ge=0, le=USAGE_RETENTION_MAX_MONTHS)
    questions_per_minute: int | None = Field(default=None, ge=0, le=QUESTION_LIMIT_MAX)
    questions_per_day: int | None = Field(default=None, ge=0, le=QUESTION_LIMIT_MAX)


class ModelPriceResponse(BaseModel):
    model: str
    configured: bool = Field(description="Falso quando o modelo foi usado mas não tem preço")
    input_per_million: float | None = Field(description="Dólares por milhão de tokens")
    output_per_million: float | None = Field(description="Dólares por milhão de tokens")

    @classmethod
    def from_pricing(cls, pricing: ModelPricing) -> Self:
        price = pricing.price
        return cls(
            model=pricing.model,
            configured=price is not None,
            input_per_million=float(price.input_per_million) if price else None,
            output_per_million=float(price.output_per_million) if price else None,
        )


class SetModelPriceRequest(BaseModel):
    model: str = Field(min_length=1, max_length=MODEL_NAME_MAX_LENGTH, examples=["gpt-4.1-mini"])
    input_per_million: Decimal = Field(ge=0, le=PRICE_MAX, decimal_places=6)
    output_per_million: Decimal = Field(ge=0, le=PRICE_MAX, decimal_places=6)
