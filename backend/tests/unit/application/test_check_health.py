import pytest

from manual_assistant.application.use_cases.check_health import CheckHealthUseCase, HealthStatus
from tests.fakes import FakeHealthIndicator

pytestmark = pytest.mark.anyio


async def test_is_up_when_there_are_no_indicators() -> None:
    report = await CheckHealthUseCase().execute()

    assert report.status is HealthStatus.UP
    assert report.components == {}


async def test_is_up_when_all_indicators_are_healthy() -> None:
    use_case = CheckHealthUseCase([FakeHealthIndicator("database"), FakeHealthIndicator("llm")])

    report = await use_case.execute()

    assert report.is_healthy
    assert report.components == {"database": HealthStatus.UP, "llm": HealthStatus.UP}


async def test_is_down_when_any_indicator_is_unhealthy() -> None:
    use_case = CheckHealthUseCase(
        [FakeHealthIndicator("database"), FakeHealthIndicator("llm", healthy=False)]
    )

    report = await use_case.execute()

    assert not report.is_healthy
    assert report.components["llm"] is HealthStatus.DOWN


async def test_treats_indicator_errors_as_down() -> None:
    use_case = CheckHealthUseCase(
        [FakeHealthIndicator("database", error=ConnectionError("timeout"))]
    )

    report = await use_case.execute()

    assert report.status is HealthStatus.DOWN
    assert report.components == {"database": HealthStatus.DOWN}
