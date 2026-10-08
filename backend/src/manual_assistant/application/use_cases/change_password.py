from manual_assistant.application.ports.security import PasswordHasher
from manual_assistant.application.ports.user_repository import UserRepository
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import User, validate_password


class ChangePasswordUseCase:
    """O próprio usuário troca a senha (obrigatório depois de uma senha provisória)."""

    def __init__(self, *, users: UserRepository, hasher: PasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    async def execute(self, user: User, *, current_password: str, new_password: str) -> None:
        if not self._hasher.verify(current_password, user.password_hash):
            raise InvalidValueError("A senha atual está incorreta")
        if new_password == current_password:
            raise InvalidValueError("A nova senha precisa ser diferente da atual")
        validate_password(new_password, username=user.username)

        user.change_password(self._hasher.hash(new_password))
        await self._users.save(user)
