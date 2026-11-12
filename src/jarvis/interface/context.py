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
from jarvis.context.service import ContextService
from uuid import uuid4

from jarvis.context.command_outcomes import (
    CommandOutcome,
    classify_outcome,
)

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
    execution_finished = Signal(object)
    execution_reserved = Signal(str)
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
        self.stopped = False
        self.last_requested_mode = None
        self.current_execution_id = None
        self._active_command_id = None
        self._last_execution_value = None
        self._last_execution_failed = False
        self._last_execution_error = ""

    def submit(self, command: str) -> bool:
        if self.stopped:
            return False
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
        # Réserver l'identifiant AVANT le lancement
        # du worker pour éviter une fin trop rapide.
        execution_id = uuid4().hex

        self.current_execution_id = execution_id
        self._active_command_id = identifier
        self._last_execution_value = None
        self._last_execution_failed = False
        self._last_execution_error = ""

        # Réserver le bus avant les notifications Qt.
        # Une commande réentrante doit être refusée.
        self.busy = True
        self.busy_changed.emit(True)

        # Le WorkflowRunner connaît maintenant
        # l'identifiant avant l'exécution.
        self.execution_reserved.emit(execution_id)

        try:
            accepted = self.runner.start(run)
        except Exception:
            self.current_execution_id = None
            self._active_command_id = None
            self._last_execution_value = None
            self._last_execution_failed = False
            self._last_execution_error = ""
            self.busy = False
            self.busy_changed.emit(False)
            raise

        if not accepted:
            self.current_execution_id = None
            self._active_command_id = None
            self._last_execution_value = None
            self._last_execution_failed = False
            self._last_execution_error = ""
            self.busy = False
            self.busy_changed.emit(False)
            return False

        if identifier in {
            "modes.travail",
            "modes.gaming",
            "modes.etudes",
        }:
            self.last_requested_mode = (
                identifier.split(".")[1]
            )

        self.started.emit(identifier)

        if identifier in {"ai.open", "ai.talk"}:
            self.page_requested.emit("assistant")

        elif identifier == "scenarios.open":
            self.page_requested.emit("scenarios")

        elif (
            identifier == "modes.configure"
            and resolved.arguments[0] in {
                "travail",
                "gaming",
                "etudes",
            }
        ):
            self.page_requested.emit(
                "modes:" + resolved.arguments[0]
            )

        return True

    def submit_operation(self, operation) -> bool:
        if self.stopped:
            return False
        """Action HUD typée utilisant le même verrou de commandes que Mini."""
        if self.busy or not self.runner.start(operation):
            return False
        self.busy = True
        self.current_execution_id = uuid4().hex
        self._active_command_id = "windows.action"
        self._last_execution_value = None
        self._last_execution_failed = False
        self._last_execution_error = ""
        self.busy_changed.emit(True)
        self.started.emit("windows.action")
        return True

    @Slot(object)
    def receive_result(self, result):
        if isinstance(result, ConversationReply):
            result = (
                "Génération annulée ; contenu de la session "
                "effacé ou interrompu."
                if result.cancelled.is_set()
                else result.text
            )

        self._last_execution_value = result
        self.result.emit(result)

    @Slot(str)
    def failure(self, error):
        self._last_execution_failed = True
        self._last_execution_error = str(error)

        message = (
            f"Erreur Jarvis ({error}). "
            "Réessaie ou consulte les logs."
        )

        self._last_execution_value = message
        self.result.emit(message)

    @Slot()
    def finished(self):
        execution_id = self.current_execution_id
        command_id = self._active_command_id

        confirmation_required = False

        # Une activation de mode peut demander
        # une confirmation supplémentaire au
        # moteur des scénarios.
        if (
            execution_id is not None
            and command_id in {
                "modes.travail",
                "modes.gaming",
                "modes.etudes",
            }
            and not self._last_execution_failed
        ):
            try:
                from jarvis.scenarios.engine import engine

                confirmation_required = (
                    engine.confirmation_pending()
                )
            except Exception:
                # On ne peut pas prouver la réussite.
                # Le statut restera "unknown".
                confirmation_required = False

        if execution_id is not None:
            status = classify_outcome(
                self._last_execution_value,
                failed=self._last_execution_failed,
                confirmation_required=confirmation_required,
            )

            outcome = CommandOutcome(
                execution_id=execution_id,
                command_id=command_id or "unknown",
                status=status,
                response=self._last_execution_value,
                error=self._last_execution_error,
            )
        else:
            outcome = None

        # Libérer l'exécution avant de notifier
        # les composants qui pourraient soumettre
        # une nouvelle commande.
        self.current_execution_id = None
        self._active_command_id = None
        self._last_execution_value = None
        self._last_execution_failed = False
        self._last_execution_error = ""

        self.busy = False
        self.busy_changed.emit(False)

        if outcome is not None:
            self.execution_finished.emit(outcome)

        # Compatibilité Mini / HUD / Voice.
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
        self.context_service = ContextService(
            monitor_reader=lambda: self.monitor.latest
        )
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
        """Arrête la session et ses workers dans un ordre sûr."""

        if self.stopped:
            return

        self.stopped = True

        # Refuser immédiatement toute nouvelle commande.
        self.commands.stopped = True

        # Le runner de workflow appartient à AppContext,
        # même si le HUD a été fermé ou détruit.
        workflow = getattr(
            self,
            "_workflow_runner",
            None,
        )

        if workflow is not None:
            workflow.shutdown()

        # Arrêter les autres activités de la session.
        self.commands.conversation.stop()
        self.voice.shutdown()
        self.scenario_engine.cancel()

        # Attendre les tâches existantes.
        self.monitor.shutdown()
        self.commands.runner.shutdown()
        self.preference_runner.shutdown()

        if self.scenario_listener in self.scenario_engine.listeners:
            self.scenario_engine.listeners.remove(
                self.scenario_listener
            )

        for runner in self.readers:
            runner.shutdown()
