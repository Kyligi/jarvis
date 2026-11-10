
import logging
import subprocess
import time
from collections import deque

import psutil

from jarvis.config import settings
from jarvis.persistence.sqlite import connect

# =========================================================
# CONFIGURATION
# =========================================================

DB_PATH = settings.data_dir / "performance.db"

CPU_LIMIT = 90
RAM_LIMIT = 90
DISK_LIMIT = 95

# Capteurs détectés sur ton ASUS Vivobook
SENSOR_NAMES = {
    "k10temp": "CPU AMD",
    "amdgpu": "GPU Radeon 860M",
    "nvme": "SSD NVMe",
    "mt7921_phy0": "Wi-Fi",
    "acpitz": "Zone thermique ACPI",
}


# =========================================================
# CAPTEURS DE TEMPÉRATURE
# =========================================================

def read_sensors() -> dict[str, float]:
    """Récupère les températures Linux avec noms lisibles."""

    try:
        raw = psutil.sensors_temperatures() or {}
    except (AttributeError, OSError):
        return {}

    result = {}

    for chip, entries in raw.items():
        for index, entry in enumerate(entries):
            temperature = entry.current

            if temperature is None:
                continue

            if not 0 < temperature < 150:
                continue

            label = entry.label or f"capteur {index}"
            name = SENSOR_NAMES.get(chip, chip)

            result[f"{name} / {label}"] = temperature

    return result


def sensors_text() -> str:
    """Formate les températures pour une commande Jarvis."""

    sensors = read_sensors()

    if not sensors:
        return "Aucun capteur de température accessible."

    lines = [
        "J.A.R.V.I.S. — CAPTEURS",
        "",
    ]

    for name, value in sensors.items():
        lines.append(
            f"{name} : {value:.1f} °C"
        )

    return "\n".join(lines)


# =========================================================
# BASE DE DONNÉES SQLITE
# =========================================================

def init_database() -> None:
    """Initialise la base de données des performances."""

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                cpu REAL NOT NULL,
                ram REAL NOT NULL,
                disk REAL NOT NULL
            )
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_time
            ON metrics(timestamp)
        """)


def save_metrics(
    cpu: float,
    ram: float,
    disk: float,
) -> None:
    """Sauvegarde un échantillon de performances."""

    init_database()

    now = int(time.time())

    with connect(DB_PATH) as db:
        db.execute(
            """
            INSERT INTO metrics
                (timestamp, cpu, ram, disk)
            VALUES (?, ?, ?, ?)
            """,
            (
                now,
                float(cpu),
                float(ram),
                float(disk),
            ),
        )

        # Nettoyage automatique :
        # conserver les sept derniers jours.
        db.execute(
            """
            DELETE FROM metrics
            WHERE timestamp < ?
            """,
            (now - 7 * 24 * 3600,),
        )


# =========================================================
# HISTORIQUE DES PERFORMANCES
# =========================================================

def history_text() -> str:
    """Retourne les statistiques de la dernière heure."""

    init_database()

    since = int(time.time()) - 3600

    with connect(DB_PATH) as db:
        row = db.execute(
            """
            SELECT
                COUNT(*),
                AVG(cpu),
                MAX(cpu),
                AVG(ram),
                MAX(ram)
            FROM metrics
            WHERE timestamp >= ?
            """,
            (since,),
        ).fetchone()

    count, cpu_avg, cpu_max, ram_avg, ram_max = row

    if count == 0:
        return (
            "J.A.R.V.I.S. — HISTORIQUE\n\n"
            "Aucune mesure enregistrée "
            "sur la dernière heure."
        )

    return (
        "J.A.R.V.I.S. — HISTORIQUE (1 HEURE)\n\n"
        f"Échantillons : {count}\n"
        f"CPU moyen : {cpu_avg:.1f} %\n"
        f"CPU maximum : {cpu_max:.1f} %\n"
        f"RAM moyenne : {ram_avg:.1f} %\n"
        f"RAM maximum : {ram_max:.1f} %"
    )


# =========================================================
# NOTIFICATIONS LINUX
# =========================================================

def notify(title: str, message: str) -> None:
    """Envoie une notification via notify-send."""

    try:
        subprocess.Popen(
            [
                "notify-send",
                "-a",
                "Jarvis",
                title,
                message,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    except OSError:
        logging.getLogger(__name__).warning("notification_unavailable")


# =========================================================
# MOTEUR D'ALERTES
# =========================================================

class AlertEngine:
    """Surveille les ressources et évite le spam."""

    def __init__(self):
        self.counts = {
            "cpu": 0,
            "ram": 0,
            "disk": 0,
        }

        self.last_alert = {}
        self.recent = deque(maxlen=20)

        # Une alerte maximum toutes les 5 minutes
        # pour chaque ressource.
        self.cooldown = 300

        # Trois mesures consécutives nécessaires.
        self.required_samples = 3

    def check(
        self,
        cpu: float,
        ram: float,
        disk: float,
    ) -> None:
        """Analyse les mesures et déclenche les alertes."""

        measurements = {
            "cpu": (cpu, CPU_LIMIT),
            "ram": (ram, RAM_LIMIT),
            "disk": (disk, DISK_LIMIT),
        }

        now = time.monotonic()

        for name, (value, limit) in measurements.items():

            # Retour à une valeur normale
            if value < limit:
                self.counts[name] = 0
                continue

            # Une mesure supplémentaire au-dessus du seuil
            self.counts[name] += 1

            if self.counts[name] < self.required_samples:
                continue

            last = self.last_alert.get(
                name,
                float("-inf"),
            )

            # Anti-spam
            if now - last < self.cooldown:
                continue

            self.last_alert[name] = now
            self.recent.append(f"{time.strftime('%H:%M:%S')} — {name.upper()} à {value:.0f} % (seuil {limit} %)")

            notify(
                "Jarvis — Alerte système",
                (
                    f"{name.upper()} à {value:.0f} %\n"
                    f"Seuil : {limit} %"
                ),
            )
