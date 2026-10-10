from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field

from manual_assistant.domain.answer import Answer, Citation
from manual_assistant.domain.question import QUESTION_MAX_LENGTH, QUESTION_MIN_LENGTH


class QuestionRequest(BaseModel):
    question: str = Field(
        min_length=QUESTION_MIN_LENGTH,
        max_length=QUESTION_MAX_LENGTH,
        examples=["Qual a pressão máxima de trabalho da prensa P-200?"],
    )
    conversation_id: UUID | None = Field(
        default=None, description="Conversa em andamento; vazio começa uma nova"
    )


class CitationResponse(BaseModel):
    manual_id: UUID
    manual_title: str
    pages: list[int]
    pages_label: str = Field(examples=["p. 3, 12-14"])

    @classmethod
    def from_citation(cls, citation: Citation) -> Self:
        return cls(
            manual_id=citation.manual_id,
            manual_title=citation.manual_title,
            pages=list(citation.pages),
            pages_label=format_pages(citation.pages),
        )


class AnswerResponse(BaseModel):
    answer: str
    found: bool = Field(description="false quando a informação não consta nos manuais")
    citations: list[CitationResponse]

    @classmethod
    def from_answer(cls, answer: Answer) -> Self:
        return cls(
            answer=answer.text,
            found=answer.has_sources,
            citations=[CitationResponse.from_citation(c) for c in answer.citations],
        )


def format_pages(pages: tuple[int, ...]) -> str:
    """(3, 12, 13, 14) -> 'p. 3, 12-14': agrupa páginas consecutivas."""
    groups: list[list[int]] = []
    for page in pages:
        if groups and page == groups[-1][-1] + 1:
            groups[-1].append(page)
        else:
            groups.append([page])
    parts = [str(g[0]) if len(g) == 1 else f"{g[0]}-{g[-1]}" for g in groups]
    return "p. " + ", ".join(parts)
