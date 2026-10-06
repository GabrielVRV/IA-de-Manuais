from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request

from manual_assistant.application.use_cases.check_health import CheckHealthUseCase


@dataclass(frozen=True, slots=True)
class UseCases:
    """Casos de uso disponíveis para a API, montados na raiz de composição."""

    check_health: CheckHealthUseCase


def get_use_cases(request: Request) -> UseCases:
    return cast(UseCases, request.app.state.use_cases)


def get_check_health(
    use_cases: Annotated[UseCases, Depends(get_use_cases)],
) -> CheckHealthUseCase:
    return use_cases.check_health
