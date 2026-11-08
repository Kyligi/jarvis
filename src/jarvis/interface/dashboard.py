from collections import deque
from jarvis.interface.workers import Runner
from jarvis.monitoring.collector import Collector

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

        painter.setPen(QPen(QColor("#293d55"), 1))
        for level in (25, 50, 75):
            y = height * (1 - level / 100)
            painter.drawLine(
                0, int(y), width, int(y)
            )

        for values, color in (
            (self.cpu, "#22d3ee"),
            (self.ram, "#a78bfa"),
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

        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(8, 7, 8, 7)

        self.title = QLabel(name)
        self.value = QLabel("-- %")
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
    def __init__(self, parent=None):
        super().__init__(parent)

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

        grid.addWidget(self.cpu, 0, 0)
        grid.addWidget(self.ram, 0, 1)
        grid.addWidget(self.disk, 1, 0)
        grid.addWidget(self.battery, 1, 1)

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
        layout.addWidget(self.temperature)

        self.setStyleSheet("""
            QWidget#monitorDashboard {
                background: #101c2d;
                border-radius: 10px;
            }

            QLabel {
                color: #dce9f5;
                background: transparent;
            }

            QProgressBar {
                background: #2b3d53;
                border: none;
                border-radius: 3px;
            }

            QProgressBar::chunk {
                background: #22d3ee;
                border-radius: 3px;
            }
        """)

        self.collector = Collector()
        self.runner = Runner(self)
        self.runner.result.connect(self.apply_snapshot)
        self.runner.failed.connect(self.show_error)
        QApplication.instance().aboutToQuit.connect(self.runner.shutdown)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)

        self.refresh()

    @Slot()
    def refresh(self):
        self.runner.start(self.collector.collect)

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
                "\n".join(temperatures[:6])
            )

        else:
            self.temperature.setText(
                "Capteurs de température indisponibles"
            )

        if snapshot.warning:
            self.temperature.setText(self.temperature.text() + "\n" + snapshot.warning)
