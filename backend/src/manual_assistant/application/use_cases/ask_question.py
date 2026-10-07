import logging

from manual_assistant.application.ports.embedding_provider import EmbeddingProvider
from manual_assistant.application.ports.language_model import CompletionRequest, LanguageModel
from manual_assistant.application.ports.vector_store import VectorStore
from manual_assistant.application.rag_prompt import (
    NOT_FOUND_MESSAGE,
    SYSTEM_INSTRUCTION,
    build_prompt,
    parse_completion,
)
from manual_assistant.domain.answer import Answer
from manual_assistant.domain.question import Question

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6  # ~6 x 1500 caracteres: contexto suficiente com custo baixo
DEFAULT_MAX_OUTPUT_TOKENS = 1024


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
    ) -> None:
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._language_model = language_model
        self._top_k = top_k
        # Com o Gemini, trechos sem relação ainda pontuam ~0,6: o corte não separa
        # "relevante" de "irrelevante". Quem decide "não encontrei" é o modelo.
        self._min_score = min_score

    async def execute(self, question: Question) -> Answer:
        query = await self._embeddings.embed_query(question.text)
        results = await self._vector_store.search(
            query, limit=self._top_k, min_score=self._min_score
        )
        if not results:
            # Nada indexado (ou nada acima do corte): não gasta tokens do modelo.
            return Answer(NOT_FOUND_MESSAGE)

        chunks = [result.chunk for result in results]
        completion = await self._language_model.complete(
            CompletionRequest(
                system_instruction=SYSTEM_INSTRUCTION,
                prompt=build_prompt(question, chunks),
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )
        )
        answer = parse_completion(completion.text, chunks)

        logger.info(
            "Pergunta respondida: modelo=%s tokens_entrada=%d tokens_saida=%d "
            "trechos=%d citacoes=%d",
            completion.model,
            completion.usage.input_tokens,
            completion.usage.output_tokens,
            len(chunks),
            len(answer.citations),
        )
        return answer
