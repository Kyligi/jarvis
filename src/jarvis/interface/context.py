"""Services de présentation partagés par Mini et HUD dans un seul processus."""
import logging
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from jarvis import preferences
from jarvis.core.commands import execute
from jarvis.interface.workers import Runner
from jarvis.monitoring.collector import Collector
from jarvis.registry import resolve
from jarvis.services.overview import OverviewService
from jarvis.memory.service import MemoryService
from jarvis.memory.conversation_service import ConversationService

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


@dataclass(frozen=True)
class ConversationReply:
    text: str
    cancelled: object


class CommandBus(QObject):
    result = Signal(object)
    busy_changed = Signal(bool)
    completed = Signal()
    started = Signal(str)
    page_requested = Signal(str)
    scenario_progress = Signal(object)
    ai_event = Signal(object)

    def __init__(self, parent=None, executor=None):
        super().__init__(parent)
        self.executor = executor or execute
        from jarvis.ai import config as ai_config
        from jarvis.ai.conversation import Conversation
        self.ai_warning = ''
        try:
            configuration = ai_config.load()
        except (OSError, ValueError, TypeError, KeyError):
            configuration = ai_config.AIConfig()
            self.ai_warning = 'Configuration IA invalide : fichier conservé ; IA désactivée.'
        self.memory_service = MemoryService()
        self.conversation_store = ConversationService()

        self.conversation = Conversation(
            configuration,
            listener=self.ai_event.emit,
            memory_service=self.memory_service,
            conversation_service=self.conversation_store,
	    persistence_saver=ai_config.save,
        )
        self.inference_available = lambda: True
        self.runner = Runner(self)
        self.runner.result.connect(self.receive_result)
        self.runner.failed.connect(self.failure)
        self.runner.idle.connect(self.finished)
        self.busy = False
        self.last_requested_mode = None

    def submit(self, command: str) -> bool:
        text = command.strip()
        if not text:
            return False
        resolved = resolve(text)
        identifier = resolved.command.id if resolved else 'unknown'
        if identifier in {'ai.stop', 'ai.cancel', 'ai.clear', 'ai.disable'}:
            from jarvis.ai.commands import route
            self.result.emit(route(self.conversation, text, self.executor))
            return True
        if resolved and resolved.command.id in {"scenarios.cancel", "scenarios.status", "voice.stop", "voice.disable", "voice.quiet", "voice.status", "voice.wake_off"}:
            self.result.emit(resolved.run())
            return True
        if self.busy:
            return False
        if resolved is None and not self.inference_available():
            self.result.emit('Attendre la fin de la capture/transcription ou de la synthèse avant l’inférence IA.')
            return False
        from jarvis.ai.commands import route
        # Reserve the turn before launching the worker, so an immediate Stop cannot be lost.
        if resolved is None:
            self.conversation.prepare()
        turn_cancelled = self.conversation.cancelled
        def run():
            value = route(self.conversation, text, self.executor)
            return ConversationReply(value, turn_cancelled) if resolved is None else value
        if not self.runner.start(run):
            return False
        identifier = resolved.command.id if resolved else "unknown"
        if identifier in {"modes.travail", "modes.gaming", "modes.etudes"}:
            self.last_requested_mode = identifier.split(".")[1]
        self.busy = True
        self.busy_changed.emit(True)
        self.started.emit(identifier)
        if identifier in {'ai.open', 'ai.talk'}:
            self.page_requested.emit('assistant')
        elif identifier == "scenarios.open":
            self.page_requested.emit("scenarios")
        elif identifier == "modes.configure" and resolved.arguments[0] in {"travail", "gaming", "etudes"}:
            self.page_requested.emit("modes:" + resolved.arguments[0])
        return True

    def submit_operation(self, operation) -> bool:
        """Action HUD typée utilisant le même verrou de commandes que Mini."""
        if self.busy or not self.runner.start(operation):
            return False
        self.busy = True
        self.busy_changed.emit(True)
        self.started.emit("windows.action")
        return True

    @Slot(object)
    def receive_result(self, result):
        if isinstance(result, ConversationReply):
            result = 'Génération annulée ; contenu de la session effacé ou interrompu.' if result.cancelled.is_set() else result.text
        self.result.emit(result)

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
        from jarvis.scenarios.engine import engine
        self.scenario_engine = engine
        self.scenario_listener = self.commands.scenario_progress.emit
        engine.listeners.append(self.scenario_listener)
        from jarvis.interface.voice import VoiceBridge
        self.voice = VoiceBridge(self)
        from jarvis.voice.controller import State
        self.commands.inference_available = lambda: self.voice.controller.snapshot.state in (
            State.IDLE, State.ERROR, State.EXECUTING, State.AWAITING_CONFIRMATION)

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
        self.commands.conversation.stop()
        self.voice.shutdown()
        self.scenario_engine.cancel()
        self.monitor.shutdown()
        self.commands.runner.shutdown()
        self.preference_runner.shutdown()
        if self.scenario_listener in self.scenario_engine.listeners:
            self.scenario_engine.listeners.remove(self.scenario_listener)
        for runner in self.readers:
            runner.shutdown()
