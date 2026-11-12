"""Suggestions contextuelles locales de Jarvis V1.7."""

import time
from dataclasses import dataclass
from typing import Callable

from jarvis.context.models import ContextSnapshot


@dataclass(frozen=True)
class Suggestion:
    """Proposition informative, sans exécution automatique."""

    id: str
    title: str
    description: str
    action_id: str
    priority: int = 1


class SuggestionEngine:
    """Évalue des règles locales et limite leurs répétitions."""

    def __init__(
        self,
        cooldown_seconds: float = 300,
        clock: Callable[[], float] = time.monotonic,
    ):
        if cooldown_seconds < 0:
            raise ValueError("Délai de répétition invalide.")

        self.cooldown_seconds = cooldown_seconds
        self.clock = clock
        self.last_shown: dict[str, float] = {}

    def evaluate(
        self,
        context: ContextSnapshot,
    ) -> tuple[Suggestion, ...]:
        """Construit les suggestions autorisées par le contexte."""

        candidates = []

        # Projet actif alors que le mode Études est sélectionné.
        if (
            context.active_project
            and context.active_mode == "etudes"
        ):
            candidates.append(Suggestion(
                id="development_mode",
                title="Passer en mode Travail",
                description=(
                    "Un projet est actif alors que le mode "
                    "Études est sélectionné."
                ),
                action_id="suggest_mode_travail",
                priority=2,
            ))

        # Mode Travail sans projet actif.
        if (
            context.active_mode == "travail"
            and not context.active_project
            and "project" not in context.errors
        ):
            candidates.append(Suggestion(
                id="select_project",
                title="Choisir un projet",
                description=(
                    "Le mode Travail est actif, mais aucun "
                    "projet courant n'est identifié."
                ),
                action_id="suggest_select_project",
                priority=1,
            ))

        # Les seuils sont volontairement explicites.
        if (
            context.cpu_percent is not None
            and context.cpu_percent >= 90
        ):
            candidates.append(Suggestion(
                id="high_cpu",
                title="Analyser l'utilisation du CPU",
                description=(
                    f"Le CPU est à {context.cpu_percent:.1f} %. "
                    "Un diagnostic peut être utile."
                ),
                action_id="suggest_system_diagnostic",
                priority=3,
            ))

        if (
            context.ram_percent is not None
            and context.ram_percent >= 90
        ):
            candidates.append(Suggestion(
                id="high_ram",
                title="Examiner la mémoire vive",
                description=(
                    f"La RAM est utilisée à "
                    f"{context.ram_percent:.1f} %."
                ),
                action_id="suggest_memory_diagnostic",
                priority=3,
            ))

        if (
            context.disk_percent is not None
            and context.disk_percent >= 90
        ):
            candidates.append(Suggestion(
                id="high_disk",
                title="Examiner l'espace disque",
                description=(
                    f"Le disque est utilisé à "
                    f"{context.disk_percent:.1f} %."
                ),
                action_id="suggest_disk_diagnostic",
                priority=3,
            ))

        # Ordre déterministe : urgence, puis identifiant.
        candidates.sort(
            key=lambda item: (-item.priority, item.id)
        )

        now = self.clock()
        visible = []

        for suggestion in candidates:
            previous = self.last_shown.get(suggestion.id)

            if (
                previous is not None
                and now - previous < self.cooldown_seconds
            ):
                continue

            visible.append(suggestion)
            self.last_shown[suggestion.id] = now

        return tuple(visible)

    def reset(self):
        """Réinitialise les délais sans agir sur Omarchy."""
        self.last_shown.clear()
