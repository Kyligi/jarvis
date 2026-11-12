"""Tests de stabilité des workers Qt de Jarvis."""

import threading

from PySide6.QtCore import QCoreApplication, QEvent

from jarvis.interface.workers import Runner


def flush_qt(qapp):
    """Traite les signaux et destructions différées."""
    qapp.processEvents()

    QCoreApplication.sendPostedEvents(
        None,
        QEvent.Type.DeferredDelete,
    )

    qapp.processEvents()


def test_shutdown_waits_for_running_worker(qapp):
    """L'arrêt attend réellement une tâche active."""

    runner = Runner()
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def operation():
        started.set()

        if not release.wait(timeout=2):
            raise RuntimeError("Test timeout")

        finished.set()
        return "Terminé"

    assert runner.start(operation)
    assert started.wait(timeout=2)

    # Libérer le worker depuis un autre thread
    # pendant que Runner.shutdown() attend.
    timer = threading.Timer(
        0.05,
        release.set,
    )
    timer.daemon = True
    timer.start()

    try:
        runner.shutdown()
    finally:
        release.set()
        timer.join(timeout=2)

    assert finished.is_set()
    assert runner.stopped

    flush_qt(qapp)


def test_shutdown_refuses_new_tasks(qapp):
    """Aucune nouvelle tâche après la fermeture."""

    runner = Runner()
    runner.shutdown()

    executed = []

    assert not runner.start(
        lambda: executed.append("unexpected")
    )

    flush_qt(qapp)

    assert executed == []


def test_finished_worker_can_be_cleaned_up(qapp):
    """Qt traite les signaux et DeferredDelete."""

    runner = Runner()
    worker_finished = threading.Event()
    results = []

    runner.result.connect(results.append)

    def operation():
        worker_finished.set()
        return "OK"

    assert runner.start(operation)
    assert worker_finished.wait(timeout=2)

    # shutdown() attend la fin réelle du QThread.
    runner.shutdown()

    flush_qt(qapp)

    assert results == ["OK"]
    assert runner.task is None


def test_late_idle_cannot_restart_worker(qapp):
    """Un signal idle tardif ne contourne pas shutdown."""

    runner = Runner()
    worker_finished = threading.Event()
    executions = []

    def operation():
        executions.append("first")
        worker_finished.set()
        return "OK"

    # Simulation d'un composant qui souhaite
    # lancer une tâche dès que le worker est libre.
    runner.idle.connect(
        lambda: runner.start(
            lambda: executions.append("second")
        )
    )

    assert runner.start(operation)
    assert worker_finished.wait(timeout=2)

    runner.shutdown()

    flush_qt(qapp)

    assert executions == ["first"]
    assert runner.stopped
