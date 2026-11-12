"""Tests du moteur de contexte Jarvis V1.7."""

from pathlib import Path
from types import SimpleNamespace

from jarvis.context.models import ContextSnapshot
from jarvis.context.service import ContextService
from jarvis.services.windows import WindowError


def make_service(
    window=None,
    mode="travail",
    project=None,
    monitor=None,
):
    return ContextService(
        window_reader=lambda: window,
        mode_reader=lambda: mode,
        project_reader=lambda: project,
        monitor_reader=lambda: monitor,
    )


def test_empty_context():
    service = make_service(
        mode=None,
        project=None,
    )

    snapshot = service.collect()

    assert isinstance(snapshot, ContextSnapshot)
    assert snapshot.active_app is None
    assert snapshot.active_mode is None
    assert snapshot.active_project is None
    assert snapshot.complete


def test_active_window():
    window = SimpleNamespace(
        app="code",
        title="Jarvis — Visual Studio Code",
        workspace=2,
    )

    snapshot = make_service(window=window).collect()

    assert snapshot.active_app == "code"
    assert snapshot.active_window_title == (
        "Jarvis — Visual Studio Code"
    )
    assert snapshot.active_workspace == 2


def test_current_mode():
    snapshot = make_service(
        mode="etudes"
    ).collect()

    assert snapshot.active_mode == "etudes"


def test_invalid_mode_is_ignored():
    snapshot = make_service(
        mode="unknown"
    ).collect()

    assert snapshot.active_mode is None


def test_active_project():
    project = Path("/home/test/Projects/jarvis")

    snapshot = make_service(
        project=project
    ).collect()

    assert snapshot.active_project == str(project)


def test_monitoring_snapshot():
    monitor = SimpleNamespace(
        cpu=23.5,
        ram=48.0,
        disk=61.2,
    )

    snapshot = make_service(
        monitor=monitor
    ).collect()

    assert snapshot.cpu_percent == 23.5
    assert snapshot.ram_percent == 48.0
    assert snapshot.disk_percent == 61.2


def test_window_failure_does_not_block_other_sources():
    def broken_window():
        raise WindowError("Hyprland indisponible")

    service = ContextService(
        window_reader=broken_window,
        mode_reader=lambda: "travail",
        project_reader=lambda: Path("/tmp/projet"),
        monitor_reader=lambda: None,
    )

    snapshot = service.collect()

    assert snapshot.active_app is None
    assert snapshot.active_mode == "travail"
    assert snapshot.active_project == "/tmp/projet"
    assert snapshot.errors == ("windows",)
    assert not snapshot.complete


def test_monitor_failure_does_not_block_context():
    def broken_monitor():
        raise RuntimeError("Monitoring indisponible")

    service = ContextService(
        window_reader=lambda: None,
        mode_reader=lambda: "gaming",
        project_reader=lambda: None,
        monitor_reader=broken_monitor,
    )

    snapshot = service.collect()

    assert snapshot.active_mode == "gaming"
    assert snapshot.cpu_percent is None
    assert snapshot.errors == ("monitor",)


def test_summary_contains_context():
    snapshot = make_service(
        window=SimpleNamespace(
            app="kitty",
            title="Terminal",
            workspace=1,
        ),
        mode="travail",
    ).collect()

    text = snapshot.summary()

    assert "kitty" in text
    assert "Terminal" in text
    assert "travail" in text


def test_context_is_read_only():
    service = make_service()
    snapshot = service.collect()

    from dataclasses import FrozenInstanceError
    import pytest

    with pytest.raises(FrozenInstanceError):
        snapshot.active_mode = "gaming"
