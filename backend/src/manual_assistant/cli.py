r"""Comandos de administração executados no servidor.

Criar um administrador (inclusive o primeiro, ou para recuperar o acesso):
    python -m manual_assistant.cli create-admin --username gabriel --name "Gabriel"

No Docker (na raiz do projeto):
    docker compose exec api python -m manual_assistant.cli create-admin \
        --username gabriel --name "Gabriel"
"""

import argparse
import asyncio
import getpass
import sys

from manual_assistant.application.errors import UserAlreadyExistsError, UserNotFoundError
from manual_assistant.application.use_cases.manage_users import (
    CreateUserUseCase,
    UseTotvsLoginUseCase,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import UserRole
from manual_assistant.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from manual_assistant.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from manual_assistant.infrastructure.settings import Settings


async def create_admin(settings: Settings, username: str, display_name: str, password: str) -> None:
    engine = create_database_engine(settings.database_url)
    try:
        users = SqlAlchemyUserRepository(create_session_factory(engine))
        create = CreateUserUseCase(users=users, hasher=Argon2PasswordHasher())
        user = await create.execute_as_system(
            username=username, display_name=display_name, role=UserRole.ADMIN, password=password
        )
        print(f"Administrador '{user.username}' criado.")
    finally:
        await engine.dispose()


async def use_totvs(settings: Settings, username: str) -> None:
    engine = create_database_engine(settings.database_url)
    try:
        users = SqlAlchemyUserRepository(create_session_factory(engine))
        user = await UseTotvsLoginUseCase(users).execute_as_system(username=username)
        print(f"'{user.username}' agora entra com a senha do TOTVS.")
    finally:
        await engine.dispose()


def _ask_password() -> str:
    # getpass não mostra o que é digitado e não deixa a senha no histórico do terminal.
    password = getpass.getpass("Senha do administrador: ")
    if password != getpass.getpass("Repita a senha: "):
        raise InvalidValueError("As senhas não conferem")
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m manual_assistant.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="Cria um usuário administrador")
    admin.add_argument("--username", required=True)
    admin.add_argument("--name", required=True, help="Nome de exibição")
    totvs = commands.add_parser(
        "use-totvs", help="Passa um usuário local a entrar com a senha do TOTVS"
    )
    totvs.add_argument("--username", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "use-totvs":
            asyncio.run(use_totvs(Settings(), args.username))
        else:
            asyncio.run(create_admin(Settings(), args.username, args.name, _ask_password()))
    except (InvalidValueError, UserAlreadyExistsError, UserNotFoundError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
