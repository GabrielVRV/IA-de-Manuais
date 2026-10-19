import pytest

from manual_assistant.domain.manual_code import ManualCode


def test_reads_number_revision_and_language() -> None:
    code = ManualCode.from_file_name("95007003-01P.pdf")

    assert code == ManualCode(number="95007003", revision=1, language="P")
    assert code.key == "95007003P"


def test_same_key_across_revisions() -> None:
    old = ManualCode.from_file_name("95007008-00P.pdf")
    new = ManualCode.from_file_name("95007008-05P.pdf")

    assert old is not None
    assert new is not None
    assert old.key == new.key
    assert new.revision > old.revision


def test_each_language_is_a_different_manual() -> None:
    portuguese = ManualCode.from_file_name("95007001-00P.pdf")
    english = ManualCode.from_file_name("95007001-00E.pdf")

    assert portuguese is not None
    assert english is not None
    assert portuguese.key != english.key


def test_ignores_case_of_language_and_extension() -> None:
    assert ManualCode.from_file_name("95007001-00p.PDF") == ManualCode("95007001", 0, "P")


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("95021401-v2-ca10.pdf", ManualCode("95021401", 2, "P")),
        ("95021408-V3-CA100.PDF", ManualCode("95021408", 3, "P")),
        ("95021422-v1-scc040.pdf", ManualCode("95021422", 1, "P")),
        ("95021422-v1.pdf", ManualCode("95021422", 1, "P")),
    ],
)
def test_reads_the_versioned_variant_as_portuguese(file_name: str, expected: ManualCode) -> None:
    # Variante de parte dos secadores: sem letra de idioma, e a revisão vem depois do "v".
    assert ManualCode.from_file_name(file_name) == expected


def test_versioned_variant_is_the_same_manual_as_the_usual_name() -> None:
    usual = ManualCode.from_file_name("95021401-02P.pdf")
    versioned = ManualCode.from_file_name("95021401-v2-ca10.pdf")

    assert versioned == usual
    assert versioned is not None
    assert versioned.catalog_code == "95021401-02P"


@pytest.mark.parametrize(
    "file_name",
    [
        "P&D 08 - Manuais.pdf",
        "95007001-00P.docx",
        "95007001P.pdf",
        "95007001-00.pdf",
        "95021401-ca10.pdf",
        "95021401-v-ca10.pdf",
        "",
    ],
)
def test_rejects_names_outside_the_pattern(file_name: str) -> None:
    assert ManualCode.from_file_name(file_name) is None
