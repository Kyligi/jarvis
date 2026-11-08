"""Chargements de page à la demande, jamais de service appelé au dessin."""
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from jarvis.interface.components import label


class DataPage(QWidget):
    def __init__(self, context, title, subtitle):
        super().__init__()
        self.context = context
        self.active = False
        self.pending = False
        self.cached = None
        self.runner = context.reader()
        self.runner.result.connect(self.receive)
        self.runner.failed.connect(self.failure)
        self.runner.idle.connect(self.finished)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(8, 8, 8, 8)
        self.body.setSpacing(16)
        self.body.addWidget(label(title, "heading"))
        self.body.addWidget(label(subtitle, "muted"))
        row = QHBoxLayout()
        self.state = label("Données à charger", "muted")
        row.addWidget(self.state, 1)
        self.refresh_button = QPushButton("Actualiser")
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        self.body.addLayout(row)

    def set_active(self, active):
        self.active = active
        if active:
            if self.cached is not None:
                self.render(self.cached)
            self.refresh()

    @Slot()
    def refresh(self):
        if not self.active:
            return
        if self.runner.start(self.load):
            self.state.setText("Chargement…")
            self.refresh_button.setEnabled(False)
            self.pending = False
        else:
            self.pending = True

    @Slot(object)
    def receive(self, value):
        self.cached = value
        self.state.setText("À jour")
        if self.active:
            self.render(value)

    @Slot(str)
    def failure(self, error):
        self.state.setText(f"Lecture impossible ({error}). Actualiser pour réessayer.")

    @Slot()
    def finished(self):
        self.refresh_button.setEnabled(True)
        if self.pending and self.active:
            self.refresh()

    def load(self):
        return {}

    def render(self, value):
        pass
