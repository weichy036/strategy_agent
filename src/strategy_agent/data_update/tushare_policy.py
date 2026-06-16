from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter, sleep
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class TushareRetryPolicy:
    max_attempts: int = 2
    retry_delays: tuple[float, ...] = (2.0, 5.0)
    stop_after_failures: int = 5


@dataclass(frozen=True)
class TushareCallResult:
    ok: bool
    frame: pd.DataFrame | None
    attempts: int
    elapsed_seconds: float
    error: str | None

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("frame", None)
        return data


def call_tushare(request: Callable[[], pd.DataFrame | None], *, policy: TushareRetryPolicy | None = None) -> TushareCallResult:
    active_policy = policy or TushareRetryPolicy()
    attempts = max(1, active_policy.max_attempts)
    started = perf_counter()
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        try:
            frame = request()
            return TushareCallResult(
                ok=True,
                frame=frame,
                attempts=attempt,
                elapsed_seconds=perf_counter() - started,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempt >= attempts:
                break
            delay = _retry_delay(active_policy.retry_delays, attempt)
            if delay > 0:
                sleep(delay)
    return TushareCallResult(
        ok=False,
        frame=None,
        attempts=attempts,
        elapsed_seconds=perf_counter() - started,
        error=last_error,
    )


def _retry_delay(delays: tuple[float, ...], attempt: int) -> float:
    if not delays:
        return 0.0
    index = min(max(attempt - 1, 0), len(delays) - 1)
    return max(float(delays[index]), 0.0)


__all__ = ["TushareCallResult", "TushareRetryPolicy", "call_tushare"]
