
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
    lines = ["J.A.R.V.I.S. — COMMANDES DISPONIBLES", ""]

    for command in COMMANDS:
        lines.append(
            f"• {command.name}\n  {command.description}"
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
