from dataclasses import dataclass


@dataclass
class FakeHealthIndicator:
    name: str
    healthy: bool = True
    error: Exception | None = None

    async def is_healthy(self) -> bool:
        if self.error is not None:
            raise self.error
        return self.healthy
