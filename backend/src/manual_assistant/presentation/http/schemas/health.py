from typing import Self

from pydantic import BaseModel

from manual_assistant.application.use_cases.check_health import HealthReport, HealthStatus


class HealthResponse(BaseModel):
    status: HealthStatus
    version: str
    components: dict[str, HealthStatus]

    @classmethod
    def from_report(cls, report: HealthReport, *, version: str) -> Self:
        return cls(status=report.status, version=version, components=dict(report.components))
