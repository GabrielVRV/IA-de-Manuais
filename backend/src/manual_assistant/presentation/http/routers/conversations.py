from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response, status

from manual_assistant.domain.conversation import ConversationId
from manual_assistant.presentation.http.dependencies import CurrentUser, UseCasesDep
from manual_assistant.presentation.http.schemas.conversations import (
    ConversationRefResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    RenameConversationRequest,
)
from manual_assistant.presentation.http.schemas.manuals import ErrorResponse

# Cada usuário só enxerga as próprias conversas: a de outra pessoa responde 404.
router = APIRouter(prefix="/conversations", tags=["conversations"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}


@router.get("", summary="Lista as conversas do usuário, das mais recentes para as antigas")
async def list_conversations(
    user: CurrentUser, use_cases: UseCasesDep
) -> list[ConversationSummaryResponse]:
    summaries = await use_cases.list_conversations.execute(user)
    return [ConversationSummaryResponse.from_summary(s) for s in summaries]


@router.get("/{conversation_id}", responses=NOT_FOUND, summary="Abre uma conversa do histórico")
async def get_conversation(
    conversation_id: UUID, user: CurrentUser, use_cases: UseCasesDep
) -> ConversationResponse:
    conversation = await use_cases.get_conversation.execute(user, ConversationId(conversation_id))
    return ConversationResponse.from_entity(conversation)


@router.patch("/{conversation_id}", responses=NOT_FOUND, summary="Renomeia uma conversa")
async def rename_conversation(
    conversation_id: UUID,
    request: RenameConversationRequest,
    user: CurrentUser,
    use_cases: UseCasesDep,
) -> ConversationRefResponse:
    conversation = await use_cases.rename_conversation.execute(
        user, ConversationId(conversation_id), request.title
    )
    return ConversationRefResponse(id=conversation.id, title=conversation.title)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    summary="Apaga uma conversa do histórico",
)
async def delete_conversation(
    conversation_id: UUID, user: CurrentUser, use_cases: UseCasesDep
) -> Response:
    await use_cases.delete_conversation.execute(user, ConversationId(conversation_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
