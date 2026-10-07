from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request

from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.get_manual import GetManualUseCase
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.list_manuals import ListManualsUseCase
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase


@dataclass(frozen=True, slots=True)
class UseCases:
    """Casos de uso disponíveis para a API, montados na raiz de composição."""

    check_health: CheckHealthUseCase
    register_manual: RegisterManualUseCase
    index_manual: IndexManualUseCase
    list_manuals: ListManualsUseCase
    get_manual: GetManualUseCase
    delete_manual: DeleteManualUseCase
    ask_question: AskQuestionUseCase


def get_use_cases(request: Request) -> UseCases:
    return cast(UseCases, request.app.state.use_cases)


UseCasesDep = Annotated[UseCases, Depends(get_use_cases)]


def get_check_health(use_cases: UseCasesDep) -> CheckHealthUseCase:
    return use_cases.check_health
