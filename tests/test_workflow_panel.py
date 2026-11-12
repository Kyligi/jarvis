"""Tests de l'interface des workflows supervisés."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from jarvis.interface.workflow_panel import WorkflowPanel


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

    def finish(self, response):
        self.result.emit(response)
        self.busy = False
        self.completed.emit()


@pytest.fixture
def panel_ui(qapp):
    bus = FakeBus()
    context = SimpleNamespace(commands=bus)
    panel = WorkflowPanel(context)

    yield panel, bus

    panel.close()
    panel.deleteLater()
    qapp.processEvents()


def test_panel_initial_state(panel_ui):
    panel, bus = panel_ui

    assert panel.selector.count() == 2
    assert panel.start_button.isEnabled()
    assert not panel.continue_button.isEnabled()
    assert not panel.cancel_button.isEnabled()
    assert bus.commands == []


def test_preview_has_no_side_effect(panel_ui):
    panel, bus = panel_ui

    panel.show_preview()

    assert "mode Travail" in panel.preview.toPlainText()
    assert bus.commands == []


def test_cancel_start_confirmation(panel_ui, monkeypatch):
    panel, bus = panel_ui

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )

    panel.start_selected()

    assert bus.commands == []


def test_start_and_continue(panel_ui, monkeypatch):
    panel, bus = panel_ui

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    panel.start_selected()

    assert bus.commands == ["mode Travail"]
    assert panel.runner.state.status == "running"

    bus.finish("Mode Travail activé")

    assert panel.runner.state.status == "review"
    assert panel.continue_button.isEnabled()

    panel.continue_workflow()

    assert bus.commands == [
        "mode Travail",
        "diagnostic",
    ]

    bus.finish("Diagnostic terminé")

    assert panel.runner.state.status == "completed"
    assert len(panel.runner.state.history) == 2


def test_cancel_workflow(panel_ui, monkeypatch):
    panel, bus = panel_ui

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    panel.start_selected()
    bus.finish("Première étape terminée")

    panel.cancel_workflow()

    assert panel.runner.state.status == "cancelled"
    assert bus.commands == ["mode Travail"]


def test_runner_shared_by_same_context(qapp):
    """Deux panneaux retrouvent le même runner."""

    bus = FakeBus()
    context = SimpleNamespace(commands=bus)

    first = WorkflowPanel(context)
    runner = first.runner

    second = WorkflowPanel(context)

    assert second.runner is runner
    assert context._workflow_runner is runner

    first.close()
    second.close()
    first.deleteLater()
    second.deleteLater()
    qapp.processEvents()


def test_workflow_survives_panel_recreation(
    qapp,
    monkeypatch,
):
    """Fermer le panneau ne perd pas le workflow."""

    bus = FakeBus()
    context = SimpleNamespace(commands=bus)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    first = WorkflowPanel(context)
    first.start_selected()

    assert first.runner.state.status == "running"
    assert bus.commands == ["mode Travail"]

    runner = first.runner

    first.close()
    first.deleteLater()
    qapp.processEvents()

    # La commande termine après la fermeture.
    bus.finish("Mode Travail activé")

    assert runner.state.status == "review"

    second = WorkflowPanel(context)

    assert second.runner is runner
    assert second.runner.state.status == "review"
    assert second.continue_button.isEnabled()
    assert "Mode Travail activé" in (
        second.history.toPlainText()
    )

    # Aucune commande n'a été relancée
    # simplement parce que le HUD a été recréé.
    assert bus.commands == ["mode Travail"]

    second.close()
    second.deleteLater()
    qapp.processEvents()


def test_cancel_after_panel_recreation(
    qapp,
    monkeypatch,
):
    """Une annulation reste valable après réouverture."""

    bus = FakeBus()
    context = SimpleNamespace(commands=bus)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    first = WorkflowPanel(context)
    first.start_selected()

    runner = first.runner

    first.close()
    first.deleteLater()
    qapp.processEvents()

    second = WorkflowPanel(context)
    second.cancel_workflow()

    assert runner.state.status == "cancelling"

    # La commande déjà lancée termine normalement.
    bus.finish("Commande terminée")

    assert runner.state.status == "cancelled"
    assert bus.commands == ["mode Travail"]
    assert not runner.advance(approved=True)

    second.close()
    second.deleteLater()
    qapp.processEvents()


def test_different_context_has_different_runner(qapp):
    """Les sessions Jarvis ne partagent pas leur workflow."""

    first_context = SimpleNamespace(
        commands=FakeBus()
    )
    second_context = SimpleNamespace(
        commands=FakeBus()
    )

    first = WorkflowPanel(first_context)
    second = WorkflowPanel(second_context)

    assert first.runner is not second.runner

    first.close()
    second.close()
    first.deleteLater()
    second.deleteLater()
    qapp.processEvents()
