from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QPushButton

from jarvis.interface.components import Card, text_view
from jarvis.interface.dashboard import MonitorDashboard
from jarvis.interface.pages.base import DataPage


class SystemPage(DataPage):
    def __init__(self, context):
        super().__init__(context, "Système", "Mesures en direct · historique local · diagnostic à la demande")
        self.dashboard = MonitorDashboard(monitor=context.monitor)
        self.dashboard.set_active(False)
        self.body.addWidget(self.dashboard)
        row = QHBoxLayout()
        history, processes = Card("PERFORMANCES · DERNIÈRE HEURE"), Card("PROCESSUS · CPU")
        self.history, self.processes = text_view(), text_view()
        history.body.addWidget(self.history)
        processes.body.addWidget(self.processes)
        row.addWidget(history)
        row.addWidget(processes)
        self.body.addLayout(row)
        diagnostic = QPushButton("Lancer le diagnostic avancé")
        diagnostic.clicked.connect(lambda: context.commands.submit("diagnostic avancé"))
        self.body.insertWidget(3, diagnostic)
        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.refresh)

    def set_active(self, active):
        super().set_active(active)
        self.dashboard.set_active(active)
        self.timer.start() if active else self.timer.stop()

    def load(self):
        return self.context.service.system()

    def render(self, value):
        self.history.setPlainText(value["history"])
        self.processes.setPlainText(value["processes"])
