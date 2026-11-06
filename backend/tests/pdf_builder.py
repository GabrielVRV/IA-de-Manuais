"""Gera PDFs mínimos e válidos para testes, sem depender de arquivos binários no repositório."""

import struct


def _escape(text: str) -> bytes:
    raw = text.encode("cp1252")  # WinAnsiEncoding: cobre os acentos do português
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _content_stream(text: str) -> bytes:
    commands = [b"BT", b"/F1 11 Tf", b"14 TL", b"50 790 Td"]
    for line in text.splitlines():
        commands.append(b"(" + _escape(line) + b") Tj T*")
    commands.append(b"ET")
    return b"\n".join(commands)


def build_pdf(*pages: str) -> bytes:
    """Cria um PDF com uma página por argumento. Linhas vazias viram parágrafos."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # árvore de páginas, preenchida abaixo
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    page_ids = []
    for text in pages:
        stream = _content_stream(text)
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        content_id = len(objects)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % content_id
        )
        page_ids.append(len(objects))
    kids = b" ".join(b"%d 0 R" % page_id for page_id in page_ids)
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))

    return _assemble(objects)


# Na ordem padrão de glifos do TrueType (a da Arial), o espaço é o glifo 3: glifo = código - 29.
GLYPH_SHIFT = 29


def build_truetype_font(extra: dict[str, int] | None = None) -> bytes:
    """Fonte TrueType mínima: só a tabela ``cmap`` (formato 4), com ASCII na ordem padrão.

    ``extra`` acrescenta caracteres fora do ASCII (ex.: ``{"ó": 121}``).
    """
    mapping = _glyph_mapping(extra)
    segments = [(code, code, (glyph - code) & 0xFFFF) for code, glyph in sorted(mapping.items())]
    segments.append((0xFFFF, 0xFFFF, 1))
    count = len(segments)
    subtable = struct.pack(">HHHHHHH", 4, 16 + 8 * count, 0, 2 * count, 0, 0, 0)
    subtable += b"".join(struct.pack(">H", end) for _start, end, _delta in segments)
    subtable += b"\x00\x00"
    subtable += b"".join(struct.pack(">H", start) for start, _end, _delta in segments)
    subtable += b"".join(struct.pack(">H", delta) for _start, _end, delta in segments)
    subtable += b"\x00\x00" * count
    cmap = struct.pack(">HHHHI", 0, 1, 3, 1, 12) + subtable
    header = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
    directory = struct.pack(">4sIII", b"cmap", 0, 12 + 16, len(cmap))
    return header + directory + cmap


def build_glyph_coded_pdf(text: str, extra: dict[str, int] | None = None) -> bytes:
    """PDF de uma página com fonte Identity-H **sem ToUnicode**, como alguns gerados pelo Word.

    O texto é gravado como números de glifo (``código - 29``): sem tradução, o PDFium
    devolve ``Óleo`` como ``ÏOHR`` e o espaço como o caractere de controle U+0003.
    """
    mapping = _glyph_mapping(extra)
    font = build_truetype_font(extra)
    glyphs = b"".join(struct.pack(">H", mapping[ord(char)]) for char in text)
    stream = b"BT /F1 11 Tf 50 790 Td <" + glyphs.hex().encode() + b"> Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type0 /BaseFont /ArialMT /Encoding /Identity-H "
        b"/DescendantFonts [6 0 R] >>",
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /ArialMT "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
        b"/FontDescriptor 7 0 R /CIDToGIDMap /Identity /DW 1000 >>",
        b"<< /Type /FontDescriptor /FontName /ArialMT /Flags 32 /FontBBox [0 0 1000 1000] "
        b"/ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 "
        b"/FontFile2 8 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(font), font),
    ]
    return _assemble(objects)


def _glyph_mapping(extra: dict[str, int] | None) -> dict[int, int]:
    """Caractere → glifo: ASCII na ordem padrão do TrueType, mais os extras."""
    mapping = {code: code - GLYPH_SHIFT for code in range(0x20, 0x7F)}
    mapping.update({ord(char): glyph for char, glyph in (extra or {}).items()})
    return mapping


def _assemble(objects: list[bytes]) -> bytes:
    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref_offset = len(output)
    output += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    output += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    output += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_offset,
    )
    return bytes(output)
