r"""Comandos de administração executados no servidor.

Criar um administrador (inclusive o primeiro, ou para recuperar o acesso):
    python -m manual_assistant.cli create-admin --username gabriel --name "Gabriel"

No Docker (na raiz do projeto):
    docker compose exec api python -m manual_assistant.cli create-admin \
        --username gabriel --name "Gabriel"

Sincronizar com a pasta de manuais da Engenharia (a pasta só é lida, nunca alterada):
    python -m manual_assistant.cli sync-manuals --dry-run      # só mostra o plano
    python -m manual_assistant.cli sync-manuals --limit 3      # indexa no máximo 3
    python -m manual_assistant.cli sync-manuals --folder "J:\engpub_consulta\Manuais"
"""

import argparse
import asyncio
import getpass
import sys
from collections import Counter
from pathlib import Path

from manual_assistant.application.errors import ApplicationError
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.manage_users import (
    CreateUserUseCase,
    UseTotvsLoginUseCase,
)
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.application.use_cases.sync_manuals import (
    ApplyManualSyncUseCase,
    PlanManualSyncUseCase,
    SyncAction,
    SyncOutcome,
    SyncPlan,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import UserRole
from manual_assistant.infrastructure.ai.factory import build_ai_providers
from manual_assistant.infrastructure.documents.line_chunker import LineChunker
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from manual_assistant.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from manual_assistant.infrastructure.persistence.manual_repository import (
    SqlAlchemyManualRepository,
)
from manual_assistant.infrastructure.persistence.models import EMBEDDING_DIMENSIONS
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from manual_assistant.infrastructure.persistence.vector_store import PgVectorStore
from manual_assistant.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from manual_assistant.infrastructure.settings import Settings
from manual_assistant.infrastructure.source.folder_manual_source import FolderManualSource
from manual_assistant.infrastructure.storage.local_file_storage import LocalFileStorage

_ACTION_LABELS = {
    SyncAction.ADD: "novos",
    SyncAction.UPDATE: "alterados (nova revisão ou arquivo)",
    SyncAction.RETITLE: "com título novo na planilha",
    SyncAction.REMOVE: "a remover do sistema (saíram da pasta)",
    SyncAction.UNCHANGED: "sem mudança",
    SyncAction.IGNORE: "ignorados (use --verbose para ver o motivo)",
}


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


async def sync_manuals(
    settings: Settings, folder: Path, *, dry_run: bool, limit: int | None, verbose: bool, yes: bool
) -> int:
    engine = create_database_engine(settings.database_url)
    try:
        session_factory = create_session_factory(engine)
        repository = SqlAlchemyManualRepository(session_factory)
        source = FolderManualSource(folder, catalog_file=settings.sync_catalog_file)
        print(f"Lendo {folder} (somente leitura)...")
        plan = await PlanManualSyncUseCase(
            source=source, repository=repository, languages=settings.sync_languages
        ).execute()
        _print_plan(plan, verbose=verbose)

        pending = [
            item
            for item in plan.items
            if item.action not in (SyncAction.UNCHANGED, SyncAction.IGNORE)
        ]
        if dry_run or not pending:
            print("\nSimulação: nada foi alterado." if dry_run else "\nTudo em dia.")
            return 0
        to_index = sum(item.costs_indexing for item in pending)
        if limit is not None:
            to_index = min(to_index, limit)
        question = f"\nAplicar o plano e indexar {to_index} manual(is) (gasta API de IA)? [s/N] "
        if not yes and input(question).strip().lower() != "s":
            print("Cancelado: nada foi alterado.")
            return 0

        # Só aqui o provedor de IA é montado: a simulação funciona sem chave de API.
        ai = build_ai_providers(settings, embedding_dimensions=EMBEDDING_DIMENSIONS)
        storage = LocalFileStorage(settings.storage_dir)
        vector_store = PgVectorStore(session_factory, dimensions=EMBEDDING_DIMENSIONS)
        apply = ApplyManualSyncUseCase(
            source=source,
            repository=repository,
            storage=storage,
            register_manual=RegisterManualUseCase(
                repository, storage, max_bytes=settings.max_upload_bytes
            ),
            index_manual=IndexManualUseCase(
                repository=repository,
                storage=storage,
                parser=PdfiumDocumentParser(),
                chunker=LineChunker(),
                embeddings=ai.embeddings,
                vector_store=vector_store,
            ),
            delete_manual=DeleteManualUseCase(
                repository=repository, vector_store=vector_store, storage=storage
            ),
        )
        outcomes = await apply.execute(plan, limit=limit, on_progress=_print_outcome)
    finally:
        await engine.dispose()

    failures = sum(not outcome.ok for outcome in outcomes)
    print(f"\nConcluído: {len(outcomes) - failures} ok, {failures} com falha ou adiado(s).")
    return 1 if failures else 0


def _print_plan(plan: SyncPlan, *, verbose: bool) -> None:
    counts = Counter(item.action for item in plan.items)
    print()
    for action, label in _ACTION_LABELS.items():
        print(f"  {counts[action]:4d} {label}")
    print()
    for item in plan.items:
        if item.action is SyncAction.IGNORE:
            if verbose:
                print(f"  [ignorado] {item.reason}")
        elif item.action is not SyncAction.UNCHANGED:
            print(f"  [{item.action.value}] {item.file_name}: {item.title}")


def _print_outcome(outcome: SyncOutcome) -> None:
    mark = "ok" if outcome.ok else "FALHA"
    print(f"  [{mark}] {outcome.item.action.value} {outcome.item.file_name}: {outcome.detail}")


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
    sync = commands.add_parser(
        "sync-manuals", help="Sincroniza com a pasta de manuais da Engenharia (só leitura)"
    )
    sync.add_argument("--folder", type=Path, help="Padrão: APP_SYNC_SOURCE_DIR")
    sync.add_argument("--dry-run", action="store_true", help="Só mostra o plano, sem alterar nada")
    sync.add_argument("--limit", type=int, help="Máximo de manuais (re)indexados nesta execução")
    sync.add_argument("--verbose", action="store_true", help="Lista também os ignorados")
    sync.add_argument("--yes", action="store_true", help="Não pede confirmação")
    args = parser.parse_args(argv)

    try:
        if args.command == "sync-manuals":
            settings = Settings()
            folder = args.folder or settings.sync_source_dir
            if folder is None:
                raise InvalidValueError("Informe --folder ou defina APP_SYNC_SOURCE_DIR")
            return asyncio.run(
                sync_manuals(
                    settings,
                    folder,
                    dry_run=args.dry_run,
                    limit=args.limit,
                    verbose=args.verbose,
                    yes=args.yes,
                )
            )
        if args.command == "use-totvs":
            asyncio.run(use_totvs(Settings(), args.username))
        else:
            asyncio.run(create_admin(Settings(), args.username, args.name, _ask_password()))
    except (InvalidValueError, ApplicationError) as error:
        # UserAlreadyExistsError e UserNotFoundError são ApplicationError.
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
