from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
from manual_assistant.presentation.http.dependencies import get_check_health
from manual_assistant.presentation.http.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
    summary="Verifica se a API e suas dependências estão operacionais",
)
async def health(
    request: Request,
    response: Response,
    check_health: Annotated[CheckHealthUseCase, Depends(get_check_health)],
) -> HealthResponse:
    report = await check_health.execute()
    if not report.is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse.from_report(report, version=request.app.version)
