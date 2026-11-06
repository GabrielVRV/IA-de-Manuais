from pathlib import PureWindowsPath
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    status,
)

from manual_assistant.domain.manual import TITLE_MAX_LENGTH, ManualId
from manual_assistant.presentation.http.dependencies import (
    CurrentUser,
    UseCasesDep,
    get_admin_user,
    get_current_user,
)
from manual_assistant.presentation.http.schemas.manuals import (
    ErrorResponse,
    FigurePlanResponse,
    ManualResponse,
)

# Consultar exige login; alterar (enviar, reprocessar, excluir) exige administrador.
router = APIRouter(prefix="/manuals", tags=["manuals"], dependencies=[Depends(get_current_user)])
ADMIN_ONLY = [Depends(get_admin_user)]

Responses = dict[int | str, dict[str, Any]]

NOT_FOUND: Responses = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
INVALID: Responses = {status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse}}
CONFLICT: Responses = {status.HTTP_409_CONFLICT: {"model": ErrorResponse}}

_DESCRIBE_FIGURES = (
    "Também descreve por IA as figuras das páginas (uma chamada por página com figuras)"
)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses=INVALID,
    dependencies=ADMIN_ONLY,
    summary="Envia o PDF de um manual; a indexação continua em segundo plano",
)
async def upload_manual(
    use_cases: UseCasesDep,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File(description="PDF do manual")],
    title: Annotated[
        str | None,
        Form(max_length=TITLE_MAX_LENGTH, description="Padrão: nome do arquivo"),
    ] = None,
    describe_figures: Annotated[bool, Form(description=_DESCRIBE_FIGURES)] = False,
) -> ManualResponse:
    register, index = use_cases.register_manual, use_cases.index_manual
    # Lê no máximo 1 byte além do limite: suficiente para recusar, sem carregar tudo.
    content = await file.read(register.max_bytes + 1)
    file_name = PureWindowsPath(file.filename or "manual.pdf").name  # aceita / e \
    manual = await register.execute(
        title=title or _title_from(file_name), file_name=file_name, content=content
    )

    manual = await index.prepare(manual.id)
    background.add_task(index.run, manual, describe_figures=describe_figures)
    return ManualResponse.from_entity(manual)


@router.get("", summary="Lista os manuais, do mais recente para o mais antigo")
async def list_manuals(use_cases: UseCasesDep) -> list[ManualResponse]:
    figures = use_cases.figure_descriptions
    return [
        ManualResponse.from_entity(m, figures.job(m.id))
        for m in await use_cases.list_manuals.execute()
    ]


@router.get("/{manual_id}", responses=NOT_FOUND, summary="Consulta um manual e seu status")
async def get_manual(manual_id: UUID, use_cases: UseCasesDep) -> ManualResponse:
    manual = await use_cases.get_manual.execute(ManualId(manual_id))
    return ManualResponse.from_entity(manual, use_cases.figure_descriptions.job(manual.id))


@router.get(
    "/{manual_id}/file",
    response_class=Response,
    responses={**NOT_FOUND, status.HTTP_200_OK: {"content": {"application/pdf": {}}}},
    summary="Abre o PDF original (use #page=N na URL para ir direto à página)",
)
async def get_manual_file(manual_id: UUID, user: CurrentUser, use_cases: UseCasesDep) -> Response:
    manual_file = await use_cases.get_manual_file.execute(user, ManualId(manual_id))
    return Response(
        content=manual_file.content,
        media_type="application/pdf",
        headers={
            # inline: o navegador abre o PDF em vez de baixar; filename* aceita acentos.
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(manual_file.file_name)}",
        },
    )


@router.post(
    "/{manual_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**NOT_FOUND, **CONFLICT},
    dependencies=ADMIN_ONLY,
    summary="Reprocessa um manual (ex.: após uma falha ou troca de provedor de IA)",
)
async def reindex_manual(
    manual_id: UUID,
    use_cases: UseCasesDep,
    background: BackgroundTasks,
    describe_figures: Annotated[bool, Query(description=_DESCRIBE_FIGURES)] = False,
) -> ManualResponse:
    index = use_cases.index_manual
    manual = await index.prepare(ManualId(manual_id))
    background.add_task(index.run, manual, describe_figures=describe_figures)
    return ManualResponse.from_entity(manual)


@router.get(
    "/{manual_id}/figures",
    responses=NOT_FOUND,
    dependencies=ADMIN_ONLY,
    summary="Quantas páginas têm figuras e quantas faltam descrever (não chama a IA)",
)
async def get_figure_plan(manual_id: UUID, use_cases: UseCasesDep) -> FigurePlanResponse:
    plan = await use_cases.figure_descriptions.plan(ManualId(manual_id))
    return FigurePlanResponse.from_plan(plan)


@router.post(
    "/{manual_id}/figures",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**NOT_FOUND, **CONFLICT},
    dependencies=ADMIN_ONLY,
    summary="Descreve por IA as figuras de um manual indexado, sem refazer o texto",
)
async def describe_figures(manual_id: UUID, use_cases: UseCasesDep) -> ManualResponse:
    figures = use_cases.figure_descriptions
    manual = await figures.start(ManualId(manual_id))
    return ManualResponse.from_entity(manual, figures.job(manual.id))


@router.delete(
    "/{manual_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    dependencies=ADMIN_ONLY,
    summary="Exclui o manual, seus trechos e o arquivo original",
)
async def delete_manual(manual_id: UUID, use_cases: UseCasesDep) -> None:
    await use_cases.delete_manual.execute(ManualId(manual_id))


def _title_from(file_name: str) -> str:
    """'Manual_Prensa-P200.pdf' -> 'Manual Prensa P200'."""
    stem = PureWindowsPath(file_name).stem.replace("_", " ").replace("-", " ")
    return " ".join(stem.split())[:TITLE_MAX_LENGTH] or "Manual sem título"
