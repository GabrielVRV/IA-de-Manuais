from typing import Any

from fastapi import APIRouter, Request, Response, status

from manual_assistant.presentation.http.dependencies import (
    SESSION_COOKIE,
    SessionUser,
    UseCasesDep,
)
from manual_assistant.presentation.http.schemas.manuals import ErrorResponse
from manual_assistant.presentation.http.schemas.users import (
    ChangePasswordRequest,
    LoginRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}
}


@router.post(
    "/login",
    responses={
        **UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
    summary="Entra no sistema (usuário local ou do TOTVS); a sessão fica num cookie HttpOnly",
)
async def login(
    credentials: LoginRequest, request: Request, response: Response, use_cases: UseCasesDep
) -> UserResponse:
    session = await use_cases.authenticate_user.execute(
        username=credentials.username, password=credentials.password
    )
    response.set_cookie(
        SESSION_COOKIE,
        session.token.value,
        expires=session.token.expires_at,
        httponly=True,  # inacessível a scripts: um XSS não consegue roubar a sessão
        samesite="lax",  # não é enviado em requisições vindas de outros sites
        secure=request.app.state.cookie_secure,  # ligar quando houver HTTPS
        path="/",
    )
    return UserResponse.from_entity(session.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sai do sistema")
async def logout(request: Request, response: Response, use_cases: UseCasesDep) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await use_cases.logout.execute(token)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", responses=UNAUTHORIZED, summary="Usuário da sessão atual")
async def me(user: SessionUser) -> UserResponse:
    return UserResponse.from_entity(user)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=UNAUTHORIZED,
    summary="Troca a própria senha de um usuário local (obrigatório após uma senha provisória)",
)
async def change_password(
    request: ChangePasswordRequest, user: SessionUser, use_cases: UseCasesDep
) -> None:
    await use_cases.change_password.execute(
        user, current_password=request.current_password, new_password=request.new_password
    )
