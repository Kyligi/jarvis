"""Suggestions de restauration des environnements Jarvis."""

import logging

from jarvis.context.environment import inspect_environment
from jarvis.context.suggestions import Suggestion
from jarvis.modes.manager import MODES, current_mode

logger = logging.getLogger(__name__)

ACTION_IDS = {
    "travail": "suggest_restore_travail",
    "gaming": "suggest_restore_gaming",
    "etudes": "suggest_restore_etudes",
}

MODE_NAMES = {
    "travail": "Travail",
    "gaming": "Gaming",
    "etudes": "Études",
}


def is_custom_profile(mode: str) -> bool | None:
    """Détecte les profils personnalisés.

    None indique une configuration indisponible.
    """
    from jarvis.modes import profiles

    try:
        saved = profiles.load()
        defaults = profiles.defaults()

        return saved[mode] != defaults[mode]
    except (KeyError, OSError, ValueError, TypeError):
        logger.warning(
            "environment_profile_unavailable",
            extra={"mode": mode},
        )
        return None


def suggest_environment_restore(
    mode: str | None = None,
    *,
    report=None,
    customized: bool | None = None,
) -> tuple[Suggestion, ...]:
    """Produit au maximum une suggestion de restauration.

    Ne lance aucune commande et ne modifie aucune fenêtre.
    """

    if mode is None:
        mode = current_mode()

    if mode not in MODES:
        return ()

    # Les profils personnalisés utilisent le moteur
    # de scénarios et ne sont pas diagnostiqués ici.
    if customized is None:
        customized = is_custom_profile(mode)

        # Un état inconnu n'autorise aucune suggestion.
        if customized is None:
            return ()

    if customized:
        return ()

    if report is None:
        report = inspect_environment(mode)

    # Ne jamais proposer une restauration à partir
    # d'un diagnostic d'un autre mode.
    if report.mode != mode:
        return ()

    if report.status != "incomplete":
        return ()

    if not report.missing:
        return ()

    missing = ", ".join(report.missing)
    display_name = MODE_NAMES[mode]

    suggestion = Suggestion(
        id=f"restore_environment_{mode}",
        title=f"Restaurer l'environnement {display_name}",
        description=(
            f"Applications manquantes : {missing}. "
            "Jarvis peut restaurer ce mode après "
            "ton autorisation."
        ),
        action_id=ACTION_IDS[mode],
        priority=70,
    )

    return (suggestion,)
