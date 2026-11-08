"""Découverte et ouverture explicite des projets Rust locaux."""
from pathlib import Path
import shutil
import subprocess

from jarvis.config import settings
from jarvis.projects.manager import git_summary

ROOT = settings.projects_root


def rust_projects(root: Path | None = None) -> list[Path]:
    """Cherche Cargo.toml à profondeur raisonnable, sans suivre les symlinks."""
    root = root or ROOT
    if not root.is_dir():
        return []
    found: set[Path] = set()
    for entry in root.iterdir():
        if entry.is_symlink() or not entry.is_dir():
            continue
        for directory in [entry, *(p for p in entry.iterdir() if p.is_dir() and not p.is_symlink() and p.name not in {"target", ".git", ".venv"})]:
            if (directory / "Cargo.toml").is_file():
                found.add(directory)
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def open_project(path: Path) -> str:
    path = path.expanduser().resolve()
    if not (path / "Cargo.toml").is_file() or ROOT.resolve() not in path.parents:
        return "Ouverture refusée : projet Rust non valide dans ~/Projects."
    for editor in settings.rust_editors:
        if shutil.which(editor):
            subprocess.Popen([editor, str(path)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Projet ouvert dans {editor} : {path.name}"
    if shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", str(path)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Dossier ouvert : {path.name} (aucun éditeur détecté)."
    return "Aucun éditeur ou gestionnaire de fichiers détecté."
