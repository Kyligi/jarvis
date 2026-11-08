from collections import deque
from jarvis.interface.context import MonitorHub
from jarvis.interface import theme

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QGridLayout
)


class HistoryGraph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cpu = deque(maxlen=60)
        self.ram = deque(maxlen=60)
        self.setMinimumHeight(95)

    def add_values(self, cpu, ram):
        self.cpu.append(cpu)
        self.ram.append(ram)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        width = self.width()
        height = self.height()

        painter.setPen(QPen(QColor(theme.BORDER), 1))
        for level in (25, 50, 75):
            y = height * (1 - level / 100)
            painter.drawLine(
                0, int(y), width, int(y)
            )

        for values, color in (
            (self.cpu, theme.CYAN),
            (self.ram, theme.VIOLET),
        ):
            if len(values) < 2:
                continue

            painter.setPen(QPen(QColor(color), 2))
            data = list(values)

            for i in range(1, len(data)):
                x1 = (i - 1) * width / 59
                x2 = i * width / 59
                y1 = height * (1 - data[i - 1] / 100)
                y2 = height * (1 - data[i] / 100)

                painter.drawLine(
                    int(x1), int(y1),
                    int(x2), int(y2)
                )


class Metric(QWidget):
    def __init__(self, name):
        super().__init__()

        self.setMinimumHeight(76)
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(8, 7, 8, 7)

        self.title = QLabel(name)
        self.value = QLabel("-- %")
        self.value.setObjectName("metricValue")
        self.bar = QProgressBar()

        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)

        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.bar)

    def set_value(self, value, text=None):
        value = max(0, min(100, float(value)))
        self.bar.setValue(round(value))
        self.value.setText(text or f"{value:.0f} %")


class MonitorDashboard(QWidget):
    def __init__(self, parent=None, monitor=None, compact=False):
        super().__init__(parent)

        self.compact = compact
        self.setObjectName("monitorDashboard")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("SYSTEM MONITOR  •  LIVE")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(8)

        self.cpu = Metric("CPU")
        self.ram = Metric("RAM")
        self.disk = Metric("SSD / DISQUE")
        self.battery = Metric("BATTERIE")

        for index, metric in enumerate((self.cpu, self.ram, self.disk, self.battery)):
            grid.addWidget(metric, 0 if compact else index // 2, index if compact else index % 2)

        layout.addLayout(grid)

        self.graph = HistoryGraph()
        layout.addWidget(self.graph)

        legend = QLabel(
            "● CPU (cyan)     ● RAM (violet)"
        )
        layout.addWidget(legend)

        self.temperature = QLabel(
            "Température : recherche des capteurs..."
        )
        self.temperature.setWordWrap(True)
        layout.addWidget(self.temperature)

        self.monitor = monitor or MonitorHub(self)
        self.owns_monitor = monitor is None
        self.active = True
        self.runner = self.monitor.runner
        self.timer = self.monitor.timer
        self.monitor.updated.connect(self.receive_snapshot)
        self.monitor.failed.connect(self.show_error)
        if self.owns_monitor:
            QApplication.instance().aboutToQuit.connect(self.monitor.shutdown)
        if self.monitor.latest is not None:
            self.apply_snapshot(self.monitor.latest)

    def set_active(self, active):
        self.active = active
        if active and self.monitor.latest is not None:
            self.apply_snapshot(self.monitor.latest)
            self.graph.cpu.clear()
            self.graph.ram.clear()
            for cpu, ram in self.monitor.history:
                self.graph.cpu.append(cpu)
                self.graph.ram.append(ram)
            self.graph.update()

    @Slot(object)
    def receive_snapshot(self, snapshot):
        if self.active:
            self.apply_snapshot(snapshot)

    @Slot()
    def refresh(self):
        self.monitor.refresh()

    @Slot(str)
    def show_error(self, error):
        self.temperature.setText(f"Monitoring indisponible : {error}")

    @Slot(object)
    def apply_snapshot(self, snapshot):
        cpu, ram, disk, battery = snapshot.cpu, snapshot.ram, snapshot.disk, snapshot.battery
        self.cpu.set_value(cpu)
        self.ram.set_value(ram)
        self.disk.set_value(disk)

        if battery is None:
            self.battery.set_value(0, "Non détectée")
        else:
            self.battery.set_value(
                battery.percent,
                f"{battery.percent:.0f} %"
                + (" ⚡" if battery.power_plugged else "")
            )

        self.graph.add_values(cpu, ram)


        # ==========================================
        # V0.6 — TEMPÉRATURES AMD
        # ==========================================

        sensors = snapshot.sensors

        if sensors:
            temperatures = []

            for name, value in sensors.items():
                temperatures.append(
                    f"{name} : {value:.1f} °C"
                )

            self.temperature.setText(
                "\n".join(temperatures[:3] if self.compact else temperatures)
                + (f"\n+ {len(temperatures) - 3} capteur(s) dans le HUD" if self.compact and len(temperatures) > 3 else "")
            )

        else:
            self.temperature.setText(
                "Capteurs de température indisponibles"
            )

        if snapshot.warning:
            self.temperature.setText(self.temperature.text() + "\n" + snapshot.warning)
