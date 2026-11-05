from typing import Annotated

from fastapi import APIRouter, Query, status

from manual_assistant.domain.usage import MODEL_NAME_MAX_LENGTH
from manual_assistant.presentation.http.dependencies import AdminUser, UseCasesDep
from manual_assistant.presentation.http.schemas.settings import (
    ModelPriceResponse,
    SetModelPriceRequest,
    SystemSettingsResponse,
    UpdateSystemSettingsRequest,
)

# Configurações alteradas pela tela de administração, sem reiniciar a API.
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", summary="Configurações do sistema (somente administradores)")
async def get_settings(admin: AdminUser, use_cases: UseCasesDep) -> SystemSettingsResponse:
    return SystemSettingsResponse.from_entity(await use_cases.get_settings.execute(admin))


@router.patch("", summary="Altera as configurações enviadas (somente administradores)")
async def update_settings(
    request: UpdateSystemSettingsRequest, admin: AdminUser, use_cases: UseCasesDep
) -> SystemSettingsResponse:
    settings = await use_cases.update_settings.execute(
        admin, usage_retention_months=request.usage_retention_months
    )
    return SystemSettingsResponse.from_entity(settings)


@router.get(
    "/model-prices",
    summary="Preço de cada modelo, incluindo os já usados sem preço (somente administradores)",
)
async def list_model_prices(admin: AdminUser, use_cases: UseCasesDep) -> list[ModelPriceResponse]:
    pricings = await use_cases.list_model_prices.execute(admin)
    return [ModelPriceResponse.from_pricing(pricing) for pricing in pricings]


@router.put(
    "/model-prices",
    summary="Cadastra ou altera o preço de um modelo (somente administradores)",
)
async def set_model_price(
    request: SetModelPriceRequest, admin: AdminUser, use_cases: UseCasesDep
) -> ModelPriceResponse:
    price = await use_cases.set_model_price.execute(
        admin,
        model=request.model,
        input_per_million=request.input_per_million,
        output_per_million=request.output_per_million,
    )
    return ModelPriceResponse(
        model=price.model,
        configured=True,
        input_per_million=float(price.input_per_million),
        output_per_million=float(price.output_per_million),
    )


@router.delete(
    "/model-prices",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove o preço de um modelo (somente administradores)",
)
async def delete_model_price(
    admin: AdminUser,
    use_cases: UseCasesDep,
    model: Annotated[str, Query(min_length=1, max_length=MODEL_NAME_MAX_LENGTH)],
) -> None:
    await use_cases.delete_model_price.execute(admin, model=model)
