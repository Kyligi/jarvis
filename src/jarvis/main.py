import sys
from PySide6.QtWidgets import QApplication
from jarvis.interface.mini import JarvisWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = JarvisWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
