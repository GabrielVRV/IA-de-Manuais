from typing import Any

from fastapi import APIRouter, Depends, status

from manual_assistant.presentation.http.dependencies import (
    AdminUser,
    UseCasesDep,
    get_admin_user,
)
from manual_assistant.presentation.http.schemas.manual_sync import (
    SyncCheckResponse,
    SyncRunResponse,
    SyncStatusResponse,
)
from manual_assistant.presentation.http.schemas.manuals import ErrorResponse

# Sincronização com a pasta de manuais da Engenharia (ADR 0009). Só administradores.
# A pasta só é lida: nada aqui cria, altera ou apaga arquivos nela.
router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(get_admin_user)])

UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}


@router.get("", summary="Situação da sincronização: em andamento ou resultado da última")
async def get_sync_status(use_cases: UseCasesDep) -> SyncStatusResponse:
    sync = use_cases.manual_sync
    return SyncStatusResponse(
        enabled=sync.enabled,
        running=sync.running,
        last_run=SyncRunResponse.from_run(sync.last_run) if sync.last_run else None,
    )


@router.post(
    "/check",
    responses=UNAVAILABLE,
    summary="Compara a pasta com os manuais cadastrados, sem alterar nada nem gastar API",
)
async def check_sync(use_cases: UseCasesDep) -> SyncCheckResponse:
    return SyncCheckResponse.from_plan(await use_cases.manual_sync.check())


@router.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    responses=UNAVAILABLE,
    summary="Sincroniza com a pasta; a indexação continua em segundo plano",
)
async def run_sync(use_cases: UseCasesDep, admin: AdminUser) -> SyncRunResponse:
    run = await use_cases.manual_sync.start(started_by=admin.display_name or admin.username)
    return SyncRunResponse.from_run(run)
