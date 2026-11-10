"""Une tâche à la fois par runner ; seuls les slots GUI manipulent les widgets."""
import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot


class Task(QThread):
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, function: Callable[[], object], parent=None):
        super().__init__(parent)
        self.function = function

    def run(self) -> None:
        try:
            self.result.emit(self.function())
        except Exception as error:
            logging.getLogger(__name__).error("background_task_failed", extra={
                "error_type": type(error).__name__,
            })
            self.failed.emit(type(error).__name__)


class Runner(QObject):
    result = Signal(object)
    failed = Signal(str)
    idle = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.task: Task | None = None
        self.stopped = False

    def start(self, function: Callable[[], object]) -> bool:
        if self.task is not None or self.stopped:
            return False
        self.task = Task(function, self)
        self.task.result.connect(self.result)
        self.task.failed.connect(self.failed)
        self.task.finished.connect(self._finished)
        self.task.start()
        return True

    @Slot()
    def _finished(self) -> None:
        if self.task is not None:
            self.task.deleteLater()
            self.task = None
        self.idle.emit()

    @Slot()
    def shutdown(self) -> None:
        self.stopped = True
        if self.task is not None:
            # Ne jamais détruire un QThread actif ni interrompre une transaction.
            self.task.wait()
