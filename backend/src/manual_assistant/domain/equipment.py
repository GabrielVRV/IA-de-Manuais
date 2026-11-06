import re
import unicodedata

# Palavras que podem ficar entre o nome e os números: "Siloflex diâmetros 55, 75 e 100",
# "Siloflex modelo 75", "Siloflex Ø 75".
_FILLER = r"(?:(?:diametros?|modelos?|tamanhos?|mod|ø|de|do|da|dos|das)\.?\s*)*"
# Um número ou uma lista deles: "55", "55, 75 e 100", "55/75/100", "75 ou 100".
_NUMBERS = r"\d+(?:\s*(?:,|/|\be\b|\bou\b)\s*\d+)*"
# Nome + número(s) de um modelo: "S-70", "s70", "s 70", "C-220", "Siloflex 55", "CSI 600".
_MODEL = re.compile(rf"(?<![a-z0-9])([a-z]+)[ \-./]?{_FILLER}({_NUMBERS})(?![0-9])")
_NUMBER = re.compile(r"\d+")


def equipment_models(text: str) -> frozenset[str]:
    """Modelos de equipamento citados no texto, normalizados (ex.: "S-70" → ``s70``).

    Serve para ligar uma pergunta ("qual o óleo do s70?") aos manuais cujo título cita o
    mesmo modelo ("COMEDOURO DE CORRENTE S-70"), mesmo escrito de outro jeito. Uma lista
    vale para cada número: "siloflex 55, 75 e 100" → ``siloflex55``, ``siloflex75``,
    ``siloflex100``.
    """
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return frozenset(
        f"{name}{number}"
        for name, numbers in _MODEL.findall(plain)
        for number in _NUMBER.findall(numbers)
    )
