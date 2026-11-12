"""Actions autorisées pour les suggestions Jarvis V1.7."""

from dataclasses import dataclass

from jarvis.context.suggestions import Suggestion


@dataclass(frozen=True)
class SuggestedAction:
    """Commande explicitement autorisée par Jarvis."""

    action_id: str
    command: str
    description: str


ALLOWED_ACTIONS = {
    "suggest_mode_travail": SuggestedAction(
        action_id="suggest_mode_travail",
        command="mode Travail",
        description=(
            "Demander l'activation du mode Travail. "
            "Selon la configuration, Jarvis peut changer "
            "de workspace et ouvrir des applications."
        ),
    ),
    "suggest_restore_travail": SuggestedAction(
        action_id="suggest_restore_travail",
        command="mode Travail",
        description=(
            "Restaurer l'environnement Travail. "
            "Jarvis vérifiera les applications présentes "
            "et tentera de relancer celles qui manquent."
        ),
    ),
    "suggest_restore_gaming": SuggestedAction(
        action_id="suggest_restore_gaming",
        command="mode Gaming",
        description=(
            "Restaurer l'environnement Gaming "
            "et relancer Steam si nécessaire."
        ),
    ),
    "suggest_restore_etudes": SuggestedAction(
        action_id="suggest_restore_etudes",
        command="mode Etudes",
        description=(
            "Restaurer l'environnement Études "
            "et relancer les applications manquantes."
        ),
    ),
}


def resolve_action(
    suggestion: Suggestion,
) -> SuggestedAction | None:
    """Résout une suggestion depuis une liste fermée."""

    if not isinstance(suggestion, Suggestion):
        raise TypeError("Suggestion invalide.")

    return ALLOWED_ACTIONS.get(suggestion.action_id)


def submit_action(
    suggestion: Suggestion,
    command_bus,
) -> bool:
    """Transmet une commande autorisée au CommandBus.

    Cette fonction ne demande pas de confirmation :
    l'interface doit l'obtenir avant de l'appeler.
    """

    action = resolve_action(suggestion)

    if action is None:
        return False

    return bool(command_bus.submit(action.command))
