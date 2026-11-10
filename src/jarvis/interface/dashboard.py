
"""Affichage numérique du monitoring Jarvis.

Interface légère sans courbes ni barres de progression.
Réutilise MonitorHub et les données du collecteur existant.
"""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from jarvis.interface.context import MonitorHub


def format_number(value, decimals=2):
    """Nombre avec virgule française."""
    if value is None:
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",")


def format_gib(value):
    """Convertit les octets en Gio."""
    if value is None:
        return "—"
    return format_number(value / (1024 ** 3))


class Metric(QWidget):
    """Carte affichant une mesure et ses détails numériques."""

    def __init__(self, name):
        super().__init__()

        self.setObjectName("metricCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(4)

        self.title = QLabel(name)
        self.title.setObjectName("metricTitle")

        self.value = QLabel("—")
        self.value.setObjectName("metricValue")

        self.detail = QLabel("")
        self.detail.setObjectName("metricDetail")
        self.detail.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

        self.setStyleSheet("""
            QWidget#metricCard {
                background-color: #15243A;
                border: 1px solid #263C54;
                border-radius: 10px;
            }

            QLabel {
                border: none;
                background: transparent;
            }

            QLabel#metricTitle {
                color: #92AEC6;
                font-size: 11px;
                font-weight: 600;
            }

            QLabel#metricValue {
                color: #EAF8FF;
                font-size: 21px;
                font-weight: 700;
            }

            QLabel#metricDetail {
                color: #9DB5C9;
                font-size: 11px;
            }
        """)

    def set_value(self, value, detail=""):
        """Met à jour la valeur affichée."""
        self.value.setText(str(value))
        self.detail.setText(str(detail))


class MonitorDashboard(QWidget):
    """Tableau de bord numérique partagé par Mini et HUD."""

    def __init__(self, parent=None, monitor=None, compact=False):
        super().__init__(parent)

        self.compact = compact
        self.active = True

        self.setObjectName("monitorDashboard")

        layout = QVBoxLayout(self)
        layout.setSpacing(7)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("SYSTEM MONITOR  •  LIVE")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(7)

        self.cpu = Metric("CPU")
        self.ram = Metric("RAM")
        self.disk = Metric("SSD / DISQUE")
        self.battery = Metric("BATTERIE")

        metrics = (
            self.cpu,
            self.ram,
            self.disk,
            self.battery,
        )

        for index, metric in enumerate(metrics):
            # Mini : une rangée de 4 indicateurs.
            # HUD : disposition 2 x 2.
            row = 0 if compact else index // 2
            column = index if compact else index % 2
            grid.addWidget(metric, row, column)

        layout.addLayout(grid)

        self.temperature = QLabel(
            "Températures : recherche des capteurs…"
        )
        self.temperature.setWordWrap(True)

        layout.addWidget(self.temperature)

        # Conserver le collecteur partagé existant.
        self.monitor = monitor or MonitorHub(self)
        self.owns_monitor = monitor is None

        self.runner = self.monitor.runner
        self.timer = self.monitor.timer

        self.monitor.updated.connect(
            self.receive_snapshot
        )
        self.monitor.failed.connect(
            self.show_error
        )

        if self.owns_monitor:
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(
                    self.monitor.shutdown
                )

        if self.monitor.latest is not None:
            self.apply_snapshot(self.monitor.latest)

    def set_active(self, active):
        """Évite de rafraîchir une page inactive."""
        self.active = active

        if active and self.monitor.latest is not None:
            self.apply_snapshot(self.monitor.latest)

    @Slot()
    def refresh(self):
        """Demande un rafraîchissement au service existant."""
        self.monitor.refresh()

    @Slot(object)
    def receive_snapshot(self, snapshot):
        if self.active:
            self.apply_snapshot(snapshot)

    @Slot(str)
    def show_error(self, error):
        self.temperature.setText(
            f"Monitoring indisponible : {error}"
        )

    @Slot(object)
    def apply_snapshot(self, snapshot):
        """Affiche les mesures exactes du Snapshot."""

        # ==========================================
        # CPU
        # ==========================================

        cpu_details = []

        if snapshot.cpu_cores is not None:
            cpu_details.append(
                f"{snapshot.cpu_cores} cœurs"
            )

        if snapshot.cpu_threads is not None:
            cpu_details.append(
                f"{snapshot.cpu_threads} threads"
            )

        if snapshot.cpu_freq_mhz is not None:
            cpu_details.append(
                f"{format_number(snapshot.cpu_freq_mhz / 1000)} GHz"
            )

        self.cpu.set_value(
            f"{format_number(snapshot.cpu, 1)} %",
            " · ".join(cpu_details),
        )

        # ==========================================
        # RAM
        # ==========================================

        ram_used = format_gib(snapshot.ram_used)
        ram_total = format_gib(snapshot.ram_total)

        if snapshot.ram_used is not None:
            ram_value = f"{ram_used} Gio"
        else:
            ram_value = f"{format_number(snapshot.ram, 1)} %"

        self.ram.set_value(
            ram_value,
            (
                f"{ram_used} / {ram_total} Gio"
                f" · {format_number(snapshot.ram, 1)} %"
            ),
        )

        # ==========================================
        # DISQUE
        # ==========================================

        disk_used = format_gib(snapshot.disk_used)
        disk_total = format_gib(snapshot.disk_total)
        disk_free = format_gib(snapshot.disk_free)

        if snapshot.disk_used is not None:
            disk_value = f"{disk_used} Gio"
        else:
            disk_value = f"{format_number(snapshot.disk, 1)} %"

        disk_detail = (
            f"{disk_used} / {disk_total} Gio"
            f" · {format_number(snapshot.disk, 1)} %"
        )

        if snapshot.disk_free is not None:
            disk_detail += f" · {disk_free} Gio libres"

        self.disk.set_value(
            disk_value,
            disk_detail,
        )

        # ==========================================
        # BATTERIE
        # ==========================================

        battery = snapshot.battery

        if battery is None:
            self.battery.set_value(
                "—",
                "Batterie non détectée",
            )
        else:
            status = (
                "Branchée"
                if battery.power_plugged
                else "Sur batterie"
            )

            self.battery.set_value(
                f"{format_number(battery.percent, 1)} %",
                status,
            )

        # ==========================================
        # TEMPÉRATURES
        # ==========================================

        sensors = snapshot.sensors

        if sensors:
            temperatures = []

            for name, value in sensors.items():
                temperatures.append(
                    f"{name} : {format_number(value, 1)} °C"
                )

            if self.compact:
                shown = temperatures[:3]
            else:
                shown = temperatures

            result = " · ".join(shown)

            if self.compact and len(temperatures) > 3:
                remaining = len(temperatures) - 3
                result += f" · +{remaining} capteur(s)"

            self.temperature.setText(result)

        else:
            self.temperature.setText(
                "Capteurs de température indisponibles"
            )

        # ==========================================
        # AVERTISSEMENTS
        # ==========================================

        if snapshot.warning:
            self.temperature.setText(
                self.temperature.text()
                + "\n"
                + snapshot.warning
            )
