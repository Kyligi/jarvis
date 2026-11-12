"""Tests du cycle de vie des workflows Jarvis."""

from PySide6.QtCore import QObject, Signal

from jarvis.context.workflow_runner import WorkflowRunner


class FakeBus(QObject):
    result = Signal(object)
    completed = Signal()

    def __init__(self):
        super().__init__()
        self.busy = False
        self.commands = []

    def submit(self, command):
        if self.busy:
            return False

        self.busy = True
        self.commands.append(command)
        return True

    def finish(self, response="Terminé"):
        assert self.busy
        self.result.emit(response)
        self.busy = False
        self.completed.emit()


def test_shutdown_without_active_workflow():
    bus = FakeBus()
    runner = WorkflowRunner(bus)

    runner.shutdown()

    assert not runner.start(
        "prepare_work",
        approved=True,
    )
    assert bus.commands == []


def test_shutdown_while_running():
    bus = FakeBus()
    runner = WorkflowRunner(bus)

    assert runner.start(
        "prepare_work",
        approved=True,
    )

    runner.shutdown()

    assert runner.state.status == "cancelling"
    assert bus.busy

    bus.finish("Commande terminée")

    assert runner.state.status == "cancelled"
    assert len(bus.commands) == 1


def test_shutdown_between_steps():
    bus = FakeBus()
    runner = WorkflowRunner(bus)

    runner.start("prepare_work", approved=True)
    bus.finish("Première étape terminée")

    assert runner.state.status == "review"

    runner.shutdown()

    assert runner.state.status == "cancelled"
    assert not runner.advance(approved=True)
    assert bus.commands == ["mode Travail"]


def test_shutdown_is_idempotent():
    bus = FakeBus()
    runner = WorkflowRunner(bus)

    runner.shutdown()
    runner.shutdown()

    assert not runner.start(
        "prepare_work",
        approved=True,
    )


def test_late_result_after_shutdown():
    bus = FakeBus()
    runner = WorkflowRunner(bus)

    runner.start("prepare_work", approved=True)
    runner.shutdown()

    bus.finish("Commande terminée")

    assert runner.state.status == "cancelled"

    # Événements tardifs : aucun nouveau lancement.
    bus.result.emit("Autre résultat")
    bus.completed.emit()

    assert runner.state.status == "cancelled"
    assert bus.commands == ["mode Travail"]


def test_shutdown_does_not_stop_command_bus():
    bus = FakeBus()
    runner = WorkflowRunner(bus)

    runner.start("prepare_work", approved=True)
    runner.shutdown()

    # La commande active continue d'exister.
    assert bus.busy
    assert bus.commands == ["mode Travail"]

    bus.finish()

    assert not bus.busy
    assert runner.state.status == "cancelled"
