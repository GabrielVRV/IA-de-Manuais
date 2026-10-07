from pathlib import Path

import pytest

from manual_assistant.application.errors import StoredFileNotFoundError
from manual_assistant.infrastructure.storage.local_file_storage import LocalFileStorage

pytestmark = pytest.mark.anyio


@pytest.fixture
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(tmp_path / "manuais")  # a pasta é criada no primeiro save


async def test_saves_reads_and_overwrites(storage: LocalFileStorage) -> None:
    await storage.save("manual.pdf", b"v1")
    await storage.save("manual.pdf", b"v2")

    assert await storage.read("manual.pdf") == b"v2"


async def test_leaves_no_temporary_files(storage: LocalFileStorage, tmp_path: Path) -> None:
    await storage.save("manual.pdf", b"conteudo")

    assert [p.name for p in (tmp_path / "manuais").iterdir()] == ["manual.pdf"]


async def test_reading_a_missing_file_raises(storage: LocalFileStorage) -> None:
    with pytest.raises(StoredFileNotFoundError):
        await storage.read("inexistente.pdf")


async def test_delete_is_idempotent(storage: LocalFileStorage) -> None:
    await storage.save("manual.pdf", b"x")

    await storage.delete("manual.pdf")
    await storage.delete("manual.pdf")

    with pytest.raises(StoredFileNotFoundError):
        await storage.read("manual.pdf")


@pytest.mark.parametrize("key", ["../fora.pdf", "sub/pasta.pdf", "..", "", ".oculto", "a\\b.pdf"])
async def test_rejects_keys_that_could_escape_the_folder(
    storage: LocalFileStorage, key: str
) -> None:
    with pytest.raises(ValueError, match="inválida"):
        await storage.save(key, b"x")
