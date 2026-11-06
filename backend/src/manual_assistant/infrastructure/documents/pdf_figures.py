"""Páginas com figuras: detecção e renderização com o PDFium (ADR 0014)."""

import asyncio
import io
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from manual_assistant.application.errors import UnreadableDocumentError
from manual_assistant.application.ports.language_model import ImageInput
from manual_assistant.infrastructure.documents.pdf_parser import PDFIUM_LOCK

# Figuras dentro de "form XObjects" (blocos reaproveitados) também contam.
_OBJECT_DEPTH = 3
# Desenhos vetoriais: bem mais traços que as páginas só de texto do mesmo documento.
# A base é uma página "comum" (percentil 20), porque nos manuais da Engenharia até as
# páginas de texto têm mais de mil traços na moldura; e há manuais quase só de desenhos.
_BASELINE_QUANTILE = 5  # quintis: o primeiro corte é o percentil 20
_DRAWING_MIN_EXTRA_PATHS = 300
# Lado maior da imagem enviada: legível para cotas e legendas sem gastar tokens à toa.
_MAX_IMAGE_SIDE = 2000
_JPEG_QUALITY = 80


@dataclass(frozen=True, slots=True)
class _PageStats:
    number: int
    has_text: bool
    image_area: float  # fração da página coberta por imagens
    paths: int  # traços vetoriais


class PdfiumPageRenderer:
    """Uma página tem figuras quando:

    - imagens cobrem ao menos ``min_image_area`` dela (fotos, desenhos digitalizados,
      páginas escaneadas); ícones e logotipos pequenos ficam de fora; ou
    - tem muito mais traços vetoriais que uma página comum do documento (desenhos
      técnicos e diagramas exportados do CAD); ou
    - não tem texto, mas tem algum desenho.
    """

    def __init__(self, *, min_image_area: float = 0.05, dpi: int = 150) -> None:
        self._min_image_area = min_image_area
        self._scale = dpi / 72  # o PDF mede em pontos (1/72 de polegada)

    async def pages_with_figures(self, content: bytes) -> list[int]:
        stats = await asyncio.to_thread(self._stats, content)
        if not stats:
            return []
        threshold = _drawing_threshold([page.paths for page in stats])
        return [
            page.number
            for page in stats
            if page.image_area >= self._min_image_area
            or page.paths >= threshold
            or (not page.has_text and page.paths > 0)
        ]

    async def render(self, content: bytes, pages: Sequence[int]) -> list[ImageInput]:
        return await asyncio.to_thread(self._render, content, pages)

    def _stats(self, content: bytes) -> list[_PageStats]:
        with PDFIUM_LOCK:
            document = _open(content)
            try:
                return [_page_stats(document, index) for index in range(len(document))]
            finally:
                document.close()

    def _render(self, content: bytes, pages: Sequence[int]) -> list[ImageInput]:
        with PDFIUM_LOCK:
            document = _open(content)
            try:
                return [self._render_page(document, number) for number in pages]
            finally:
                document.close()

    def _render_page(self, document: pdfium.PdfDocument, number: int) -> ImageInput:
        if not 1 <= number <= len(document):
            raise UnreadableDocumentError(f"O PDF não tem a página {number}")
        page = document[number - 1]
        try:
            width, height = page.get_size()
            scale = min(self._scale, _MAX_IMAGE_SIDE / max(width, height, 1))
            bitmap = page.render(scale=scale)
            try:
                image = bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
        finally:
            page.close()
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        return ImageInput(data=buffer.getvalue(), mime_type="image/jpeg")


def _open(content: bytes) -> pdfium.PdfDocument:
    try:
        return pdfium.PdfDocument(content)
    except pdfium.PdfiumError as error:
        raise UnreadableDocumentError(
            "Não foi possível abrir o PDF: o arquivo está corrompido ou protegido por senha"
        ) from error


def _page_stats(document: pdfium.PdfDocument, index: int) -> _PageStats:
    page = document[index]
    try:
        width, height = page.get_size()
        area = max(width * height, 1.0)
        text_page = page.get_textpage()
        try:
            has_text = bool(text_page.get_text_range().strip())
        finally:
            text_page.close()
        image_area = 0.0
        paths = 0
        for obj in page.get_objects(max_depth=_OBJECT_DEPTH):
            if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE:
                left, bottom, right, top = obj.get_bounds()
                visible_width = max(0.0, min(right, width) - max(left, 0.0))
                visible_height = max(0.0, min(top, height) - max(bottom, 0.0))
                image_area += visible_width * visible_height / area
            elif obj.type == pdfium_c.FPDF_PAGEOBJ_PATH:
                paths += 1
    finally:
        page.close()
    return _PageStats(index + 1, has_text, min(image_area, 1.0), paths)


def _drawing_threshold(path_counts: Sequence[int]) -> float:
    if len(path_counts) >= _BASELINE_QUANTILE:
        baseline = statistics.quantiles(path_counts, n=_BASELINE_QUANTILE)[0]
    else:
        baseline = min(path_counts)
    return max(2 * baseline, baseline + _DRAWING_MIN_EXTRA_PATHS)
