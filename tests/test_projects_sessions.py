import json
import subprocess
from unittest.mock import Mock
import pytest
from jarvis.projects import manager, sessions
from jarvis.modules import projects as legacy


def test_discovery_depth_hidden_and_symlinks(isolated, tmp_path):
    for name, marker in [("rust", "Cargo.toml"), ("group/python", "pyproject.toml"), ("a/b/c", "requirements.txt"), ("x/y/z/deep", "Cargo.toml"), (".hidden", "Cargo.toml"), ("target", "Cargo.toml")]:
        p = isolated / name
        p.mkdir(parents=True, exist_ok=True)
        (p / marker).touch()
    outside = tmp_path / "external"
    outside.mkdir()
    (outside / "Cargo.toml").touch()
    (isolated / "link").symlink_to(outside, target_is_directory=True)
    assert {p["name"] for p in manager.discover_projects()} == {"rust", "python", "c"}
    assert set(legacy.rust_projects()) == {isolated / "rust", isolated / ".hidden", isolated / "target"}


def test_project_resume_objective_history(project, monkeypatch):
    monkeypatch.setattr(manager, "open_editor", lambda p: "code")
    monkeypatch.setattr(manager, "git_summary", lambda p: "Git simulé")
    assert "SESSION REPRISE" in manager.open_named_project("projetecole")
    assert manager.get_active_project()["path"] == project
    assert "enregistré" in manager.set_objective("Réviser ABC")
    assert "Réviser ABC" in manager.active_project_text()
    assert project.name in manager.recent_sessions()
    assert "500" in manager.set_objective("x" * 501)
    assert "Non" not in manager.resume_language("Python")


def test_ambiguity_and_outside_project(project, isolated, tmp_path):
    second = isolated / "group" / project.name
    second.mkdir(parents=True)
    (second / "pyproject.toml").touch()
    assert "Plusieurs" in manager.open_named_project(project.name)
    assert "refusé" in manager.resume({"path": tmp_path, "language": "Python"})


def test_track_save_restore(project, monkeypatch):
    monkeypatch.setattr(sessions, "git_summary", lambda p: "snapshot")
    assert "Fichier suivi" in sessions.track_file("Ébauche.py")
    assert "Fichier suivi" in sessions.track_file("Ébauche.py")
    assert sessions.tracked_files(project) == ["Ébauche.py"]
    assert "SAUVEGARDÉE" in sessions.save_session()
    assert "Fichiers : 1" in sessions.session_info()
    workspace = Mock()
    editor = Mock(return_value="éditeur")
    terminal = Mock(return_value="terminal")
    monkeypatch.setattr(sessions, "switch_workspace", workspace)
    monkeypatch.setattr(sessions, "launch_editor", editor)
    monkeypatch.setattr(sessions, "launch_terminal", terminal)
    assert "RESTAURÉE" in sessions.restore_session()
    workspace.assert_called_once_with()
    editor.assert_called_once_with(project, ["Ébauche.py"])
    terminal.assert_called_once_with(project)


def test_path_escape_and_replaced_symlink(project, tmp_path, monkeypatch):
    outside = tmp_path / "private.txt"
    outside.write_text("private")
    (project / "link").symlink_to(outside)
    assert "refusé" in sessions.track_file("link")
    assert "refusé" in sessions.track_file(str(outside))
    assert "refusé" in sessions.track_file("../../private.txt")
    popen = Mock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(sessions.shutil, "which", lambda app: "/usr/bin/" + app)
    sessions.launch_editor(project, ["link", "../../private.txt", "Ébauche.py"])
    args = popen.call_args.args[0]
    assert str(outside) not in args
    assert str(project / "Ébauche.py") in args


def test_corrupt_session_and_hypr_failure(project, monkeypatch):
    monkeypatch.setattr(sessions, "git_summary", lambda p: "snapshot")
    sessions.save_session()
    monkeypatch.setattr(sessions, "switch_workspace", Mock(side_effect=RuntimeError("no display")))
    assert "Impossible" in sessions.restore_session()
    with manager.database() as db:
        db.execute("UPDATE saved_sessions SET files_json = ?", (json.dumps({"bad": 1}),))
    with pytest.raises(ValueError):
        sessions.restore_session()


def test_git_read_only_and_timeout(project, monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0, "main\n", ""))
    monkeypatch.setattr(subprocess, "run", run)
    assert "main" in manager.git_summary(project)
    assert [c.args[0][3] for c in run.call_args_list] == ["branch", "log", "status"]
    assert all(c.kwargs["timeout"] == 5 and "shell" not in c.kwargs for c in run.call_args_list)
    run.side_effect = subprocess.TimeoutExpired("git", 5)
    assert "inaccessible" in manager.git_summary(project)


def test_git_destructive_queries_rejected(project):
    with pytest.raises(ValueError):
        manager.git(project, "reset", "--hard")
    with pytest.raises(ValueError):
        manager.git(project, "checkout", "main")


def test_project_named_jarvis_is_not_an_address(isolated, monkeypatch):
    for name in ("Jarvis Demo", "Demo"):
        path = isolated / name
        path.mkdir()
        (path / "pyproject.toml").touch()
    monkeypatch.setattr(manager, "resume", lambda project: project["name"])
    assert manager.open_named_project("Jarvis Demo") == "Jarvis Demo"
    assert manager.open_named_project("Demo") == "Demo"
