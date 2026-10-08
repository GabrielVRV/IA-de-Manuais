from manual_assistant.application.errors import NotAuthenticatedError
from manual_assistant.application.ports.security import TokenService
from manual_assistant.application.ports.user_repository import UserRepository
from manual_assistant.domain.user import User


class ResolveSessionUseCase:
    """Identifica o usuário de uma requisição a partir do token de sessão."""

    def __init__(self, *, users: UserRepository, tokens: TokenService) -> None:
        self._users = users
        self._tokens = tokens

    async def execute(self, token: str) -> User:
        """
        Raises:
            NotAuthenticatedError: token inválido/expirado, ou usuário removido/desativado.
        """
        user = await self._users.get(self._tokens.verify(token))
        if user is None or not user.is_active:
            raise NotAuthenticatedError("Sua sessão foi encerrada. Faça login novamente.")
        return user
