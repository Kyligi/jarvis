from jarvis.integrations.desktop import focus_workspace

import json
import shutil
import subprocess

from jarvis.projects.sessions import active_path
from jarvis.config import settings
import logging


STATE_PATH = settings.data_dir / "active_mode.json"

# Profils autorisés
MODES = {
    "travail": {
        "workspace": settings.workspaces["travail"],
        "description": "Développement Rust / Python",
    },
    "gaming": {
        "workspace": settings.workspaces["gaming"],
        "description": "Steam et jeux",
    },
    "etudes": {
        "workspace": settings.workspaces["etudes"],
        "description": "Cours et révisions",
    },
}


def current_mode():
    if not STATE_PATH.exists():
        return None

    try:
        state = json.loads(STATE_PATH.read_text())
        return state.get("mode") if isinstance(state, dict) else None
    except (OSError, ValueError) as error:
        logging.getLogger(__name__).warning("mode_state_unavailable", extra={"error_type": type(error).__name__})
        return None


def save_mode(name):
    STATE_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"mode": name}),
        encoding="utf-8",
    )
    temporary.replace(STATE_PATH)


def switch_workspace(number):
    focus_workspace(number, "mode")


def launch(candidates, args=None):
    """Lance uniquement une application prédéfinie."""

    for name in candidates:
        executable = shutil.which(name)

        if executable:
            subprocess.Popen(
                [executable, *(args or [])],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return name

    return None


def activate_mode(name):
    if name not in MODES:
        return "Mode inconnu."

    profile = MODES[name]

    try:
        switch_workspace(profile["workspace"])
    except (OSError, subprocess.TimeoutExpired,
            RuntimeError) as error:
        return f"Erreur Hyprland : {error}"

    # Si le même mode est déjà actif,
    # on ne relance pas toutes les applications.
    if current_mode() == name:
        return (
            f"Mode {name.capitalize()} déjà actif.\n"
            f"Workspace {profile['workspace']} affiché."
        )

    launched = []

    if name == "travail":
        path = active_path()
        project_path = str(path) if path is not None else None

        editor = launch(
            settings.editors,
            [project_path] if project_path else [],
        )
        if editor:
            launched.append(editor)

        terminal_args = (
            ["--working-directory", project_path]
            if project_path else []
        )

        if launch([settings.terminal], terminal_args):
            launched.append("Foot")

    elif name == "gaming":
        if launch([settings.gaming]):
            launched.append("Steam")

    elif name == "etudes":
        # Ouvrir Chrome
        browser = launch(settings.browsers)

        if browser:
            launched.append(browser)

        # Ouvrir Notion via son lanceur .desktop
        notion_launcher = shutil.which(settings.desktop_launcher)

        if notion_launcher:
            subprocess.Popen(
                [notion_launcher, settings.notion_desktop],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            launched.append("Notion")
        else:
            launched.append("Notion : gtk-launch indisponible")

    try:
        save_mode(name)
    except OSError as error:
        return f"Mode activé, mais mémoire indisponible : {error}"

    return (
        f"J.A.R.V.I.S. — MODE {name.upper()}\n\n"
        f"Workspace : {profile['workspace']}\n"
        f"Profil : {profile['description']}\n"
        f"Applications lancées : "
        f"{', '.join(launched) if launched else 'aucune'}"
    )


def mode_status():
    name = current_mode()

    if name not in MODES:
        return "Aucun mode Jarvis enregistré."

    profile = MODES[name]

    return (
        f"Mode enregistré : {name.capitalize()}\n"
        f"Workspace : {profile['workspace']}\n"
        f"Profil : {profile['description']}"
    )
