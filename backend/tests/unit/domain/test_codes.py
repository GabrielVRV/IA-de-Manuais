import pytest

from manual_assistant.domain.codes import compact, part_codes


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("o que é a peça 20.400.319?", {"20400319"}),
        ("e a 20400319", {"20400319"}),
        ("motorredutor GA56/71", {"ga5671"}),
        ("manual 95007008-05P", {"9500700805p"}),
        ("códigos 20.400.300 e 20.400.303", {"20400300", "20400303"}),
        # Não são códigos de peça:
        ("qual o óleo do s70?", set()),
        ("siloflex 55, 75 e 100", set()),
        ("comedouro CSI 600 e CSI600", set()),
        ("motor 220/380V 60Hz de 1,5 CV", set()),
        ("linhas de 0 a 120 m", set()),
    ],
)
def test_finds_part_codes_however_they_are_written(text: str, codes: set[str]) -> None:
    assert part_codes(text) == codes


def test_compact_ignores_dots_dashes_and_slashes() -> None:
    assert compact("20.400.319") == compact("20400319") == "20400319"
    assert compact("GA56/71") == "ga5671"
