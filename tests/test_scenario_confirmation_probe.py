"""Tests de lecture des confirmations de scénarios."""

import threading
import time

from jarvis.scenarios.engine import Engine


def make_engine():
    instance = object.__new__(Engine)
    instance._lock = threading.RLock()
    instance._approval = None
    return instance


def test_no_confirmation_pending():
    engine = make_engine()

    assert not engine.confirmation_pending()


def test_confirmation_expiration():
    engine = make_engine()

    engine._approval = (
        "secret",
        time.monotonic() + 30,
        {},
        "fingerprint",
    )

    assert engine.confirmation_pending()

    engine._approval = (
        "secret",
        time.monotonic() - 1,
        {},
        "fingerprint",
    )

    assert not engine.confirmation_pending()
