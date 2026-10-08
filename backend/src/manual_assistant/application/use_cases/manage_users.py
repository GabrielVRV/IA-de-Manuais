"""Administração de usuários. Toda operação recebe quem está agindo (``actor``): a regra
"só administradores" vive aqui, e não apenas na API."""

from collections.abc import Sequence

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import (
    PermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from manual_assistant.application.ports.security import PasswordHasher
from manual_assistant.application.ports.user_repository import UserRepository
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import (
    User,
    UserId,
    UserRole,
    normalize_username,
    validate_password,
)


def _require_admin(actor: User) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Apenas administradores podem gerenciar usuários")


class CreateUserUseCase:
    def __init__(
        self, *, users: UserRepository, hasher: PasswordHasher, clock: Clock = utc_now
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._clock = clock

    async def execute(
        self,
        actor: User,
        *,
        username: str,
        display_name: str,
        role: UserRole,
        temporary_password: str,
    ) -> User:
        """Cria com senha provisória: o usuário precisa trocá-la no primeiro acesso."""
        _require_admin(actor)
        return await self._create(
            username=username,
            display_name=display_name,
            role=role,
            password=temporary_password,
            must_change_password=True,
        )

    async def execute_as_system(
        self, *, username: str, display_name: str, role: UserRole, password: str
    ) -> User:
        """Para o terminal do servidor (ex.: criar o primeiro administrador).

        Quem tem acesso ao servidor já é de confiança; a senha escolhida ali é definitiva.
        """
        return await self._create(
            username=username,
            display_name=display_name,
            role=role,
            password=password,
            must_change_password=False,
        )

    async def _create(
        self,
        *,
        username: str,
        display_name: str,
        role: UserRole,
        password: str,
        must_change_password: bool,
    ) -> User:
        normalized = normalize_username(username)
        validate_password(password, username=normalized)
        if await self._users.get_by_username(normalized) is not None:
            raise UserAlreadyExistsError(normalized)

        user = User.register(
            username=normalized,
            display_name=display_name,
            role=role,
            password_hash=self._hasher.hash(password),
            now=self._clock(),
        )
        user.must_change_password = must_change_password
        await self._users.save(user)
        return user


class ListUsersUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, actor: User) -> Sequence[User]:
        _require_admin(actor)
        return await self._users.list_all()


class ResetUserPasswordUseCase:
    def __init__(self, *, users: UserRepository, hasher: PasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    async def execute(self, actor: User, user_id: UserId, *, temporary_password: str) -> User:
        _require_admin(actor)
        user = await _get_or_raise(self._users, user_id)
        validate_password(temporary_password, username=user.username)
        user.reset_password(self._hasher.hash(temporary_password))
        await self._users.save(user)
        return user


class UpdateUserUseCase:
    """Ativa/desativa e muda o perfil de um usuário."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(
        self,
        actor: User,
        user_id: UserId,
        *,
        is_active: bool | None = None,
        role: UserRole | None = None,
    ) -> User:
        _require_admin(actor)
        if user_id == actor.id and (is_active is False or role is UserRole.USER):
            # Evita que o último administrador se tranque do lado de fora por engano.
            raise InvalidValueError("Você não pode desativar nem rebaixar a si mesmo")

        user = await _get_or_raise(self._users, user_id)
        if is_active is True:
            user.activate()
        elif is_active is False:
            user.deactivate()
        if role is not None:
            user.role = role
        await self._users.save(user)
        return user


async def _get_or_raise(users: UserRepository, user_id: UserId) -> User:
    user = await users.get(user_id)
    if user is None:
        raise UserNotFoundError(user_id)
    return user
