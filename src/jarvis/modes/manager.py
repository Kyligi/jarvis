import json
import logging
import shutil
import subprocess

from jarvis.config import settings
from jarvis.projects.sessions import active_path
from jarvis.services.windows import WindowError, existing_application
from jarvis.services.windows import service as window_service

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
    window_service.switch(number, "mode")


def launch(candidates, args=None):
    """Lance uniquement une application prédéfinie."""

    try:
        existing = existing_application(candidates)
    except WindowError:
        return "Inventaire indisponible : lancement évité"
    if existing:
        return f"{existing[0].app} déjà ouvert ({len(existing)} fenêtre(s), position conservée)"
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

def launch_terminal_on_workspace(workspace, args=None):
    """Lance le terminal si aucun n'existe sur ce workspace."""

    try:
        existing = existing_application([settings.terminal])
    except WindowError:
        return "Inventaire indisponible : lancement évité"

    # Une fenêtre présente sur un autre workspace
    # ne doit pas empêcher la création du terminal.
    for window in existing:
        window_workspace = getattr(window, "workspace", None)

        if isinstance(window_workspace, dict):
            window_workspace = window_workspace.get("id")

        if window_workspace == workspace:
            return (
                f"Terminal déjà ouvert sur "
                f"workspace {workspace}"
            )

    executable = shutil.which(settings.terminal)

    if not executable:
        return "Terminal introuvable"

    subprocess.Popen(
        [executable, *(args or [])],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return f"Terminal lancé sur workspace {workspace}"
def activate_mode(name):
    if name not in MODES:
        return "Mode inconnu."

    from . import profiles
    try:
        customized = profiles.load()[name] != profiles.defaults()[name]
        if customized:
            from jarvis.scenarios.engine import engine
            response = engine.request(profiles.scenario_for_mode(name))
            if 'confirme scénario' not in response:
                state = engine.status()
                if state and state['state'] == 'success':
                    save_mode(name)
            return response
    except (ValueError, OSError, RuntimeError) as error:
        return f"Mode non activé : {error}"

    profile = MODES[name]

    try:
        switch_workspace(profile["workspace"])
    except (OSError, subprocess.TimeoutExpired,
            RuntimeError) as error:
        return f"Erreur Hyprland : {error}"

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

        terminal_result = launch_terminal_on_workspace(
            profile["workspace"],
            terminal_args,
        )

        if terminal_result:
            launched.append(terminal_result)
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

        try:
            notion_exists = existing_application(["notion"])
        except WindowError:
            notion_exists = None
        if notion_exists is None:
            launched.append("Notion : inventaire indisponible, lancement évité")
        elif notion_exists:
            launched.append("Notion déjà ouvert, position conservée")
        elif notion_launcher:
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
        f"Applications : "
        f"{', '.join(launched) if launched else 'aucune'}"
    )


def mode_status():
    name = current_mode()

    if name not in MODES:
        return "Aucun mode Jarvis enregistré."

    from .profiles import load
    try:
        profile = dict(MODES[name], workspace=load()[name]['workspace'])
    except (ValueError, OSError) as error:
        return f"Mode enregistré : {name}. Configuration indisponible : {error}"

    return (
        f"Mode enregistré : {name.capitalize()}\n"
        f"Workspace : {profile['workspace']}\n"
        f"Profil : {profile['description']}"
    )
