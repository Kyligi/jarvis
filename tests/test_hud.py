from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import pytest
from PySide6.QtCore import QAbstractAnimation, QThread
from PySide6.QtWidgets import QWidget
from jarvis.interface.context import AppContext
from jarvis.interface.mini import JarvisWindow
from jarvis.monitoring.collector import Snapshot
from jarvis.preferences import Preferences
from jarvis import preferences
from test_interface import pump


class FakeService:
    def __init__(self):
        self.calls = []
        self.project = {"name": "Nebula", "path": Path("/tmp/Nebula"), "language": "Python",
                        "objective": "Terminer l'interface HUD", "last_opened": 1794132000}

    def home(self):
        self.calls.append("home")
        return {"project": self.project, "mode": "travail"}

    def projects(self):
        self.calls.append("projects")
        return [self.project]

    def project_details(self, path):
        self.calls.append("git")
        return "Branche : main\nDernier commit : a1b2c3 Ajouter le HUD\nFichiers : Aucune modification locale"

    def session(self):
        self.calls.append("sessions")
        return {"project": "Nebula · Python\nObjectif : Terminer l'interface HUD",
                "saved": "08/11/2026 18:00 · 3 fichiers\nObjectif : Terminer l'interface HUD",
                "files": "src/main.py\nsrc/ui.py\nREADME.md", "history": "08/11/2026 — Nebula"}

    def system(self):
        self.calls.append("system")
        return {"history": "Dernière heure\nCPU moyen : 24 %\nRAM moyenne : 42 %",
                "processes": "python (PID 1204) — CPU 8 % | RAM 180 Mo\ncode (PID 812) — CPU 3 % | RAM 460 Mo"}

    def modes(self):
        self.calls.append("modes")
        return {"mode": "travail"}


@pytest.fixture
def ui(qapp):
    service = FakeService()
    sample = Snapshot(24, 42, 38, SimpleNamespace(percent=83, power_plugged=True),
                      {"CPU AMD / Tctl": 52, "GPU Radeon / edge": 44, "SSD NVMe": 39},
                      alerts=("18:01:00 — CPU à 92 % (seuil 90 %)",))
    collector = Mock()
    collector.collect.return_value = sample
    executor = Mock(return_value="Réponse du moteur")
    context = AppContext(service=service, collector=collector, executor=executor)
    mini = JarvisWindow(context)
    mini.show()
    mini.open_hud()
    hud = mini.hud
    pump(qapp, lambda: context.monitor.runner.task is None and hud.pages[0].runner.task is None)
    yield mini, hud, context, service, collector, executor
    mini.close()
    qapp.processEvents()


def select(qapp, hud, index):
    hud.navigation.setCurrentRow(index)
    page = hud.pages[index]
    pump(qapp, lambda: page.runner.task is None)
    return page


def test_creation_navigation_and_shared_services(qapp, ui):
    mini, hud, context, service, collector, executor = ui
    assert len(hud.pages) == 9
    assert mini.dashboard.monitor is hud.pages[1].dashboard.monitor is context.monitor
    assert mini.console.bus is hud.console.bus is context.commands
    assert collector.collect.call_count == 1
    assert len(hud.pages[1].dashboard.graph.cpu) <= 1
    for index in range(9):
        select(qapp, hud, index)
        assert hud.stack.currentIndex() == index
        assert [p.active for p in hud.pages] == [i == index for i in range(9)]
        assert hud.pages[1].timer.isActive() == (index == 1)
    assert collector.collect.call_count == 1


def test_simulated_data_and_search(qapp, ui):
    _, hud, _, service, _, _ = ui
    home = hud.pages[0]
    assert home.project.text() == "Nebula"
    assert "interface HUD" in home.objective.text()
    assert "92 %" in home.alerts.toPlainText()
    projects = select(qapp, hud, 2)
    assert projects.table.rowCount() == 1
    projects.table.selectRow(0)
    pump(qapp, lambda: projects.detail_runner.task is None)
    assert "main" in projects.details.toPlainText()
    assert "a1b2c3" in projects.details.toPlainText()
    projects.search.setText("missing")
    assert projects.table.isRowHidden(0)
    assert not projects.open_button.isEnabled()
    projects.search.setText("python")
    projects.table.selectRow(0)
    assert projects.open_button.isEnabled()
    session = select(qapp, hud, 3)
    assert "3 fichiers" in session.views["saved"].toPlainText()
    modes = select(qapp, hud, 4)
    assert "Travail" in modes.current.text()


def test_close_reopen_reuses_hud_and_readers(qapp, ui):
    mini, hud, context, _, collector, _ = ui
    readers = len(context.readers)
    count = len(hud.findChildren(QWidget))
    for _ in range(4):
        hud.close()
        assert not hud.isVisible()
        assert not any(page.active for page in hud.pages)
        assert not hud.pages[1].timer.isActive()
        mini.open_hud()
        assert mini.hud is hud
        pump(qapp, lambda: hud.pages[0].runner.task is None)
    assert len(context.readers) == readers
    assert len(hud.findChildren(QWidget)) == count
    assert not context.stopped
    assert collector.collect.call_count == 1


def test_global_command_and_response_history(qapp, ui):
    mini, hud, context, _, _, executor = ui
    hud.console.command.setText("aide")
    hud.console.submit()
    assert not hud.console.command.isEnabled()
    assert not mini.command.isEnabled()
    assert "en cours" in hud.console.status.text()
    pump(qapp, lambda: context.commands.runner.task is None)
    executor.assert_called_once_with("aide")
    assert "Réponse du moteur" in hud.console.output.toPlainText()
    assert "Réponse du moteur" in mini.output.toPlainText()
    hud.console.command.setText("statut")
    hud.console.submit()
    pump(qapp, lambda: context.commands.runner.task is None)
    assert hud.console.output.toPlainText().count("Réponse du moteur") == 2


def test_buttons_use_existing_engine(qapp, ui):
    _, hud, context, _, _, executor = ui
    modes = select(qapp, hud, 4)
    modes.buttons["etudes"].click()
    pump(qapp, lambda: context.commands.runner.task is None)
    executor.assert_called_with("mode Études")
    projects = select(qapp, hud, 2)
    projects.table.selectRow(0)
    projects.open_button.click()
    pump(qapp, lambda: context.commands.runner.task is None)
    executor.assert_called_with("ouvre projet Nebula")


def test_preferences_applied_and_persisted(qapp, ui):
    _, hud, context, _, _, _ = ui
    page = select(qapp, hud, 5)
    page.animations.setChecked(False)
    page.interval.setValue(7)
    page.save_button.click()
    pump(qapp, lambda: context.preference_runner.task is None)
    assert preferences.load_preferences() == Preferences(False, 7)
    assert context.monitor.timer.interval() == 7000
    assert not context.preferences.animations
    select(qapp, hud, 0)
    assert hud.animation.state() == QAbstractAnimation.State.Stopped
    assert hud.effect.opacity() == 1
    assert "enregistrées" in page.state.text()


def test_preferences_write_error_keeps_runtime(qapp, ui, monkeypatch):
    _, hud, context, _, _, _ = ui
    monkeypatch.setattr(preferences, "save_preferences", Mock(side_effect=OSError("private")))
    page = select(qapp, hud, 5)
    page.interval.setValue(6)
    page.save_button.click()
    pump(qapp, lambda: context.preference_runner.task is None)
    assert "impossible" in page.state.text()
    assert context.monitor.timer.interval() == 2000
    assert "private" not in page.state.text()
    assert page.save_button.isEnabled()


def test_page_error_retry_and_hidden_page_no_refresh(qapp, ui, monkeypatch):
    _, hud, context, service, _, _ = ui
    monkeypatch.setattr(service, "projects", Mock(side_effect=OSError("private")))
    page = select(qapp, hud, 2)
    assert "Lecture impossible" in page.state.text()
    assert "private" not in page.state.text()
    service.projects.side_effect = None
    service.projects.return_value = []
    page.refresh_button.click()
    pump(qapp, lambda: page.runner.task is None)
    assert "Aucun projet" in page.state.text()
    select(qapp, hud, 0)
    calls = service.projects.call_count
    page.refresh()
    assert service.projects.call_count == calls


def test_empty_services(qapp, ui, monkeypatch):
    _, hud, _, service, _, _ = ui
    monkeypatch.setattr(service, "home", lambda: {"project": None, "mode": None})
    monkeypatch.setattr(service, "projects", lambda: [])
    hud.pages[0].refresh()
    pump(qapp, lambda: hud.pages[0].runner.task is None)
    assert "Aucun projet" in hud.pages[0].project.text()
    assert "Aucun mode" in hud.pages[0].mode.text()
    assert select(qapp, hud, 2).table.rowCount() == 0


def test_command_error_and_shutdown(qapp, ui):
    mini, hud, context, _, _, executor = ui
    executor.side_effect = OSError("private")
    context.commands.submit("aide")
    pump(qapp, lambda: context.commands.runner.task is None)
    assert "Erreur Jarvis (OSError)" in hud.console.output.toPlainText()
    assert "private" not in hud.console.output.toPlainText()
    mini.close()
    assert context.stopped
    assert not context.monitor.timer.isActive()
    assert not context.commands.submit("aide")


def test_slow_page_does_not_block_navigation(qapp, ui, monkeypatch):
    _, hud, _, service, _, _ = ui
    release = threading.Event()
    threads = []
    def slow():
        threads.append(QThread.currentThread())
        release.wait(2)
        return []
    monkeypatch.setattr(service, "projects", slow)
    hud.navigation.setCurrentRow(2)
    pump(qapp, lambda: bool(threads))
    hud.navigation.setCurrentRow(4)
    assert hud.stack.currentIndex() == 4
    assert threads[0] != qapp.thread()
    release.set()
    pump(qapp, lambda: hud.pages[2].runner.task is None)


def test_render_all_pages(qapp, ui, tmp_path):
    mini, hud, context, _, _, _ = ui
    context.preferences = Preferences(False, 2)
    for index in range(9):
        select(qapp, hud, index)
        hud.animation.stop()
        hud.effect.setOpacity(1)
        qapp.processEvents()
        image = hud.grab()
        assert not image.isNull()
        assert image.save(str(tmp_path / f"hud-{index}.png"))
    assert mini.grab().save(str(tmp_path / "mini.png"))


def test_hidden_dashboard_keeps_history_without_rendering(qapp, ui):
    _, hud, context, _, _, _ = ui
    dashboard = hud.pages[1].dashboard
    before = list(dashboard.graph.cpu)
    for value in (10, 20, 30):
        context.monitor.receive(Snapshot(value, 40, 30, None, {}))
    assert list(dashboard.graph.cpu) == before
    select(qapp, hud, 1)
    assert list(dashboard.graph.cpu)[-3:] == [10, 20, 30]
    assert dashboard.cpu.bar.value() == 30


def test_requested_mode_distinct_from_saved_mode(qapp, ui):
    _, hud, context, _, _, executor = ui
    executor.return_value = "Erreur Hyprland"
    page = select(qapp, hud, 4)
    page.buttons["etudes"].click()
    pump(qapp, lambda: context.commands.runner.task is None and page.runner.task is None)
    assert "Etudes" in page.requested.text()
    assert "Travail" in page.current.text()


def test_corrupt_preferences_fallback_preserves_file(qapp, tmp_path):
    preferences.PREFERENCES_PATH.write_text('refresh_seconds = "bad"')
    context = AppContext(service=FakeService(), collector=Mock(collect=Mock(return_value=Snapshot(0, 0, 0, None, {}))))
    try:
        assert context.preferences == Preferences()
        assert "illisibles" in context.preference_warning
        assert preferences.PREFERENCES_PATH.read_text() == 'refresh_seconds = "bad"'
    finally:
        context.shutdown()
        qapp.processEvents()


def test_command_bus_serializes_both_windows(qapp, ui):
    mini, hud, context, _, _, executor = ui
    release = threading.Event()
    executor.side_effect = lambda text: (release.wait(2), "done")[1]
    try:
        assert context.commands.submit("aide")
        assert not context.commands.submit("mode Gaming")
        assert not mini.button.isEnabled()
        assert not hud.console.button.isEnabled()
    finally:
        release.set()
        pump(qapp, lambda: context.commands.runner.task is None)
    executor.assert_called_once_with("aide")
