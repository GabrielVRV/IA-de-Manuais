from manual_assistant.application.errors import NotAuthenticatedError
from manual_assistant.application.ports.user_repository import UserRepository
from manual_assistant.application.sessions import SessionManager
from manual_assistant.domain.user import User


class ResolveSessionUseCase:
    """Identifica o usuário de uma requisição a partir do token de sessão."""

    def __init__(self, *, users: UserRepository, sessions: SessionManager) -> None:
        self._users = users
        self._sessions = sessions

    async def execute(self, token: str) -> User:
        """
        Raises:
            NotAuthenticatedError: sessão inválida/expirada, ou usuário removido/desativado.
        """
        user = await self._users.get(await self._sessions.resolve(token))
        if user is None or not user.is_active:
            raise NotAuthenticatedError("Sua sessão foi encerrada. Faça login novamente.")
        return user


class LogoutUseCase:
    def __init__(self, sessions: SessionManager) -> None:
        self._sessions = sessions

    async def execute(self, token: str) -> None:
        """Apaga a sessão no banco: o cookie deixa de valer mesmo que alguém o tenha copiado."""
        await self._sessions.end(token)
