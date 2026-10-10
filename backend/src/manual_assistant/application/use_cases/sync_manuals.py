"""Sincronização dos manuais com a pasta da Engenharia (ADR 0009).

Duas etapas: ``PlanManualSyncUseCase`` compara a pasta com o que já está cadastrado
sem alterar nada (é o modo simulação); ``ApplyManualSyncUseCase`` executa o plano.
A pasta de origem só é lida, nunca alterada.
"""

import hashlib
import logging
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import TypeVar

from manual_assistant.application.errors import ApplicationError
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.ports.manual_source import ManualSource, SourceDocument
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.application.use_cases.register_manual import (
    RegisterManualUseCase,
    validate_pdf,
)
from manual_assistant.domain.errors import DomainError
from manual_assistant.domain.manual import TITLE_MAX_LENGTH, Manual, ManualStatus, SourceFile
from manual_assistant.domain.manual_code import ManualCode

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EmptyManualSourceError(ApplicationError):
    def __init__(self) -> None:
        # Sem esta trava, uma pasta de rede fora do ar faria todos os manuais serem removidos.
        super().__init__("A pasta de manuais está vazia ou não pôde ser lida. Nada foi alterado.")


class SyncAction(StrEnum):
    ADD = "add"  # novo na pasta
    UPDATE = "update"  # arquivo mudou (nova revisão ou conteúdo)
    RETITLE = "retitle"  # só a descrição na planilha mudou
    REMOVE = "remove"  # saiu da pasta (ou foi para "Versões Obsoletas")
    UNCHANGED = "unchanged"
    IGNORE = "ignore"  # fora das regras: nome fora do padrão, outro idioma, revisão antiga


@dataclass(frozen=True, slots=True)
class SyncItem:
    action: SyncAction
    file_name: str
    title: str = ""
    reason: str | None = None  # por que foi ignorado
    document: SourceDocument | None = None
    manual: Manual | None = None
    key: str | None = None

    @property
    def costs_indexing(self) -> bool:
        """Ações que (podem) gerar embeddings, ou seja, gastam API de IA."""
        return self.action in (SyncAction.ADD, SyncAction.UPDATE)


@dataclass(frozen=True, slots=True)
class SyncPlan:
    items: Sequence[SyncItem]

    def with_action(self, action: SyncAction) -> list[SyncItem]:
        return [item for item in self.items if item.action is action]


@dataclass(frozen=True, slots=True)
class SyncOutcome:
    item: SyncItem
    ok: bool
    detail: str


class PlanManualSyncUseCase:
    """Compara a pasta da Engenharia com os manuais cadastrados. Não altera nada."""

    def __init__(
        self,
        *,
        source: ManualSource,
        repository: ManualRepository,
        languages: Collection[str],
    ) -> None:
        self._source = source
        self._repository = repository
        self._languages = frozenset(language.upper() for language in languages)

    async def execute(self) -> SyncPlan:
        documents = await self._source.list_documents()
        if not documents:
            raise EmptyManualSourceError()

        items: list[SyncItem] = []
        current: dict[str, tuple[ManualCode, SourceDocument]] = {}
        for document in sorted(documents, key=lambda d: d.path):
            code = ManualCode.from_file_name(document.file_name)
            if code is None:
                items.append(_ignored(document, "nome fora do padrão código-revisãoIdioma.pdf"))
            elif code.language not in self._languages:
                items.append(_ignored(document, f"idioma '{code.language}' não sincronizado"))
            elif (best := current.get(code.key)) is None or code.revision > best[0].revision:
                if best is not None:
                    items.append(_ignored(best[1], f"revisão anterior a {document.file_name}"))
                current[code.key] = (code, document)
            else:
                items.append(_ignored(document, f"revisão anterior ou repetida de {best[1].path}"))

        synced = {m.source.key: m for m in await self._repository.list_all() if m.source}
        for key, (_, document) in sorted(current.items()):
            items.append(_compare(key, document, synced.pop(key, None)))
        items.extend(
            SyncItem(SyncAction.REMOVE, m.file_name, m.title, manual=m, key=m.source.key)
            for m in synced.values()
            if m.source
        )
        return SyncPlan(items)


class ApplyManualSyncUseCase:
    """Executa um plano: importa, atualiza e remove manuais no sistema.

    Uma falha num manual é registrada e não interrompe os demais.
    """

    def __init__(
        self,
        *,
        source: ManualSource,
        repository: ManualRepository,
        storage: FileStorage,
        register_manual: RegisterManualUseCase,
        index_manual: IndexManualUseCase,
        delete_manual: DeleteManualUseCase,
    ) -> None:
        self._source = source
        self._repository = repository
        self._storage = storage
        self._register = register_manual
        self._index = index_manual
        self._delete = delete_manual

    async def execute(
        self,
        plan: SyncPlan,
        *,
        limit: int | None = None,
        on_progress: Callable[[SyncOutcome], None] | None = None,
    ) -> list[SyncOutcome]:
        """``limit`` restringe quantos manuais são (re)indexados nesta execução, útil
        para testar com poucos antes de gastar API com a pasta inteira."""
        outcomes: list[SyncOutcome] = []
        indexed = 0
        for item in plan.items:
            if item.action in (SyncAction.UNCHANGED, SyncAction.IGNORE):
                continue
            if item.costs_indexing and limit is not None and indexed >= limit:
                outcome = SyncOutcome(item, ok=False, detail="adiado: limite desta execução")
            else:
                indexed += item.costs_indexing
                outcome = await self._apply_safely(item)
            outcomes.append(outcome)
            if on_progress is not None:
                on_progress(outcome)
        return outcomes

    async def _apply_safely(self, item: SyncItem) -> SyncOutcome:
        try:
            detail = await self._apply(item)
        except (ApplicationError, DomainError) as error:
            logger.warning("Falha ao sincronizar %s: %s", item.file_name, error)
            return SyncOutcome(item, ok=False, detail=str(error))
        return SyncOutcome(item, ok=True, detail=detail)

    async def _apply(self, item: SyncItem) -> str:
        match item.action:
            case SyncAction.ADD:
                return await self._add(item)
            case SyncAction.UPDATE:
                return await self._update(item)
            case SyncAction.RETITLE:
                manual = _required(item.manual)
                manual.update_from_source(
                    title=item.title, file_name=manual.file_name, source=_required(manual.source)
                )
                await self._repository.save(manual)
                return "título atualizado"
            case SyncAction.REMOVE:
                await self._delete.execute(_required(item.manual).id)
                return "removido do sistema (a pasta não foi alterada)"
            case _:
                return "nada a fazer"

    async def _add(self, item: SyncItem) -> str:
        document = _required(item.document)
        content = await self._source.read(document.path)
        manual = await self._register.execute(
            title=item.title,
            file_name=item.file_name,
            content=content,
            source=_source_file(_required(item.key), document, content),
        )
        return _indexing_result(await self._index.execute(manual.id))

    async def _update(self, item: SyncItem) -> str:
        document, manual = _required(item.document), _required(item.manual)
        if manual.status is ManualStatus.PROCESSING:
            raise SyncIndexingError(f"'{manual.title}' já está sendo indexado; fica para a próxima")

        content = await self._source.read(document.path)
        source = _source_file(_required(item.key), document, content)
        same_content = source.content_hash == _required(manual.source).content_hash
        if not same_content:
            validate_pdf(content, max_bytes=self._register.max_bytes)
            await self._storage.save(original_file_key(manual.id), content)
        manual.update_from_source(title=item.title, file_name=item.file_name, source=source)
        await self._repository.save(manual)
        if same_content:
            return "conteúdo igual ao já indexado: não precisou reindexar"
        return _indexing_result(await self._index.execute(manual.id))


def _compare(key: str, document: SourceDocument, manual: Manual | None) -> SyncItem:
    title = _title_of(document)
    item = SyncItem(
        SyncAction.UNCHANGED, document.file_name, title, document=document, manual=manual, key=key
    )
    if manual is None or manual.source is None:
        return _with_action(item, SyncAction.ADD)
    if manual.source.fingerprint != document.fingerprint or manual.file_name != document.file_name:
        return _with_action(item, SyncAction.UPDATE)
    if manual.title != title:
        return _with_action(item, SyncAction.RETITLE)
    return item


def _with_action(item: SyncItem, action: SyncAction) -> SyncItem:
    return SyncItem(
        action,
        item.file_name,
        item.title,
        document=item.document,
        manual=item.manual,
        key=item.key,
    )


def _ignored(document: SourceDocument, reason: str) -> SyncItem:
    return SyncItem(SyncAction.IGNORE, document.file_name, reason=f"{document.path}: {reason}")


def _title_of(document: SourceDocument) -> str:
    """Descrição da planilha; sem ela, o nome do arquivo (ex.: "95007003-01P")."""
    title = " ".join((document.title or "").split())
    return (title or PurePosixPath(document.file_name).stem)[:TITLE_MAX_LENGTH].strip()


def _source_file(key: str, document: SourceDocument, content: bytes) -> SourceFile:
    return SourceFile(
        key=key,
        fingerprint=document.fingerprint,
        content_hash=hashlib.sha256(content).hexdigest(),
    )


def _indexing_result(manual: Manual) -> str:
    if manual.status is ManualStatus.INDEXED:
        return f"indexado: {manual.page_count} páginas, {manual.chunk_count} trechos"
    raise SyncIndexingError(manual.failure_reason or "falha na indexação")


def _required(value: T | None) -> T:
    """Os campos de um SyncItem dependem da ação; o plano sempre preenche os necessários."""
    if value is None:
        raise ApplicationError("Plano de sincronização inconsistente")
    return value


class SyncIndexingError(ApplicationError):
    """O manual foi cadastrado/atualizado, mas a indexação falhou (detalhe no manual)."""
