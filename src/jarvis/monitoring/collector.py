"""Collecte périodique indépendante de Qt, exécutée par un worker."""

from dataclasses import dataclass
import logging
from pathlib import Path
import sqlite3
import time

import psutil

from jarvis.monitoring.intelligence import (
    AlertEngine,
    read_sensors,
    save_metrics,
)


@dataclass(frozen=True)
class Snapshot:
    cpu: float
    ram: float
    disk: float
    battery: object
    sensors: dict[str, float]
    warning: str = ""
    alerts: tuple[str, ...] = ()

    # Quantités de mémoire en octets
    ram_used: int | None = None
    ram_total: int | None = None

    # Quantités de stockage en octets
    disk_used: int | None = None
    disk_total: int | None = None
    disk_free: int | None = None

    # Informations sur le processeur
    cpu_cores: int | None = None
    cpu_threads: int | None = None
    cpu_freq_mhz: float | None = None


class Collector:
    def __init__(self):
        self.alerts = AlertEngine()
        self.last_saved = float("-inf")

    def collect(self) -> Snapshot:
        # Un intervalle explicite évite une première
        # mesure CPU à zéro pour chaque thread psutil.
        cpu = psutil.cpu_percent(interval=0.2)

        # Mémoire vive
        memory = psutil.virtual_memory()
        ram = memory.percent

        # Stockage : même partition qu'auparavant
        storage = psutil.disk_usage(str(Path.home()))
        disk = storage.percent

        # Batterie et capteurs
        battery = psutil.sensors_battery()
        sensors = read_sensors()

        # Informations CPU
        cpu_cores = psutil.cpu_count(logical=False)
        cpu_threads = psutil.cpu_count(logical=True)

        try:
            frequency = psutil.cpu_freq()
            freq_mhz = (
                frequency.current
                if frequency is not None
                else None
            )
        except (OSError, RuntimeError, AttributeError):
            freq_mhz = None

        # Alertes historiques
        self.alerts.check(cpu, ram, disk)

        warning = ""
        now = time.monotonic()

        # Sauvegarde périodique des métriques SQLite
        if now - self.last_saved >= 10:
            try:
                save_metrics(cpu, ram, disk)
                self.last_saved = now
            except (sqlite3.Error, OSError) as error:
                logging.getLogger(__name__).warning(
                    "metrics_storage_unavailable",
                    extra={
                        "error_type": type(error).__name__,
                    },
                )
                warning = "Historique indisponible"

        # Snapshot compatible avec l'ancienne interface
        # et enrichi pour le nouvel affichage numérique.
        return Snapshot(
            cpu=cpu,
            ram=ram,
            disk=disk,
            battery=battery,
            sensors=sensors,
            warning=warning,
            alerts=tuple(self.alerts.recent),

            ram_used=memory.used,
            ram_total=memory.total,

            disk_used=storage.used,
            disk_total=storage.total,
            disk_free=getattr(storage, "free", None),

            cpu_cores=cpu_cores,
            cpu_threads=cpu_threads,
            cpu_freq_mhz=freq_mhz,
        )

