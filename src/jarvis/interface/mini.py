from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton
from jarvis.core.commands import execute


class JarvisWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. — Omarchy")
        self.resize(560, 360)
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
        layout.addWidget(QLabel("Prototype V0.1 · commandes locales contrôlées"))
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

    def run_command(self):
        command = self.command.text().strip()
        if command:
            try:
                self.output.setPlainText(execute(command))
            except Exception as error:
                self.output.setPlainText(f"Erreur : {error}")
            self.command.clear()
