import re
import unicodedata

from manual_assistant.domain.equipment import equipment_models

# Palavra com números, com ou sem separadores: "20.400.319", "GA56/71", "95007008-05P".
_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*")
_SEPARATORS = re.compile(r"[.\-/]")
# Tensões e frequências ("220/380V", "60Hz") não são códigos de peça.
_ELECTRICAL = re.compile(r"\d+(?:/\d+)*(?:v|hz|cv|kw|w|a)")

MIN_DIGITS = 5  # "20.400.319", "95007008"; números menores costumam ser medidas
MIN_DIGITS_WITH_LETTERS = 3  # "GA56/71", "R37DT80"


def compact(text: str) -> str:
    """Forma comparável de um código: minúsculo e sem pontos, hífens e barras."""
    return _SEPARATORS.sub("", text.lower())


def part_codes(text: str) -> frozenset[str]:
    """Códigos de peça citados no texto, na forma de ``compact``.

    A busca por sentido (embedding) trata "20.400.319" e "20.400.391" quase como iguais;
    esses códigos são buscados também pelo texto exato (ADR 0015). Modelos de equipamento
    ("Siloflex 55", "CSI 600") ficam de fora: já têm a busca por modelo.
    """
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    models = equipment_models(plain)
    codes: set[str] = set()
    for token in _TOKEN.findall(plain):
        code = compact(token)
        digits = sum(char.isdigit() for char in code)
        letters = len(code) - digits
        if code in models or _ELECTRICAL.fullmatch(token):
            continue
        if digits >= MIN_DIGITS or (
            letters and digits >= MIN_DIGITS_WITH_LETTERS and len(code) >= 5
        ):
            codes.add(code)
    return frozenset(codes)
