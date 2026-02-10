from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


RETRY_ACTIVE = "active"
RETRY_WAITING = "waiting_retry"
RETRY_RECOVERED = "recovered"
RETRY_FAILED = "failed"


@dataclass(frozen=True)
class RetryTelemetry:
    provider: str
    state: str
    error_type: str
    attempt: int
    max_attempts: int
    sleep_s: float
    recovered: bool


def adaptive_backoff_sleep(
    *,
    base_sleep_s: float,
    retry_after_s: Optional[float],
    jitter_ratio: float = 0.12,
    rng: Optional[random.Random] = None,
) -> float:
    base = max(0.0, float(base_sleep_s or 0.0))
    if retry_after_s is not None:
        try:
            base = max(base, float(retry_after_s))
        except Exception:
            pass
    ratio = max(0.0, float(jitter_ratio or 0.0))
    rnd = (rng.random() if rng is not None else random.random()) if ratio > 0 else 0.0
    jitter = base * ratio * max(0.0, min(1.0, float(rnd)))
    return max(0.0, base + jitter)


def retry_state_for_attempt(attempt: int, max_attempts: int) -> str:
    cur = max(1, int(attempt))
    limit = max(1, int(max_attempts))
    return RETRY_WAITING if cur < limit else RETRY_FAILED


def format_retry_telemetry(evt: RetryTelemetry) -> str:
    return (
        f"[RETRY] provider={evt.provider} state={evt.state} error_type={evt.error_type} "
        f"attempt={int(evt.attempt)}/{int(evt.max_attempts)} sleep_s={float(evt.sleep_s):.2f} "
        f"recovered={1 if evt.recovered else 0}"
    )


def terminal_retry_summary(*, provider: str, error_type: str, max_attempts: int, last_error: Exception) -> str:
    return (
        f"{provider} retry budget exhausted after {int(max_attempts)} attempts "
        f"(error_type={error_type}): {last_error}"
    )
