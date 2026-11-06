import struct

from manual_assistant.infrastructure.documents.truetype_cmap import glyph_to_char_map
from tests.pdf_builder import GLYPH_SHIFT, build_truetype_font


def test_inverts_the_format_4_cmap() -> None:
    glyphs = glyph_to_char_map(build_truetype_font({"ó": 121}))

    assert glyphs[3] == " "
    assert glyphs[ord("O") - GLYPH_SHIFT] == "O"
    assert glyphs[121] == "ó"


def test_prefers_the_lowest_regular_character_when_glyphs_are_shared() -> None:
    """A Arial liga ``fi`` a U+F001 (uso privado) e a U+FB01; fica o caractere real."""
    glyphs = glyph_to_char_map(build_truetype_font({"\uf001": 192, "\ufb01": 192}))

    assert glyphs[192] == "\ufb01"


def test_reads_the_format_12_cmap() -> None:
    subtable = struct.pack(">HHIII", 12, 0, 16 + 12, 0, 1) + struct.pack(">III", 0x41, 0x43, 36)
    cmap = struct.pack(">HHHHI", 0, 1, 3, 10, 12) + subtable
    font = (
        struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
        + struct.pack(">4sIII", b"cmap", 0, 28, len(cmap))
        + cmap
    )

    assert glyph_to_char_map(font) == {36: "A", 37: "B", 38: "C"}


def test_returns_nothing_for_fonts_it_cannot_read() -> None:
    assert glyph_to_char_map(b"") == {}
    assert glyph_to_char_map(b"OTTO" + b"\x00" * 40) == {}  # CFF: códigos não são glifos
    assert glyph_to_char_map(build_truetype_font()[:40]) == {}  # truncada
