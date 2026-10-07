from collections.abc import Iterator, Sequence
from typing import TypeVar

T = TypeVar("T")


def batched(items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    """Divide em lotes respeitando o limite de itens por requisição do provedor."""
    for start in range(0, len(items), size):
        yield items[start : start + size]
