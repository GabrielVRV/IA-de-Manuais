import logging
from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil

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
from manual_assistant.domain.chunk import ChunkId, ScoredChunk
from manual_assistant.domain.codes import part_codes
from manual_assistant.domain.conversation import Exchange
from manual_assistant.domain.equipment import equipment_models
from manual_assistant.domain.manual import ManualId
from manual_assistant.domain.question import Question

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6  # ~6 x 1500 caracteres: contexto suficiente com custo baixo
# Pergunta sobre vários modelos: cada um recebe ao menos esta quantidade de trechos, e o
# total pode crescer até MAX_TOP_K_FACTOR x top_k (3 modelos → 12 trechos com top_k 6).
# Com 3 por modelo, a tabela de códigos de um modelo podia ficar de fora (Siloflex 55).
MIN_CHUNKS_PER_MODEL = 4
MAX_TOP_K_FACTOR = 2
# Seção "Especificações Técnicas" (potência, comprimento, vazão...): o resumo do
# equipamento vai sempre junto quando a pergunta cita o modelo. Sem ela, "quais os
# acionamentos do Siloflex" trazia só tabelas de códigos, que repetem "acionamento"
# dezenas de vezes, e perdia "0,5 CV para linhas de 0 a 80 m". O PDF às vezes extrai
# "Especificaç ões", com espaço; as maiúsculas acentuadas vão explícitas porque o ~* do
# PostgreSQL não as iguala às minúsculas em todo locale.
# Nos manuais da pasta o resumo se chama "Especificações Técnicas", "Dados Técnicos (do
# equipamento)" ou "(Principais) Características". Só vale como título: no começo da
# linha (com ou sem numeração) e terminando a linha, com ":" ou ".". Assim ficam de fora
# o sumário ("Técnicas........3") e a frase padrão "especificações técnicas contidas
# neste manual, sem prévio aviso".
SPECIFICATIONS_PATTERN = (
    r"(^|\n)[0-9. \t-]*"
    r"(especifica[cçÇ]\s*[oõÕ]es\s+t[eéÉ]cnicas|dados\s+t[eéÉ]cnicos"
    r"|(principais\s+)?caracter[iíÍ]sticas)"
    # Complemento curto ("do Equipamento", "e Características"); frases longas não são título.
    r"[^\n.:]{0,25}[.:]?[ \t]*(\n|$)"
)
# Trechos que contêm literalmente um código de peça citado na pergunta (ADR 0015).
MAX_CODE_CHUNKS = 3
# Teto, não meta: só os tokens gerados são cobrados. Com respostas mais completas
# (regra 5 do prompt), 1024 cortava procedimentos longos no meio.
DEFAULT_MAX_OUTPUT_TOKENS = 2048
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
        results = await self._with_exact_codes(part_codes(text), results)
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

    async def _search(
        self, query: Embedding, groups: Sequence[frozenset[ManualId]]
    ) -> Sequence[ScoredChunk]:
        """Com um modelo citado, os trechos dos manuais dele vêm primeiro; a busca geral
        completa as vagas. Sem isso, "o óleo do s70" perde para trechos de outros
        equipamentos que falam mais de óleo, porque o embedding dá pouco peso ao "s70".

        Com vários modelos ("siloflex 55, 75 e 100"), cada um tem a sua cota de trechos:
        numa busca só, o manual mais parecido com a pergunta ocupava todas as vagas e a
        resposta dizia que os outros modelos "não constam"."""
        if len(groups) <= 1:
            limit = self._top_k
            per_group = self._top_k
        else:
            per_group = max(MIN_CHUNKS_PER_MODEL, ceil(self._top_k / len(groups)))
            limit = min(per_group * len(groups), self._top_k * MAX_TOP_K_FACTOR)
        found = await self._vector_store.search(query, limit=limit, min_score=self._min_score)
        if not groups:
            return found
        selected: list[ScoredChunk] = []
        chosen: set[ChunkId] = set()
        for manual_ids in groups:
            # O resumo do equipamento vai junto, fora da cota (ver SPECIFICATIONS_PATTERN).
            specifications = await self._vector_store.search_pattern(
                SPECIFICATIONS_PATTERN, manual_ids=manual_ids, limit=1
            )
            limit += len(specifications)
            focused = await self._vector_store.search(
                query, limit=per_group, min_score=self._min_score, manual_ids=manual_ids
            )
            for result in [*specifications, *focused]:
                if result.chunk.id not in chosen:
                    chosen.add(result.chunk.id)
                    selected.append(result)
        others = [result for result in found if result.chunk.id not in chosen]
        return [*selected, *others][:limit]

    async def _with_exact_codes(
        self, codes: frozenset[str], results: Sequence[ScoredChunk]
    ) -> Sequence[ScoredChunk]:
        """Trechos que contêm o código citado ("20.400.319") vêm primeiro: a busca por
        sentido trata códigos parecidos quase como iguais e pode nem trazê-los."""
        if not codes:
            return results
        exact = await self._vector_store.search_codes(codes, limit=MAX_CODE_CHUNKS)
        chosen = {result.chunk.id for result in exact}
        others = [result for result in results if result.chunk.id not in chosen]
        return [*exact, *others][: max(len(results), len(exact))]

    async def _manuals_of_models_in(self, text: str) -> list[frozenset[ManualId]]:
        """Para cada modelo citado no texto (ex.: "s70"), os manuais indexados cujo título
        cita esse modelo. Modelos sem manual ficam de fora."""
        models = equipment_models(text)
        if not models or self._manuals is None:
            return []
        searchable = [manual for manual in await self._manuals.list_all() if manual.is_searchable]
        groups: list[frozenset[ManualId]] = []
        for model in sorted(models):
            ids = frozenset(m.id for m in searchable if model in equipment_models(m.title))
            if ids and ids not in groups:
                groups.append(ids)
        return groups
