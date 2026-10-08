from collections.abc import Sequence
from typing import Protocol

from manual_assistant.domain.user import User, UserId


class UserRepository(Protocol):
    """
    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def save(self, user: User) -> None:
        """Insere ou atualiza.

        Raises:
            UserAlreadyExistsError: se outro usuário já usar o mesmo login.
        """
        ...

    async def get(self, user_id: UserId) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None:
        """Busca pelo login já normalizado (minúsculas)."""
        ...

    async def list_all(self) -> Sequence[User]:
        """Todos os usuários, em ordem alfabética de nome."""
        ...
