from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from manual_assistant.domain.user import UserId
from manual_assistant.presentation.http.dependencies import AdminUser, UseCasesDep
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
    return [UserResponse.from_entity(u) for u in await use_cases.list_users.execute(admin)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"model": ErrorResponse}},
    summary="Cria um usuário com senha provisória (somente administradores)",
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
    summary="Define uma senha provisória (somente administradores)",
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
