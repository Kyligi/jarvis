"""Same-user local IPC: only toggle/stop, never arbitrary commands or focus changes."""
import os
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication


def endpoint():
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime:
        return None
    path = Path(runtime)
    if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        return None
    return str(path / 'jarvis-voice.sock')


def send_toggle():
    name = endpoint()
    if not name:
        return False
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(500):
        return False
    socket.write(b'toggle\n')
    success = socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return success


class VoiceIPC(QObject):
    def __init__(self, bridge):
        super().__init__(bridge)
        self.bridge = bridge
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.accept)
        self.name = endpoint()
        if self.name:
            probe = QLocalSocket()
            probe.connectToServer(self.name)
            if probe.waitForConnected(100):
                probe.disconnectFromServer()
                self.name = None  # another Jarvis owns this endpoint
            else:
                QLocalServer.removeServer(self.name)
                if not self.server.listen(self.name):
                    self.name = None

    def accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.setReadBufferSize(32)
            socket.readyRead.connect(lambda socket=socket: self.read(socket))
            socket.disconnected.connect(socket.deleteLater)
            QTimer.singleShot(1000, socket, socket.disconnectFromServer)
            if socket.bytesAvailable():
                self.read(socket)

    def read(self, socket):
        payload = bytes(socket.readAll())
        if payload == b'toggle\n':
            # Never start a hidden microphone. Stop is always allowed.
            visible = any(w.isVisible() and type(w).__name__ in ('JarvisWindow', 'HudWindow')
                          for w in QApplication.topLevelWidgets())
            if visible or self.bridge.controller.snapshot.state == 'listening':
                self.bridge.toggle()
        socket.disconnectFromServer()

    def close(self):
        self.server.close()
