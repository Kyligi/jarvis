import sys
from PySide6.QtWidgets import QApplication
from jarvis.interface.mini import JarvisWindow
from jarvis.logging_setup import configure_logging


def main() -> None:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("jarvis")
    app.setDesktopFileName("jarvis")
    window = JarvisWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
