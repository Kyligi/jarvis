"""Tests du verrou d'arrêt de CommandBus."""

from unittest.mock import Mock

from jarvis.interface.context import CommandBus


def test_submit_rejected_after_shutdown():
    bus = CommandBus(executor=Mock())
    bus.stopped = True

    assert bus.submit("mode Travail") is False


def test_immediate_command_rejected_after_shutdown():
    bus = CommandBus(executor=Mock())
    bus.stopped = True

    assert bus.submit("arrête IA") is False


def test_operation_rejected_after_shutdown():
    bus = CommandBus(executor=Mock())
    bus.stopped = True

    assert bus.submit_operation(Mock()) is False
