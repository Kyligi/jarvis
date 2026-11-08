
import os
import re
import shutil
import sqlite3
import subprocess
import time
import unicodedata
from pathlib import Path
from contextlib import contextmanager

PROJECTS_ROOT = Path.home() / "Projects"
DB_PATH = Path.home() / ".local/share/jarvis/projects.db"

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules",
    "target", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build",
}


# =====================================================
# BASE DE DONNÉES
# =====================================================

@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                path TEXT PRIMARY KEY,
                language TEXT NOT NULL,
                objective TEXT NOT NULL DEFAULT '',
                last_opened INTEGER NOT NULL DEFAULT 0
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                opened_at INTEGER NOT NULL
            )
        """)
        connection.commit()

        with connection:
            yield connection
    finally:
        connection.close()

def normalize(text):
    value = unicodedata.normalize("NFKD", text.lower())
    return "".join(
        c for c in value
        if not unicodedata.combining(c)
    ).strip()


# =====================================================
# DÉTECTION DES PROJETS
# =====================================================

def discover_projects():
    """Cherche les projets sous ~/Projects."""

    if not PROJECTS_ROOT.is_dir():
        return []

    found = []

    for root, dirs, files in os.walk(PROJECTS_ROOT):
        path = Path(root)

        depth = len(path.relative_to(PROJECTS_ROOT).parts)

        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIRS and not d.startswith(".")
        ]

        if depth > 3:
            dirs[:] = []
            continue

        if "Cargo.toml" in files:
            language = "Rust"
        elif (
            "pyproject.toml" in files
            or "requirements.txt" in files
        ):
            language = "Python"
        else:
            continue

        found.append({
            "name": path.name,
            "path": path.resolve(),
            "language": language,
        })

        # Ne pas traiter les sous-projets de ce dossier.
        dirs[:] = []

    return sorted(
        found,
        key=lambda item: item["name"].lower(),
    )


def list_projects():
    projects = discover_projects()

    if not projects:
        return "Aucun projet Rust/Python trouvé dans ~/Projects."

    lines = ["J.A.R.V.I.S. — MES PROJETS", ""]

    for project in projects:
        lines.append(
            f"• {project['name']} [{project['language']}]"
        )

    return "\n".join(lines)


# =====================================================
# GIT
# =====================================================

def git(path, *args):
    """Lecture Git, sans shell ni modification du dépôt."""

    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def git_summary(path):
    branch = git(path, "branch", "--show-current")
    commit = git(
        path, "log", "-1", "--format=%h %s"
    )
    status = git(
        path, "status", "--short",
        "--untracked-files=normal",
    )

    if branch is None and commit is None and status is None:
        return "Git : dépôt non initialisé ou inaccessible."

    branch = branch or "HEAD détaché / branche inconnue"
    commit = commit or "Aucun commit"

    if status is None:
        changes = "État des fichiers indisponible"
    elif not status:
        changes = "Aucune modification locale"
    else:
        changed = status.splitlines()
        preview = "\n".join(changed[:8])
        changes = (
            f"{len(changed)} entrée(s) modifiée(s)\n"
            f"{preview}"
        )
        if len(changed) > 8:
            changes += "\n..."

    return (
        f"Branche : {branch}\n"
        f"Dernier commit : {commit}\n"
        f"Fichiers : {changes}"
    )


# =====================================================
# MÉMOIRE ET REPRISE
# =====================================================

def get_active_project(language=None):
    with database() as db:
        if language:
            row = db.execute(
                """
                SELECT path, language, objective
                FROM projects
                WHERE language = ?
                ORDER BY last_opened DESC
                LIMIT 1
                """,
                (language,),
            ).fetchone()
        else:
            row = db.execute(
                """
                SELECT path, language, objective
                FROM projects
                WHERE last_opened > 0
                ORDER BY last_opened DESC
                LIMIT 1
                """
            ).fetchone()

    if not row:
        return None

    return {
        "path": Path(row[0]),
        "language": row[1],
        "objective": row[2],
    }


def open_editor(path):
    """Ouvre un éditeur installé sans passer par un shell."""

    for app in ("code", "codium", "cursor"):
        executable = shutil.which(app)
        if executable:
            try:
                subprocess.Popen(
                    [executable, str(path)],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return app
            except OSError:
                continue

    # Repli : gestionnaire de fichiers.
    executable = shutil.which("xdg-open")
    if executable:
        try:
            subprocess.Popen(
                [executable, str(path)],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "gestionnaire de fichiers"
        except OSError:
            pass

    return None


def resume(project):
    path = project["path"].resolve()

    if not path.is_dir():
        return f"Le dossier n'existe plus : {path}"

    # Uniquement des projets présents dans ~/Projects.
    allowed = {
        item["path"]
        for item in discover_projects()
    }

    if path not in allowed:
        return "Projet refusé : dossier non reconnu."

    with database() as db:
        previous = db.execute(
            "SELECT objective FROM projects WHERE path = ?",
            (str(path),),
        ).fetchone()

        objective = previous[0] if previous else ""

        db.execute(
            """
            INSERT INTO projects
                (path, language, objective, last_opened)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                language = excluded.language,
                last_opened = excluded.last_opened
            """,
            (
                str(path),
                project["language"],
                objective,
                int(time.time()),
            ),
        )

        db.execute(
            """
            INSERT INTO sessions (path, opened_at)
            VALUES (?, ?)
            """,
            (str(path), int(time.time())),
        )

    editor = open_editor(path)

    lines = [
        "J.A.R.V.I.S. — SESSION REPRISE",
        "",
        f"Projet : {path.name}",
        f"Langage : {project['language']}",
        f"Dossier : {path}",
        f"Ouverture : {editor or 'éditeur indisponible'}",
        "",
        git_summary(path),
        "",
        "DERNIER OBJECTIF",
        objective or "Aucun objectif enregistré.",
    ]

    return "\n".join(lines)


def resume_language(language):
    projects = [
        p for p in discover_projects()
        if p["language"] == language
    ]

    if not projects:
        return f"Aucun projet {language} trouvé."

    previous = get_active_project(language)

    if previous:
        for project in projects:
            if project["path"] == previous["path"]:
                return resume(project)

    if len(projects) == 1:
        return resume(projects[0])

    names = "\n".join(
        f"• {p['name']}" for p in projects
    )

    return (
        f"Plusieurs projets {language} trouvés.\n"
        "Choisis-en un avec : ouvre projet NOM\n\n"
        + names
    )


def open_named_project(name):
    name = normalize(name)
    projects = [
        p for p in discover_projects()
        if normalize(p["name"]) == name
    ]

    if len(projects) == 1:
        return resume(projects[0])

    if len(projects) > 1:
        return (
            "Plusieurs projets ont ce nom. "
            "Renomme-les ou précise leur identité."
        )

    return "Projet introuvable. Essaie : mes projets"


def active_project_text():
    project = get_active_project()

    if project is None:
        return "Aucun projet actif. Utilise : mes projets"

    return (
        "J.A.R.V.I.S. — PROJET ACTIF\n\n"
        f"Dossier : {project['path']}\n"
        f"Langage : {project['language']}\n"
        f"Objectif : {project['objective'] or 'Non défini'}"
    )


def active_git():
    project = get_active_project()

    if project is None:
        return "Aucun projet actif."

    if not project["path"].is_dir():
        return "Le projet actif n'existe plus."

    return git_summary(project["path"])


def set_objective(objective):
    project = get_active_project()

    if not project:
        return "Ouvre d'abord un projet."

    objective = objective.strip()

    if not objective:
        return "Indique un objectif après les deux-points."

    if len(objective) > 500:
        return "Objectif trop long (500 caractères maximum)."

    with database() as db:
        db.execute(
            """
            UPDATE projects
            SET objective = ?
            WHERE path = ?
            """,
            (objective, str(project["path"])),
        )

    return f"Objectif enregistré : {objective}"


def recent_sessions():
    with database() as db:
        rows = db.execute(
            """
            SELECT path, opened_at
            FROM sessions
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

    if not rows:
        return "Aucune session enregistrée."

    lines = ["J.A.R.V.I.S. — SESSIONS RÉCENTES", ""]

    for path, timestamp in rows:
        date = time.strftime(
            "%d/%m/%Y %H:%M",
            time.localtime(timestamp),
        )
        lines.append(f"• {date} — {Path(path).name}")

    return "\n".join(lines)


# =====================================================
# INTERPRÉTEUR DE COMMANDES V0.7
# =====================================================

def handle_project_command(message):
    text = normalize(message)
    text = re.sub(r"^jarvis[\s,:]*", "", text)

    if text in ("mes projets", "liste mes projets"):
        return list_projects()

    if text in (
        "reprends mon projet rust",
        "reprendre mon projet rust",
    ):
        return resume_language("Rust")

    if text in (
        "reprends mon projet python",
        "reprendre mon projet python",
    ):
        return resume_language("Python")

    if text.startswith("ouvre projet "):
        name = text[len("ouvre projet "):].strip()
        return open_named_project(name)

    if text == "projet actif":
        return active_project_text()

    if text in ("etat git", "git status"):
        return active_git()

    if text.startswith("objectif projet :"):
        return set_objective(
            message.split(":", 1)[1]
        )

    if text == "sessions projets":
        return recent_sessions()

    return None
