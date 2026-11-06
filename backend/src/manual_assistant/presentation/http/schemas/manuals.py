from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field

from manual_assistant.application.use_cases.describe_figures import FigureJob, FigurePlanItem
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
    figure_count: int | None = Field(description="Páginas com figuras descritas pela IA")
    describing_figures: bool = Field(description="As figuras estão sendo descritas agora")
    figures_described: int = Field(description="Páginas descritas no pedido atual ou último")
    figures_error: str | None = Field(description="Por que a última descrição de figuras parou")
    failure_reason: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, manual: Manual, figures: FigureJob | None = None) -> Self:
        return cls(
            id=manual.id,
            title=manual.title,
            file_name=manual.file_name,
            status=manual.status,
            page_count=manual.page_count,
            chunk_count=manual.chunk_count,
            figure_count=manual.figure_count,
            describing_figures=figures is not None and figures.running,
            figures_described=figures.described if figures else 0,
            figures_error=figures.error if figures else None,
            failure_reason=manual.failure_reason,
            created_at=manual.created_at,
        )


class FigurePlanResponse(BaseModel):
    with_figures: int = Field(description="Páginas com fotos, diagramas ou desenhos")
    pending: int = Field(description="Ainda sem descrição: cada uma é uma chamada à IA")

    @classmethod
    def from_plan(cls, plan: FigurePlanItem) -> Self:
        return cls(with_figures=plan.with_figures, pending=plan.pending)


class ErrorResponse(BaseModel):
    detail: str
