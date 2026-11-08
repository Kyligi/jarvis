"""Découverte et ouverture explicite des projets Rust locaux."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path.home() / "Projects"


def rust_projects(root: Path = ROOT) -> list[Path]:
    """Cherche Cargo.toml à profondeur raisonnable, sans suivre les symlinks."""
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


def git_summary(path: Path) -> str:
    if not (path / ".git").exists():
        return "Projet sans dépôt Git local."
    def run(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=5, check=False)
        return result.stdout.strip() or result.stderr.strip() or "(aucune information)"
    return f"Branche : {run('branch', '--show-current')}\nDernier commit : {run('log', '-1', '--format=%s')}\nModifications :\n{run('status', '--short')}"


def open_project(path: Path) -> str:
    path = path.expanduser().resolve()
    if not (path / "Cargo.toml").is_file() or ROOT.resolve() not in path.parents:
        return "Ouverture refusée : projet Rust non valide dans ~/Projects."
    for editor in ("code", "codium", "zed", "cursor"):
        if shutil.which(editor):
            subprocess.Popen([editor, str(path)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Projet ouvert dans {editor} : {path.name}"
    if shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", str(path)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Dossier ouvert : {path.name} (aucun éditeur détecté)."
    return "Aucun éditeur ou gestionnaire de fichiers détecté."
