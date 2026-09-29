import sys

from study_tutor.gemini_client import _contents, _parse_json, friendly_api_error
from study_tutor.runner import run_user_code


def test_busy_model_message_is_plain():
    message = friendly_api_error(
        RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
    )
    assert "busy" in message.lower()
    assert "UNAVAILABLE" not in message


def test_invalid_key_message_does_not_repeat_the_key():
    message = friendly_api_error(RuntimeError("400 API_KEY_INVALID secret-key-value"), "secret-key-value")
    assert "Google AI Studio" in message
    assert "secret-key-value" not in message


def test_history_starts_with_a_user_turn():
    contents = _contents([("model", "Earlier lesson")], "What is a metric?")
    assert contents[0]["role"] == "user"
    assert contents[-1]["role"] == "user"
    assert "metric" in contents[-1]["parts"][0]["text"]


def test_json_parser_reads_a_fenced_object():
    payload = _parse_json('```json\n{"percent": 80}\n```')
    assert payload["percent"] == 80


def test_runner_prints_and_stops():
    result = run_user_code("print(6 * 7)", sys.executable)
    assert result.ok
    assert "42" in result.stdout


def test_runner_times_out():
    result = run_user_code("while True:\n    pass\n", sys.executable, timeout=1)
    assert result.ok is False
    assert "Timed out" in result.stderr
