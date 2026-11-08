"""Services de présentation partagés par Mini et HUD dans un seul processus."""
from collections import deque
import logging
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication
from jarvis import preferences
from jarvis.core.commands import execute
from jarvis.registry import resolve
from jarvis.interface.workers import Runner
from jarvis.monitoring.collector import Collector
from jarvis.services.overview import OverviewService


class MonitorHub(QObject):
    updated = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None, collector=None, interval=2):
        super().__init__(parent)
        self.collector = collector or Collector()
        self.latest = None
        self.history = deque(maxlen=60)
        self.runner = Runner(self)
        self.runner.result.connect(self.receive)
        self.runner.failed.connect(self.failed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(interval * 1000)
        self.refresh()

    @Slot()
    def refresh(self):
        self.runner.start(self.collector.collect)

    @Slot(object)
    def receive(self, snapshot):
        self.latest = snapshot
        self.history.append((snapshot.cpu, snapshot.ram))
        self.updated.emit(snapshot)

    def shutdown(self):
        self.timer.stop()
        self.runner.shutdown()


class CommandBus(QObject):
    result = Signal(object)
    busy_changed = Signal(bool)
    completed = Signal()
    started = Signal(str)

    def __init__(self, parent=None, executor=None):
        super().__init__(parent)
        self.executor = executor or execute
        self.runner = Runner(self)
        self.runner.result.connect(self.result)
        self.runner.failed.connect(self.failure)
        self.runner.idle.connect(self.finished)
        self.busy = False
        self.last_requested_mode = None

    def submit(self, command: str) -> bool:
        text = command.strip()
        if not text or self.busy:
            return False
        if not self.runner.start(lambda: self.executor(text)):
            return False
        resolved = resolve(text)
        identifier = resolved.command.id if resolved else "unknown"
        if identifier in {"modes.travail", "modes.gaming", "modes.etudes"}:
            self.last_requested_mode = identifier.split(".")[1]
        self.busy = True
        self.busy_changed.emit(True)
        self.started.emit(identifier)
        return True

    @Slot(str)
    def failure(self, error):
        self.result.emit(f"Erreur Jarvis ({error}). Réessaie ou consulte les logs.")

    @Slot()
    def finished(self):
        self.busy = False
        self.busy_changed.emit(False)
        self.completed.emit()


class AppContext(QObject):
    preferences_changed = Signal(object)
    preferences_saved = Signal()
    preferences_failed = Signal(str)

    def __init__(self, parent=None, service=None, collector=None, executor=None):
        super().__init__(parent)
        self.service = service or OverviewService()
        self.preference_warning = ""
        try:
            self.preferences = preferences.load_preferences()
        except (OSError, ValueError, TypeError) as error:
            self.preferences = preferences.Preferences()
            self.preference_warning = "Préférences illisibles : valeurs par défaut, fichier conservé."
            logging.getLogger(__name__).warning("preferences_load_failed", extra={"error_type": type(error).__name__})
        self.monitor = MonitorHub(self, collector, self.preferences.refresh_seconds)
        self.commands = CommandBus(self, executor)
        self.preference_runner = Runner(self)
        self.preference_runner.result.connect(self.apply_preferences)
        self.preference_runner.failed.connect(self.preferences_failed)
        self.readers = []
        self.stopped = False
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def reader(self) -> Runner:
        runner = Runner(self)
        self.readers.append(runner)
        return runner

    def save_preferences(self, value: preferences.Preferences) -> bool:
        def save():
            preferences.save_preferences(value)
            return value
        return self.preference_runner.start(save)

    @Slot(object)
    def apply_preferences(self, value):
        self.preferences = value
        self.monitor.timer.setInterval(value.refresh_seconds * 1000)
        self.preference_warning = ""
        self.preferences_changed.emit(value)
        self.preferences_saved.emit()

    @Slot()
    def shutdown(self):
        if self.stopped:
            return
        self.stopped = True
        self.monitor.shutdown()
        self.commands.runner.shutdown()
        self.preference_runner.shutdown()
        for runner in self.readers:
            runner.shutdown()
