
import shutil
import subprocess


def hyprland(lua_command: str) -> str:
    """Exécute un dispatcher Lua Hyprland prédéfini."""
    result = subprocess.run(
        ["hyprctl", "dispatch", lua_command],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    return result.stdout.strip()


def open_terminal() -> str:
    """Ouvre Foot sans passer par un shell."""
    executable = shutil.which("foot")
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

    hyprland(f"hl.dsp.focus({{workspace={number}}})")
    return f"Workspace {number} activé."


def work_mode() -> str:
    """Lance les outils du mode Travail."""
    applications = ["foot", "code"]

    launched = []
    missing = []

    for app in applications:
        executable = shutil.which(app)
        if executable:
            subprocess.Popen(
                [executable],
                start_new_session=True,
            )
            launched.append(app)
        else:
            missing.append(app)

    message = "Mode Travail activé : " + (
        ", ".join(launched) if launched else "aucune application lancée"
    )

    if missing:
        message += ". Applications absentes : " + ", ".join(missing)

    return message
