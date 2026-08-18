"""Fixtures scoped to the unit suite.

Two invariants hold for every test under ``tests/unit``: it never sleeps for real
and it never opens a socket. Both are enforced here by autouse fixtures rather
than by convention, so a regression shows up as a failing test instead of a slow
or flaky one.
"""

import socket
import time
from typing import List

import pytest


@pytest.fixture(autouse=True)
def recorded_sleeps(monkeypatch: pytest.MonkeyPatch) -> List[float]:
    """Replace ``time.sleep`` with a recorder for the duration of one test.

    Retry and deep-sleep behaviour is worth asserting on; waiting out the real
    delay is not. Tests that care about backoff request this fixture and read the
    recorded durations.

    Args:
        monkeypatch: Pytest monkeypatch fixture, used to restore ``time.sleep``.

    Returns:
        A list that accumulates every requested sleep duration, in order.
    """
    recorded: List[float] = []

    def _record(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(time, "sleep", _record)
    return recorded


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any unit test that tries to open a real socket.

    Unit tests mock at the ``requests`` layer. A test that slips past the mock
    would otherwise reach Wikidata and turn a deterministic suite into a flaky
    one, so the socket layer itself is closed off.

    Args:
        monkeypatch: Pytest monkeypatch fixture, used to restore the socket.
    """

    def _blocked(*args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "A unit test attempted a real network connection. Mock the HTTP layer "
            "(responses / mocker.patch) or move the test to tests/integration."
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked)
