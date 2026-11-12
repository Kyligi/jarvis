"""Résultats d'exécution structurés de Jarvis V1.7."""

from dataclasses import dataclass
from typing import Literal


OutcomeStatus = Literal[
    "success",
    "failed",
    "confirmation_required",
    "unknown",
]


@dataclass(frozen=True)
class CommandOutcome:
    """Résultat d'une exécution précise du CommandBus."""

    execution_id: str
    command_id: str
    status: OutcomeStatus
    response: object = None
    error: str = ""

    @property
    def verified_success(self) -> bool:
        return self.status == "success"


def classify_outcome(
    response,
    *,
    failed: bool = False,
    confirmation_required: bool = False,
) -> OutcomeStatus:
    """Classe uniquement les résultats explicitement fiables.

    Les textes libres ne prouvent pas la réussite
    d'une commande, même s'ils semblent positifs.
    """

    if failed:
        return "failed"

    if confirmation_required:
        return "confirmation_required"

    if isinstance(response, dict):
        if (
            "scenario_error" in response
            or "mode_error" in response
        ):
            return "failed"

        state = response.get("state")

        if state == "success":
            return "success"

        if state in {"failed", "cancelled"}:
            return "failed"

        return "unknown"

    return "unknown"
