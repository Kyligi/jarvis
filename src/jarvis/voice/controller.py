"""Single-session controller. Callbacks carry snapshots; no UI or command execution."""
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import threading
import time
from jarvis.voice.backends import Cancelled, VoiceError, PipeWireCapture, WhisperCLI, PiperCLI
from jarvis.voice.config import VoiceConfig


class State(StrEnum):
    IDLE = 'idle'
    LISTENING = 'listening'
    TRANSCRIBING = 'transcribing'
    AWAITING_CONFIRMATION = 'awaiting_confirmation'
    EXECUTING = 'executing'
    SPEAKING = 'speaking'
    ERROR = 'error'


@dataclass(frozen=True)
class Snapshot:
    state: State
    text: str = ''
    message: str = ''
    level: float = 0
    seconds: float = 0
    engine: str = ''


class VoiceController:
    def __init__(self, config=None, capture=None, stt=None, tts=None, listener=lambda event: None,
                 clock=time.monotonic, allow_conversation=lambda: False):
        self.config = config or VoiceConfig()
        self.allow_conversation = allow_conversation
        self.capture = capture or PipeWireCapture()
        self.stt = stt or WhisperCLI()
        self.tts = tts or PiperCLI()
        self.listener = listener
        self.clock = clock
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.stop = threading.Event()
        self.thread = None
        self.closed = False
        self.engine = 'Accélération non vérifiée : aucune transcription effectuée.'
        self.snapshot = Snapshot(State.IDLE, engine=self.engine)
        self.pending = None
        self.last_response = ''
        self.suppress_speech = False

    def emit(self, state, **kwargs):
        self.snapshot = Snapshot(state, engine=self.engine, **kwargs)
        self.listener(self.snapshot)

    def available(self):
        return not self.closed and (self.thread is None or not self.thread.is_alive())

    def configure(self, config):
        with self.lock:
            if not self.available() or self.snapshot.state not in (State.IDLE, State.ERROR):
                raise VoiceError('Arrêter la session vocale avant de changer les paramètres.')
            self.config = config
            self.engine = 'Accélération non vérifiée : configuration modifiée.'
            self.emit(State.IDLE)

    def launch(self, function):
        self.cancelled = threading.Event()
        self.stop = threading.Event()
        def work():
            try:
                function()
            except Cancelled:
                with self.lock:
                    if self.snapshot.state == State.TRANSCRIBING:
                        self.engine = 'Transcription annulée : aucun résultat validé.'
                    self.emit(State.IDLE)
            except Exception as error:
                with self.lock:
                    message = str(error) if isinstance(error, VoiceError) else 'Erreur audio : vérifier les paramètres locaux.'
                    if self.snapshot.state == State.TRANSCRIBING:
                        if self.config.compute_backend == 'vulkan':
                            message += ' Repli : choisir CPU dans Voix, enregistrer et refaire une capture.'
                        self.engine = 'Transcription échouée : accélération non validée.'
                    self.emit(State.ERROR, message=message)
        self.thread = threading.Thread(target=work, name='jarvis-voice', daemon=False)
        self.thread.start()

    def toggle(self, test_only=False):
        with self.lock:
            if self.snapshot.state == State.LISTENING:
                self.stop.set()
                return True
            if not self.available() or self.snapshot.state not in (State.IDLE, State.ERROR):
                return False
            if not self.config.enabled:
                self.emit(State.ERROR, message='Activer la voix dans les paramètres avant de parler.')
                return False
            self.pending = None
            self.suppress_speech = False
            self.emit(State.LISTENING, message='Microphone ouvert — cliquer à nouveau pour transcrire.')
            self.launch(lambda: self.listen(test_only))
            return True

    def progress(self, level, seconds):
        with self.lock:
            if not self.cancelled.is_set():
                self.emit(State.LISTENING, level=level, seconds=seconds, message='Microphone ouvert')

    def listen(self, test_only):
        pcm = self.capture.capture(self.config, self.stop, self.cancelled, self.progress)
        with self.lock:
            if self.cancelled.is_set():
                raise Cancelled()
            if not pcm:
                self.emit(State.IDLE, message='Aucune parole détectée.')
                return
            self.engine = f'{self.config.compute_backend} demandé · chargement et transcription en cours'
            self.emit(State.TRANSCRIBING)
        result = self.stt.transcribe(pcm, self.config, self.cancelled)
        del pcm
        with self.lock:
            if self.cancelled.is_set():
                raise Cancelled()
            if not isinstance(result.text, str) or any(ord(c) < 32 for c in result.text):
                raise VoiceError('Transcription invalide : reformuler une seule commande.')
            self.engine = f'Dernière transcription : {result.backend.upper()} · {Path(self.config.stt_model).name}'
            if result.execution:
                self.engine += (f' · {result.execution.seconds:.2f} s chargement inclus'
                                f' · RSS pic échantillonné {result.execution.peak_rss_bytes / 1048576:.0f} Mio')
            text = result.text.strip()
            if not text:
                self.emit(State.IDLE, message='Transcription vide : aucune commande.')
                return
            if len(text) > 2048:
                raise VoiceError('Transcription trop longue : reformuler une seule commande.')
            from jarvis.registry import resolve
            resolved = resolve(text)
            if resolved is None:
                candidate = text.rstrip(' .!?')
                match = resolve(candidate)
                if match and not match.arguments:
                    text, resolved = candidate, match
            if test_only:
                self.emit(State.IDLE, text=text, message=result.warning + ' Test uniquement : aucune exécution.')
            elif resolved is None and not self.allow_conversation():
                self.emit(State.ERROR, text=text, message='Commande inconnue : aucune approximation exécutée.')
            elif resolved and resolved.command.id in {'scenarios.confirm', 'windows.confirm', 'ai.confirm'}:
                self.emit(State.ERROR, text=text, message='Confirmation sensible : saisir le code dans la console.')
            else:
                uncertain = result.confidence is None or result.confidence < .75
                self.pending = (text, self.clock() + 30)
                self.emit(State.AWAITING_CONFIRMATION, text=text,
                          message=result.warning + ' ' + ('Transcription incertaine. ' if uncertain else '') +
                          f'Vérifier puis valider : {resolved.command.name if resolved else "interprétation IA locale, sans autorisation d’action"} (30 s).')

    def take_pending(self):
        with self.lock:
            pending, self.pending = self.pending, None
            if not pending:
                return None
            if self.closed or self.clock() >= pending[1]:
                self.emit(State.IDLE, message='Validation expirée ou annulée.')
                return None
            self.emit(State.EXECUTING, text=pending[0])
            return pending[0]

    def expire(self):
        with self.lock:
            if self.pending and self.clock() >= self.pending[1]:
                self.pending = None
                self.emit(State.IDLE, message='Validation expirée.')

    def completed(self, result):
        with self.lock:
            self.last_response = str(result)
            self.emit(State.IDLE)
        if self.config.spoken_responses and not self.suppress_speech:
            self.speak(self.last_response)

    def speak(self, text=None):
        with self.lock:
            if not self.available() or self.snapshot.state not in (State.IDLE, State.ERROR):
                return False  # bounded queue: one item, no backlog
            text = text if text is not None else self.last_response
            if not text:
                return False
            # Exact short result, or neutral pointer; never invent a summary.
            spoken = text if len(text) <= 240 else 'Le résultat détaillé est affiché dans Jarvis.'
            self.emit(State.SPEAKING)
            self.launch(lambda: self.play(spoken))
            return True

    def play(self, text):
        self.tts.speak(text, self.config, self.cancelled)
        with self.lock:
            self.emit(State.IDLE)

    def cancel(self):
        with self.lock:
            self.pending = None
            self.suppress_speech = True
            self.cancelled.set()
            self.stop.set()
            if self.available():
                self.emit(State.IDLE)

    def shutdown(self):
        with self.lock:
            self.closed = True
            self.cancelled.set()
            self.stop.set()
            self.pending = None
        if self.thread:
            self.thread.join()
        self.emit(State.IDLE)
