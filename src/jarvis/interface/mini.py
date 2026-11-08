from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton
from jarvis.core.commands import execute
from jarvis.interface.dashboard import MonitorDashboard
from jarvis.interface.workers import Runner

class JarvisWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. — Omarchy")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setStyleSheet("""
            QWidget { background-color: #0b1220; color: #d8edff; font-size: 14px; }
            QLineEdit, QTextEdit { background-color: #17243a; border: 1px solid #345b76; border-radius: 8px; padding: 10px; }
            QPushButton { background-color: #126a91; border: none; border-radius: 8px; padding: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #1789b8; }
        """)
        layout = QVBoxLayout(self)
        title = QLabel("◉  J.A.R.V.I.S.     |     OMARCHY")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #61d9ff;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Jarvis V1.0 • Monitoring intelligent"))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlainText("Bonjour. Tape 'aide' pour connaître mes commandes.")
        layout.addWidget(self.output)
        self.command = QLineEdit()
        self.command.setPlaceholderText("Jarvis, reprends mon projet Rust")
        self.command.returnPressed.connect(self.run_command)
        layout.addWidget(self.command)
        button = self.button = QPushButton("EXÉCUTER")
        button.clicked.connect(self.run_command)
        layout.addWidget(button)
        self.runner = Runner(self)
        self.runner.result.connect(self.show_result)
        self.runner.failed.connect(self.show_error)
        self.runner.idle.connect(self.command_finished)
        QApplication.instance().aboutToQuit.connect(self.runner.shutdown)
        self.command.setFocus()
        # Jarvis V0.5 : tableau de bord
        self.dashboard = MonitorDashboard(self)
        self.layout().insertWidget(1, self.dashboard)

        self.setMinimumSize(760, 620)
        self.resize(760, 680)

    @Slot()
    def run_command(self):
        command = self.command.text().strip()
        if command and self.runner.start(lambda: execute(command)):
            self.button.setEnabled(False)
            self.command.setEnabled(False)
            self.output.setPlainText("Commande en cours…")
            self.command.clear()

    @Slot(object)
    def show_result(self, result):
        self.output.setPlainText(str(result))

    @Slot(str)
    def show_error(self, error):
        self.output.setPlainText(f"Erreur Jarvis : {error}")

    @Slot()
    def command_finished(self):
        self.button.setEnabled(True)
        self.command.setEnabled(True)
        self.command.setFocus()

    def closeEvent(self, event):
        self.dashboard.timer.stop()
        self.runner.shutdown()
        self.dashboard.runner.shutdown()
        super().closeEvent(event)
