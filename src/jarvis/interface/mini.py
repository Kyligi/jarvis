"""Mini conserve son identité jarvis et possède le contexte de l'application."""
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from jarvis.core.commands import execute
from jarvis.interface import theme
from jarvis.interface.components import CommandConsole, label
from jarvis.interface.context import AppContext
from jarvis.interface.dashboard import MonitorDashboard


class JarvisWindow(QWidget):
    def __init__(self, context=None):
        super().__init__()
        self.context = context or AppContext(executor=lambda text: execute(text))
        self.hud = None
        self.context.commands.page_requested.connect(self.open_page)
        self.setWindowTitle("J.A.R.V.I.S. — Omarchy")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setStyleSheet(theme.STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(label("J.A.R.V.I.S.", "subheading"))
        self.ai_status = label('', 'eyebrow')
        title.addWidget(self.ai_status)
        header.addLayout(title, 1)
        self.hud_button = QPushButton("Ouvrir le HUD  ↗")
        self.hud_button.setObjectName("primary")
        self.hud_button.clicked.connect(self.open_hud)
        header.addWidget(self.hud_button)
        layout.addLayout(header)
        self.dashboard = MonitorDashboard(self, self.context.monitor, compact=True)
        layout.addWidget(self.dashboard)
        from jarvis.interface.voice import VoiceControls
        self.voice_controls = VoiceControls(self.context.voice)
        layout.addWidget(self.voice_controls)
        self.console = CommandConsole(self.context.commands)
        layout.addWidget(self.console, 1)
        self.context.commands.ai_event.connect(self.ai_update)
        self.context.commands.result.connect(lambda _: self.ai_update({'kind': 'idle'}))
        self.ai_update({'kind': 'idle'})
        # Attributs de compatibilité utilisés par les tests et appelants V1.0.
        self.output = self.console.output
        self.command = self.console.command
        self.button = self.console.button
        self.runner = self.context.commands.runner
        self.command.setFocus()
        self.setMinimumSize(760, 620)
        self.resize(760, 680)

    @Slot(object)
    def ai_update(self, event):
        if event.get('cancelled') and event['cancelled'].is_set() and event['kind'] not in ('cleared', 'stopped', 'idle'):
            return
        if event['kind'] in ('waiting', 'progress'):
            self.ai_status.setText('IA locale · génération en cours…')
        elif event['kind'] in ('idle', 'stopped', 'cleared'):
            config = self.context.commands.conversation.config
            self.ai_status.setText('NEBULA / MINI · IA locale ' + (config.model if config.enabled else 'désactivée'))

    @Slot()
    def run_command(self):
        self.console.submit()

    @Slot()
    def open_hud(self):
        if self.hud is None:
            from jarvis.interface.hud import HudWindow
            self.hud = HudWindow(self.context, self)
        self.hud.show()
        self.hud.raise_()
        self.hud.activateWindow()

    @Slot(str)
    def open_page(self, name):
        self.open_hud()
        self.hud.navigation.setCurrentRow(9 if name == 'assistant' else 8 if name == 'voice' else 7 if name == 'scenarios' else 4)
        if name.startswith('modes:'):
            page = self.hud.pages[4]
            page.tabs.setCurrentIndex(page.mode_names.index(name.split(':', 1)[1]))

    def showEvent(self, event):
        self.dashboard.set_active(True)
        super().showEvent(event)

    def hideEvent(self, event):
        if self.hud is None or not self.hud.isVisible():
            self.context.voice.controller.cancel()
        self.dashboard.set_active(False)
        super().hideEvent(event)

    def closeEvent(self, event):
        # Fermer Mini quitte les deux interfaces ; masquer via Hyprland ne
        # déclenche pas closeEvent et conserve l'instance existante.
        if self.hud is not None:
            self.hud.hide()
            self.hud.deleteLater()
            self.hud = None
        self.context.shutdown()
        super().closeEvent(event)
