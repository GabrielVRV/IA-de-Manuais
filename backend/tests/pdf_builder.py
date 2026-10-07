"""Gera PDFs mínimos e válidos para testes, sem depender de arquivos binários no repositório."""


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
