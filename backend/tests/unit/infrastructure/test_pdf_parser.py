import asyncio

import pytest

from manual_assistant.application.errors import UnreadableDocumentError
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from tests.pdf_builder import build_pdf

pytestmark = pytest.mark.anyio

parser = PdfiumDocumentParser()


async def test_extracts_text_page_by_page_with_accents() -> None:
    pdf = build_pdf("Manual da Prensa P-200\nPressão máxima: 180 bar", "", "Manutenção")

    pages = await parser.parse(pdf)

    assert [page.number for page in pages] == [1, 2, 3]
    assert pages[0].text == "Manual da Prensa P-200\nPressão máxima: 180 bar"
    assert pages[1].is_blank
    assert pages[2].text == "Manutenção"


async def test_rejects_files_that_are_not_pdfs() -> None:
    with pytest.raises(UnreadableDocumentError, match="corrompido"):
        await parser.parse(b"%PDF-1.4 isso nao e um pdf de verdade")


async def test_rejects_pdfs_without_text() -> None:
    with pytest.raises(UnreadableDocumentError, match="OCR"):
        await parser.parse(build_pdf("", ""))


async def test_handles_concurrent_parsing() -> None:
    """O PDFium não é thread-safe; o adaptador serializa o acesso a ele."""
    pdfs = [build_pdf(f"Documento {i}") for i in range(8)]

    results = await asyncio.gather(*(parser.parse(pdf) for pdf in pdfs))

    assert [pages[0].text for pages in results] == [f"Documento {i}" for i in range(8)]
