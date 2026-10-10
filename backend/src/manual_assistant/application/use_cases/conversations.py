"""Conversas com o assistente e o histórico de cada usuário (ADR 0010).

Toda operação recebe quem está agindo: só o dono enxerga ou altera a conversa. A de outro
usuário responde como inexistente, para não revelar que ela existe.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import ConversationNotFoundError
from manual_assistant.application.ports.conversation_repository import ConversationRepository
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.domain.conversation import (
    Conversation,
    ConversationId,
    ConversationSummary,
    Exchange,
    RetentionPolicy,
)
from manual_assistant.domain.question import Question
from manual_assistant.domain.user import User

logger = logging.getLogger(__name__)

# Quantas trocas anteriores acompanham a pergunta: o bastante para entender
# continuações, sem encarecer cada chamada ao modelo.
CONTEXT_EXCHANGES = 3


async def _owned_conversation(
    conversations: ConversationRepository, actor: User, conversation_id: ConversationId
) -> Conversation:
    conversation = await conversations.get(conversation_id)
    if conversation is None or not conversation.is_owned_by(actor.id):
        raise ConversationNotFoundError()
    return conversation


@dataclass(frozen=True, slots=True)
class ChatReply:
    conversation: Conversation
    exchange: Exchange


class ChatUseCase:
    """Responde uma pergunta dentro de uma conversa e guarda a troca no histórico.

    Sem ``conversation_id``, começa uma conversa nova. Nada é gravado se a resposta
    falhar: o histórico só tem perguntas que foram respondidas.
    """

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        ask_question: AskQuestionUseCase,
        clock: Clock = utc_now,
    ) -> None:
        self._conversations = conversations
        self._ask_question = ask_question
        self._clock = clock

    async def execute(
        self, actor: User, question: Question, conversation_id: ConversationId | None = None
    ) -> ChatReply:
        if conversation_id is None:
            conversation, is_new = Conversation.start(actor.id, question, self._clock()), True
        else:
            conversation = await _owned_conversation(self._conversations, actor, conversation_id)
            is_new = False

        answer = await self._ask_question.execute(
            question, history=conversation.recent(CONTEXT_EXCHANGES)
        )
        exchange = conversation.record(question, answer, self._clock())

        if is_new:
            await self._conversations.add(conversation)
        else:
            await self._conversations.append(conversation, exchange)
        return ChatReply(conversation, exchange)


class ListConversationsUseCase:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(self, actor: User) -> Sequence[ConversationSummary]:
        return await self._conversations.list_by_owner(actor.id)


class GetConversationUseCase:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(self, actor: User, conversation_id: ConversationId) -> Conversation:
        return await _owned_conversation(self._conversations, actor, conversation_id)


class RenameConversationUseCase:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(
        self, actor: User, conversation_id: ConversationId, title: str
    ) -> Conversation:
        conversation = await _owned_conversation(self._conversations, actor, conversation_id)
        conversation.rename(title)
        await self._conversations.rename(conversation.id, conversation.title)
        return conversation


class DeleteConversationUseCase:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(self, actor: User, conversation_id: ConversationId) -> None:
        conversation = await _owned_conversation(self._conversations, actor, conversation_id)
        await self._conversations.delete(conversation.id)


class PurgeIdleConversationsUseCase:
    """Apaga as conversas paradas há mais tempo que a política de retenção permite."""

    def __init__(
        self,
        conversations: ConversationRepository,
        policy: RetentionPolicy,
        clock: Clock = utc_now,
    ) -> None:
        self._conversations = conversations
        self._policy = policy
        self._clock = clock

    async def execute(self) -> int:
        cutoff = self._policy.cutoff(self._clock())
        if cutoff is None:
            return 0
        removed = await self._conversations.delete_idle(updated_before=cutoff)
        if removed:
            logger.info("Conversas antigas apagadas: %d", removed)
        return removed
