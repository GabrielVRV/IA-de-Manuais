import asyncio
import re
import threading

import pypdfium2 as pdfium

from manual_assistant.application.errors import UnreadableDocumentError
from manual_assistant.domain.pages import Page

# Caracteres de controle que o PDFium às vezes emite (hifenização, marcadores internos).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")

# O PDFium não é thread-safe: duas leituras simultâneas podem derrubar o processo.
_PDFIUM_LOCK = threading.Lock()


class PdfiumDocumentParser:
    """Extrai o texto de PDFs com o PDFium (o motor de PDF do Chrome, licença BSD/Apache)."""

    async def parse(self, content: bytes) -> list[Page]:
        # Leitura de PDF é trabalho de CPU: roda fora do event loop para não travar a API.
        return await asyncio.to_thread(self._parse, content)

    @staticmethod
    def _parse(content: bytes) -> list[Page]:
        with _PDFIUM_LOCK:
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

        if all(page.is_blank for page in pages):
            raise UnreadableDocumentError(
                "O PDF não contém texto selecionável. Se for um documento escaneado, "
                "ele precisa passar por OCR antes de ser cadastrado"
            )
        return pages


def _extract_text(page: pdfium.PdfPage) -> str:
    text_page = page.get_textpage()
    try:
        raw = text_page.get_text_range()
    finally:
        text_page.close()
        page.close()
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_CHARS.sub("", normalized)
