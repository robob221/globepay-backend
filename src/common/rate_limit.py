"""In-process rate limiting - a fixed-window counter per key, kept in
memory. This app runs as a single process (see src/scheduler.py for the
same reasoning about APScheduler) so a plain in-memory dict is the right
amount of infrastructure for a pitch-stage product; a multi-instance
deployment would need this moved to a shared store (Redis) since each
instance would otherwise enforce its own independent limit rather than
one shared one. Counters also reset on process restart - acceptable here,
not for a production abuse defense at scale.
"""

import time
from collections import defaultdict

from fastapi import HTTPException

_windows: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Raises 429 if `key` has already been hit `limit` times within the
    last `window_seconds`; otherwise records this call as one more hit."""
    now = time.monotonic()
    window_start = now - window_seconds
    timestamps = _windows[key]

    while timestamps and timestamps[0] < window_start:
        timestamps.pop(0)

    if len(timestamps) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests - please try again later")

    timestamps.append(now)


def reset() -> None:
    """Test-only: clear all counters. Every test's requests otherwise share
    this module-level state (and, via the ASGI test transport, the same
    reported client IP) across the whole pytest run, so without a reset
    between tests the register/login/password-reset limits below would
    trip on an unrelated later test rather than on real abuse."""
    _windows.clear()
