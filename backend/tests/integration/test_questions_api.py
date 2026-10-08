import pytest

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.pages import PageRange
from manual_assistant.presentation.http.schemas.questions import format_pages
from tests.factories import make_chunk, make_manual
from tests.http_app import FakeBackend

URL = "/api/v1/questions"
manual = make_manual("Manual da Prensa P-200")


@pytest.fixture
def backend() -> FakeBackend:
    backend = FakeBackend()
    backend.vector_store.search_results = [
        ScoredChunk(make_chunk(manual, text="Pressão: 180 bar.", pages=PageRange(12, 14)), 0.9),
        ScoredChunk(make_chunk(manual, text="Capa do manual.", pages=PageRange(1, 1)), 0.6),
    ]
    backend.language_model.answer = "A pressão máxima é 180 bar [1]."
    return backend


def test_answers_with_formatted_citations(backend: FakeBackend) -> None:
    response = backend.client_logged_in_as().post(URL, json={"question": "Pressão máxima?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "A pressão máxima é 180 bar.",
        "found": True,
        "citations": [
            {
                "manual_id": str(manual.id),
                "manual_title": "Manual da Prensa P-200",
                "pages": [12, 13, 14],
                "pages_label": "p. 12-14",
            }
        ],
    }


def test_reports_when_the_answer_is_not_in_the_manuals(backend: FakeBackend) -> None:
    backend.language_model.answer = "NAO_ENCONTRADO"

    body = backend.client_logged_in_as().post(URL, json={"question": "Como faço café?"}).json()

    assert body["found"] is False
    assert body["citations"] == []
    assert "Não encontrei" in body["answer"]


@pytest.mark.parametrize("question", ["", "oi", "x" * 2001])
def test_rejects_invalid_questions(backend: FakeBackend, question: str) -> None:
    response = backend.client_logged_in_as().post(URL, json={"question": question})

    assert response.status_code == 422


def test_returns_503_when_the_ai_provider_fails(backend: FakeBackend) -> None:
    backend.language_model.error = ExternalServiceError("Gemini falhou ao gerar a resposta")

    response = backend.client_logged_in_as().post(URL, json={"question": "Pressão máxima?"})

    assert response.status_code == 503
    assert "Gemini" in response.json()["detail"]


@pytest.mark.parametrize(
    ("pages", "label"),
    [((3,), "p. 3"), ((3, 4, 5), "p. 3-5"), ((3, 12, 13, 14, 20), "p. 3, 12-14, 20")],
)
def test_formats_page_labels(pages: tuple[int, ...], label: str) -> None:
    assert format_pages(pages) == label
