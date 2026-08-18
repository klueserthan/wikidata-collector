"""Fixtures scoped to the integration suite.

Integration tests drive the full pipeline over a mocked transport. They exercise
retry and backoff logic, but there is nothing to learn from waiting out the delay
itself, so sleeps are recorded rather than performed — except for `live` tests,
which talk to the real endpoint and must honour real rate limits.
"""

import time
from typing import List

import pytest


@pytest.fixture(autouse=True)
def recorded_sleeps(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> List[float]:
    """Record `time.sleep` calls instead of performing them, off the live path.

    Args:
        request: Pytest request, used to detect the `live` marker.
        monkeypatch: Pytest monkeypatch fixture, used to restore `time.sleep`.

    Returns:
        Sleep durations in order — empty and unused for `live` tests, which keep
        sleeping for real.
    """
    recorded: List[float] = []
    if request.node.get_closest_marker("live"):
        return recorded

    monkeypatch.setattr(time, "sleep", lambda seconds: recorded.append(seconds))
    return recorded
