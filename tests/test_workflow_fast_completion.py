"""Tests des exécutions terminées immédiatement."""

from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from jarvis.context.command_outcomes import CommandOutcome
from jarvis.context.workflow_runner import WorkflowRunner


class ImmediateBus(QObject):
    execution_reserved = Signal(str)
    execution_finished = Signal(object)

    def __init__(self):
        super().__init__()
        self.busy = False
        self.current_execution_id = None
        self.commands = []
        self.accept = True

    def submit(self, command):
        if self.busy or not self.accept:
            return False

        execution_id = uuid4().hex

        self.current_execution_id = execution_id
        self.busy = True
        self.commands.append(command)

        self.execution_reserved.emit(execution_id)

        # Simulation : exécution et résultat immédiats.
        self.execution_finished.emit(
            CommandOutcome(
                execution_id=execution_id,
                command_id="test.command",
                status="unknown",
                response="Résultat immédiat",
            )
        )

        self.current_execution_id = None
        self.busy = False
        return True


def test_immediate_completion_not_lost():
    bus = ImmediateBus()
    runner = WorkflowRunner(
        bus,
        confirmation_probe=lambda: False,
    )

    assert runner.start(
        "prepare_work",
        approved=True,
    )

    assert runner.state.status == "review"
    assert len(runner.state.history) == 1
    assert runner.state.last_result == (
        "Résultat immédiat"
    )


def test_immediate_second_step():
    bus = ImmediateBus()
    runner = WorkflowRunner(
        bus,
        confirmation_probe=lambda: False,
    )

    assert runner.start(
        "prepare_work",
        approved=True,
    )

    assert runner.advance(approved=True)
    assert runner.state.status == "completed"

    assert bus.commands == [
        "mode Travail",
        "diagnostic",
    ]
    assert len(runner.state.history) == 2


def test_immediate_refusal():
    bus = ImmediateBus()
    bus.accept = False

    runner = WorkflowRunner(
        bus,
        confirmation_probe=lambda: False,
    )

    assert not runner.start(
        "prepare_work",
        approved=True,
    )

    assert runner.state.status == "blocked"
    assert bus.commands == []
    assert runner.state.history == ()
