import re

# Só letras (com acento): números e códigos têm a própria busca (domain.codes).
_WORD = re.compile(r"[^\W\d_]+")

MIN_KEYWORD_LENGTH = 4  # corta "com", "de", "do"; o dicionário do banco tira o resto


def keywords(text: str) -> tuple[str, ...]:
    """Palavras da pergunta que valem para a busca por texto, sem repetição e na ordem.

    A busca por sentido (embedding) pode não ligar "maternidade" a um trecho que diz
    "aleitamento" ou "desmame". A busca por palavras acha o trecho que traz as palavras
    da pergunta, mesmo quando o sentido geral do trecho é outro. Só devolve letras: o
    resultado vai direto para uma consulta de texto no banco, sem operadores."""
    words = (word.lower() for word in _WORD.findall(text))
    return tuple(dict.fromkeys(word for word in words if len(word) >= MIN_KEYWORD_LENGTH))
