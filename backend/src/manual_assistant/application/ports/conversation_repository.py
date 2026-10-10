from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from manual_assistant.domain.conversation import (
    Conversation,
    ConversationId,
    ConversationSummary,
    Exchange,
)
from manual_assistant.domain.user import UserId


class ConversationRepository(Protocol):
    """
    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def add(self, conversation: Conversation) -> None:
        """Grava uma conversa nova, com as trocas que ela já tiver."""
        ...

    async def get(self, conversation_id: ConversationId) -> Conversation | None:
        """A conversa com todas as trocas, da mais antiga para a mais nova."""
        ...

    async def list_by_owner(self, owner_id: UserId) -> Sequence[ConversationSummary]:
        """Conversas do usuário, da usada mais recentemente para a mais antiga."""
        ...

    async def append(self, conversation: Conversation, exchange: Exchange) -> None:
        """Acrescenta a troca no fim e atualiza ``updated_at`` da conversa."""
        ...

    async def rename(self, conversation_id: ConversationId, title: str) -> None: ...

    async def delete(self, conversation_id: ConversationId) -> None: ...

    async def delete_idle(self, *, updated_before: datetime) -> int:
        """Apaga as conversas paradas desde antes de ``updated_before``; devolve quantas."""
        ...
