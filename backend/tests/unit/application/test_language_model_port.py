from manual_assistant.application.ports.language_model import CompletionRequest, TokenUsage


def test_total_tokens_adds_input_and_output() -> None:
    assert TokenUsage(input_tokens=1200, output_tokens=300).total_tokens == 1500


def test_requests_default_to_a_low_temperature() -> None:
    request = CompletionRequest(system_instruction="Responda com base nos manuais.", prompt="?")

    assert request.temperature <= 0.3
