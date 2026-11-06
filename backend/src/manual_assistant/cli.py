r"""Comandos de administração executados no servidor.

Criar um administrador (inclusive o primeiro, ou para recuperar o acesso):
    python -m manual_assistant.cli create-admin --username gabriel --name "Gabriel"

No Docker (na raiz do projeto):
    docker compose exec api python -m manual_assistant.cli create-admin \
        --username gabriel --name "Gabriel"

Passar alguém a entrar com o usuário de rede (AD), mantendo perfil e histórico. Use
--ad-login quando o login de rede for diferente do atual (ex.: vinha do TOTVS):
    python -m manual_assistant.cli use-ad --username gviaro --ad-login gabriel.viaro

Sincronizar com a pasta de manuais da Engenharia (a pasta só é lida, nunca alterada):
    python -m manual_assistant.cli sync-manuals --dry-run      # só mostra o plano
    python -m manual_assistant.cli sync-manuals --limit 3      # indexa no máximo 3
    python -m manual_assistant.cli sync-manuals --folder "J:\engpub_consulta\Manuais"
    python -m manual_assistant.cli sync-manuals --figures      # descreve também as figuras

Descrever as figuras dos manuais já indexados, sem refazer o texto (ADR 0014). Gasta
uma chamada de IA por página com figuras; o que já foi descrito nunca é pago de novo:
    python -m manual_assistant.cli describe-figures --dry-run  # só conta as páginas
    python -m manual_assistant.cli describe-figures --limit 3  # no máximo 3 manuais
"""

import argparse
import asyncio
import getpass
import sys
from collections import Counter
from pathlib import Path

from manual_assistant.application.errors import ApplicationError
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.describe_figures import (
    DescribeFiguresUseCase,
    FigurePlanItem,
)
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.manage_users import (
    CreateUserUseCase,
    UseDirectoryLoginUseCase,
)
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.application.use_cases.sync_manuals import (
    ApplyManualSyncUseCase,
    PlanManualSyncUseCase,
    SyncAction,
    SyncOutcome,
    SyncPlan,
)
from manual_assistant.domain.errors import DomainError, InvalidValueError
from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.manual import ManualStatus
from manual_assistant.domain.user import UserRole
from manual_assistant.infrastructure.ai.factory import build_ai_providers
from manual_assistant.infrastructure.documents.line_chunker import LineChunker
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from manual_assistant.infrastructure.figures import build_figure_describer
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


async def use_ad(settings: Settings, username: str, ad_login: str | None) -> None:
    engine = create_database_engine(settings.database_url)
    try:
        users = SqlAlchemyUserRepository(create_session_factory(engine))
        user = await UseDirectoryLoginUseCase(users).execute_as_system(
            username=username, ad_login=ad_login
        )
        print(f"'{user.username}' agora entra com a senha de rede (AD).")
    finally:
        await engine.dispose()


async def sync_manuals(
    settings: Settings,
    folder: Path,
    *,
    dry_run: bool,
    limit: int | None,
    verbose: bool,
    yes: bool,
    describe_figures: bool = False,
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
        figures_note = " descrevendo as figuras" if describe_figures else ""
        question = (
            f"\nAplicar o plano e indexar {to_index} manual(is){figures_note} "
            "(gasta API de IA)? [s/N] "
        )
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
                figures=build_figure_describer(settings, session_factory, ai),
            ),
            delete_manual=DeleteManualUseCase(
                repository=repository, vector_store=vector_store, storage=storage
            ),
        )
        outcomes = await apply.execute(
            plan, limit=limit, on_progress=_print_outcome, describe_figures=describe_figures
        )
    finally:
        await engine.dispose()

    failures = sum(not outcome.ok for outcome in outcomes)
    print(f"\nConcluído: {len(outcomes) - failures} ok, {failures} com falha ou adiado(s).")
    return 1 if failures else 0


async def describe_figures(
    settings: Settings, *, dry_run: bool, limit: int | None, yes: bool
) -> int:
    engine = create_database_engine(settings.database_url)
    try:
        session_factory = create_session_factory(engine)
        repository = SqlAlchemyManualRepository(session_factory)
        ai = build_ai_providers(settings, embedding_dimensions=EMBEDDING_DIMENSIONS)
        use_case = DescribeFiguresUseCase(
            repository=repository,
            storage=LocalFileStorage(settings.storage_dir),
            parser=PdfiumDocumentParser(),
            figures=build_figure_describer(settings, session_factory, ai),
            embeddings=ai.embeddings,
            vector_store=PgVectorStore(session_factory, dimensions=EMBEDDING_DIMENSIONS),
        )
        manuals = [m for m in await repository.list_all() if m.status is ManualStatus.INDEXED]
        print(f"Procurando figuras em {len(manuals)} manual(is) indexado(s)...")
        plan: list[FigurePlanItem] = []
        for manual in manuals:
            try:
                plan.append(await use_case.plan(manual))
            except (ApplicationError, DomainError) as error:
                print(f"  [FALHA] {manual.file_name}: {error}")
        pending = [item for item in plan if item.pending]
        if limit is not None:
            pending = pending[:limit]
        for item in pending:
            print(
                f"  {item.pending:4d} de {item.with_figures:4d} página(s) com figuras: "
                f"{item.manual.file_name} ({item.manual.title})"
            )
        pages = sum(item.pending for item in pending)
        print(
            f"\n{sum(i.with_figures for i in plan)} página(s) com figuras; "
            f"{pages} a descrever em {len(pending)} manual(is)."
        )
        if dry_run or not pending:
            print("Simulação: nada foi alterado." if dry_run else "Tudo em dia.")
            return 0
        question = f"\nDescrever {pages} página(s) (uma chamada de IA por página)? [s/N] "
        if not yes and input(question).strip().lower() != "s":
            print("Cancelado: nada foi alterado.")
            return 0

        failures = input_tokens = output_tokens = 0
        for item in pending:
            print(f"\n{item.manual.file_name}: {item.pending} página(s)")
            try:
                result = await use_case.execute(item.manual, on_page=_print_figure)
            except (ApplicationError, DomainError) as error:
                failures += 1
                print(f"  [FALHA] {error} (o que já foi descrito fica guardado)")
                continue
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
            print(f"  [ok] {result.figure_count} página(s) com figuras no índice")
    finally:
        await engine.dispose()

    print(
        f"\nConcluído: {len(pending) - failures} ok, {failures} com falha. "
        f"Tokens: {input_tokens} de entrada, {output_tokens} de saída."
    )
    return 1 if failures else 0


def _print_figure(description: FigureDescription) -> None:
    summary = "descrita" if description.has_content else "sem conteúdo técnico"
    print(f"    p. {description.page}: {summary}")


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
    ad = commands.add_parser(
        "use-ad", help="Passa um usuário a entrar com a senha de rede (AD), mantendo o perfil"
    )
    ad.add_argument("--username", required=True, help="Login atual neste sistema")
    ad.add_argument("--ad-login", help="Login de rede, se for diferente do atual")
    sync = commands.add_parser(
        "sync-manuals", help="Sincroniza com a pasta de manuais da Engenharia (só leitura)"
    )
    sync.add_argument("--folder", type=Path, help="Padrão: APP_SYNC_SOURCE_DIR")
    sync.add_argument("--dry-run", action="store_true", help="Só mostra o plano, sem alterar nada")
    sync.add_argument("--limit", type=int, help="Máximo de manuais (re)indexados nesta execução")
    sync.add_argument("--verbose", action="store_true", help="Lista também os ignorados")
    sync.add_argument("--yes", action="store_true", help="Não pede confirmação")
    sync.add_argument(
        "--figures",
        action="store_true",
        help="Também descreve por IA as figuras (uma chamada por página com figuras)",
    )
    figures = commands.add_parser(
        "describe-figures", help="Descreve por IA as figuras dos manuais já indexados"
    )
    figures.add_argument(
        "--dry-run", action="store_true", help="Só conta as páginas, sem chamar a IA"
    )
    figures.add_argument("--limit", type=int, help="Máximo de manuais nesta execução")
    figures.add_argument("--yes", action="store_true", help="Não pede confirmação")
    args = parser.parse_args(argv)

    try:
        if args.command == "describe-figures":
            return asyncio.run(
                describe_figures(Settings(), dry_run=args.dry_run, limit=args.limit, yes=args.yes)
            )
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
                    describe_figures=args.figures,
                )
            )
        if args.command == "use-ad":
            asyncio.run(use_ad(Settings(), args.username, args.ad_login))
        else:
            asyncio.run(create_admin(Settings(), args.username, args.name, _ask_password()))
    except (InvalidValueError, ApplicationError) as error:
        # UserAlreadyExistsError e UserNotFoundError são ApplicationError.
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
