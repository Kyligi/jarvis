"""Moteur de contexte local de Jarvis V1.7."""

import logging
from collections.abc import Callable
from typing import Any

from jarvis.context.models import ContextSnapshot
from jarvis.modes.manager import current_mode
from jarvis.projects.sessions import active_path
from jarvis.services.windows import (
    WindowError,
    service as window_service,
)

logger = logging.getLogger(__name__)


class ContextService:
    """Collecte un contexte local sans exécuter d'action."""

    def __init__(
        self,
        window_reader: Callable[[], Any] | None = None,
        mode_reader: Callable[[], Any] | None = None,
        project_reader: Callable[[], Any] | None = None,
        monitor_reader: Callable[[], Any] | None = None,
    ):
        self.window_reader = (
            window_reader
            if window_reader is not None
            else window_service.active
        )
        self.mode_reader = (
            mode_reader
            if mode_reader is not None
            else current_mode
        )
        self.project_reader = (
            project_reader
            if project_reader is not None
            else active_path
        )

        # Le monitoring doit utiliser un relevé existant.
        # Ne jamais déclencher une nouvelle collecte ici.
        self.monitor_reader = monitor_reader

    def collect(self) -> ContextSnapshot:
        """Construit un instantané, même si une source échoue."""

        errors = []
        values = {}

        # Fenêtre active
        try:
            window = self.window_reader()

            if window is not None:
                values["active_app"] = window.app
                values["active_window_title"] = window.title
                values["active_workspace"] = window.workspace

        except (WindowError, OSError, RuntimeError) as error:
            errors.append("windows")
            logger.warning(
                "context_windows_unavailable: %s",
                type(error).__name__,
            )

        # Mode actuel
        try:
            mode = self.mode_reader()

            if mode in ("travail", "gaming", "etudes"):
                values["active_mode"] = mode

        except (OSError, RuntimeError, ValueError) as error:
            errors.append("mode")
            logger.warning(
                "context_mode_unavailable: %s",
                type(error).__name__,
            )

        # Projet actif
        try:
            project = self.project_reader()

            if project is not None:
                values["active_project"] = str(project)

        except (OSError, RuntimeError, ValueError) as error:
            errors.append("project")
            logger.warning(
                "context_project_unavailable: %s",
                type(error).__name__,
            )

        # Dernier relevé système disponible
        if self.monitor_reader is not None:
            try:
                monitor = self.monitor_reader()

                if monitor is not None:
                    values["cpu_percent"] = monitor.cpu
                    values["ram_percent"] = monitor.ram
                    values["disk_percent"] = monitor.disk

            except (OSError, RuntimeError, ValueError) as error:
                errors.append("monitor")
                logger.warning(
                    "context_monitor_unavailable: %s",
                    type(error).__name__,
                )

        values["errors"] = tuple(errors)

        return ContextSnapshot(**values)
