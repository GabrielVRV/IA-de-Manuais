"""Descrição das figuras das páginas por um modelo com visão (ADR 0014).

Usado na indexação (manuais novos ou alterados) e no comando ``describe-figures``
(manuais já indexados). Cada descrição é gravada assim que chega: se algo falhar no
meio, o que já foi pago não se perde e a próxima execução continua de onde parou.
"""

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.ports.figure_repository import FigureDescriptionRepository
from manual_assistant.application.ports.language_model import (
    CompletionRequest,
    ImageInput,
    LanguageModel,
)
from manual_assistant.application.ports.page_renderer import PageRenderer
from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.manual import Manual, ManualId
from manual_assistant.domain.pages import Page

NO_FIGURES_MARKER = "SEM_FIGURAS"
# O texto da página vai junto só como contexto; páginas muito longas são cortadas.
PAGE_TEXT_MAX_CHARS = 3000
# Páginas renderizadas por vez: limita a memória com manuais de centenas de páginas.
RENDER_BATCH_SIZE = 4
# Uma página escaneada precisa ter o texto todo transcrito: uma lista de peças densa passa
# de 2.000 tokens. É teto, não meta: só o que o modelo escreve é cobrado. Em modelos de
# raciocínio o raciocínio também conta neste limite (por isso ``light_reasoning``).
MAX_OUTPUT_TOKENS = 8192

FIGURE_SYSTEM_INSTRUCTION = f"""\
Você descreve páginas de manuais técnicos de equipamentos industriais para um sistema \
de busca. Recebe a imagem de uma página e o texto que já foi extraído dela.

Descreva em português do Brasil o que as figuras, fotos, diagramas, esquemas, desenhos \
técnicos e tabelas em imagem mostram:
- componentes e seus nomes, números de posição, códigos de peça e legendas;
- cotas, medidas, valores e unidades exatamente como aparecem;
- ligações, fluxos, sentido de giro, sequência de montagem ou de operação;
- símbolos e avisos de segurança.

Regras:
1. Transcreva os textos que aparecem dentro das figuras (rótulos, legendas, tabelas).
2. Se não houver texto extraído (página escaneada), transcreva também todo o texto da página.
3. Não repita o texto já extraído, a não ser para explicar a figura.
4. Descreva só o que está visível. Não invente peças, valores ou procedimentos.
5. Se as figuras não tiverem informação técnica (só logotipo, moldura ou decoração), \
responda exatamente: {NO_FIGURES_MARKER}
6. Responda em texto simples, sem títulos nem formatação markdown."""


def content_hash(content: bytes) -> str:
    """Identifica a versão do arquivo: as descrições valem só para a versão descrita."""
    return hashlib.sha256(content).hexdigest()


def figure_chunk_text(description: FigureDescription) -> str:
    """Texto do trecho: o cabeçalho avisa o modelo de resposta de onde veio a informação."""
    return (
        f"[Figuras da página {description.page}, descritas por IA a partir da imagem]\n"
        f"{description.text}"
    )


@dataclass(frozen=True, slots=True)
class FigurePages:
    with_figures: Sequence[int]
    pending: Sequence[int]  # ainda sem descrição nesta versão do arquivo


class FigureDescriber:
    def __init__(
        self,
        *,
        renderer: PageRenderer,
        model: LanguageModel,
        repository: FigureDescriptionRepository,
        clock: Clock = utc_now,
    ) -> None:
        self._renderer = renderer
        self._model = model
        self._repository = repository
        self._clock = clock

    async def pages(self, manual_id: ManualId, content: bytes, version: str) -> FigurePages:
        """Quais páginas têm figuras e quais ainda faltam descrever. Não chama a IA."""
        with_figures = await self._renderer.pages_with_figures(content)
        done = {d.page for d in await self._repository.list(manual_id, version)}
        return FigurePages(with_figures, [page for page in with_figures if page not in done])

    async def cached(self, manual_id: ManualId, version: str) -> list[FigureDescription]:
        return _by_page(await self._repository.list(manual_id, version))

    async def describe(
        self,
        manual: Manual,
        content: bytes,
        pages: Sequence[Page],
        *,
        version: str,
        on_page: Callable[[FigureDescription], None] | None = None,
    ) -> list[FigureDescription]:
        """Descreve as páginas com figuras que ainda faltam e devolve todas as descrições
        desta versão do arquivo, na ordem das páginas.

        Raises:
            ExternalServiceError: se o modelo falhar (o que já foi descrito fica gravado).
            UnreadableDocumentError: se o documento não puder ser lido.
        """
        pending = (await self.pages(manual.id, content, version)).pending
        texts = {page.number: page.text for page in pages}
        for start in range(0, len(pending), RENDER_BATCH_SIZE):
            batch = pending[start : start + RENDER_BATCH_SIZE]
            images = await self._renderer.render(content, batch)
            for number, image in zip(batch, images, strict=True):
                description = await self._describe_page(
                    manual.title, number, texts.get(number, ""), image
                )
                await self._repository.add(manual.id, version, description)
                if on_page is not None:
                    on_page(description)
        return await self.cached(manual.id, version)

    async def discard_other_versions(self, manual_id: ManualId, version: str) -> None:
        await self._repository.delete_other_versions(manual_id, version)

    async def _describe_page(
        self, title: str, number: int, text: str, image: ImageInput
    ) -> FigureDescription:
        completion = await self._model.complete(
            CompletionRequest(
                system_instruction=FIGURE_SYSTEM_INSTRUCTION,
                prompt=_prompt(title, number, text),
                max_output_tokens=MAX_OUTPUT_TOKENS,
                images=(image,),
                light_reasoning=True,
            )
        )
        answer = completion.text.strip()
        return FigureDescription(
            page=number,
            text=None if not answer or answer.startswith(NO_FIGURES_MARKER) else answer,
            model=completion.model,
            described_at=self._clock(),
            input_tokens=completion.usage.input_tokens,
            output_tokens=completion.usage.output_tokens,
        )


def _prompt(title: str, number: int, text: str) -> str:
    extracted = text.strip()[:PAGE_TEXT_MAX_CHARS] or "(nenhum: a página parece escaneada)"
    return (
        f"Manual: {title}\nPágina: {number}\n\n"
        f"Texto já extraído desta página:\n<texto>\n{extracted}\n</texto>\n\n"
        "Descreva as figuras desta página, conforme as regras."
    )


def _by_page(descriptions: Sequence[FigureDescription]) -> list[FigureDescription]:
    return sorted(descriptions, key=lambda d: d.page)
