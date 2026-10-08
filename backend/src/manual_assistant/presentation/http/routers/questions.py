from typing import Any

from fastapi import APIRouter, Depends, status

from manual_assistant.domain.question import Question
from manual_assistant.presentation.http.dependencies import UseCasesDep, get_current_user
from manual_assistant.presentation.http.schemas.manuals import ErrorResponse
from manual_assistant.presentation.http.schemas.questions import AnswerResponse, QuestionRequest

router = APIRouter(
    prefix="/questions", tags=["questions"], dependencies=[Depends(get_current_user)]
)

UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}
}


@router.post(
    "",
    responses=UNAVAILABLE,
    summary="Responde uma pergunta com base nos manuais, citando manual e páginas",
)
async def ask_question(request: QuestionRequest, use_cases: UseCasesDep) -> AnswerResponse:
    answer = await use_cases.ask_question.execute(Question(request.question))
    return AnswerResponse.from_answer(answer)
