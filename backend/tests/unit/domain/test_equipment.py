import pytest

from manual_assistant.domain.equipment import equipment_models


@pytest.mark.parametrize(
    ("text", "models"),
    [
        ("qual oleo utilizado no motorredutor do s70", {"s70"}),
        ("MANUAL MONTAGEM COMEDOURO DE CORRENTE S-70", {"s70"}),
        ("o S 70", {"s70"}),
        ("Distribuidor automático Siloflex 55", {"siloflex55"}),
        ("NINHO DE COLETA DE OVOS AUTOMÁTICO C-220", {"c220"}),
        ("Comedouro terminação CSI 600 R", {"csi600"}),
        ("diferença entre o s70 e o s-700", {"s70", "s700"}),
        ("Qual a pressão máxima?", set()),
    ],
)
def test_finds_equipment_models_however_they_are_written(text: str, models: set[str]) -> None:
    assert equipment_models(text) == models


def test_a_longer_number_is_another_model() -> None:
    assert equipment_models("S-700") == {"s700"}
    assert not equipment_models("S-700") & equipment_models("s70")
