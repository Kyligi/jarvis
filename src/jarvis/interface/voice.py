"""Qt bridge: queued events and the existing CommandBus are the sole UI boundary."""
from dataclasses import replace

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jarvis.interface.components import label
from jarvis.interface.workers import Runner
from jarvis.voice import commands, config
from jarvis.voice.backends import VoiceError, devices
from jarvis.voice.controller import State, VoiceController


class VoiceBridge(QObject):
    changed = Signal(object)
    action = Signal(str)

    def __init__(self, context):
        super().__init__(context)
        self.context = context
        self.bus = context.commands
        self.warning = ''
        try:
            value = config.load()
        except (OSError, ValueError, TypeError, KeyError):
            value = config.VoiceConfig()
            self.warning = 'Configuration vocale invalide : fichier conservé, valeurs par défaut.'
        self.controller = VoiceController(value, listener=self.changed.emit,
                                          allow_conversation=lambda: self.bus.conversation.config.enabled)
        self.action.connect(self.handle)
        self.listener = self.action.emit
        commands.listener = self.listener
        self.saver = Runner(self)
        self.saver.result.connect(self.saved)
        self.saver.failed.connect(lambda _: self.bus.result.emit('Préférences vocales non enregistrées.'))
        self.active_command = False
        self.command_result = ''
        self.bus.result.connect(self.result)
        self.bus.ai_event.connect(self.ai_changed)
        self.bus.completed.connect(self.finished)
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.controller.expire)
        self.timer.start()

    @Slot(object)
    def ai_changed(self, event):
        if event['kind'] == 'cleared':
            self.controller.cancel()
            self.controller.last_response = ''
            self.command_result = ''

    @Slot()
    def toggle(self):
        if self.bus.busy and self.controller.snapshot.state != State.LISTENING:
            return
        self.controller.toggle()

    @Slot()
    def confirm(self):
        if self.bus.busy:
            self.bus.result.emit('Commande déjà en cours ; validation vocale conservée.')
            return
        text = self.controller.take_pending()
        if text is None:
            return
        from jarvis.registry import resolve
        resolved = resolve(text)
        control = resolved and resolved.command.id.startswith('voice.')
        self.active_command = not control
        if control:
            self.controller.emit(State.IDLE)
        self.command_result = ''
        if not self.bus.submit(text):
            self.active_command = False
            self.controller.completed('Commande non soumise : bus occupé.')

    @Slot(object)
    def result(self, result):
        if self.active_command:
            self.command_result = str(result)

    @Slot()
    def finished(self):
        if self.active_command:
            self.active_command = False
            self.controller.completed(self.command_result)

    def save(self, value):
        if self.controller.snapshot.state not in (State.IDLE, State.ERROR) or not self.controller.available():
            self.bus.result.emit('Arrêter la voix avant de modifier les paramètres.')
            return False
        return self.saver.start(lambda: (config.save(value), value)[1])

    @Slot(object)
    def saved(self, value):
        try:
            self.controller.configure(value)
            self.bus.result.emit('Préférences vocales enregistrées.')
        except VoiceError:
            self.bus.result.emit('Préférences enregistrées ; arrêter la voix puis réappliquer.')

    @Slot(str)
    def handle(self, action):
        c = self.controller
        if action == 'listen':
            # This request's own registry worker may still be finishing.
            if not self.bus.busy or not self.active_command:
                c.toggle()
        elif action == 'stop':
            c.stop.set()
        elif action in ('quiet', 'disable'):
            c.cancel()
            if action == 'disable':
                c.config = replace(c.config, enabled=False, spoken_responses=False)
        elif action == 'enable':
            c.config = replace(c.config, enabled=True)
            self.bus.result.emit('Voix autorisée pour cette session. Microphone fermé.')
        elif action == 'repeat':
            c.speak()
        elif action == 'settings':
            self.bus.page_requested.emit('voice')
        elif action == 'status':
            self.bus.result.emit(f'Voix : {c.snapshot.state}. Wake word désactivé. {c.snapshot.message}')
        elif action.startswith('wake_'):
            self.bus.result.emit('Wake word désactivé : modèle et détection matérielle non validés. Utiliser le bouton microphone.')

    def shutdown(self):
        self.timer.stop()
        if commands.listener == self.listener:
            commands.listener = None
        self.controller.shutdown()
        self.saver.shutdown()


class VoiceControls(QWidget):
    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.microphone = QPushButton('Microphone')
        self.microphone.clicked.connect(bridge.toggle)
        self.cancel = QPushButton('Annuler / couper le son')
        self.cancel.clicked.connect(bridge.controller.cancel)
        self.approve = QPushButton('Valider la commande reconnue')
        self.approve.clicked.connect(bridge.confirm)
        for button in (self.microphone, self.cancel, self.approve):
            row.addWidget(button)
        layout.addLayout(row)
        self.status = label('idle · microphone fermé', 'muted')
        self.status.setWordWrap(True)
        self.engine = label('', 'muted')
        self.engine.setWordWrap(True)
        layout.addWidget(self.engine)
        self.transcript = label('', 'muted')
        self.transcript.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(self.transcript)
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setMaximumHeight(8)
        self.meter.setTextVisible(False)
        layout.addWidget(self.meter)
        bridge.changed.connect(self.update_state)
        self.update_state(bridge.controller.snapshot)

    @Slot(object)
    def update_state(self, value):
        self.status.setText(f'{value.state} · {value.seconds:.1f} s · {value.message}')
        self.engine.setText(value.engine)
        self.transcript.setText(value.text)
        self.transcript.setVisible(bool(value.text))
        self.meter.setVisible(value.state == State.LISTENING)
        self.meter.setValue(int(value.level * 100))
        self.approve.setVisible(value.state == State.AWAITING_CONFIRMATION)
        self.microphone.setText('Terminer et transcrire' if value.state == State.LISTENING else 'Microphone')
        self.microphone.setEnabled(value.state in (State.IDLE, State.ERROR, State.LISTENING))


class VoicePage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.bridge = context.voice
        self.active = False
        self.body = QVBoxLayout(self)
        self.body.addWidget(label('Voix locale', 'heading'))
        self.body.addWidget(label('PipeWire → Whisper → validation → commandes / IA locale → Piper → PipeWire', 'muted'))
        self.notice = label(self.bridge.warning or 'Aucun téléchargement automatique. Audio temporaire supprimé. Aucun journal de transcription.', 'muted')
        self.notice.setWordWrap(True)
        self.body.addWidget(self.notice)
        form = QFormLayout()
        value = self.bridge.controller.config
        self.enabled = QCheckBox('Autoriser le push-to-talk (aucune écoute au démarrage)')
        self.enabled.setChecked(value.enabled)
        form.addRow(self.enabled)
        self.spoken = QCheckBox('Lire les résultats à voix haute')
        self.spoken.setChecked(value.spoken_responses)
        form.addRow(self.spoken)
        self.backend = QComboBox()
        self.backend.addItem('CPU — moteur précédent', 'cpu')
        self.backend.addItem('Vulkan — vérification effective obligatoire', 'vulkan')
        self.backend.setCurrentIndex(self.backend.findData(value.compute_backend))
        form.addRow('Calcul Whisper', self.backend)
        form.addRow(label('En cas d’échec Vulkan : choisir CPU, enregistrer et refaire une capture.', 'muted'))
        self.fields = {}
        for key, title in [('stt_executable', 'Exécutable whisper-cli CPU'), ('gpu_executable', 'Exécutable whisper-cli Vulkan distinct'), ('stt_model', 'Modèle multilingue .bin'),
                           ('vad_model', 'Modèle Silero local (facultatif)'),
                           ('whisper_prompt', 'Contexte Whisper (vide par défaut)'),
                           ('tts_executable', 'Exécutable Piper OHF'), ('tts_voice', 'Voix française .onnx')]:
            widget = QLineEdit(getattr(value, key))
            self.fields[key] = widget
            form.addRow(title, widget)
        choose_model = QPushButton('Choisir un modèle multilingue local…')
        choose_model.clicked.connect(self.choose_model)
        form.addRow(choose_model)
        self.microphone = QComboBox()
        self.output = QComboBox()
        for widget, key in [(self.microphone, 'microphone_device'), (self.output, 'output_device')]:
            widget.addItem('Périphérique par défaut', '')
            if getattr(value, key):
                widget.addItem(getattr(value, key), getattr(value, key))
                widget.setCurrentIndex(1)
        form.addRow('Microphone', self.microphone)
        form.addRow('Sortie', self.output)
        self.numbers = {}
        for key, title, low, high in [('tts_speed', 'Vitesse', .5, 2), ('tts_volume', 'Volume', 0, 1),
                                     ('max_recording_seconds', 'Durée maximale (s)', 5, 30),
                                     ('pre_recording_ms', 'Pré-enregistrement (ms)', 0, 1000),
                                     ('silence_seconds', 'Arrêt après silence (s)', .3, 10),
                                     ('silence_threshold', 'Seuil RMS de parole', .001, .5),
                                     ('timeout_seconds', 'Délai maximal moteur (s)', 1, 300)]:
            spin = QDoubleSpinBox()
            spin.setDecimals(3)
            spin.setRange(low, high)
            spin.setValue(getattr(value, key))
            self.numbers[key] = spin
            form.addRow(title, spin)
        self.vad = QCheckBox('Activer Silero VAD (repli sans VAD si indisponible)')
        self.vad.setChecked(value.vad_enabled)
        form.addRow(self.vad)
        self.noise = QCheckBox('Adapter le seuil au bruit de fond')
        self.noise.setChecked(value.adaptive_noise)
        form.addRow(self.noise)
        wake = QCheckBox('Wake word — indisponible, modèle non validé')
        wake.setEnabled(False)
        form.addRow(wake)
        self.body.addLayout(form)
        row = QHBoxLayout()
        for title, callback in [('Périphériques', self.refresh), ('Enregistrer', self.save),
                                ('Tester micro / transcription', self.test_capture),
                                ('Tester la voix', lambda: self.bridge.controller.speak('Bonjour, ceci est un test vocal local.'))]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        self.body.addLayout(row)
        self.body.addStretch()
        self.reader = context.reader()
        self.runner = self.reader
        self.reader.result.connect(self.receive_devices)
        self.reader.failed.connect(lambda _: self.notice.setText('PipeWire indisponible : vérifier la session audio.'))

    def test_capture(self):
        if not self.context.commands.busy:
            self.bridge.controller.toggle(test_only=True)

    def choose_model(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Modèle Whisper multilingue',
                                             self.fields['stt_model'].text(), 'Whisper (*.bin)')
        if path:
            self.fields['stt_model'].setText(path)

    def set_active(self, active):
        self.active = active

    def refresh(self):
        if self.active:
            self.reader.start(devices)

    @Slot(object)
    def receive_devices(self, values):
        for widget, kind in ((self.microphone, 'Audio/Source'), (self.output, 'Audio/Sink')):
            selected = widget.currentData()
            widget.clear()
            widget.addItem('Périphérique par défaut', '')
            for name, title, media in values:
                if kind == media:
                    widget.addItem(title, name)
            index = widget.findData(selected)
            if index < 0 and selected:
                widget.addItem('Déconnecté : ' + selected, selected)
                index = widget.count() - 1
            widget.setCurrentIndex(max(0, index))

    def save(self):
        try:
            value = replace(self.bridge.controller.config, enabled=self.enabled.isChecked(),
                            spoken_responses=self.spoken.isChecked(), compute_backend=self.backend.currentData(),
                            vad_enabled=self.vad.isChecked(), adaptive_noise=self.noise.isChecked(),
                            microphone_device=self.microphone.currentData(), output_device=self.output.currentData(),
                            **{k: w.text() for k, w in self.fields.items()},
                            **{k: w.value() for k, w in self.numbers.items()})
            self.bridge.save(value)
        except ValueError as error:
            self.notice.setText(str(error))
