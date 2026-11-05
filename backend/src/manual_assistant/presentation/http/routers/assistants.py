from typing import Any

from fastapi import APIRouter, status

from manual_assistant.domain.assistant import AssistantId
from manual_assistant.presentation.http.dependencies import AdminUser, CurrentUser, UseCasesDep
from manual_assistant.presentation.http.schemas.assistants import (
    AccessPolicyResponse,
    AvailableAssistantResponse,
    UpdateAccessPolicyRequest,
)
from manual_assistant.presentation.http.schemas.manuals import ErrorResponse

# Os assistentes do chat e quem pode usar cada um (ADR 0013).
router = APIRouter(prefix="/assistants", tags=["assistants"])

INVALID: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse}
}


@router.get("", summary="Os assistentes do chat e se quem está usando tem acesso a cada um")
async def list_my_assistants(
    user: CurrentUser, use_cases: UseCasesDep
) -> list[AvailableAssistantResponse]:
    return [
        AvailableAssistantResponse.from_entity(item)
        for item in await use_cases.list_my_assistants.execute(user)
    ]


@router.get("/access", summary="Acesso padrão de cada assistente (somente administradores)")
async def list_access_policies(
    admin: AdminUser, use_cases: UseCasesDep
) -> list[AccessPolicyResponse]:
    return [
        AccessPolicyResponse.from_entity(item)
        for item in await use_cases.list_access_policies.execute(admin)
    ]


@router.put(
    "/{assistant_id}/access",
    responses=INVALID,
    summary="Define o acesso padrão de um assistente (somente administradores)",
)
async def update_access_policy(
    assistant_id: AssistantId,
    request: UpdateAccessPolicyRequest,
    admin: AdminUser,
    use_cases: UseCasesDep,
) -> AccessPolicyResponse:
    await use_cases.update_access_policy.execute(
        admin,
        assistant_id,
        default_access=request.default_access,
        request_instructions=request.request_instructions,
    )
    policies = await use_cases.list_access_policies.execute(admin)
    return AccessPolicyResponse.from_entity(
        next(item for item in policies if item.assistant.id is assistant_id)
    )
