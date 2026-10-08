"""Tradução centralizada dos erros de negócio para respostas HTTP."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from manual_assistant.application.errors import (
    AccountLockedError,
    ExternalServiceError,
    InvalidCredentialsError,
    InvalidDocumentError,
    ManualNotFoundError,
    NotAuthenticatedError,
    PermissionDeniedError,
    StoredFileNotFoundError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from manual_assistant.domain.errors import InvalidStateTransitionError, InvalidValueError

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[Exception], int] = {
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    NotAuthenticatedError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    AccountLockedError: status.HTTP_429_TOO_MANY_REQUESTS,
    ManualNotFoundError: status.HTTP_404_NOT_FOUND,
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    UserAlreadyExistsError: status.HTTP_409_CONFLICT,
    StoredFileNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidDocumentError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidValueError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidStateTransitionError: status.HTTP_409_CONFLICT,
    ExternalServiceError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


async def _handle(request: Request, error: Exception) -> JSONResponse:
    status_code = next(
        code for error_type, code in _STATUS_BY_ERROR.items() if isinstance(error, error_type)
    )
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error("%s %s: %s", request.method, request.url.path, error, exc_info=error)
    return JSONResponse(status_code=status_code, content={"detail": str(error)})


def register_error_handlers(app: FastAPI) -> None:
    for error_type in _STATUS_BY_ERROR:
        app.add_exception_handler(error_type, _handle)
