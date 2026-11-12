"""Protection des workflows contre les résultats externes."""

from uuid import uuid4

import pytest
from PySide6.QtCore import QObject, Signal

from jarvis.context.command_outcomes import CommandOutcome
from jarvis.context.workflow_runner import WorkflowRunner


class TypedFakeBus(QObject):
    execution_finished = Signal(object)

    def __init__(self):
        super().__init__()
        self.busy = False
        self.current_execution_id = None
        self.commands = []

    def submit(self, command):
        if self.busy:
            return False

        self.busy = True
        self.current_execution_id = uuid4().hex
        self.commands.append(command)
        return True

    def finish(
        self,
        status="success",
        response="Commande terminée",
    ):
        assert self.busy

        outcome = CommandOutcome(
            execution_id=self.current_execution_id,
            command_id="test.command",
            status=status,
            response=response,
        )

        self.busy = False
        self.current_execution_id = None
        self.execution_finished.emit(outcome)

    def emit_external(
        self,
        status="success",
        response="Commande extérieure",
    ):
        self.execution_finished.emit(
            CommandOutcome(
                execution_id=uuid4().hex,
                command_id="external.command",
                status=status,
                response=response,
            )
        )


@pytest.fixture
def typed_workflow():
    bus = TypedFakeBus()
    runner = WorkflowRunner(
        bus,
        confirmation_probe=lambda: False,
    )
    return runner, bus


def test_correct_execution_id(typed_workflow):
    runner, bus = typed_workflow

    assert runner.start(
        "prepare_work",
        approved=True,
    )

    bus.finish("success", "Mode activé")

    assert runner.state.status == "review"
    assert runner.state.history[0].status == "success"


def test_external_result_ignored(typed_workflow):
    runner, bus = typed_workflow

    runner.start(
        "prepare_work",
        approved=True,
    )

    bus.emit_external()

    assert runner.state.status == "running"
    assert runner.state.history == ()

    bus.finish()

    assert runner.state.status == "review"
    assert len(runner.state.history) == 1


def test_external_failure_ignored(typed_workflow):
    runner, bus = typed_workflow

    runner.start(
        "prepare_work",
        approved=True,
    )

    bus.emit_external(
        status="failed",
        response="Erreur extérieure",
    )

    assert runner.state.status == "running"

    bus.finish("success")

    assert runner.state.status == "review"


def test_failed_step_blocks_following_step(typed_workflow):
    runner, bus = typed_workflow

    runner.start(
        "prepare_work",
        approved=True,
    )

    bus.finish(
        status="failed",
        response="Échec de l'activation",
    )

    assert runner.state.status == "blocked"
    assert runner.state.history[0].status == "failed"

    assert not runner.advance(approved=True)
    assert bus.commands == ["mode Travail"]


def test_pending_confirmation_blocks(typed_workflow):
    runner, bus = typed_workflow

    runner.start(
        "prepare_work",
        approved=True,
    )

    bus.finish(
        status="confirmation_required",
        response="Confirmation nécessaire",
    )

    assert runner.state.status == "confirmation_required"
    assert not runner.advance(approved=True)


def test_unknown_requires_review(typed_workflow):
    runner, bus = typed_workflow

    runner.start(
        "prepare_work",
        approved=True,
    )

    bus.finish(
        status="unknown",
        response="Résultat non vérifié",
    )

    assert runner.state.status == "review"
    assert runner.state.history[0].status == "unknown"
    assert bus.commands == ["mode Travail"]

    assert not runner.advance()

    assert runner.advance(approved=True)
    assert bus.commands == [
        "mode Travail",
        "diagnostic",
    ]


def test_cancel_waits_for_matching_execution(typed_workflow):
    runner, bus = typed_workflow

    runner.start(
        "prepare_work",
        approved=True,
    )

    assert runner.cancel()

    bus.emit_external()

    assert runner.state.status == "cancelling"

    bus.finish("success")

    assert runner.state.status == "cancelled"
    assert bus.commands == ["mode Travail"]
