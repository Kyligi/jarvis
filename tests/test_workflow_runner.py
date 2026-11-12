"""Tests du moteur supervisé de workflows."""

import pytest
from PySide6.QtCore import QObject, Signal

from jarvis.context.workflow_runner import WorkflowRunner


class FakeBus(QObject):
    result = Signal(object)
    completed = Signal()

    def __init__(self):
        super().__init__()
        self.busy = False
        self.commands = []
        self.accept = True

    def submit(self, command):
        if self.busy or not self.accept:
            return False

        self.busy = True
        self.commands.append(command)
        return True

    def finish(self, response="Terminé"):
        assert self.busy
        self.result.emit(response)
        self.busy = False
        self.completed.emit()


@pytest.fixture
def workflow():
    bus = FakeBus()
    runner = WorkflowRunner(bus)
    return runner, bus


def test_approval_required(workflow):
    runner, bus = workflow

    assert not runner.start("prepare_work")
    assert bus.commands == []


def test_first_step_only(workflow):
    runner, bus = workflow

    assert runner.start("prepare_work", approved=True)
    assert bus.commands == ["mode Travail"]
    assert runner.state.status == "running"


def test_waits_for_result(workflow):
    runner, bus = workflow

    runner.start("prepare_work", approved=True)
    bus.finish("Mode Travail activé")

    assert runner.state.status == "review"
    assert bus.commands == ["mode Travail"]
    assert runner.state.last_result == (
        "Mode Travail activé"
    )


def test_second_approval_required(workflow):
    runner, bus = workflow

    runner.start("prepare_work", approved=True)
    bus.finish("Mode Travail activé")

    assert not runner.advance()
    assert bus.commands == ["mode Travail"]


def test_second_step_after_approval(workflow):
    runner, bus = workflow

    runner.start("prepare_work", approved=True)
    bus.finish("Mode Travail activé")

    assert runner.advance(approved=True)
    assert bus.commands == [
        "mode Travail",
        "diagnostic",
    ]

    bus.finish("Diagnostic disponible")

    assert runner.state.status == "completed"
    assert len(runner.state.history) == 2


def test_cancel_between_steps(workflow):
    runner, bus = workflow

    runner.start("prepare_work", approved=True)
    bus.finish("Première étape terminée")

    assert runner.cancel()
    assert runner.state.status == "cancelled"
    assert not runner.advance(approved=True)
    assert len(bus.commands) == 1


def test_cancel_while_running(workflow):
    runner, bus = workflow

    runner.start("prepare_work", approved=True)

    assert runner.cancel()
    assert runner.state.status == "cancelling"

    # La commande active n'est pas interrompue.
    assert bus.busy

    bus.finish("Commande terminée")

    assert runner.state.status == "cancelled"
    assert len(bus.commands) == 1


def test_busy_bus_rejected(workflow):
    runner, bus = workflow
    bus.busy = True

    assert not runner.start(
        "prepare_work",
        approved=True,
    )

    assert bus.commands == []


def test_rejected_command(workflow):
    runner, bus = workflow
    bus.accept = False

    assert not runner.start(
        "prepare_work",
        approved=True,
    )

    assert runner.state.status == "blocked"
    assert bus.commands == []


def test_unknown_plan_rejected(workflow):
    runner, bus = workflow

    with pytest.raises(ValueError):
        runner.start("unknown", approved=True)

    assert bus.commands == []


def test_no_parallel_workflows(workflow):
    runner, bus = workflow

    runner.start("prepare_work", approved=True)

    assert not runner.start(
        "save_and_check",
        approved=True,
    )

    assert len(bus.commands) == 1


def test_result_is_not_assumed_success(workflow):
    runner, bus = workflow

    runner.start("prepare_work", approved=True)
    bus.finish("Erreur : action non exécutée")

    assert runner.state.status == "review"
    assert runner.state.last_result == (
        "Erreur : action non exécutée"
    )

    # Aucune seconde commande automatiquement.
    assert bus.commands == ["mode Travail"]


def test_history_contains_commands(workflow):
    runner, bus = workflow

    runner.start("save_and_check", approved=True)
    bus.finish("Session enregistrée")

    assert runner.state.history[0].step_id == (
        "save_session"
    )
    assert runner.state.history[0].command == (
        "sauvegarde ma session"
    )


def test_cancelled_workflow_can_restart(workflow):
    runner, bus = workflow

    runner.start("prepare_work", approved=True)
    bus.finish("Terminé")
    runner.cancel()

    assert runner.start(
        "save_and_check",
        approved=True,
    )

    assert bus.commands[-1] == (
        "sauvegarde ma session"
    )


def test_pending_confirmation_blocks_next_step():
    bus = FakeBus()

    runner = WorkflowRunner(
        bus,
        confirmation_probe=lambda: True,
    )

    assert runner.start(
        "prepare_work",
        approved=True,
    )

    bus.finish("Confirme scénario abc123")

    assert runner.state.status == (
        "confirmation_required"
    )
    assert not runner.advance(approved=True)
    assert bus.commands == ["mode Travail"]


def test_no_pending_confirmation_allows_review():
    bus = FakeBus()

    runner = WorkflowRunner(
        bus,
        confirmation_probe=lambda: False,
    )

    assert runner.start(
        "prepare_work",
        approved=True,
    )

    bus.finish("Mode Travail activé")

    assert runner.state.status == "review"
    assert runner.advance(approved=True)

    assert bus.commands == [
        "mode Travail",
        "diagnostic",
    ]


def test_confirmation_probe_failure_blocks_workflow():
    def unavailable():
        raise RuntimeError("Scénarios indisponibles")

    bus = FakeBus()

    runner = WorkflowRunner(
        bus,
        confirmation_probe=unavailable,
    )

    assert runner.start(
        "prepare_work",
        approved=True,
    )

    bus.finish("Résultat indéterminé")

    assert runner.state.status == "blocked"
    assert not runner.advance(approved=True)
    assert bus.commands == ["mode Travail"]
