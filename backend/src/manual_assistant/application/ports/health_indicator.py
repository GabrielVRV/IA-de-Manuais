from typing import Protocol


class HealthIndicator(Protocol):
    """Componente externo cuja saúde pode ser verificada (banco, provedor de LLM...)."""

    @property
    def name(self) -> str: ...

    async def is_healthy(self) -> bool: ...
