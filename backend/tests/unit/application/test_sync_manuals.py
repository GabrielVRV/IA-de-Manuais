import pytest

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.application.use_cases.sync_manuals import (
    ApplyManualSyncUseCase,
    EmptyManualSourceError,
    PlanManualSyncUseCase,
    SyncAction,
    SyncOutcome,
    SyncPlan,
)
from manual_assistant.domain.manual import Manual, ManualStatus
from tests.factories import FIXED_NOW
from tests.fakes import (
    FakeDocumentParser,
    FakeEmbeddingProvider,
    FakeManualSource,
    InMemoryFileStorage,
    InMemoryManualRepository,
    InMemoryVectorStore,
    OnePagePerFragmentChunker,
)

pytestmark = pytest.mark.anyio

V1 = b"%PDF-1.4 primeira revisao"
V2 = b"%PDF-1.4 segunda revisao"


class Context:
    def __init__(self) -> None:
        self.source = FakeManualSource()
        self.repository = InMemoryManualRepository()
        self.storage = InMemoryFileStorage()
        self.embeddings = FakeEmbeddingProvider()
        self.vector_store = InMemoryVectorStore()
        self.plan_use_case = PlanManualSyncUseCase(
            source=self.source, repository=self.repository, languages=["P"]
        )
        self.apply_use_case = ApplyManualSyncUseCase(
            source=self.source,
            repository=self.repository,
            storage=self.storage,
            register_manual=RegisterManualUseCase(
                self.repository, self.storage, clock=lambda: FIXED_NOW
            ),
            index_manual=IndexManualUseCase(
                repository=self.repository,
                storage=self.storage,
                parser=FakeDocumentParser(),
                chunker=OnePagePerFragmentChunker(),
                embeddings=self.embeddings,
                vector_store=self.vector_store,
            ),
            delete_manual=DeleteManualUseCase(
                repository=self.repository, vector_store=self.vector_store, storage=self.storage
            ),
        )

    async def plan(self) -> SyncPlan:
        return await self.plan_use_case.execute()

    async def sync(self, *, limit: int | None = None) -> list[SyncOutcome]:
        return await self.apply_use_case.execute(await self.plan(), limit=limit)

    def only_manual(self) -> Manual:
        [manual] = self.repository.manuals.values()
        return manual


@pytest.fixture
def ctx() -> Context:
    return Context()


def _actions(plan: SyncPlan) -> dict[str, SyncAction]:
    return {item.file_name: item.action for item in plan.items}


async def test_refuses_an_empty_folder_so_nothing_is_removed(ctx: Context) -> None:
    # Pasta de rede fora do ar costuma aparecer vazia: remover tudo seria um desastre.
    with pytest.raises(EmptyManualSourceError):
        await ctx.plan()


async def test_planning_reads_no_file_and_changes_nothing(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95007003-01P.pdf", V1)

    plan = await ctx.plan()

    assert _actions(plan) == {"95007003-01P.pdf": SyncAction.ADD}
    assert ctx.source.reads == []
    assert ctx.repository.manuals == {}


async def test_ignores_files_outside_the_rules(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95007003-01P.pdf")
    ctx.source.put("PROTEÍNA/95007003-01E.pdf")  # inglês: não sincronizado
    ctx.source.put("PROTEÍNA/P&D 08 - Manuais.pdf")  # fora do padrão de nome
    ctx.source.put("PROTEÍNA/95007008-00P.pdf")
    ctx.source.put("PROTEÍNA/95007008-05P.pdf")  # vale só a revisão mais nova
    ctx.source.put("PROTEÍNA/95007008-01P.pdf")

    plan = await ctx.plan()

    assert _actions(plan) == {
        "95007003-01P.pdf": SyncAction.ADD,
        "95007003-01E.pdf": SyncAction.IGNORE,
        "P&D 08 - Manuais.pdf": SyncAction.IGNORE,
        "95007008-00P.pdf": SyncAction.IGNORE,
        "95007008-01P.pdf": SyncAction.IGNORE,
        "95007008-05P.pdf": SyncAction.ADD,
    }


async def test_imports_and_indexes_a_new_manual(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95006001-00P.pdf", V1, title="MANUAL DE MONTAGEM INCUBADORA")

    [outcome] = await ctx.sync()

    manual = ctx.only_manual()
    assert outcome.ok
    assert (manual.title, manual.file_name, manual.status) == (
        "MANUAL DE MONTAGEM INCUBADORA",
        "95006001-00P.pdf",
        ManualStatus.INDEXED,
    )
    assert manual.source is not None
    assert manual.source.key == "95006001P"
    assert ctx.storage.files[original_file_key(manual.id)] == V1


async def test_title_falls_back_to_the_file_name(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95006001-00P.pdf")

    await ctx.sync()

    assert ctx.only_manual().title == "95006001-00P"


async def test_second_sync_has_nothing_to_do(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95006001-00P.pdf")
    await ctx.sync()
    ctx.source.reads.clear()

    plan = await ctx.plan()

    assert _actions(plan) == {"95006001-00P.pdf": SyncAction.UNCHANGED}
    assert await ctx.apply_use_case.execute(plan) == []
    assert ctx.source.reads == []


async def test_new_revision_replaces_the_same_manual_and_reindexes(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95007003-01P.pdf", V1)
    await ctx.sync()
    manual_id = ctx.only_manual().id
    # A Engenharia move a revisão antiga para "Versões Anteriores" e põe a nova.
    del ctx.source.files["PROTEÍNA/95007003-01P.pdf"]
    ctx.source.put("PROTEÍNA/95007003-02P.pdf", V2)
    ctx.embeddings.embedded_texts.clear()

    [outcome] = await ctx.sync()

    manual = ctx.only_manual()
    assert outcome.item.action is SyncAction.UPDATE
    assert (manual.id, manual.file_name, manual.status) == (
        manual_id,
        "95007003-02P.pdf",
        ManualStatus.INDEXED,
    )
    assert ctx.storage.files[original_file_key(manual_id)] == V2
    assert ctx.embeddings.embedded_texts  # reindexou


async def test_same_content_copied_again_is_not_reindexed(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95007003-01P.pdf", V1)
    await ctx.sync()
    ctx.source.put("PROTEÍNA/95007003-01P.pdf", V1)  # mesma coisa, data nova
    ctx.embeddings.embedded_texts.clear()

    [outcome] = await ctx.sync()

    assert outcome.ok
    assert "não precisou reindexar" in outcome.detail
    assert ctx.embeddings.embedded_texts == []
    assert _actions(await ctx.plan()) == {"95007003-01P.pdf": SyncAction.UNCHANGED}


async def test_updates_only_the_title_when_the_spreadsheet_changes(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95007003-01P.pdf", V1, title="Antigo")
    await ctx.sync()
    ctx.source.files["PROTEÍNA/95007003-01P.pdf"] = (V1, "Novo")
    ctx.source.reads.clear()

    [outcome] = await ctx.sync()

    assert outcome.item.action is SyncAction.RETITLE
    assert ctx.only_manual().title == "Novo"
    assert ctx.source.reads == []


async def test_removes_from_the_system_what_left_the_folder(ctx: Context) -> None:
    ctx.source.put("PROTEÍNA/95007003-01P.pdf")
    ctx.source.put("PROTEÍNA/95006001-00P.pdf")
    await ctx.sync()
    removed = next(m for m in ctx.repository.manuals.values() if m.file_name.startswith("950070"))
    del ctx.source.files["PROTEÍNA/95007003-01P.pdf"]

    await ctx.sync()

    assert removed.id not in ctx.repository.manuals
    assert original_file_key(removed.id) not in ctx.storage.files
    assert [m.file_name for m in ctx.repository.manuals.values()] == ["95006001-00P.pdf"]


async def test_never_touches_manuals_uploaded_by_hand(ctx: Context) -> None:
    uploaded = Manual.register(title="Enviado pela tela", file_name="x.pdf", now=FIXED_NOW)
    await ctx.repository.save(uploaded)
    ctx.source.put("PROTEÍNA/95006001-00P.pdf")

    plan = await ctx.plan()

    assert all(item.manual is not uploaded for item in plan.items)
    await ctx.apply_use_case.execute(plan)
    assert uploaded.id in ctx.repository.manuals


async def test_limit_postpones_the_rest(ctx: Context) -> None:
    for number in ("95000001", "95000002", "95000003"):
        ctx.source.put(f"ARMAZENAGEM/{number}-00P.pdf")

    outcomes = await ctx.sync(limit=2)

    assert [o.ok for o in outcomes] == [True, True, False]
    assert "adiado" in outcomes[2].detail
    assert len(ctx.repository.manuals) == 2
    # Na próxima execução, o que ficou para trás entra.
    assert [i.action for i in (await ctx.plan()).items].count(SyncAction.ADD) == 1


async def test_one_failure_does_not_stop_the_others(ctx: Context) -> None:
    ctx.source.put("ARMAZENAGEM/95000001-00P.pdf", b"isto nao e um pdf")
    ctx.source.put("ARMAZENAGEM/95000002-00P.pdf")

    outcomes = await ctx.sync()

    assert [(o.item.file_name, o.ok) for o in outcomes] == [
        ("95000001-00P.pdf", False),
        ("95000002-00P.pdf", True),
    ]
    assert "não é um PDF" in outcomes[0].detail


async def test_indexing_failure_is_reported(ctx: Context) -> None:
    ctx.source.put("ARMAZENAGEM/95000001-00P.pdf")
    ctx.embeddings.error = ExternalServiceError("cota esgotada")

    [outcome] = await ctx.sync()

    assert not outcome.ok
    assert "serviço externo" in outcome.detail
    assert ctx.only_manual().status is ManualStatus.FAILED
