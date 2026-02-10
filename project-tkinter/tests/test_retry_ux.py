from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from retry_ux import (  # noqa: E402
    RETRY_FAILED,
    RETRY_WAITING,
    RetryTelemetry,
    adaptive_backoff_sleep,
    format_retry_telemetry,
    retry_state_for_attempt,
)
from translation_engine import GoogleClient, GoogleConfig  # noqa: E402


class _DeterministicRng:
    def random(self) -> float:
        return 0.5


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, headers: dict | None = None, text: str = "") -> None:
        self.status_code = int(status_code)
        self._payload = payload
        self.headers = headers or {}
        self.text = text

    def json(self) -> dict:
        return dict(self._payload)


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.headers = {}

    def post(self, *_args, **_kwargs) -> _FakeResponse:
        assert self._responses
        return self._responses.pop(0)


def test_retry_ux_backoff_and_states() -> None:
    sleep_s = adaptive_backoff_sleep(base_sleep_s=5.0, retry_after_s=8.0, jitter_ratio=0.1, rng=_DeterministicRng())
    assert sleep_s > 8.0
    assert retry_state_for_attempt(1, 3) == RETRY_WAITING
    assert retry_state_for_attempt(3, 3) == RETRY_FAILED


def test_retry_telemetry_format_contains_structured_fields() -> None:
    line = format_retry_telemetry(
        RetryTelemetry(
            provider="google",
            state=RETRY_WAITING,
            error_type="http_429",
            attempt=1,
            max_attempts=3,
            sleep_s=5.25,
            recovered=False,
        )
    )
    assert "provider=google" in line
    assert "state=waiting_retry" in line
    assert "error_type=http_429" in line
    assert "attempt=1/3" in line


def test_google_client_emits_waiting_and_recovered_retry_states(monkeypatch, capsys) -> None:
    cfg = GoogleConfig(api_key="k", model="models/fake", max_attempts=3, backoff_s=(1, 1, 1))
    client = GoogleClient(cfg)
    client.session = _FakeSession(
        [
            _FakeResponse(429, payload={"error": "rate"}, headers={"Retry-After": "0"}),
            _FakeResponse(
                200,
                payload={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
            ),
        ]
    )
    monkeypatch.setattr("translation_engine.time.sleep", lambda _x: None)
    out = client.generate("prompt", model="models/fake")
    log = capsys.readouterr().out
    assert out == "OK"
    assert "[RETRY] provider=google state=waiting_retry" in log
    assert "[RETRY] provider=google state=recovered" in log
