from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field

from manual_assistant.domain.user import (
    DISPLAY_NAME_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    AuthSource,
    User,
    UserRole,
)


class UserResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: UserRole
    auth_source: AuthSource
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> Self:
        return cls(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            auth_source=user.auth_source,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class CreateUserRequest(BaseModel):
    """Usuário local. Os do TOTVS são cadastrados sozinhos no primeiro login."""

    username: str = Field(examples=["maria.silva"])
    display_name: str = Field(max_length=DISPLAY_NAME_MAX_LENGTH, examples=["Maria Silva"])
    role: UserRole = UserRole.USER
    temporary_password: str = Field(
        max_length=PASSWORD_MAX_LENGTH,
        description="Senha provisória: o usuário precisa trocá-la no primeiro acesso",
    )


class ResetPasswordRequest(BaseModel):
    temporary_password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    role: UserRole | None = None
