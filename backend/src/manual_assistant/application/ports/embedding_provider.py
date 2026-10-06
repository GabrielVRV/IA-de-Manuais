from collections.abc import Sequence
from typing import Protocol, TypeAlias

# Representação numérica do significado de um texto.
Embedding: TypeAlias = tuple[float, ...]


class EmbeddingProvider(Protocol):
    """Converte textos em embeddings.

    Documentos e perguntas têm métodos separados porque provedores como o Gemini
    otimizam o vetor de forma diferente para cada papel na busca.

    Raises (todos os métodos):
        ExternalServiceError: se o provedor falhar ou não responder.
    """

    @property
    def dimensions(self) -> int:
        """Tamanho dos vetores gerados (precisa bater com o banco vetorial)."""
        ...

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Embedding]:
        """Um embedding por texto, na mesma ordem recebida."""
        ...

    async def embed_query(self, text: str) -> Embedding: ...
