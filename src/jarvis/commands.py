"""Compatibilité V0.3 : le catalogue est désormais dans jarvis.registry."""
from jarvis.core.text import normalize  # noqa : F401


def handle_system_command(message: str) -> str | None:
    from jarvis.registry import resolve
    resolved = resolve(message)
    if resolved and (resolved.command.category == "Omarchy" or resolved.command.id == "modes.travail"):
        return resolved.run()
    return None
