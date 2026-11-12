import subprocess
from unittest.mock import Mock

import pytest

from jarvis.integrations.desktop import focus_workspace
from jarvis.modes import manager as modes


@pytest.mark.parametrize(("name", "workspace"), [("travail", 3), ("gaming", 4), ("etudes", 5)])
def test_modes_launch_and_no_duplicate(name, workspace, monkeypatch):
    switch = Mock()
    launch = Mock(return_value="application")
    popen = Mock()
    monkeypatch.setattr(modes, "switch_workspace", switch)
    monkeypatch.setattr(modes, "launch", launch)
    monkeypatch.setattr(modes.shutil, "which", lambda app: "/usr/bin/" + app)
    monkeypatch.setattr(subprocess, "Popen", popen)
    assert "MODE" in modes.activate_mode(name)
    switch.assert_called_once_with(workspace)
    assert modes.current_mode() == name
    if name == "etudes":
        assert popen.call_args.args[0] == ["/usr/bin/gtk-launch", "notion"]
        assert launch.call_args.args[0] == modes.settings.browsers
    count = launch.call_count

    result = modes.activate_mode(name)

    assert "MODE" in result
    assert launch.call_count > count
    assert modes.current_mode() == name

def test_mode_hypr_failure_does_not_save_or_launch(monkeypatch):
    monkeypatch.setattr(modes, "switch_workspace", Mock(side_effect=RuntimeError("refusé")))
    launch = Mock()
    monkeypatch.setattr(modes, "launch", launch)
    assert "Erreur Hyprland" in modes.activate_mode("gaming")
    launch.assert_not_called()
    assert not modes.STATE_PATH.exists()


def test_mode_untrusted_project_not_opened(project, tmp_path, monkeypatch):
    from jarvis.projects.manager import database
    with database() as db:
        db.execute("UPDATE projects SET path = ?", (str(tmp_path),))
    monkeypatch.setattr(modes, "switch_workspace", Mock())
    launch = Mock(return_value=None)
    monkeypatch.setattr(modes, "launch", launch)
    terminal_launch = Mock(return_value="Terminal déjà ouvert")

    monkeypatch.setattr(
        modes,
        "launch_terminal_on_workspace",
        terminal_launch,
    )
    modes.activate_mode("travail")
    assert launch.call_args_list[0].args[1] == []


@pytest.mark.parametrize(("style", "expected"), [
    ("command", ["hyprctl", "dispatch", "hl.dsp.focus({workspace=3})"]),
    ("mode", ["hyprctl", "dispatch", 'hl.dsp.focus({ workspace = "3" })']),
    ("session", ["hyprctl", "eval", "hl.dispatch(hl.dsp.focus({workspace=3}))"]),
])
def test_historical_lua_forms(style, expected, monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0, "ok", ""))
    monkeypatch.setattr(subprocess, "run", run)
    focus_workspace(3, style)
    assert run.call_args.args[0] == expected
    run.return_value.stdout = "error: invalid"
    with pytest.raises(RuntimeError):
        focus_workspace(3, style)


@pytest.mark.parametrize("number", [0, 10, True, '3});evil()'])
def test_invalid_workspace(number):
    with pytest.raises(ValueError):
        focus_workspace(number)


def test_corrupt_mode_state():
    modes.STATE_PATH.write_text("not json")
    assert modes.current_mode() is None
    modes.STATE_PATH.write_text("[]")
    assert modes.current_mode() is None

def test_launch_reuses_existing_application(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    existing = SimpleNamespace(app="code")

    detector = Mock(return_value=[existing])
    launcher = Mock()

    monkeypatch.setattr(
        modes,
        "existing_application",
        detector,
    )
    monkeypatch.setattr(
        modes.subprocess,
        "Popen",
        launcher,
    )

    result = modes.launch(["code"])

    assert "déjà ouvert" in result
    launcher.assert_not_called()
