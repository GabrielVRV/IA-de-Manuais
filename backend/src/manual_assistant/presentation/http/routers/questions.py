from typing import Any

from fastapi import APIRouter, status

from manual_assistant.domain.conversation import ConversationId
from manual_assistant.domain.question import Question
from manual_assistant.presentation.http.dependencies import CurrentUser, UseCasesDep
from manual_assistant.presentation.http.schemas.conversations import ChatResponse
from manual_assistant.presentation.http.schemas.manuals import ErrorResponse
from manual_assistant.presentation.http.schemas.questions import QuestionRequest

router = APIRouter(prefix="/questions", tags=["questions"])

RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}


@router.post(
    "",
    responses=RESPONSES,
    summary="Responde uma pergunta com base nos manuais e guarda a troca no histórico",
)
async def ask_question(
    request: QuestionRequest, user: CurrentUser, use_cases: UseCasesDep
) -> ChatResponse:
    conversation_id = ConversationId(request.conversation_id) if request.conversation_id else None
    reply = await use_cases.chat.execute(user, Question(request.question), conversation_id)
    return ChatResponse.from_reply(reply)
