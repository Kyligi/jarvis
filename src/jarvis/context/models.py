"""Structures de données du contexte Jarvis V1.7."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class ContextSnapshot:
    """Instantané en lecture seule du contexte local."""

    captured_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    active_app: str | None = None
    active_window_title: str | None = None
    active_workspace: int | None = None

    active_project: str | None = None
    active_mode: str | None = None

    cpu_percent: float | None = None
    ram_percent: float | None = None
    disk_percent: float | None = None

    errors: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        """Indique si toutes les sources ont été lues."""
        return not self.errors

    def summary(self) -> str:
        """Résumé lisible du contexte."""

        def value(item):
            return str(item) if item is not None else "Inconnu"

        return "\n".join([
            "J.A.R.V.I.S. — CONTEXTE ACTUEL",
            f"Application : {value(self.active_app)}",
            f"Fenêtre : {value(self.active_window_title)}",
            f"Workspace : {value(self.active_workspace)}",
            f"Projet : {value(self.active_project)}",
            f"Mode : {value(self.active_mode)}",
            f"CPU : {value(self.cpu_percent)} %",
            f"RAM : {value(self.ram_percent)} %",
            f"Disque : {value(self.disk_percent)} %",
            f"Sources indisponibles : {', '.join(self.errors) if self.errors else 'aucune'}",
        ])
