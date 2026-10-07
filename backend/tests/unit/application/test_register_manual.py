import pytest

from manual_assistant.application.errors import InvalidDocumentError
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.domain.manual import ManualStatus
from tests.factories import FIXED_NOW
from tests.fakes import InMemoryFileStorage, InMemoryManualRepository

pytestmark = pytest.mark.anyio

PDF = b"%PDF-1.4 conteudo"
ONE_MB = 1024 * 1024


@pytest.fixture
def repository() -> InMemoryManualRepository:
    return InMemoryManualRepository()


@pytest.fixture
def storage() -> InMemoryFileStorage:
    return InMemoryFileStorage()


@pytest.fixture
def register(
    repository: InMemoryManualRepository, storage: InMemoryFileStorage
) -> RegisterManualUseCase:
    return RegisterManualUseCase(repository, storage, max_bytes=ONE_MB, clock=lambda: FIXED_NOW)


async def test_registers_a_pending_manual_and_stores_the_file(
    register: RegisterManualUseCase,
    repository: InMemoryManualRepository,
    storage: InMemoryFileStorage,
) -> None:
    manual = await register.execute(title="Prensa P-200", file_name="p200.pdf", content=PDF)

    assert manual.status is ManualStatus.PENDING
    assert manual.created_at == FIXED_NOW
    assert repository.manuals[manual.id] is manual
    assert storage.files[original_file_key(manual.id)] == PDF


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "vazio"),
        (b"%PDF-" + b"x" * ONE_MB, "limite de 1 MB"),
        (b"PK\x03\x04 planilha renomeada", "não é um PDF"),
    ],
    ids=["vazio", "grande-demais", "nao-e-pdf"],
)
async def test_rejects_invalid_files(
    register: RegisterManualUseCase,
    repository: InMemoryManualRepository,
    storage: InMemoryFileStorage,
    content: bytes,
    message: str,
) -> None:
    with pytest.raises(InvalidDocumentError, match=message):
        await register.execute(title="Manual", file_name="m.pdf", content=content)

    assert repository.manuals == {}
    assert storage.files == {}


async def test_removes_the_file_if_the_manual_cannot_be_saved(
    register: RegisterManualUseCase,
    repository: InMemoryManualRepository,
    storage: InMemoryFileStorage,
) -> None:
    repository.error_on_save = RuntimeError("banco fora do ar")

    with pytest.raises(RuntimeError):
        await register.execute(title="Manual", file_name="m.pdf", content=PDF)

    assert storage.files == {}
