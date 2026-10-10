from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request

from manual_assistant.application.errors import (
    AccessPendingError,
    NotAuthenticatedError,
    PasswordChangeRequiredError,
    PermissionDeniedError,
)
from manual_assistant.application.use_cases.authenticate_user import AuthenticateUserUseCase
from manual_assistant.application.use_cases.change_password import ChangePasswordUseCase
from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
from manual_assistant.application.use_cases.conversations import (
    ChatUseCase,
    DeleteConversationUseCase,
    GetConversationUseCase,
    ListConversationsUseCase,
    RenameConversationUseCase,
)
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.get_manual import GetManualUseCase
from manual_assistant.application.use_cases.get_manual_file import GetManualFileUseCase
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.list_manuals import ListManualsUseCase
from manual_assistant.application.use_cases.manage_users import (
    CreateUserUseCase,
    ListUsersUseCase,
    ResetUserPasswordUseCase,
    UpdateUserUseCase,
)
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.application.use_cases.resolve_session import (
    LogoutUseCase,
    ResolveSessionUseCase,
)
from manual_assistant.domain.user import User

SESSION_COOKIE = "ma_session"


@dataclass(frozen=True, slots=True)
class UseCases:
    """Casos de uso disponíveis para a API, montados na raiz de composição."""

    check_health: CheckHealthUseCase
    register_manual: RegisterManualUseCase
    index_manual: IndexManualUseCase
    list_manuals: ListManualsUseCase
    get_manual: GetManualUseCase
    get_manual_file: GetManualFileUseCase
    delete_manual: DeleteManualUseCase
    chat: ChatUseCase
    list_conversations: ListConversationsUseCase
    get_conversation: GetConversationUseCase
    rename_conversation: RenameConversationUseCase
    delete_conversation: DeleteConversationUseCase
    authenticate_user: AuthenticateUserUseCase
    resolve_session: ResolveSessionUseCase
    logout: LogoutUseCase
    change_password: ChangePasswordUseCase
    create_user: CreateUserUseCase
    list_users: ListUsersUseCase
    reset_user_password: ResetUserPasswordUseCase
    update_user: UpdateUserUseCase


def get_use_cases(request: Request) -> UseCases:
    return cast(UseCases, request.app.state.use_cases)


UseCasesDep = Annotated[UseCases, Depends(get_use_cases)]


def get_check_health(use_cases: UseCasesDep) -> CheckHealthUseCase:
    return use_cases.check_health


async def get_session_user(request: Request, use_cases: UseCasesDep) -> User:
    """Usuário da sessão, mesmo que ainda precise trocar a senha provisória ou aguarde
    a liberação do acesso."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise NotAuthenticatedError()
    return await use_cases.resolve_session.execute(token)


SessionUser = Annotated[User, Depends(get_session_user)]


def get_current_user(user: SessionUser) -> User:
    """Usuário liberado para usar o sistema: acesso aprovado e sem troca de senha pendente."""
    if user.is_pending:
        raise AccessPendingError()
    if user.must_change_password:
        raise PasswordChangeRequiredError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_admin_user(user: CurrentUser) -> User:
    if not user.is_admin:
        raise PermissionDeniedError("Apenas administradores podem realizar esta ação")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]
