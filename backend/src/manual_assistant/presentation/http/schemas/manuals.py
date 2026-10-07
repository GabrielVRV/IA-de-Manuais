from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field

from manual_assistant.domain.manual import Manual, ManualStatus


class ManualResponse(BaseModel):
    id: UUID
    title: str
    file_name: str
    status: ManualStatus = Field(
        description="pending → processing → indexed | failed. Só manuais 'indexed' são consultados."
    )
    page_count: int | None
    chunk_count: int | None
    failure_reason: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, manual: Manual) -> Self:
        return cls(
            id=manual.id,
            title=manual.title,
            file_name=manual.file_name,
            status=manual.status,
            page_count=manual.page_count,
            chunk_count=manual.chunk_count,
            failure_reason=manual.failure_reason,
            created_at=manual.created_at,
        )


class ErrorResponse(BaseModel):
    detail: str
