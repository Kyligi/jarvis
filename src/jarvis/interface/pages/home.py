from PySide6.QtCore import Slot
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPushButton

from jarvis.interface.components import Card, label, text_view
from jarvis.interface.dashboard import Metric
from jarvis.interface.pages.base import DataPage


class HomePage(DataPage):
    def __init__(self, context):
        super().__init__(context, "Votre centre de contrôle", "L'essentiel de votre PC, de vos projets et de votre session.")
        metrics = QHBoxLayout()
        self.cpu, self.ram, self.battery = Metric("CPU"), Metric("MÉMOIRE"), Metric("BATTERIE")
        for metric in (self.cpu, self.ram, self.battery):
            metrics.addWidget(metric)
        self.body.addLayout(metrics)
        self.system_state = label("En attente de la première mesure…", "status")
        self.body.addWidget(self.system_state)
        grid = QGridLayout()
        project = Card("REPRENDRE LE FIL")
        self.project = label("Aucun projet actif", "subheading")
        self.objective = label("Aucun objectif mémorisé.", "muted")
        project.body.addWidget(self.project)
        project.body.addWidget(self.objective)
        grid.addWidget(project, 0, 0)
        mode = Card("ENVIRONNEMENT")
        self.mode = label("Aucun mode enregistré", "subheading")
        mode.body.addWidget(self.mode)
        mode.body.addWidget(label("Le mode enregistré décrit la dernière demande, pas les applications encore ouvertes.", "muted"))
        grid.addWidget(mode, 0, 1)
        self.body.addLayout(grid)
        alerts = Card("DERNIÈRES ALERTES · DEPUIS LE DÉMARRAGE")
        self.alerts = text_view("Aucune alerte émise depuis le démarrage.")
        self.alerts.setMinimumHeight(55)
        self.alerts.setMaximumHeight(70)
        alerts.body.addWidget(self.alerts)
        self.body.addWidget(alerts)
        actions = QHBoxLayout()
        for title, command in [("Diagnostic", "diagnostic"), ("Sauvegarder la session", "sauvegarde ma session"), ("Mode Travail", "mode Travail")]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, text=command: context.commands.submit(text))
            actions.addWidget(button)
        self.body.insertLayout(5, actions)
        self.body.addStretch()
        context.monitor.updated.connect(self.snapshot)
        context.monitor.failed.connect(self.monitor_error)

    def load(self):
        return self.context.service.home()

    def render(self, value):
        project = value.get("project")
        self.project.setText(project["path"].name if project else "Aucun projet actif")
        self.objective.setText((project.get("objective") or "Aucun objectif mémorisé.") if project else "Ouvrez un projet pour reprendre votre travail.")
        mode = value.get("mode")
        self.mode.setText(mode.capitalize() if mode else "Aucun mode enregistré")

    def set_active(self, active):
        super().set_active(active)
        if active and self.context.monitor.latest:
            self.snapshot(self.context.monitor.latest)

    @Slot(object)
    def snapshot(self, value):
        if not self.active:
            return
        self.cpu.set_value(value.cpu)
        self.ram.set_value(value.ram)
        self.battery.set_value(value.battery.percent if value.battery else 0,
                               f"{value.battery.percent:.0f} %" if value.battery else "Non détectée")
        self.system_state.setText(value.warning or "● Monitoring actif · mesures locales")
        self.alerts.setPlainText("\n".join(reversed(value.alerts)))

    @Slot(str)
    def monitor_error(self, error):
        if self.active:
            self.system_state.setText(f"Mesures indisponibles ({error})")
