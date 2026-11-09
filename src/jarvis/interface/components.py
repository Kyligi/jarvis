"""Composants Nebula sans accès au système ni à la persistance."""
from datetime import datetime
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (QFrame, QLabel, QVBoxLayout, QHBoxLayout,
                              QPlainTextEdit, QLineEdit, QPushButton, QWidget)


def label(text: str, role: str = "", parent=None) -> QLabel:
    widget = QLabel(text, parent)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if role:
        widget.setObjectName(role)
    return widget


def text_view(placeholder="Aucune donnée disponible.") -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setReadOnly(True)
    widget.setPlaceholderText(placeholder)
    widget.setMinimumHeight(90)
    return widget


class Card(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(12)
        self.body.addWidget(label(title, "eyebrow"))


class CommandConsole(QWidget):
    """Même bus et même moteur V1.0 dans les deux fenêtres ; historique borné."""
    def __init__(self, bus, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.has_response = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.output = text_view()
        self.output.document().setMaximumBlockCount(500)
        self.output.setPlainText("Bonjour. Tape 'aide' pour connaître mes commandes.")
        self.output.setAccessibleName("Historique des réponses Jarvis")
        layout.addWidget(self.output)
        row = QHBoxLayout()
        self.command = QLineEdit()
        self.command.setPlaceholderText("Une commande…  ·  aide, mode Travail, mes projets")
        self.command.setAccessibleName("Commande Jarvis")
        self.command.returnPressed.connect(self.submit)
        row.addWidget(self.command, 1)
        self.button = QPushButton("Exécuter ↵")
        self.button.setObjectName("primary")
        self.button.clicked.connect(self.submit)
        row.addWidget(self.button)
        self.cancel_scenario = QPushButton("Annuler scénario")
        self.cancel_scenario.clicked.connect(lambda: bus.submit("annule scénario"))
        row.addWidget(self.cancel_scenario)
        layout.addLayout(row)
        self.status = label("Prêt  ·  commandes locales autorisées", "muted")
        layout.addWidget(self.status)
        bus.result.connect(self.show_result)
        bus.busy_changed.connect(self.set_busy)
        bus.scenario_progress.connect(self.scenario_changed)
        self.set_busy(bus.busy)

    @Slot()
    def submit(self):
        if self.bus.submit(self.command.text()):
            self.command.clear()

    @Slot(object)
    def show_result(self, result):
        if isinstance(result, dict) and 'scenario_saved' in result:
            text = 'Scénario enregistré.'
        elif isinstance(result, dict) and 'scenario_error' in result:
            text = result['scenario_error']
        elif isinstance(result, dict) and ('mode_saved' in result or 'mode_error' in result):
            text = result['message']
        else:
            text = str(result)
        if not self.has_response:
            self.output.setPlainText(text)
            self.has_response = True
        else:
            self.output.appendPlainText(f"\n── {datetime.now():%H:%M:%S} ──\n{text}")
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    @Slot(object)
    def scenario_changed(self, value):
        if value['state'] == 'running':
            self.command.setEnabled(True)
            self.status.setText("Scénario en cours · annule scénario / état scénario restent disponibles")

    @Slot(bool)
    def set_busy(self, busy):
        self.button.setEnabled(not busy)
        self.command.setEnabled(not busy)
        self.status.setText("Commande en cours…" if busy else "Prêt  ·  commandes locales autorisées")
        if not busy and self.isVisible():
            self.command.setFocus()
