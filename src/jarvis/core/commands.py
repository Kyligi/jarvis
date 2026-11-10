"""Frontière applicative : résolution, exécution, erreurs et journal sans contenu."""
import logging
import sqlite3

from jarvis.memory.database import remember
from jarvis.registry import resolve

logger = logging.getLogger(__name__)


def execute(command: str) -> str:
    if not command.strip():
        return "Écris une commande."
    resolved = resolve(command)
    if resolved is None:
        return "Commande inconnue. Tape 'aide'."
    identifier = resolved.command.id
    try:
        result = resolved.run()
    except Exception as error:
        # Frontière UI : conserver une réponse utilisable, sans exposer le contenu
        # des erreurs (arguments subprocess, chemins ou objectifs personnels).
        logger.error("command_failed", extra={
            "command_id": identifier, "error_type": type(error).__name__,
        })
        return f"Erreur Jarvis ({identifier}, {type(error).__name__}). Vérifie les ressources et réessaie."
    logger.info("command_completed", extra={"command_id": identifier})
    try:
        # La base historique est conservée, mais les nouvelles lignes n'incluent
        # aucun texte libre susceptible de contenir un secret.
        remember(identifier, "ok")
    except (OSError, sqlite3.Error) as error:
        logger.warning("history_unavailable", extra={"error_type": type(error).__name__})
        result += "\n(Avertissement : historique non enregistré.)"
    return result
