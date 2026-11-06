"""Monta a descrição das figuras por IA (ADR 0014); usada pela API e pelo CLI."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.application.figures import FigureDescriber
from manual_assistant.infrastructure.ai.factory import AiProviders
from manual_assistant.infrastructure.documents.pdf_figures import PdfiumPageRenderer
from manual_assistant.infrastructure.persistence.figure_repository import (
    SqlAlchemyFigureDescriptionRepository,
)
from manual_assistant.infrastructure.settings import Settings


def build_figure_describer(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession], ai: AiProviders
) -> FigureDescriber:
    return FigureDescriber(
        renderer=PdfiumPageRenderer(
            min_image_area=settings.figure_min_image_area, dpi=settings.figure_render_dpi
        ),
        model=ai.figure_describer_model,
        repository=SqlAlchemyFigureDescriptionRepository(session_factory),
    )
