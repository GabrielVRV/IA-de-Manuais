import re
import unicodedata

# Nome + número de um modelo: "S-70", "s70", "s 70", "C-220", "Siloflex 55", "CSI 600".
_MODEL = re.compile(r"(?<![a-z0-9])([a-z]+)[ \-./]?(\d+)(?![0-9])")


def equipment_models(text: str) -> frozenset[str]:
    """Modelos de equipamento citados no texto, normalizados (ex.: "S-70" → ``s70``).

    Serve para ligar uma pergunta ("qual o óleo do s70?") aos manuais cujo título cita o
    mesmo modelo ("COMEDOURO DE CORRENTE S-70"), mesmo escrito de outro jeito.
    """
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return frozenset(f"{name}{number}" for name, number in _MODEL.findall(plain))
