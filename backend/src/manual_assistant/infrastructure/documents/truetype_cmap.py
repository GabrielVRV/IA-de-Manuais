"""Leitura da tabela ``cmap`` de fontes TrueType, para traduzir glifo → caractere.

Alguns PDFs (ex.: gerados pelo Word) embutem a fonte com codificação Identity e **sem**
tabela ToUnicode. Nesse caso o PDFium devolve o número do glifo no lugar do caractere
(``ÏOHR PLQHUDO`` em vez de ``Óleo mineral``). Como a fonte embutida costuma trazer a
própria ``cmap`` (caractere → glifo), basta invertê-la para recuperar o texto.
"""

import struct
from collections.abc import Iterator

_TRUETYPE_SIGNATURES = (b"\x00\x01\x00\x00", b"true")

# Subtabelas Unicode, da preferida para a menos preferida: (plataforma, codificação).
_UNICODE_SUBTABLES = ((3, 10), (0, 4), (0, 6), (3, 1), (0, 3), (0, 2), (0, 1), (0, 0))


def glyph_to_char_map(font_data: bytes) -> dict[int, str]:
    """Mapa glifo → caractere de uma fonte TrueType; vazio se não der para montá-lo.

    Quando vários caracteres usam o mesmo glifo, fica o de menor código, evitando
    caracteres de controle e a área de uso privado (ex.: ``fi`` em U+F001 e U+FB01).
    """
    try:
        pairs = list(_unicode_cmap(font_data))
    except (struct.error, IndexError, ValueError):
        return {}  # fonte truncada ou corrompida: melhor não traduzir nada

    best: dict[int, int] = {}
    for codepoint, glyph in pairs:
        if glyph == 0 or codepoint < 0x20 or 0x7F <= codepoint < 0xA0:
            continue
        current = best.get(glyph)
        if current is None or _preference(codepoint) < _preference(current):
            best[glyph] = codepoint
    return {glyph: chr(codepoint) for glyph, codepoint in best.items()}


def _preference(codepoint: int) -> tuple[bool, int]:
    private_use = 0xE000 <= codepoint <= 0xF8FF or codepoint >= 0xF0000
    return private_use, codepoint


def _unicode_cmap(data: bytes) -> Iterator[tuple[int, int]]:
    if data[:4] not in _TRUETYPE_SIGNATURES:
        return
    cmap = _table_offset(data, b"cmap")
    if cmap is None:
        return
    count = _u16(data, cmap + 2)
    subtables: dict[tuple[int, int], int] = {}
    for index in range(count):
        platform, encoding, offset = struct.unpack_from(">HHI", data, cmap + 4 + 8 * index)
        subtables.setdefault((platform, encoding), cmap + offset)
    for key in _UNICODE_SUBTABLES:
        start = subtables.get(key)
        if start is None:
            continue
        form = _u16(data, start)
        if form == 12:
            yield from _format12(data, start)
            return
        if form == 4:
            yield from _format4(data, start)
            return


def _table_offset(data: bytes, tag: bytes) -> int | None:
    count = _u16(data, 4)
    for index in range(count):
        entry_tag, _checksum, offset, _length = struct.unpack_from(">4sIII", data, 12 + 16 * index)
        if entry_tag == tag:
            return int(offset)
    return None


def _format4(data: bytes, start: int) -> Iterator[tuple[int, int]]:
    segments = _u16(data, start + 6) // 2
    ends = start + 14
    starts = ends + 2 * segments + 2  # +2: reservedPad
    deltas = starts + 2 * segments
    range_offsets = deltas + 2 * segments
    for segment in range(segments):
        end = _u16(data, ends + 2 * segment)
        first = _u16(data, starts + 2 * segment)
        delta = _u16(data, deltas + 2 * segment)
        range_offset_at = range_offsets + 2 * segment
        range_offset = _u16(data, range_offset_at)
        for codepoint in range(first, min(end, 0xFFFE) + 1):
            if range_offset == 0:
                glyph = (codepoint + delta) & 0xFFFF
            else:
                glyph = _u16(data, range_offset_at + range_offset + 2 * (codepoint - first))
                if glyph:
                    glyph = (glyph + delta) & 0xFFFF
            yield codepoint, glyph


def _format12(data: bytes, start: int) -> Iterator[tuple[int, int]]:
    groups = struct.unpack_from(">I", data, start + 12)[0]
    for index in range(groups):
        first, last, glyph = struct.unpack_from(">III", data, start + 16 + 12 * index)
        if last > 0x10FFFF or last < first:
            raise ValueError("grupo inválido na cmap")
        for offset in range(last - first + 1):
            yield first + offset, glyph + offset


def _u16(data: bytes, offset: int) -> int:
    value: int = struct.unpack_from(">H", data, offset)[0]
    return value
