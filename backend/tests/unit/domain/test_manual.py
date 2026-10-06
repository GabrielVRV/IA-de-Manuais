from dataclasses import replace
from datetime import datetime

import pytest

from manual_assistant.domain.errors import InvalidStateTransitionError, InvalidValueError
from manual_assistant.domain.manual import TITLE_MAX_LENGTH, Manual, ManualStatus
from tests.factories import FIXED_NOW, make_manual


def processing_manual() -> Manual:
    manual = make_manual()
    manual.start_processing()
    return manual


class TestRegistration:
    def test_starts_pending_with_a_new_identity(self) -> None:
        manual = Manual.register(title="  Manual P-200 ", file_name=" p200.pdf ", now=FIXED_NOW)

        assert manual.status is ManualStatus.PENDING
        assert manual.title == "Manual P-200"
        assert manual.file_name == "p200.pdf"
        assert not manual.is_searchable
        assert manual.id != make_manual().id

    @pytest.mark.parametrize("title", ["", "   ", "x" * (TITLE_MAX_LENGTH + 1)])
    def test_rejects_invalid_titles(self, title: str) -> None:
        with pytest.raises(InvalidValueError):
            Manual.register(title=title, file_name="p200.pdf", now=FIXED_NOW)

    def test_rejects_blank_file_name(self) -> None:
        with pytest.raises(InvalidValueError):
            Manual.register(title="Manual", file_name=" ", now=FIXED_NOW)

    def test_rejects_dates_without_timezone(self) -> None:
        with pytest.raises(InvalidValueError, match="fuso"):
            Manual.register(title="Manual", file_name="p.pdf", now=datetime(2026, 1, 1))  # noqa: DTZ001


class TestLifecycle:
    def test_becomes_searchable_once_indexed(self) -> None:
        manual = processing_manual()

        manual.mark_indexed(page_count=40, chunk_count=120)

        assert manual.status is ManualStatus.INDEXED
        assert manual.is_searchable
        assert (manual.page_count, manual.chunk_count) == (40, 120)

    def test_records_the_failure_reason(self) -> None:
        manual = processing_manual()

        manual.mark_failed("  PDF protegido por senha ")

        assert manual.status is ManualStatus.FAILED
        assert manual.failure_reason == "PDF protegido por senha"

    @pytest.mark.parametrize("finish", ["indexed", "failed"])
    def test_can_be_reprocessed_and_forgets_previous_result(self, finish: str) -> None:
        manual = processing_manual()
        if finish == "indexed":
            manual.mark_indexed(page_count=1, chunk_count=1)
        else:
            manual.mark_failed("erro")

        manual.start_processing()

        assert manual.status is ManualStatus.PROCESSING
        assert manual.page_count is None
        assert manual.chunk_count is None
        assert manual.failure_reason is None

    def test_cannot_start_processing_twice(self) -> None:
        manual = processing_manual()

        with pytest.raises(InvalidStateTransitionError):
            manual.start_processing()

    @pytest.mark.parametrize("status", [ManualStatus.PENDING, ManualStatus.INDEXED])
    def test_only_a_manual_in_processing_can_finish(self, status: ManualStatus) -> None:
        manual = replace(make_manual(), status=status)

        with pytest.raises(InvalidStateTransitionError):
            manual.mark_indexed(page_count=1, chunk_count=1)
        with pytest.raises(InvalidStateTransitionError):
            manual.mark_failed("erro")

    @pytest.mark.parametrize(("pages", "chunks"), [(0, 5), (5, 0)])
    def test_indexed_manual_must_have_content(self, pages: int, chunks: int) -> None:
        with pytest.raises(InvalidValueError):
            processing_manual().mark_indexed(page_count=pages, chunk_count=chunks)

    def test_failure_requires_a_reason(self) -> None:
        with pytest.raises(InvalidValueError):
            processing_manual().mark_failed("   ")


class TestIdentity:
    def test_manuals_are_equal_when_they_share_the_id(self) -> None:
        manual = make_manual()
        renamed = replace(manual, title="Outro título")

        assert manual == renamed
        assert hash(manual) == hash(renamed)
        assert manual != make_manual()
        assert manual != "não é um manual"
