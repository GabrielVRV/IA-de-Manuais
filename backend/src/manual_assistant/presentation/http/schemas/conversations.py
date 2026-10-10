from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field

from manual_assistant.application.use_cases.conversations import ChatReply
from manual_assistant.domain.conversation import (
    TITLE_MAX_LENGTH,
    Conversation,
    ConversationSummary,
    Exchange,
)
from manual_assistant.presentation.http.schemas.questions import AnswerResponse


class ConversationRefResponse(BaseModel):
    id: UUID
    title: str


class ChatResponse(AnswerResponse):
    """A resposta e a conversa onde ela foi guardada (nova ou a que já estava aberta)."""

    conversation: ConversationRefResponse

    @classmethod
    def from_reply(cls, reply: ChatReply) -> Self:
        answer = AnswerResponse.from_answer(reply.exchange.answer)
        return cls(
            answer=answer.answer,
            found=answer.found,
            citations=answer.citations,
            conversation=ConversationRefResponse(
                id=reply.conversation.id, title=reply.conversation.title
            ),
        )


class ConversationSummaryResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    exchange_count: int

    @classmethod
    def from_summary(cls, summary: ConversationSummary) -> Self:
        return cls(
            id=summary.id,
            title=summary.title,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
            exchange_count=summary.exchange_count,
        )


class ExchangeResponse(BaseModel):
    question: str
    answer: AnswerResponse
    asked_at: datetime

    @classmethod
    def from_exchange(cls, exchange: Exchange) -> Self:
        return cls(
            question=exchange.question,
            answer=AnswerResponse.from_answer(exchange.answer),
            asked_at=exchange.asked_at,
        )


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    exchanges: list[ExchangeResponse]

    @classmethod
    def from_entity(cls, conversation: Conversation) -> Self:
        return cls(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            exchanges=[ExchangeResponse.from_exchange(e) for e in conversation.exchanges],
        )


class RenameConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH, examples=["Pressão da P-200"])
