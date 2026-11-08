from jarvis.services.windows import service as window_service

import shutil
import subprocess
from jarvis.config import settings


def open_terminal() -> str:
    """Ouvre Foot sans passer par un shell."""
    executable = shutil.which(settings.terminal)
    if not executable:
        return "Foot n'est pas installé."

    subprocess.Popen(
        [executable],
        start_new_session=True,
    )
    return "Terminal Foot ouvert."


def change_workspace(number: int) -> str:
    """Passe à un workspace entre 1 et 9."""
    if not 1 <= number <= 9:
        return "Le workspace doit être compris entre 1 et 9."

    window_service.switch(number, "command")
    return f"Workspace {number} activé."


def work_mode() -> str:
    """Compatibilité : un seul service pour le mode Travail."""
    from jarvis.modes.manager import activate_mode
    return activate_mode("travail")
