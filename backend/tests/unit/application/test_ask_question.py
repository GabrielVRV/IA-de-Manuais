import pytest

from manual_assistant.application.rag_prompt import NOT_FOUND_MESSAGE, SYSTEM_INSTRUCTION
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.pages import PageRange
from manual_assistant.domain.question import Question
from tests.factories import make_chunk, make_manual
from tests.fakes import FakeEmbeddingProvider, FakeLanguageModel, InMemoryVectorStore

pytestmark = pytest.mark.anyio

manual = make_manual("Manual da Prensa P-200")
RESULTS = [
    ScoredChunk(make_chunk(manual, text="Pressão máxima: 180 bar.", pages=PageRange(12, 12)), 0.9),
    ScoredChunk(make_chunk(manual, text="Óleo ISO VG 68.", pages=PageRange(30, 30)), 0.7),
]


class Context:
    def __init__(self, *, top_k: int = 6, min_score: float = 0.0) -> None:
        self.embeddings = FakeEmbeddingProvider()
        self.vector_store = InMemoryVectorStore(search_results=list(RESULTS))
        self.language_model = FakeLanguageModel(answer="A pressão máxima é 180 bar [1].")
        self.use_case = AskQuestionUseCase(
            embeddings=self.embeddings,
            vector_store=self.vector_store,
            language_model=self.language_model,
            top_k=top_k,
            min_score=min_score,
        )


async def test_answers_with_citations_of_the_chunks_used() -> None:
    ctx = Context()

    answer = await ctx.use_case.execute(Question("Qual a pressão máxima?"))

    assert answer.text == "A pressão máxima é 180 bar."
    assert [(c.manual_title, c.pages) for c in answer.citations] == [
        ("Manual da Prensa P-200", (12,))
    ]


async def test_sends_the_rules_and_the_retrieved_chunks_to_the_model() -> None:
    ctx = Context()

    await ctx.use_case.execute(Question("Qual a pressão máxima?"))

    (request,) = ctx.language_model.requests
    assert request.system_instruction == SYSTEM_INSTRUCTION
    assert "Pressão máxima: 180 bar." in request.prompt
    assert "Óleo ISO VG 68." in request.prompt
    assert request.prompt.endswith("Pergunta: Qual a pressão máxima?")


async def test_respects_top_k_and_minimum_score() -> None:
    ctx = Context(top_k=1, min_score=0.8)

    await ctx.use_case.execute(Question("Qual a pressão máxima?"))

    prompt = ctx.language_model.requests[0].prompt
    assert "Pressão máxima" in prompt
    assert "Óleo" not in prompt


async def test_does_not_call_the_model_when_nothing_is_found() -> None:
    ctx = Context()
    ctx.vector_store.search_results = []

    answer = await ctx.use_case.execute(Question("Como faço café?"))

    assert answer.text == NOT_FOUND_MESSAGE
    assert ctx.language_model.requests == []
