import asyncio
import os
import re
from pathlib import Path

from manual_assistant.application.errors import ExternalServiceError, StoredFileNotFoundError

# Só nomes simples: impede que uma chave como "../../etc/passwd" saia da pasta.
_SAFE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class LocalFileStorage:
    """Guarda os arquivos numa pasta local (no Docker, um volume persistente)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    async def save(self, key: str, content: bytes) -> None:
        path = self._path(key)
        try:
            await asyncio.to_thread(_write_atomically, path, content)
        except OSError as error:
            raise ExternalServiceError("Falha ao gravar o arquivo do manual") from error

    async def read(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as error:
            raise StoredFileNotFoundError(
                "O arquivo original do manual não foi encontrado. Envie o PDF novamente"
            ) from error
        except OSError as error:
            raise ExternalServiceError("Falha ao ler o arquivo do manual") from error

    async def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError as error:
            raise ExternalServiceError("Falha ao remover o arquivo do manual") from error

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY.fullmatch(key) or ".." in key:
            raise ValueError(f"Chave de arquivo inválida: {key!r}")
        return self._root / key


def _write_atomically(path: Path, content: bytes) -> None:
    """Grava num arquivo temporário e renomeia: nunca deixa um arquivo pela metade."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)
