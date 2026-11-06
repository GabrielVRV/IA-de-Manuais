import asyncio
import ctypes
import re
import threading
from collections import Counter
from typing import Any

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from manual_assistant.application.errors import UnreadableDocumentError
from manual_assistant.domain.pages import Page
from manual_assistant.infrastructure.documents.truetype_cmap import glyph_to_char_map

# Caracteres de controle que o PDFium às vezes emite (hifenização, marcadores internos).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")

# Texto real não tem esses códigos; numa fonte sem ToUnicode eles são glifos (o espaço é o
# glifo 3 e os dígitos, 19 a 28), sinal de que o PDFium devolveu números de glifo.
# Ficam de fora o 1 e o 2: o PDFium usa o 2 para marcar hifenização no fim da linha.
_GLYPH_CODES = frozenset({*range(0x03, 0x09), 0x0B, 0x0C, *range(0x0E, 0x20)})
_GLYPH_SPACE = 0x03

# Fração mínima dos códigos de uma fonte que a cmap precisa traduzir para confiar nela.
_MIN_TRANSLATED = 0.9

# O PDFium não é thread-safe: duas leituras simultâneas podem derrubar o processo.
PDFIUM_LOCK = threading.Lock()


class PdfiumDocumentParser:
    """Extrai o texto de PDFs com o PDFium (o motor de PDF do Chrome, licença BSD/Apache)."""

    async def parse(self, content: bytes) -> list[Page]:
        # Leitura de PDF é trabalho de CPU: roda fora do event loop para não travar a API.
        return await asyncio.to_thread(self._parse, content)

    @staticmethod
    def _parse(content: bytes) -> list[Page]:
        with PDFIUM_LOCK:
            try:
                document = pdfium.PdfDocument(content)
            except pdfium.PdfiumError as error:
                raise UnreadableDocumentError(
                    "Não foi possível abrir o PDF: o arquivo está corrompido ou protegido por senha"
                ) from error
            try:
                pages = [
                    Page(number=index + 1, text=_extract_text(document[index]))
                    for index in range(len(document))
                ]
            finally:
                document.close()

        # Páginas sem texto (escaneadas) voltam em branco: quem decide se o manual é
        # aproveitável é a indexação, que pode descrever as páginas como imagem.
        return pages


def _extract_text(page: pdfium.PdfPage) -> str:
    text_page = page.get_textpage()
    try:
        raw = _decode_glyph_coded_fonts(text_page) or text_page.get_text_range()
    finally:
        text_page.close()
        page.close()
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_CHARS.sub("", normalized)


# --------------------------------------------------------------------------- #
# Fontes sem ToUnicode
#
# Alguns PDFs (ex.: gerados pelo Word) embutem fontes com codificação Identity e sem
# tabela ToUnicode. O PDFium então devolve o número do glifo no lugar do caractere
# ("ÏOHR PLQHUDO,62" em vez de "Óleo mineral ISO 460"); espaços e dígitos viram
# caracteres de controle. Essas fontes são reconhecidas e traduzidas pela cmap da
# própria fonte embutida.
# --------------------------------------------------------------------------- #

_PROBE_CHARS = 8  # caracteres distintos testados por fonte: suficiente e barato


def _decode_glyph_coded_fonts(text_page: pdfium.PdfTextPage) -> str | None:
    """Texto da página com as fontes que devolvem números de glifo já traduzidas.

    Uma única passada pelos caracteres (e não pelos objetos da página, que em desenhos
    técnicos passam de dezenas de milhares). Devolve ``None`` quando não há o que traduzir.
    """
    handle = text_page.raw
    codes: list[int] = []
    keys: list[int] = []  # fonte de cada caractere; 0 = gerado pelo PDFium (quebra de linha)
    fonts: dict[int, Any] = {}
    last_object: int | None = None
    last_key = 0
    for index in range(pdfium_c.FPDFText_CountChars(handle)):
        codes.append(pdfium_c.FPDFText_GetUnicode(handle, index))
        text_object = pdfium_c.FPDFText_GetTextObject(handle, index)
        object_key = _handle_key(text_object) if text_object else 0
        if object_key != last_object:
            last_object = object_key
            font = pdfium_c.FPDFTextObj_GetFont(text_object) if text_object else None
            last_key = _handle_key(font) if font else 0
            if last_key:
                fonts[last_key] = font
        keys.append(last_key)

    texts: dict[int, Counter[int]] = {}
    for code, key in zip(codes, keys, strict=True):
        if key:
            texts.setdefault(key, Counter())[code] += 1

    translations: dict[int, dict[int, str]] = {}
    for key, counts in texts.items():
        if not _is_glyph_coded(fonts[key], counts):
            continue
        used = set(counts)
        glyphs = glyph_to_char_map(_font_data(fonts[key]))
        if glyphs and len(used & glyphs.keys()) >= _MIN_TRANSLATED * len(used):
            translations[key] = glyphs
    if not translations:
        return None

    chars: list[str] = []
    for code, key in zip(codes, keys, strict=True):
        translation = translations.get(key)
        if translation is not None:
            chars.append(translation.get(code, ""))
        elif code <= 0x10FFFF:
            chars.append(chr(code))
    return "".join(chars)


def _is_glyph_coded(font: Any, counts: Counter[int]) -> bool:
    if counts[0x20] > counts[_GLYPH_SPACE]:
        return False  # mais espaços de verdade que glifos de espaço: são caracteres
    if not _GLYPH_CODES.isdisjoint(counts):
        return True  # espaço (glifo 3) e dígitos (glifos 19 a 28) viram controle
    return _lacks_unicode_map(font, set(counts))


def _lacks_unicode_map(font: Any, codes: set[int]) -> bool:
    """Sem ToUnicode o PDFium não sabe voltar de caractere para código: todo caractere
    cai no glifo 0 (.notdef), com a mesma largura e o mesmo desenho."""
    visible = sorted(code for code in codes if code > 0x20 and not chr(code).isspace())
    if len(visible) < 2:
        return False
    signatures = {_glyph_signature(font, code) for code in visible[:_PROBE_CHARS]}
    return len(signatures) == 1


def _glyph_signature(font: Any, code: int) -> tuple[float, int]:
    width = ctypes.c_float()
    pdfium_c.FPDFFont_GetGlyphWidth(font, code, 1.0, ctypes.byref(width))
    path = pdfium_c.FPDFFont_GetGlyphPath(font, code, 1.0)
    segments = pdfium_c.FPDFGlyphPath_CountGlyphSegments(path) if path else -1
    return round(width.value, 4), segments


def _handle_key(pointer: Any) -> int:
    return ctypes.cast(pointer, ctypes.c_void_p).value or 0


def _font_data(font: Any) -> bytes:
    size = ctypes.c_size_t()
    if not pdfium_c.FPDFFont_GetFontData(font, None, 0, ctypes.byref(size)) or not size.value:
        return b""
    buffer = (ctypes.c_uint8 * size.value)()
    if not pdfium_c.FPDFFont_GetFontData(font, buffer, size.value, ctypes.byref(size)):
        return b""
    return bytes(buffer)
