"""Documentation de la V1.7 dans la commande aide."""

from jarvis.registry import (
    COMMANDS,
    help_text,
    resolve,
)


def test_help_describes_v17_features():
    help_output = help_text()

    for expected in (
        "FONCTIONNALITÉS V1.7",
        "Contexte actuel",
        "Suggestions intelligentes",
        "Restauration des environnements",
        "Workflows supervisés",
        "Prévisualiser",
        "Exécuter",
        "Ignorer",
        "CONFIRMATION_REQUIRED",
        "UNKNOWN",
        "docs/V1.7.md",
    ):
        assert expected in help_output


def test_help_preserves_registry():
    help_output = help_text()

    assert help_output.count("• ") == len(COMMANDS)

    for command in COMMANDS:
        assert (
            help_output.count(
                f"• {command.name}\n"
            ) == 1
        )

    for text in (
        "aide",
        "mode Travail",
        "mode Gaming",
        "mode Etudes",
    ):
        assert resolve(text) is not None

    # Les workflows sont accessibles dans le HUD,
    # pas comme des commandes ajoutées au registre.
    assert resolve(
        "Préparer ma session de travail"
    ) is None
