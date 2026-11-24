from manual_assistant.domain.keywords import keywords


def test_keeps_the_meaningful_words_in_order_without_repeating() -> None:
    assert keywords("Com quantos dias o leitão deixa a maternidade? Dias!") == (
        "quantos",
        "dias",
        "leitão",
        "deixa",
        "maternidade",
    )


def test_drops_short_words_numbers_and_symbols() -> None:
    assert keywords("O óleo do s70 é 20.400.319 | & ' ;") == ("óleo",)


def test_returns_nothing_for_text_without_words() -> None:
    assert keywords("?! 123") == ()
