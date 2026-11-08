"""Compatibilité V0.9 : aucun interpréteur indépendant."""


def handle_mode_command(message: str) -> str | None:
    from jarvis.registry import dispatch
    return dispatch(message, category="Modes")
