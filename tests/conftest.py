import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_PLATFORMTHEME"] = ""
os.environ["QT_STYLE_OVERRIDE"] = "Fusion"

import subprocess
from unittest.mock import Mock
import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Aucun accès aux bases utilisateur ni lancement de programme réel."""
    from jarvis.projects import manager
    from jarvis.modules import projects
    from jarvis.modes import manager as modes
    from jarvis.monitoring import intelligence
    from jarvis.memory import database
    from jarvis import preferences
    monkeypatch.setattr(preferences, "PREFERENCES_PATH", tmp_path / "ui.toml")
    from jarvis.services.windows import service
    monkeypatch.setattr(service, "windows", lambda: [])
    root = tmp_path / "Projects"
    root.mkdir()
    monkeypatch.setattr(manager, "PROJECTS_ROOT", root)
    monkeypatch.setattr(manager, "DB_PATH", tmp_path / "projects.db")
    monkeypatch.setattr(projects, "ROOT", root)
    monkeypatch.setattr(modes, "STATE_PATH", tmp_path / "active_mode.json")
    monkeypatch.setattr(intelligence, "DB_PATH", tmp_path / "performance.db")
    monkeypatch.setattr(database, "DB", tmp_path / "memory.sqlite3")
    monkeypatch.setattr(subprocess, "Popen", Mock(side_effect=AssertionError("Lancement réel interdit")))
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=AssertionError("Commande externe non simulée")))
    return root


@pytest.fixture
def project(isolated):
    from jarvis.projects.manager import database
    path = isolated / "ProjetÉcole"
    path.mkdir()
    (path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (path / "Ébauche.py").write_text("# test\n")
    with database() as db:
        db.execute("INSERT INTO projects VALUES (?, 'Python', 'Continuer', 1)", (str(path),))
    return path


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()
