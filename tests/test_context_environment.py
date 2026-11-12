"""Tests du diagnostic d'environnement Jarvis."""

from types import SimpleNamespace

from jarvis.context.environment import inspect_environment
from jarvis.modes.manager import MODES
from jarvis.services.windows import WindowError
from jarvis.config import settings

def window(workspace=1):
    return SimpleNamespace(workspace=workspace)


def test_work_environment_complete():
    target = MODES["travail"]["workspace"]

    def inventory(names):
        if names == list(settings.editors):
            return [window(1)]
        return [window(target)]

    report = inspect_environment(
        "travail", inventory=inventory
    )

    assert report.status == "complete"
    assert not report.needs_restore


def test_terminal_missing_on_target_workspace():
    def inventory(names):
        return [window(1)]

    report = inspect_environment(
        "travail", inventory=inventory
    )

    assert report.status == "incomplete"
    assert "Foot" in report.missing
    assert report.needs_restore


def test_missing_editor():
    target = MODES["travail"]["workspace"]

    def inventory(names):
        if names == list(settings.editors):
            return []
        return [window(target)]

    report = inspect_environment(
        "travail", inventory=inventory
    )

    assert "Éditeur" in report.missing
    assert "Foot" in report.present


def test_gaming_complete():
    report = inspect_environment(
        "gaming",
        inventory=lambda names: [window(1)],
    )

    assert report.status == "complete"


def test_gaming_missing():
    report = inspect_environment(
        "gaming",
        inventory=lambda names: [],
    )

    assert report.status == "incomplete"
    assert report.missing == ("Steam",)


def test_studies_missing_notion():
    def inventory(names):
        if names == ["notion"]:
            return []
        return [window()]

    report = inspect_environment(
        "etudes", inventory=inventory
    )

    assert report.missing == ("Notion",)
    assert "Navigateur" in report.present


def test_inventory_unavailable():
    def inventory(names):
        raise WindowError("Hyprland indisponible")

    report = inspect_environment(
        "travail", inventory=inventory
    )

    assert report.status == "unknown"
    assert not report.needs_restore


def test_inventory_none():
    report = inspect_environment(
        "travail",
        inventory=lambda names: None,
    )

    assert report.status == "unknown"


def test_unknown_mode():
    report = inspect_environment(
        "inconnu",
        inventory=lambda names: [],
    )

    assert report.status == "unknown"
    assert report.missing == ()
