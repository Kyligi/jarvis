from jarvis.integrations.desktop import focus_workspace

import json
import shutil
import subprocess
import time
from pathlib import Path

from jarvis.projects.manager import (
    database,
    discover_projects,
    get_active_project,
    git_summary,
)

from jarvis.config import settings

# Workspace de développement
DEV_WORKSPACE = settings.workspaces["travail"]


# =========================================
# BASE DE DONNÉES
# =========================================

def init_sessions():
    with database() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS saved_sessions (
                project_path TEXT PRIMARY KEY,
                saved_at INTEGER NOT NULL,
                files_json TEXT NOT NULL,
                git_snapshot TEXT NOT NULL,
                objective TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS tracked_files (
                project_path TEXT NOT NULL,
                file_path TEXT NOT NULL,
                PRIMARY KEY (project_path, file_path)
            )
        """)


# =========================================
# PROJET ACTIF
# =========================================

def active_path():
    project = get_active_project()

    if not project:
        return None

    path = project["path"].resolve()

    # Ne travailler que sur les projets connus
    allowed = {
        p["path"].resolve()
        for p in discover_projects()
    }

    if path not in allowed:
        return None

    return path


# =========================================
# FICHIERS SUIVIS
# =========================================

def track_file(filename):
    init_sessions()

    project = active_path()
    if project is None:
        return "Aucun projet actif reconnu."

    filename = filename.strip()

    if not filename:
        return "Indique un fichier à suivre."

    candidate = (project / filename).resolve()

    # Éviter toute sortie du projet
    if not candidate.is_relative_to(project):
        return "Fichier refusé : hors du projet."

    if not candidate.is_file():
        return f"Fichier introuvable : {filename}"

    relative = str(candidate.relative_to(project))

    with database() as db:
        db.execute(
            """
            INSERT OR IGNORE INTO tracked_files
                (project_path, file_path)
            VALUES (?, ?)
            """,
            (str(project), relative),
        )

    return f"Fichier suivi : {relative}"


def tracked_files(project):
    init_sessions()

    with database() as db:
        rows = db.execute(
            """
            SELECT file_path
            FROM tracked_files
            WHERE project_path = ?
            ORDER BY file_path
            """,
            (str(project),),
        ).fetchall()

    return [row[0] for row in rows]


def files_text():
    project = active_path()
    if project is None:
        return "Aucun projet actif reconnu."

    files = tracked_files(project)

    if not files:
        return "Aucun fichier suivi pour ce projet."

    return (
        "FICHIERS SUIVIS\n\n"
        + "\n".join(f"• {name}" for name in files)
    )


# =========================================
# ENREGISTRER LA SESSION
# =========================================

def save_session():
    init_sessions()

    project = get_active_project()
    path = active_path()

    if not project or path is None:
        return (
            "Ouvre d'abord un projet avec "
            "'ouvre projet NOM'."
        )

    files = tracked_files(path)
    snapshot = git_summary(path)
    objective = project["objective"]

    with database() as db:
        db.execute(
            """
            INSERT INTO saved_sessions (
                project_path,
                saved_at,
                files_json,
                git_snapshot,
                objective
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_path) DO UPDATE SET
                saved_at = excluded.saved_at,
                files_json = excluded.files_json,
                git_snapshot = excluded.git_snapshot,
                objective = excluded.objective
            """,
            (
                str(path),
                int(time.time()),
                json.dumps(files, ensure_ascii=False),
                snapshot,
                objective,
            ),
        )

    return (
        "J.A.R.V.I.S. — SESSION SAUVEGARDÉE\n\n"
        f"Projet : {path.name}\n"
        f"Fichiers suivis : {len(files)}\n"
        f"Objectif : {objective or 'Non défini'}\n\n"
        + snapshot
    )


# =========================================
# WORKSPACE HYPRLAND
# =========================================

def switch_workspace():
    focus_workspace(DEV_WORKSPACE, "session")


# =========================================
# OUVERTURE DE L'ENVIRONNEMENT
# =========================================

def launch_editor(project, filenames):
    # Éditeur disponible
    editor = None

    for name in settings.editors:
        editor = shutil.which(name)
        if editor:
            break

    if not editor:
        return "Aucun éditeur compatible trouvé."

    args = [editor, "--new-window", str(project)]

    # Ajouter les fichiers suivis encore présents
    for filename in filenames:
        path = (project / filename).resolve()

        if path.is_relative_to(project) and path.is_file():
            args.append(str(path))

    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return "Éditeur lancé."


def launch_terminal(project):
    foot = shutil.which(settings.terminal)

    if not foot:
        return "Terminal Foot indisponible."

    subprocess.Popen(
        [
            foot,
            "--working-directory",
            str(project),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return "Terminal Foot lancé."


# =========================================
# RESTAURATION
# =========================================

def restore_session():
    init_sessions()

    project = active_path()

    if project is None:
        return "Aucun projet actif reconnu."

    with database() as db:
        row = db.execute(
            """
            SELECT files_json, git_snapshot,
                   objective, saved_at
            FROM saved_sessions
            WHERE project_path = ?
            """,
            (str(project),),
        ).fetchone()

    if row is None:
        return (
            "Aucune session sauvegardée pour ce projet.\n"
            "Utilise d'abord : sauvegarde session"
        )

    files_json, previous_git, objective, saved_at = row

    filenames = parse_files(files_json)

    try:
        switch_workspace()
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        return f"Impossible d'ouvrir le workspace : {error}"

    actions = []

    try:
        actions.append(launch_editor(project, filenames))
        actions.append(launch_terminal(project))
    except OSError as error:
        actions.append(f"Erreur d'ouverture : {error}")

    date = time.strftime(
        "%d/%m/%Y %H:%M",
        time.localtime(saved_at),
    )

    return "\n".join([
        "J.A.R.V.I.S. — SESSION RESTAURÉE",
        "",
        f"Projet : {project.name}",
        f"Sauvegarde : {date}",
        f"Workspace : {DEV_WORKSPACE}",
        f"Objectif : {objective or 'Non défini'}",
        "",
        "Actions :",
        *actions,
        "",
        "ÉTAT GIT À LA SAUVEGARDE",
        previous_git,
        "",
        "ÉTAT GIT ACTUEL",
        git_summary(project),
    ])


def session_info():
    init_sessions()

    project = active_path()

    if project is None:
        return "Aucun projet actif reconnu."

    with database() as db:
        row = db.execute(
            """
            SELECT saved_at, files_json, objective
            FROM saved_sessions
            WHERE project_path = ?
            """,
            (str(project),),
        ).fetchone()

    if not row:
        return "Aucune session enregistrée."

    saved_at, files_json, objective = row

    return (
        "SESSION ENREGISTRÉE\n\n"
        f"Projet : {project.name}\n"
        f"Date : {time.ctime(saved_at)}\n"
        f"Fichiers : {len(parse_files(files_json))}\n"
        f"Objectif : {objective or 'Non défini'}"
    )


def parse_files(value: str) -> list[str]:
    files = json.loads(value)
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise ValueError("Liste de fichiers de session invalide")
    return files
