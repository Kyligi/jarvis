"""Compatibilité V0.8 : aucun interpréteur indépendant."""


def handle_session_command(message: str) -> str | None:
    from jarvis.registry import dispatch
    return dispatch(message, category="Sessions")
