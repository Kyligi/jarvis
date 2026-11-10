import sqlite3
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from jarvis.monitoring import collector, diagnostics, intelligence, system


@pytest.fixture
def metrics(monkeypatch):
    ps = collector.psutil
    monkeypatch.setattr(ps, "cpu_percent", lambda **kw: 95.0)
    monkeypatch.setattr(ps, "virtual_memory", lambda: NS(percent=92, used=4e9, total=8e9))
    monkeypatch.setattr(ps, "disk_usage", lambda p: NS(percent=96, used=40e9, total=80e9))
    monkeypatch.setattr(ps, "sensors_battery", lambda: None)
    monkeypatch.setattr(ps, "boot_time", lambda: 1)
    monkeypatch.setattr(ps, "sensors_temperatures", lambda: {
        chip: [NS(current=50, label="temp")] for chip in intelligence.SENSOR_NAMES
    })


def test_all_asus_sensors_and_unavailable(metrics, monkeypatch):
    sensors = intelligence.read_sensors()
    assert len(sensors) == 5
    assert "CPU AMD / temp" in sensors
    monkeypatch.setattr(intelligence.psutil, "sensors_temperatures", Mock(side_effect=OSError))
    assert intelligence.read_sensors() == {}
    assert "Aucun" in intelligence.sensors_text()


def test_status_diagnose_battery(metrics):
    assert "CPU : 95.0" in system.system_status()
    assert "Aucune batterie" in system.battery_status()
    assert "fortement" in system.diagnose()


def test_advanced_diagnostic(metrics, monkeypatch):
    monkeypatch.setattr(diagnostics, "get_top_processes", lambda n: [])
    assert "CPU : utilisation très élevée" in diagnostics.explain_slowdown()


def test_alert_samples_and_cooldown(monkeypatch):
    notify = Mock()
    monkeypatch.setattr(intelligence, "notify", notify)
    monkeypatch.setattr(intelligence.time, "monotonic", lambda: 1000)
    engine = intelligence.AlertEngine()
    engine.check(95, 0, 0)
    engine.check(95, 0, 0)
    notify.assert_not_called()
    engine.check(95, 0, 0)
    notify.assert_called_once()
    engine.check(95, 0, 0)
    assert notify.call_count == 1
    engine.check(0, 0, 0)
    assert engine.counts["cpu"] == 0


def test_metrics_history_and_retention():
    assert "Aucune mesure" in intelligence.history_text()
    intelligence.save_metrics(10, 20, 30)
    assert "Échantillons : 1" in intelligence.history_text()
    from jarvis.persistence.sqlite import connect
    with connect(intelligence.DB_PATH) as db:
        db.execute("INSERT INTO metrics(timestamp,cpu,ram,disk) VALUES(0,1,1,1)")
    intelligence.save_metrics(20, 30, 40)
    with connect(intelligence.DB_PATH) as db:
        assert db.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 2


def test_collector_cadence_and_storage_failure(metrics, monkeypatch):
    monkeypatch.setattr(intelligence, "notify", Mock())
    save = Mock()
    monkeypatch.setattr(collector, "save_metrics", save)
    monkeypatch.setattr(collector.time, "monotonic", lambda: 100)
    c = collector.Collector()
    snapshot = c.collect()
    c.collect()
    save.assert_called_once_with(95.0, 92, 96)
    assert snapshot.battery is None
    monkeypatch.setattr(collector.time, "monotonic", lambda: 111)
    save.side_effect = sqlite3.OperationalError("locked")
    assert c.collect().warning == "Historique indisponible"


def test_process_disappears(monkeypatch):
    import psutil
    gone = Mock()
    gone.cpu_percent.side_effect = psutil.NoSuchProcess(123)
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [gone])
    monkeypatch.setattr(system.time, "sleep", lambda n: None)
    assert system.top_processes().startswith("TOP PROCESSUS")


def test_alert_history_contains_only_emitted_alerts(monkeypatch):
    monkeypatch.setattr(intelligence, "notify", Mock())
    engine = intelligence.AlertEngine()
    engine.check(95, 0, 0)
    engine.check(95, 0, 0)
    assert not engine.recent
    engine.check(95, 0, 0)
    assert len(engine.recent) == 1
    assert "CPU à 95 %" in engine.recent[0]
    engine.check(95, 0, 0)
    assert len(engine.recent) == 1
