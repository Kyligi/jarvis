import threading
import time
from PySide6.QtCore import QTimer, QThread
from jarvis.interface.workers import Runner
from jarvis.monitoring.collector import Snapshot, Collector


def pump(qapp, predicate, timeout=3):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.005)
    assert predicate()


def test_worker_keeps_event_loop_alive_and_serializes(qapp):
    runner = Runner()
    release = threading.Event()
    results = []
    runner.result.connect(results.append)
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(5)
    try:
        assert runner.start(lambda: (release.wait(2), "result")[1])
        assert not runner.start(lambda: "duplicate")
        pump(qapp, lambda: len(ticks) >= 3)
        assert results == []
        release.set()
        pump(qapp, lambda: runner.task is None)
        assert results == ["result"]
    finally:
        release.set()
        runner.shutdown()
        timer.stop()


def test_dashboard_snapshot_and_command(qapp, monkeypatch):
    from jarvis.interface import mini
    snapshot = Snapshot(30, 40, 50, None, {"CPU AMD": 55})
    monkeypatch.setattr(Collector, "collect", lambda self: snapshot)
    worker_threads = []
    def execute(command):
        worker_threads.append(QThread.currentThread())
        return "Réponse simulée"
    monkeypatch.setattr(mini, "execute", execute)
    window = mini.JarvisWindow()
    try:
        pump(qapp, lambda: window.dashboard.runner.task is None)
        assert window.dashboard.cpu.value.text() == "30,0 %"
        assert window.dashboard.ram.value.text() == "40,0 %"
        assert not hasattr(window.dashboard, "graph")
        assert "CPU AMD : 55,0 °C" in window.dashboard.temperature.text()
        assert window.dashboard.timer.interval() == 2000
        window.command.setText("aide")
        window.run_command()
        pump(qapp, lambda: window.runner.task is None)
        assert window.output.toPlainText() == "Réponse simulée"
        assert window.command.isEnabled()
        assert worker_threads[0] != qapp.thread()
        # Rendu Qt hors écran : vérifie les cartes numériques.
        window.dashboard.apply_snapshot(snapshot)
        assert not window.grab().isNull()
    finally:
        window.close()


def test_worker_error_recovers(qapp):
    runner = Runner()
    errors = []
    runner.failed.connect(errors.append)
    def fail():
        raise OSError("private")
    runner.start(fail)
    pump(qapp, lambda: runner.task is None)
    assert errors == ["OSError"]
    assert runner.start(lambda: "retry")
    runner.shutdown()
    pump(qapp, lambda: runner.task is None)
    assert not runner.start(lambda: None)


def test_dashboard_collection_failure_is_visible(qapp, monkeypatch):
    from jarvis.interface import mini
    def fail(self):
        raise OSError("unavailable")
    monkeypatch.setattr(Collector, "collect", fail)
    window = mini.JarvisWindow()
    try:
        pump(qapp, lambda: window.dashboard.runner.task is None)
        assert "Monitoring indisponible : OSError" in window.dashboard.temperature.text()
        assert window.dashboard.timer.isActive()
    finally:
        window.close()
