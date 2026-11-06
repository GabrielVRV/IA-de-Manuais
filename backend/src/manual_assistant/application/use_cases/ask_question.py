import logging
from collections.abc import Sequence
from dataclasses import dataclass

from manual_assistant.application.ports.embedding_provider import Embedding, EmbeddingProvider
from manual_assistant.application.ports.language_model import (
    CompletionRequest,
    LanguageModel,
    TokenUsage,
)
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.ports.vector_store import VectorStore
from manual_assistant.application.rag_prompt import (
    NOT_FOUND_MESSAGE,
    SYSTEM_INSTRUCTION,
    build_prompt,
    parse_completion,
    retrieval_query,
)
from manual_assistant.domain.answer import Answer
from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.conversation import Exchange
from manual_assistant.domain.equipment import equipment_models
from manual_assistant.domain.manual import ManualId
from manual_assistant.domain.question import Question

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6  # ~6 x 1500 caracteres: contexto suficiente com custo baixo
DEFAULT_MAX_OUTPUT_TOKENS = 1024
NO_USAGE = TokenUsage(input_tokens=0, output_tokens=0)


@dataclass(frozen=True, slots=True)
class QuestionResult:
    answer: Answer
    model: str | None  # None quando nada foi enviado ao modelo (não gastou tokens)
    usage: TokenUsage = NO_USAGE


class AskQuestionUseCase:
    """Responde uma pergunta com base nos manuais (RAG), citando as fontes usadas."""

    def __init__(
        self,
        *,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        language_model: LanguageModel,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = 0.0,
        manuals: ManualRepository | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._manuals = manuals
        self._vector_store = vector_store
        self._language_model = language_model
        self._top_k = top_k
        # Com o Gemini, trechos sem relação ainda pontuam ~0,6: o corte não separa
        # "relevante" de "irrelevante". Quem decide "não encontrei" é o modelo.
        self._min_score = min_score

    async def execute(self, question: Question, history: Sequence[Exchange] = ()) -> QuestionResult:
        """``history``: últimas trocas da conversa, para entender perguntas de continuação."""
        text = retrieval_query(question, history)
        query = await self._embeddings.embed_query(text)
        results = await self._search(query, await self._manuals_of_models_in(text))
        if not results:
            # Nada indexado (ou nada acima do corte): não gasta tokens do modelo.
            return QuestionResult(Answer(NOT_FOUND_MESSAGE), model=None)

        chunks = [result.chunk for result in results]
        completion = await self._language_model.complete(
            CompletionRequest(
                system_instruction=SYSTEM_INSTRUCTION,
                prompt=build_prompt(question, chunks, history),
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )
        )
        answer = parse_completion(completion.text, chunks)

        logger.info(
            "Pergunta respondida: modelo=%s tokens_entrada=%d tokens_saida=%d "
            "trechos=%d citacoes=%d historico=%d",
            completion.model,
            completion.usage.input_tokens,
            completion.usage.output_tokens,
            len(chunks),
            len(answer.citations),
            len(history),
        )
        return QuestionResult(answer, model=completion.model, usage=completion.usage)

    async def _search(self, query: Embedding, focus: frozenset[ManualId]) -> Sequence[ScoredChunk]:
        """Com um modelo citado, os trechos dos manuais dele vêm primeiro; a busca geral
        completa as vagas. Sem isso, "o óleo do s70" perde para trechos de outros
        equipamentos que falam mais de óleo, porque o embedding dá pouco peso ao "s70"."""
        found = await self._vector_store.search(query, limit=self._top_k, min_score=self._min_score)
        if not focus:
            return found
        focused = await self._vector_store.search(
            query, limit=self._top_k, min_score=self._min_score, manual_ids=focus
        )
        chosen = {result.chunk.id for result in focused}
        others = [result for result in found if result.chunk.id not in chosen]
        return [*focused, *others][: self._top_k]

    async def _manuals_of_models_in(self, text: str) -> frozenset[ManualId]:
        """Manuais indexados cujo título cita um modelo citado no texto (ex.: "s70")."""
        models = equipment_models(text)
        if not models or self._manuals is None:
            return frozenset()
        return frozenset(
            manual.id
            for manual in await self._manuals.list_all()
            if manual.is_searchable and models & equipment_models(manual.title)
        )
