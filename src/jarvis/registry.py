
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from jarvis.monitoring.system import (
    system_status,
    battery_status,
    top_processes,
    diagnose,
)
from jarvis.monitoring.intelligence import (
    sensors_text,
    history_text,
)

from jarvis.monitoring.diagnostics import (
    explain_slowdown,
)

@dataclass(frozen=True)
class Command:
    name: str
    description: str
    examples: tuple[str, ...]
    handler: Callable[[], str] | None = None


COMMANDS = [
    Command(
        "état système",
        "Afficher CPU, RAM, disque, uptime et batterie",
        ("état système", "statut système"),
        system_status,
    ),
    Command(
        "processus",
        "Lister les processus les plus consommateurs de CPU",
        ("processus", "top processus"),
        top_processes,
    ),
    Command(
        "diagnostic",
        "Rechercher les saturations de ressources",
        ("diagnostic", "diagnostic système"),
        diagnose,
    ),
    Command(
        "batterie",
        "Afficher la charge et l'autonomie estimée",
        ("batterie", "état batterie"),
        battery_status,
    ),
    Command(
        "ouvre un terminal",
        "Lancer Foot",
        ("ouvre un terminal",),
    ),
    Command(
        "passe au workspace 2",
        "Changer de workspace (1 à 9)",
        ("passe au workspace 2",),
    ),
    Command(
        "active le mode Travail",
        "Ouvrir les outils de développement",
        ("active le mode Travail",),
    ),
    Command(
        "reprends mon projet Rust",
        "Retrouver et ouvrir un projet Rust",
        ("reprends mon projet Rust",),
    ),
    Command(
        "projets Rust",
        "Lister les projets Rust disponibles",
        ("projets Rust",),
    ),
    Command(
        "ouvre rust NOM",
        "Ouvrir un projet Rust par son nom",
        ("ouvre rust NOM",),
    ),

    Command(
        "capteurs",
        "Afficher les températures AMD et les autres capteurs Linux",
        (
            "capteurs",
            "températures",
            "temperatures",
        ),
        sensors_text,
    ),

    Command(
        "historique",
        "Afficher les statistiques CPU/RAM de la dernière heure",
        (
            "historique",
            "historique performances",
            "historique système",
        ),
        history_text,
    ),

    Command(
        "pourquoi mon pc ralentit",
        "Analyser les ressources, températures et processus",
        (
            "pourquoi mon pc ralentit",
            "analyse mon pc",
            "diagnostic avancé",
            "mon pc est lent",
        ),
        explain_slowdown,
    ),
]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^jarvis[, :]*", "", text)


def help_text() -> str:
    lines = [
        "J.A.R.V.I.S. V0.6 — COMMANDES DISPONIBLES",
        "",
        "MONITORING",
        "Dashboard temps réel, historique SQLite et alertes.",
        "",
    ]

    for command in COMMANDS:
        lines.append(
            f"• {command.name}\n"
            f"  {command.description}"
        )

    return "\n".join(lines)

def dispatch(command: str) -> str | None:
    text = normalize(command)

    if text in {"aide", "help", "commandes"}:
        return help_text()

    for entry in COMMANDS:
        if entry.handler is None:
            continue

        if any(
            text == normalize(example)
            for example in entry.examples
        ):
            return entry.handler()

    return None
