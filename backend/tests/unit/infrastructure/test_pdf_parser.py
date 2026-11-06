import asyncio

import pytest

from manual_assistant.application.errors import UnreadableDocumentError
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from tests.pdf_builder import build_glyph_coded_pdf, build_pdf

pytestmark = pytest.mark.anyio

parser = PdfiumDocumentParser()


async def test_extracts_text_page_by_page_with_accents() -> None:
    pdf = build_pdf("Manual da Prensa P-200\nPressão máxima: 180 bar", "", "Manutenção")

    pages = await parser.parse(pdf)

    assert [page.number for page in pages] == [1, 2, 3]
    assert pages[0].text == "Manual da Prensa P-200\nPressão máxima: 180 bar"
    assert pages[1].is_blank
    assert pages[2].text == "Manutenção"


# Acentos na ordem padrão de glifos do TrueType (a da Arial).
_ACCENTS = {"Ó": 207, "ó": 121, "ã": 109, "ç": 111}


async def test_translates_fonts_without_tounicode_by_the_embedded_cmap() -> None:
    """Sem ToUnicode o PDFium devolveria "ÏOHRPLQHUDO,62": glifos no lugar de letras e
    espaços/dígitos como caracteres de controle (o caso do manual do comedouro S-70)."""
    pdf = build_glyph_coded_pdf("1.1) Óleo mineral ISO 460; 0,8 litro.", _ACCENTS)

    pages = await parser.parse(pdf)

    assert pages[0].text == "1.1) Óleo mineral ISO 460; 0,8 litro."


async def test_translates_fonts_without_tounicode_even_without_spaces_or_digits() -> None:
    """Sem espaço nem dígito não há caractere de controle que denuncie a fonte; ela é
    reconhecida por não conseguir voltar de caractere para glifo."""
    pdf = build_glyph_coded_pdf("Motornãoliga", _ACCENTS)

    pages = await parser.parse(pdf)

    assert pages[0].text == "Motornãoliga"


async def test_rejects_files_that_are_not_pdfs() -> None:
    with pytest.raises(UnreadableDocumentError, match="corrompido"):
        await parser.parse(b"%PDF-1.4 isso nao e um pdf de verdade")


async def test_returns_blank_pages_for_pdfs_without_text() -> None:
    """Escaneado: quem decide é a indexação, que pode descrever as páginas como imagem."""
    pages = await parser.parse(build_pdf("", ""))

    assert [page.is_blank for page in pages] == [True, True]


async def test_handles_concurrent_parsing() -> None:
    """O PDFium não é thread-safe; o adaptador serializa o acesso a ele."""
    pdfs = [build_pdf(f"Documento {i}") for i in range(8)]

    results = await asyncio.gather(*(parser.parse(pdf) for pdf in pdfs))

    assert [pages[0].text for pages in results] == [f"Documento {i}" for i in range(8)]
