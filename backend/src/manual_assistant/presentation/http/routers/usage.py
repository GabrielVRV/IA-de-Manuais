from typing import Annotated

from fastapi import APIRouter, Query

from manual_assistant.application.use_cases.usage_report import REPORT_MAX_DAYS
from manual_assistant.presentation.http.dependencies import AdminUser, UseCasesDep
from manual_assistant.presentation.http.schemas.usage import UsageReportResponse

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get(
    "",
    summary="Consumo de tokens do período, por dia, usuário e modelo (somente administradores)",
)
async def get_usage_report(
    admin: AdminUser,
    use_cases: UseCasesDep,
    days: Annotated[int, Query(ge=1, le=REPORT_MAX_DAYS, description="Contando hoje")] = 30,
) -> UsageReportResponse:
    report = await use_cases.usage_report.execute(admin, days=days)
    return UsageReportResponse.from_report(report)
