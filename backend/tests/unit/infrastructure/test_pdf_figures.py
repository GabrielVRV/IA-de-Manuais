import io

import pypdfium2 as pdfium
import pytest
from PIL import Image

from manual_assistant.application.errors import UnreadableDocumentError
from manual_assistant.infrastructure.documents.pdf_figures import (
    PdfiumPageRenderer,
    _drawing_threshold,
)
from tests.pdf_builder import build_pdf

pytestmark = pytest.mark.anyio

renderer = PdfiumPageRenderer(min_image_area=0.05)


def _pdf_with_images(*image_sizes: tuple[float, float] | None) -> bytes:
    """Uma página A4 por item: com uma imagem do tamanho dado (em pontos), ou vazia."""
    document = pdfium.PdfDocument.new()
    for size in image_sizes:
        page = document.new_page(595, 842)
        if size is not None:
            jpeg = io.BytesIO()
            Image.new("RGB", (40, 40), "gray").save(jpeg, format="JPEG")
            image = pdfium.PdfImage.new(document)
            image.load_jpeg(io.BytesIO(jpeg.getvalue()), inline=True)
            image.set_matrix(pdfium.PdfMatrix().scale(*size).translate(50, 50))
            page.insert_obj(image)
            page.gen_content()
        page.close()
    output = io.BytesIO()
    document.save(output)
    document.close()
    return output.getvalue()


async def test_finds_pages_with_large_images_and_skips_small_icons() -> None:
    pdf = _pdf_with_images((400, 300), (20, 20), None, (595, 842))

    assert await renderer.pages_with_figures(pdf) == [1, 4]


async def test_text_pages_have_no_figures() -> None:
    assert await renderer.pages_with_figures(build_pdf("Pressão: 180 bar", "Fim")) == []


async def test_renders_pages_as_jpeg_in_the_requested_order() -> None:
    pdf = _pdf_with_images((400, 300), None)

    images = await renderer.render(pdf, [2, 1])

    assert [image.mime_type for image in images] == ["image/jpeg", "image/jpeg"]
    assert all(image.data.startswith(b"\xff\xd8") for image in images)
    width, height = Image.open(io.BytesIO(images[0].data)).size
    # 150 dpi: A4 com cerca de 1240 x 1754 pixels (o PDFium arredonda para cima).
    assert abs(width - 595 * 150 / 72) <= 1
    assert abs(height - 842 * 150 / 72) <= 1


async def test_rejects_pages_outside_the_document() -> None:
    with pytest.raises(UnreadableDocumentError):
        await renderer.render(build_pdf("Uma página"), [2])


def test_drawings_need_many_more_paths_than_a_common_page() -> None:
    # Moldura com ~1.100 traços em toda página: só os desenhos passam do dobro.
    counts = [1100, 1150, 1120, 1130, 5000, 1140]

    threshold = _drawing_threshold(counts)

    assert 1150 < threshold < 5000
    assert _drawing_threshold([0, 0, 0, 0, 0]) == 300
