import sys

from PySide6.QtWidgets import QApplication

from jarvis.interface.mini import JarvisWindow
from jarvis.logging_setup import configure_logging


def main() -> None:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("jarvis")
    app.setDesktopFileName("jarvis")
    if '--voice-toggle' in sys.argv:
        from jarvis.interface.voice_ipc import send_toggle
        raise SystemExit(0 if send_toggle() else 1)
    window = JarvisWindow()
    from jarvis.interface.voice_ipc import VoiceIPC
    voice_ipc = VoiceIPC(window.context.voice)
    app.aboutToQuit.connect(voice_ipc.close)
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
