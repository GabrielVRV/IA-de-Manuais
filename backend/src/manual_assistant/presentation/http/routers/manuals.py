from pathlib import PureWindowsPath
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, status

from manual_assistant.domain.manual import TITLE_MAX_LENGTH, ManualId
from manual_assistant.presentation.http.dependencies import UseCasesDep
from manual_assistant.presentation.http.schemas.manuals import ErrorResponse, ManualResponse

router = APIRouter(prefix="/manuals", tags=["manuals"])

Responses = dict[int | str, dict[str, Any]]

NOT_FOUND: Responses = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
INVALID: Responses = {status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse}}
CONFLICT: Responses = {status.HTTP_409_CONFLICT: {"model": ErrorResponse}}


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses=INVALID,
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
) -> ManualResponse:
    register, index = use_cases.register_manual, use_cases.index_manual
    # Lê no máximo 1 byte além do limite: suficiente para recusar, sem carregar tudo.
    content = await file.read(register.max_bytes + 1)
    file_name = PureWindowsPath(file.filename or "manual.pdf").name  # aceita / e \
    manual = await register.execute(
        title=title or _title_from(file_name), file_name=file_name, content=content
    )

    manual = await index.prepare(manual.id)
    background.add_task(index.run, manual)
    return ManualResponse.from_entity(manual)


@router.get("", summary="Lista os manuais, do mais recente para o mais antigo")
async def list_manuals(use_cases: UseCasesDep) -> list[ManualResponse]:
    return [ManualResponse.from_entity(m) for m in await use_cases.list_manuals.execute()]


@router.get("/{manual_id}", responses=NOT_FOUND, summary="Consulta um manual e seu status")
async def get_manual(manual_id: UUID, use_cases: UseCasesDep) -> ManualResponse:
    return ManualResponse.from_entity(await use_cases.get_manual.execute(ManualId(manual_id)))


@router.post(
    "/{manual_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**NOT_FOUND, **CONFLICT},
    summary="Reprocessa um manual (ex.: após uma falha ou troca de provedor de IA)",
)
async def reindex_manual(
    manual_id: UUID, use_cases: UseCasesDep, background: BackgroundTasks
) -> ManualResponse:
    index = use_cases.index_manual
    manual = await index.prepare(ManualId(manual_id))
    background.add_task(index.run, manual)
    return ManualResponse.from_entity(manual)


@router.delete(
    "/{manual_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    summary="Exclui o manual, seus trechos e o arquivo original",
)
async def delete_manual(manual_id: UUID, use_cases: UseCasesDep) -> None:
    await use_cases.delete_manual.execute(ManualId(manual_id))


def _title_from(file_name: str) -> str:
    """'Manual_Prensa-P200.pdf' -> 'Manual Prensa P200'."""
    stem = PureWindowsPath(file_name).stem.replace("_", " ").replace("-", " ")
    return " ".join(stem.split())[:TITLE_MAX_LENGTH] or "Manual sem título"
