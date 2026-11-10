"""Assistant Nebula : widgets Qt, moteur et réseau exclusivement dans les workers."""
from dataclasses import replace
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                              QLineEdit, QPushButton, QComboBox, QCheckBox,
                              QFormLayout, QSpinBox, QDoubleSpinBox)
from jarvis.interface.components import label
from jarvis.ai import config


class AssistantPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.bus = context.commands
        self.session = self.bus.conversation
        self.active = False
        self.runner = context.reader()
        self.runner.result.connect(self.detected)
        self.runner.failed.connect(lambda _: self.state.setText('Ollama indisponible ou incompatible ; aucun téléchargement effectué.'))
        body = QVBoxLayout(self)
        body.addWidget(label('Assistant', 'heading'))
        body.addWidget(label('IA LOCALE · Aucun cloud · Contexte de session uniquement', 'eyebrow'))
        self.state = label(self.bus.ai_warning or 'Ollama non vérifié. Actualiser pour détecter le serveur et les modèles.', 'muted')
        self.state.setWordWrap(True)
        body.addWidget(self.state)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.document().setMaximumBlockCount(500)
        self.output.setMinimumHeight(220)
        self.output.setAccessibleName('Conversation avec Jarvis et sources locales')
        body.addWidget(self.output, 1)
        self.progress = label('', 'muted')
        self.progress.setWordWrap(True)
        self.progress.setTextFormat(Qt.TextFormat.PlainText)
        body.addWidget(self.progress)
        self.input = QLineEdit()
        self.input.setMaxLength(2048)
        self.input.setPlaceholderText('Écrivez à Jarvis, par exemple : Affiche mes projets.')
        self.input.returnPressed.connect(self.send)
        body.addWidget(self.input)
        row = QHBoxLayout()
        self.send_button = QPushButton('Envoyer')
        self.send_button.clicked.connect(self.send)
        row.addWidget(self.send_button)
        self.stop = QPushButton('Arrêter')
        self.stop.clicked.connect(lambda: self.bus.submit('arrête génération'))
        row.addWidget(self.stop)
        self.clear = QPushButton('Effacer le contexte')
        self.clear.clicked.connect(lambda: self.bus.submit('efface conversation'))
        row.addWidget(self.clear)
        body.addLayout(row)
        body.addWidget(label('Pour autoriser une action : lire la cible et les conséquences, puis saisir le code affiché.\nLes confirmations de scénarios restent séparées.', 'muted'))
        form = QFormLayout()
        self.enabled = QCheckBox('Autoriser l’interprétation IA locale')
        self.enabled.setChecked(self.session.config.enabled)
        form.addRow(self.enabled)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItem(self.session.config.model)
        form.addRow('Modèle déjà installé', self.model)
        self.endpoint = QLineEdit(self.session.config.endpoint)
        form.addRow('Endpoint loopback', self.endpoint)
        self.retain = QCheckBox('Conserver quelques échanges pendant cette session')
        self.retain.setChecked(self.session.config.retain_context)
        form.addRow(self.retain)
        self.streaming = QCheckBox('Afficher la progression de génération')
        self.streaming.setChecked(self.session.config.streaming_enabled)
        form.addRow(self.streaming)
        self.numbers = {}
        for key, title, low, high in [('context_limit', 'Contexte maximal (tokens)', 4096, 32768),
                                     ('max_output_tokens', 'Sortie maximale (tokens)', 128, 2048),
                                     ('request_timeout', 'Timeout inférence (s)', 1, 300),
                                     ('tool_call_limit', 'Appels par message', 1, 4),
                                     ('keep_alive', 'Résidence modèle (s ; 0 = libérer)', 0, 300)]:
            widget = QSpinBox()
            widget.setRange(low, high)
            widget.setValue(int(getattr(self.session.config, key)))
            self.numbers[key] = widget
            form.addRow(title, widget)
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0, 1)
        self.temperature.setSingleStep(.1)
        self.temperature.setValue(self.session.config.temperature)
        form.addRow('Température', self.temperature)
        body.addLayout(form)
        row = QHBoxLayout()
        self.apply = QPushButton('Appliquer à la session')
        self.apply.clicked.connect(lambda: self.apply_settings(False))
        row.addWidget(self.apply)
        self.save = QPushButton('Enregistrer les préférences IA')
        self.save.clicked.connect(lambda: self.apply_settings(True))
        row.addWidget(self.save)
        self.detect = QPushButton('Actualiser Ollama / CPU-GPU')
        self.detect.clicked.connect(self.refresh)
        row.addWidget(self.detect)
        body.addLayout(row)
        self.bus.ai_event.connect(self.receive_event)
        self.bus.result.connect(self.result)
        self.bus.busy_changed.connect(self.busy)
        self.busy(self.bus.busy)

    def set_active(self, active):
        self.active = active
        # No automatic inference or model loading when navigating.

    def refresh(self):
        if not self.active:
            return
        import threading
        value = self.session.config
        def inspect():
            status = self.session.backend.inspect(value, threading.Event())
            return status, self.session.status()
        if self.runner.start(inspect):
            self.state.setText('Détection locale du serveur et du modèle…')

    @Slot(object)
    def detected(self, result):
        status, text = result
        current = self.model.currentText()
        self.model.clear()
        self.model.addItems(status['models'])
        if self.model.findText(current) < 0:
            self.model.addItem(current)
        self.model.setCurrentText(current)
        self.state.setText(text)

    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        from jarvis.registry import resolve
        if self.bus.submit(text):
            if resolve(text) is not None:
                self.output.appendPlainText('Vous : ' + text)
            self.input.clear()

    @Slot(object)
    def receive_event(self, event):
        if event.get('cancelled') and event['cancelled'].is_set() and event['kind'] not in ('cleared', 'stopped', 'idle'):
            return
        kind = event['kind']
        if kind == 'user':
            self.output.appendPlainText('Vous : ' + event['text'])
        elif kind == 'waiting':
            self.progress.setText('Attente du modèle local…')
        elif kind == 'progress':
            self.progress.setText('Brouillon IA non vérifié · ' + str(event['characters']) + ' caractères\n' + event['text'][:4000])
        elif kind == 'tool':
            self.output.appendPlainText('Outil autorisé : ' + event['text'])
        elif kind == 'cleared':
            self.output.clear()
            self.progress.clear()
        elif kind in ('idle', 'stopped'):
            self.progress.clear()

    @Slot(object)
    def result(self, value):
        self.output.appendPlainText('Jarvis : ' + str(value))
        self.enabled.setChecked(self.session.config.enabled)

    @Slot(bool)
    def busy(self, busy):
        for widget in (self.send_button, self.apply, self.save):
            widget.setEnabled(not busy)
        # Input stays editable so the user can type a stop command while generating.

    def apply_settings(self, persist):
        try:
            value = replace(self.session.config, enabled=self.enabled.isChecked(),
                            model=self.model.currentText(), endpoint=self.endpoint.text(),
                            retain_context=self.retain.isChecked(), streaming_enabled=self.streaming.isChecked(),
                            temperature=self.temperature.value(),
                            **{key: widget.value() for key, widget in self.numbers.items()})
        except ValueError as error:
            self.state.setText(str(error))
            return
        def apply():
            self.session.configure(value)
            if persist:
                config.save(value)
            return 'Préférences IA enregistrées.' if persist else 'Préférences IA appliquées à cette session.'
        if not self.bus.submit_operation(apply):
            self.state.setText('Commande en cours ; attendre avant de modifier les paramètres.')
