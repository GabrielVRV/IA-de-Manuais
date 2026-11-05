from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from manual_assistant.domain.assistant import AssistantId, UserAccess
from manual_assistant.domain.user import UserId
from manual_assistant.presentation.http.dependencies import AdminUser, UseCasesDep
from manual_assistant.presentation.http.schemas.assistants import SetUserAccessRequest
from manual_assistant.presentation.http.schemas.manuals import ErrorResponse
from manual_assistant.presentation.http.schemas.users import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["users"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}


@router.get("", summary="Lista os usuários (somente administradores)")
async def list_users(admin: AdminUser, use_cases: UseCasesDep) -> list[UserResponse]:
    access = await use_cases.list_user_access.execute(admin)
    return [
        UserResponse.from_entity(user, access.get(user.id))
        for user in await use_cases.list_users.execute(admin)
    ]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"model": ErrorResponse}},
    summary="Cria um usuário local com senha provisória (somente administradores)",
)
async def create_user(
    request: CreateUserRequest, admin: AdminUser, use_cases: UseCasesDep
) -> UserResponse:
    user = await use_cases.create_user.execute(
        admin,
        username=request.username,
        display_name=request.display_name,
        role=request.role,
        temporary_password=request.temporary_password,
    )
    return UserResponse.from_entity(user)


@router.post(
    "/{user_id}/reset-password",
    responses=NOT_FOUND,
    summary="Define uma senha provisória para um usuário local (somente administradores)",
)
async def reset_password(
    user_id: UUID, request: ResetPasswordRequest, admin: AdminUser, use_cases: UseCasesDep
) -> UserResponse:
    user = await use_cases.reset_user_password.execute(
        admin, UserId(user_id), temporary_password=request.temporary_password
    )
    return UserResponse.from_entity(user)


@router.patch(
    "/{user_id}",
    responses=NOT_FOUND,
    summary="Ativa/desativa ou muda o perfil (somente administradores)",
)
async def update_user(
    user_id: UUID, request: UpdateUserRequest, admin: AdminUser, use_cases: UseCasesDep
) -> UserResponse:
    user = await use_cases.update_user.execute(
        admin, UserId(user_id), is_active=request.is_active, role=request.role
    )
    return UserResponse.from_entity(user)


@router.put(
    "/{user_id}/assistants/{assistant_id}",
    responses=NOT_FOUND,
    summary="Libera ou bloqueia um assistente para o usuário, ou volta ao padrão "
    "(somente administradores)",
)
async def set_user_access(
    user_id: UUID,
    assistant_id: AssistantId,
    request: SetUserAccessRequest,
    admin: AdminUser,
    use_cases: UseCasesDep,
) -> dict[AssistantId, UserAccess]:
    return dict(
        await use_cases.set_user_access.execute(
            admin, UserId(user_id), assistant_id, request.access
        )
    )
