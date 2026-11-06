import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.figures import FigureDescription
from manual_assistant.domain.manual import Manual
from manual_assistant.infrastructure.persistence.figure_repository import (
    SqlAlchemyFigureDescriptionRepository,
)
from manual_assistant.infrastructure.persistence.manual_repository import (
    SqlAlchemyManualRepository,
)
from tests.factories import FIXED_NOW, make_manual

pytestmark = [pytest.mark.anyio, pytest.mark.db]


@pytest.fixture
def figures(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyFigureDescriptionRepository:
    return SqlAlchemyFigureDescriptionRepository(session_factory)


@pytest.fixture
async def manual(session_factory: async_sessionmaker[AsyncSession]) -> Manual:
    manual = make_manual()
    await SqlAlchemyManualRepository(session_factory).save(manual)
    return manual


def described(page: int, text: str | None = "Motor M1") -> FigureDescription:
    return FigureDescription(
        page=page,
        text=text,
        model="gemini-3.5-flash",
        described_at=FIXED_NOW,
        input_tokens=1200,
        output_tokens=300,
    )


async def test_lists_the_descriptions_of_one_file_version_by_page(
    figures: SqlAlchemyFigureDescriptionRepository, manual: Manual
) -> None:
    await figures.add(manual.id, "v1", described(3, None))
    await figures.add(manual.id, "v1", described(1))

    assert await figures.list(manual.id, "v1") == [described(1), described(3, None)]
    assert await figures.list(manual.id, "v2") == []


async def test_a_page_described_again_replaces_the_previous_description(
    figures: SqlAlchemyFigureDescriptionRepository, manual: Manual
) -> None:
    await figures.add(manual.id, "v1", described(1, "antiga"))

    await figures.add(manual.id, "v2", described(1, "nova"))

    assert await figures.list(manual.id, "v1") == []
    assert [d.text for d in await figures.list(manual.id, "v2")] == ["nova"]


async def test_deletes_other_versions_and_follows_the_manual(
    figures: SqlAlchemyFigureDescriptionRepository,
    manual: Manual,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await figures.add(manual.id, "v1", described(1))
    await figures.add(manual.id, "v2", described(2))

    assert await figures.delete_other_versions(manual.id, "v2") == 1
    assert [d.page for d in await figures.list(manual.id, "v2")] == [2]

    await SqlAlchemyManualRepository(session_factory).delete(manual.id)  # ON DELETE CASCADE
    assert await figures.list(manual.id, "v2") == []
