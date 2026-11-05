from collections.abc import Mapping
from typing import Protocol

from manual_assistant.domain.assistant import AccessPolicy, AssistantId, UserAccess
from manual_assistant.domain.user import UserId


class AssistantAccessRepository(Protocol):
    """Acesso padrão de cada assistente e as exceções por usuário.

    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def get_policy(self, assistant_id: AssistantId) -> AccessPolicy:
        """A política salva, ou a padrão (liberado para todos) se nunca foi alterada."""
        ...

    async def save_policy(self, policy: AccessPolicy) -> None: ...

    async def user_access(self, user_id: UserId) -> Mapping[AssistantId, UserAccess]:
        """As exceções de um usuário; assistente ausente = segue o padrão."""
        ...

    async def all_user_access(self) -> Mapping[UserId, Mapping[AssistantId, UserAccess]]:
        """As exceções de todos os usuários que têm alguma."""
        ...

    async def set_user_access(
        self, user_id: UserId, assistant_id: AssistantId, access: UserAccess | None
    ) -> None:
        """Grava a exceção; ``None`` remove, e o usuário volta a seguir o padrão."""
        ...
