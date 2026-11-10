from unittest.mock import Mock

import pytest

from jarvis import preferences
from jarvis.preferences import Preferences


def test_roundtrip_and_no_business_config_change(tmp_path):
    path = tmp_path / "ui.toml"
    config = tmp_path / "config.toml"
    config.write_text('# Commentaire utilisateur\nterminal="foot"\n')
    original = config.read_bytes()
    assert preferences.load_preferences(path) == Preferences()
    preferences.save_preferences(Preferences(False, 12), path)
    assert preferences.load_preferences(path) == Preferences(False, 12)
    assert config.read_bytes() == original


@pytest.mark.parametrize("value", ['animations="yes"', 'refresh_seconds=true', 'refresh_seconds=0', 'refresh_seconds=31', 'surprise=1', 'bad = ['])
def test_invalid_preferences_preserved(tmp_path, value):
    path = tmp_path / "ui.toml"
    path.write_text(value)
    with pytest.raises((ValueError, TypeError)):
        preferences.load_preferences(path)
    assert path.read_text() == value


def test_atomic_failure_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "ui.toml"
    preferences.save_preferences(Preferences(), path)
    original = path.read_bytes()
    monkeypatch.setattr(preferences.os, "fsync", Mock(side_effect=OSError("disk")))
    with pytest.raises(OSError):
        preferences.save_preferences(Preferences(False, 5), path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".ui-*"))
