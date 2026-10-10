from pathlib import Path

import pytest
from openpyxl import Workbook

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.infrastructure.source.folder_manual_source import FolderManualSource

pytestmark = pytest.mark.anyio

CATALOG = "MANUAIS PRODUTO.xlsm"


def _write(path: Path, content: bytes = b"%PDF-1.4") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_catalog(path: Path) -> None:
    # Mesmo formato da planilha da Engenharia: título e linhas soltas antes do cabeçalho.
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["#VALUE!", "Manuais Produto"])
    sheet.append([])
    sheet.append(["Código", "Descrição", "Segmento", "Situação"])
    sheet.append(["95006001-00P", "MANUAL DE MONTAGEM INCUBADORAS", "INCUBAÇÃO", "Ativo"])
    sheet.append(["95006002-00p", "  NASCEDOURO G 21  ", "INCUBAÇÃO", "Ativo"])
    workbook.save(path)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "Manuais"
    _write(root / "PROTEÍNA" / "95006001-00P.pdf")
    _write(root / "PROTEÍNA" / "95006002-00P.pdf", b"%PDF-1.4 outro")
    _write(root / "PROTEÍNA" / "Versões Anteriores" / "95006001-00P.pdf")
    _write(root / "PROTEÍNA" / "~$temporario.pdf")
    _write(root / "PROTEÍNA" / "leia-me.txt")
    _write(root / "ARMAZENAGEM" / "95021036-02P.pdf")
    _write(root / "ARMAZENAGEM" / "Versões Obsoletas" / "95021036-01P.pdf")
    _write(root / "solto-na-raiz.pdf")
    _write_catalog(root / CATALOG)
    return root


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.rglob("*")
    }


async def test_lists_only_pdfs_directly_inside_each_subfolder(root: Path) -> None:
    documents = await FolderManualSource(root, catalog_file=CATALOG).list_documents()

    assert [d.path for d in documents] == [
        "ARMAZENAGEM/95021036-02P.pdf",
        "PROTEÍNA/95006001-00P.pdf",
        "PROTEÍNA/95006002-00P.pdf",
    ]


async def test_takes_titles_from_the_spreadsheet(root: Path) -> None:
    documents = await FolderManualSource(root, catalog_file=CATALOG).list_documents()

    assert {d.file_name: d.title for d in documents} == {
        "95021036-02P.pdf": None,  # não está na planilha
        "95006001-00P.pdf": "MANUAL DE MONTAGEM INCUBADORAS",
        "95006002-00P.pdf": "NASCEDOURO G 21",
    }


async def test_works_without_the_spreadsheet(root: Path) -> None:
    (root / CATALOG).unlink()

    documents = await FolderManualSource(root, catalog_file=CATALOG).list_documents()

    assert len(documents) == 3
    assert all(d.title is None for d in documents)


async def test_a_broken_spreadsheet_does_not_stop_the_listing(root: Path) -> None:
    (root / CATALOG).write_bytes(b"isto nao e uma planilha")

    documents = await FolderManualSource(root, catalog_file=CATALOG).list_documents()

    assert len(documents) == 3


async def test_fingerprint_changes_when_the_file_changes(root: Path) -> None:
    source = FolderManualSource(root)
    before = {d.path: d.fingerprint for d in await source.list_documents()}

    _write(root / "PROTEÍNA" / "95006001-00P.pdf", b"%PDF-1.4 revisado")

    after = {d.path: d.fingerprint for d in await source.list_documents()}
    assert after["PROTEÍNA/95006001-00P.pdf"] != before["PROTEÍNA/95006001-00P.pdf"]
    assert after["PROTEÍNA/95006002-00P.pdf"] == before["PROTEÍNA/95006002-00P.pdf"]


async def test_reads_a_listed_document(root: Path) -> None:
    source = FolderManualSource(root)

    assert await source.read("PROTEÍNA/95006002-00P.pdf") == b"%PDF-1.4 outro"


@pytest.mark.parametrize("path", ["../fora.pdf", "PROTEÍNA/../../fora.pdf", CATALOG])
async def test_refuses_paths_outside_the_folder_or_not_pdf(root: Path, path: str) -> None:
    _write(root.parent / "fora.pdf")

    with pytest.raises(ValueError, match="fora da pasta"):
        await FolderManualSource(root).read(path)


async def test_never_changes_anything_in_the_folder(root: Path) -> None:
    """A pasta é da Engenharia: listar e ler não pode criar, alterar nem apagar nada."""
    before = _snapshot(root)
    source = FolderManualSource(root, catalog_file=CATALOG)

    for document in await source.list_documents():
        await source.read(document.path)

    assert _snapshot(root) == before


async def test_unreachable_folder_is_an_external_failure(tmp_path: Path) -> None:
    with pytest.raises(ExternalServiceError, match="pasta de manuais"):
        await FolderManualSource(tmp_path / "nao-existe").list_documents()


async def test_retries_a_momentary_network_failure(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FolderManualSource(root, retry_delay_seconds=0)
    original = Path.iterdir
    failures = iter([OSError(59, "Erro de rede inesperado")])

    def flaky_iterdir(path: Path):  # type: ignore[no-untyped-def]
        if (error := next(failures, None)) is not None:
            raise error
        return original(path)

    monkeypatch.setattr(Path, "iterdir", flaky_iterdir)

    assert len(await source.list_documents()) == 3


async def test_gives_up_after_repeated_network_failures(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_iterdir(_: Path) -> None:
        raise OSError(59, "Erro de rede inesperado")

    monkeypatch.setattr(Path, "iterdir", broken_iterdir)

    with pytest.raises(ExternalServiceError, match="Erro de rede"):
        await FolderManualSource(root, retry_delay_seconds=0).list_documents()
