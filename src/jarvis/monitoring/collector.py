"""Collecte périodique indépendante de Qt, exécutée par un worker."""
from dataclasses import dataclass
import logging
from pathlib import Path
import sqlite3
import time
import psutil
from jarvis.monitoring.intelligence import AlertEngine, read_sensors, save_metrics


@dataclass(frozen=True)
class Snapshot:
    cpu: float
    ram: float
    disk: float
    battery: object
    sensors: dict[str, float]
    warning: str = ""
    alerts: tuple[str, ...] = ()


class Collector:
    def __init__(self):
        self.alerts = AlertEngine()
        self.last_saved = float("-inf")

    def collect(self) -> Snapshot:
        # Chaque tâche utilise un thread neuf : un intervalle explicite évite
        # une première mesure CPU à zéro pour chaque thread psutil.
        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(str(Path.home())).percent
        battery = psutil.sensors_battery()
        sensors = read_sensors()
        self.alerts.check(cpu, ram, disk)
        warning = ""
        now = time.monotonic()
        if now - self.last_saved >= 10:
            try:
                save_metrics(cpu, ram, disk)
                self.last_saved = now
            except (sqlite3.Error, OSError) as error:
                logging.getLogger(__name__).warning("metrics_storage_unavailable", extra={
                    "error_type": type(error).__name__,
                })
                warning = "Historique indisponible"
        return Snapshot(cpu, ram, disk, battery, sensors, warning, tuple(self.alerts.recent))
