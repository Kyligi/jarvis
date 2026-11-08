from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton
from jarvis.core.commands import execute
from jarvis.interface.dashboard import MonitorDashboard

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
        layout.addWidget(QLabel("Jarvis V0.5 • Monitoring intelligent"))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlainText("Bonjour. Tape 'aide' pour connaître mes commandes.")
        layout.addWidget(self.output)
        self.command = QLineEdit()
        self.command.setPlaceholderText("Jarvis, reprends mon projet Rust")
        self.command.returnPressed.connect(self.run_command)
        layout.addWidget(self.command)
        button = QPushButton("EXÉCUTER")
        button.clicked.connect(self.run_command)
        layout.addWidget(button)
        self.command.setFocus()
        # Jarvis V0.5 : tableau de bord
        self.dashboard = MonitorDashboard(self)
        self.layout().insertWidget(1, self.dashboard)

        self.setMinimumSize(760, 620)
        self.resize(760, 680)

    def run_command(self):
        command = self.command.text().strip()
        if command:
            try:
                self.output.setPlainText(execute(command))
            except Exception as error:
                self.output.setPlainText(f"Erreur : {error}")
            self.command.clear()
