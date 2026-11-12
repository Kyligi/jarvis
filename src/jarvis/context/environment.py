"""Diagnostic des environnements Jarvis V1.7."""

from dataclasses import dataclass

from jarvis.config import settings
from jarvis.modes.manager import MODES, current_mode
from jarvis.services.windows import (
    WindowError,
    existing_application,
)


@dataclass(frozen=True)
class ApplicationRequirement:
    """Application attendue pour un mode."""

    name: str
    candidates: tuple[str, ...]
    workspace: int | None = None


@dataclass(frozen=True)
class EnvironmentReport:
    """État observé d'un environnement."""

    mode: str | None
    status: str
    present: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    reason: str = ""

    @property
    def needs_restore(self) -> bool:
        return self.status == "incomplete"


def requirements_for_mode(
    mode: str,
) -> tuple[ApplicationRequirement, ...]:
    """Applications des profils par défaut."""

    if mode not in MODES:
        return ()

    if mode == "travail":
        return (
            ApplicationRequirement(
                "Éditeur",
                tuple(settings.editors),
            ),
            ApplicationRequirement(
                "Foot",
                (settings.terminal,),
                MODES["travail"]["workspace"],
            ),
        )

    if mode == "gaming":
        return (
            ApplicationRequirement(
                "Steam",
                (settings.gaming,),
            ),
        )

    if mode == "etudes":
        return (
            ApplicationRequirement(
                "Navigateur",
                tuple(settings.browsers),
            ),
            ApplicationRequirement(
                "Notion",
                ("notion",),
            ),
        )

    return ()


def inspect_environment(
    mode: str | None = None,
    *,
    inventory=None,
) -> EnvironmentReport:
    """Observe les fenêtres sans modifier le système.

    Une application avec workspace=None peut être
    présente sur n'importe quel workspace.

    Si Hyprland ne peut pas être interrogé,
    le diagnostic reste inconnu.
    """

    if mode is None:
        mode = current_mode()

    if mode not in MODES:
        return EnvironmentReport(
            mode=mode,
            status="unknown",
            reason="Aucun mode reconnu.",
        )

    reader = (
        existing_application
        if inventory is None
        else inventory
    )

    present = []
    missing = []

    for requirement in requirements_for_mode(mode):
        try:
            windows = reader(
                list(requirement.candidates)
            )
        except WindowError:
            return EnvironmentReport(
                mode=mode,
                status="unknown",
                present=tuple(present),
                reason="Inventaire Hyprland indisponible.",
            )

        if windows is None:
            return EnvironmentReport(
                mode=mode,
                status="unknown",
                present=tuple(present),
                reason="Inventaire incomplet.",
            )

        found = any(
            requirement.workspace is None
            or window.workspace == requirement.workspace
            for window in windows
        )

        if found:
            present.append(requirement.name)
        else:
            missing.append(requirement.name)

    return EnvironmentReport(
        mode=mode,
        status="incomplete" if missing else "complete",
        present=tuple(present),
        missing=tuple(missing),
    )
