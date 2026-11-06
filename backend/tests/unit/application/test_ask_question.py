import pytest

from manual_assistant.application.rag_prompt import NOT_FOUND_MESSAGE, SYSTEM_INSTRUCTION
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.manual import Manual
from manual_assistant.domain.pages import PageRange
from manual_assistant.domain.question import Question
from tests.factories import make_chunk, make_manual
from tests.fakes import (
    FakeEmbeddingProvider,
    FakeLanguageModel,
    InMemoryManualRepository,
    InMemoryVectorStore,
)

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

    answer = (await ctx.use_case.execute(Question("Qual a pressão máxima?"))).answer

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

    answer = (await ctx.use_case.execute(Question("Como faço café?"))).answer

    assert answer.text == NOT_FOUND_MESSAGE
    assert ctx.language_model.requests == []


async def test_reports_the_tokens_spent_by_the_model() -> None:
    ctx = Context()

    result = await ctx.use_case.execute(Question("Qual a pressão máxima?"))

    assert result.model == "fake-model"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (1, 1)


async def test_reports_no_model_and_no_tokens_when_nothing_is_found() -> None:
    ctx = Context()
    ctx.vector_store.search_results = []

    result = await ctx.use_case.execute(Question("Como faço café?"))

    assert result.model is None
    assert result.usage.total_tokens == 0


# --------------------------------------------------------------------------- #
# Modelo de equipamento citado na pergunta
# --------------------------------------------------------------------------- #


def _indexed(title: str) -> Manual:
    manual = make_manual(title)
    manual.start_processing()
    manual.mark_indexed(page_count=10, chunk_count=3)
    return manual


async def test_prioritizes_the_manuals_of_the_equipment_model_in_the_question() -> None:
    """ "o óleo do s70" perdia para trechos de outros equipamentos que falam mais de óleo:
    o embedding dá pouco peso ao "s70". Os manuais do modelo citado vêm primeiro."""
    s70 = _indexed("MANUAL MONTAGEM COMEDOURO DE CORRENTE S-70")
    siloflex = _indexed("Distribuidor automático Siloflex 55")
    manuals = InMemoryManualRepository()
    for manual in (s70, siloflex):
        await manuals.save(manual)
    other = [
        ScoredChunk(make_chunk(siloflex, text=f"Óleo do motoredutor {n}.", position=n), 0.55)
        for n in range(3)
    ]
    oil = ScoredChunk(make_chunk(s70, text="Óleo mineral ISO 460.", position=9), 0.53)
    vector_store = InMemoryVectorStore(search_results=[*other, oil])
    language_model = FakeLanguageModel(answer="Óleo mineral ISO 460 [1].")
    use_case = AskQuestionUseCase(
        embeddings=FakeEmbeddingProvider(),
        vector_store=vector_store,
        language_model=language_model,
        top_k=2,
        manuals=manuals,
    )

    result = await use_case.execute(Question("qual oleo utilizado no motorredutor do s70"))

    assert vector_store.searched_manual_ids == [None, {s70.id}]
    prompt = language_model.requests[0].prompt
    assert prompt.index("Óleo mineral ISO 460.") < prompt.index("Óleo do motoredutor 0.")
    assert "Óleo do motoredutor 1." not in prompt  # o modelo citado ocupou a vaga
    assert result.answer.citations[0].manual_title == s70.title


async def test_each_model_in_the_question_gets_its_share_of_chunks() -> None:
    """Em "siloflex 55, 75 e 100", o manual do 55 ocupava todas as vagas e a resposta
    dizia que o 75 e o 100 "não constam"."""
    s55 = _indexed("MANUAL MONTAGEM E PECAS SILOFLEX 55")
    s75 = _indexed("MANUAL MONTAGEM E PECAS SILOFLEX 75")
    s100 = _indexed("MANUAL MONTAGEM E PECAS SILOFLEX 100")
    manuals = InMemoryManualRepository()
    for manual in (s55, s75, s100):
        await manuals.save(manual)
    results = [
        ScoredChunk(make_chunk(manual, text=f"Acionamento {manual.title} {n}.", position=n), score)
        for manual, score in ((s55, 0.9), (s75, 0.6), (s100, 0.5))
        for n in range(6)
    ]
    vector_store = InMemoryVectorStore(search_results=results)
    language_model = FakeLanguageModel(answer="Acionamentos [1].")
    use_case = AskQuestionUseCase(
        embeddings=FakeEmbeddingProvider(),
        vector_store=vector_store,
        language_model=language_model,
        top_k=6,
        manuals=manuals,
    )

    await use_case.execute(
        Question("quais os acionamentos utilizados nos siloflex diametros 55, 75 e 100")
    )

    assert vector_store.searched_manual_ids[0] is None
    searched = [frozenset(ids or ()) for ids in vector_store.searched_manual_ids[1:]]
    assert sorted(searched, key=str) == sorted(
        [frozenset({s55.id}), frozenset({s75.id}), frozenset({s100.id})], key=str
    )
    prompt = language_model.requests[0].prompt
    for manual in (s55, s75, s100):
        assert prompt.count(f"Acionamento {manual.title}") == 3  # 3 modelos x 3 = 9 trechos


async def test_chunks_with_the_exact_part_code_come_first() -> None:
    """A busca por sentido trata "20.400.319" e "20.400.391" quase como iguais."""
    manual = _indexed("MANUAL MONTAGEM E PECAS SILOFLEX 55")
    similar = [
        ScoredChunk(make_chunk(manual, text=f"Código 20.400.39{n}.", position=n), 0.8)
        for n in range(3)
    ]
    exact = ScoredChunk(make_chunk(manual, text="Acionamento 1,0CV: 20.400.319", position=9), 0.4)
    vector_store = InMemoryVectorStore(search_results=[*similar, exact])
    language_model = FakeLanguageModel(answer="É o acionamento 1,0CV [1].")
    use_case = AskQuestionUseCase(
        embeddings=FakeEmbeddingProvider(),
        vector_store=vector_store,
        language_model=language_model,
        top_k=2,
    )

    result = await use_case.execute(Question("o que é o código 20400319?"))

    assert vector_store.searched_codes == [{"20400319"}]
    prompt = language_model.requests[0].prompt
    assert prompt.index("20.400.319") < prompt.index("20.400.390")
    assert "20.400.391" not in prompt  # top_k continua 2
    assert result.answer.citations


async def test_questions_without_codes_do_not_search_by_code() -> None:
    vector_store = InMemoryVectorStore(search_results=list(RESULTS))
    use_case = AskQuestionUseCase(
        embeddings=FakeEmbeddingProvider(),
        vector_store=vector_store,
        language_model=FakeLanguageModel(),
    )

    await use_case.execute(Question("Qual o óleo do s70?"))

    assert vector_store.searched_codes == []


async def test_searches_everything_when_no_manual_matches_the_model() -> None:
    manuals = InMemoryManualRepository()
    await manuals.save(_indexed("Manual da Prensa P-200"))
    vector_store = InMemoryVectorStore(search_results=list(RESULTS))
    use_case = AskQuestionUseCase(
        embeddings=FakeEmbeddingProvider(),
        vector_store=vector_store,
        language_model=FakeLanguageModel(),
        manuals=manuals,
    )

    await use_case.execute(Question("Qual o óleo do C-220?"))

    assert vector_store.searched_manual_ids == [None]


async def test_ignores_manuals_that_are_not_indexed_yet() -> None:
    manuals = InMemoryManualRepository()
    await manuals.save(make_manual("COMEDOURO S-70"))  # pendente
    vector_store = InMemoryVectorStore(search_results=list(RESULTS))
    use_case = AskQuestionUseCase(
        embeddings=FakeEmbeddingProvider(),
        vector_store=vector_store,
        language_model=FakeLanguageModel(),
        manuals=manuals,
    )

    await use_case.execute(Question("Qual o óleo do s70?"))

    assert vector_store.searched_manual_ids == [None]
