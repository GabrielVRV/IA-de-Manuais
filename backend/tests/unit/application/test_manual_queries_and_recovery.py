from uuid import uuid4

import pytest

from manual_assistant.application.errors import ManualNotFoundError
from manual_assistant.application.use_cases.get_manual import GetManualUseCase
from manual_assistant.application.use_cases.recover_interrupted_indexing import (
    INTERRUPTED_REASON,
    RecoverInterruptedIndexingUseCase,
)
from manual_assistant.domain.manual import ManualId, ManualStatus
from tests.factories import make_manual
from tests.fakes import InMemoryManualRepository

pytestmark = pytest.mark.anyio


async def test_gets_a_manual_by_id() -> None:
    repository = InMemoryManualRepository()
    manual = make_manual()
    await repository.save(manual)

    assert await GetManualUseCase(repository).execute(manual.id) is manual


async def test_get_rejects_unknown_manual() -> None:
    with pytest.raises(ManualNotFoundError):
        await GetManualUseCase(InMemoryManualRepository()).execute(ManualId(uuid4()))


async def test_marks_interrupted_indexing_as_failed_and_leaves_others_alone() -> None:
    repository = InMemoryManualRepository()
    interrupted, pending = make_manual("Interrompido"), make_manual("Pendente")
    interrupted.start_processing()
    await repository.save(interrupted)
    await repository.save(pending)

    recovered = await RecoverInterruptedIndexingUseCase(repository).execute()

    assert recovered == 1
    assert interrupted.status is ManualStatus.FAILED
    assert interrupted.failure_reason == INTERRUPTED_REASON
    assert pending.status is ManualStatus.PENDING
