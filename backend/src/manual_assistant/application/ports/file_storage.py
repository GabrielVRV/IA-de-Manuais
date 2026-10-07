from typing import Protocol


class FileStorage(Protocol):
    """Guarda os arquivos originais dos manuais.

    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def save(self, key: str, content: bytes) -> None:
        """Grava (ou substitui) o arquivo identificado por ``key``."""
        ...

    async def read(self, key: str) -> bytes:
        """
        Raises:
            StoredFileNotFoundError: se não existir arquivo com essa chave.
        """
        ...

    async def delete(self, key: str) -> None:
        """Remove o arquivo; não faz nada se ele não existir."""
        ...
