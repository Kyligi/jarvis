"""Fenêtre HUD unique, masquée à la fermeture et réutilisée par Mini."""
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Slot
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QListWidget, QStackedWidget, QScrollArea,
                              QGraphicsOpacityEffect, QPushButton, QSplitter)
from jarvis.interface import theme
from jarvis.interface.components import CommandConsole, label
from jarvis.interface.pages.home import HomePage
from jarvis.interface.pages.system import SystemPage
from jarvis.interface.pages.projects import ProjectsPage
from jarvis.interface.pages.sessions import SessionsPage
from jarvis.interface.pages.modes import ModesPage
from jarvis.interface.pages.settings import SettingsPage


class HudWindow(QMainWindow):
    def __init__(self, context, mini=None):
        # Pas de parent natif : le HUD n'est pas une fenêtre transitoire du
        # workspace spécial de Mini. La référence Python reste détenue par Mini.
        super().__init__()
        self.context = context
        self.mini = mini
        self.setWindowTitle("J.A.R.V.I.S. — HUD")
        self.setObjectName("jarvisHud")
        self.setStyleSheet(theme.STYLE)
        self.resize(1180, 780)
        self.setMinimumSize(900, 640)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(24, 22, 24, 22)
        outer.setSpacing(24)
        sidebar = QVBoxLayout()
        sidebar.addWidget(label("J.A.R.V.I.S.", "subheading"))
        sidebar.addWidget(label("NEBULA / CONTROL CENTER", "eyebrow"))
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setAccessibleName("Navigation du HUD")
        self.navigation.setFixedWidth(185)
        self.navigation.addItems(["01   Accueil", "02   Système", "03   Projets", "04   Sessions", "05   Modes", "06   Paramètres"])
        sidebar.addWidget(self.navigation, 1)
        mini_button = QPushButton("Retour à Mini")
        mini_button.clicked.connect(self.show_mini)
        sidebar.addWidget(mini_button)
        sidebar.addWidget(label("LOCAL · CONTRÔLÉ\nVos outils, votre contexte.", "muted"))
        outer.addLayout(sidebar)
        content = QVBoxLayout()
        header = QHBoxLayout()
        header.addWidget(label("PERSONAL OPERATING ASSISTANT", "eyebrow"), 1)
        self.connection = label("● Services locaux", "status")
        header.addWidget(self.connection)
        content.addLayout(header)
        self.stack = QStackedWidget()
        self.pages = [HomePage(context), SystemPage(context), ProjectsPage(context),
                      SessionsPage(context), ModesPage(context), SettingsPage(context)]
        for page in self.pages:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        self.effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self.effect)
        self.effect.setOpacity(1)
        self.animation = QPropertyAnimation(self.effect, b"opacity", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.console = CommandConsole(context.commands)
        self.console.setMinimumHeight(155)
        self.console.output.setMaximumHeight(180)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.stack)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        content.addWidget(splitter, 1)
        outer.addLayout(content, 1)
        self.navigation.currentRowChanged.connect(self.navigate)
        self.navigation.setCurrentRow(0)
        self.focus_command = QShortcut(QKeySequence("Ctrl+L"), self)
        self.focus_command.activated.connect(self.console.command.setFocus)
        context.commands.completed.connect(self.refresh_current)
        context.preferences_changed.connect(self.preferences_changed)
        context.monitor.failed.connect(self.monitor_failed)
        context.monitor.updated.connect(self.monitor_ready)

    def show(self):
        # Qt Wayland lit desktopFileName à la création du rôle xdg_toplevel.
        # Un identifiant limité à cette présentation protège class:jarvis
        # dans le script existant, sans créer un processus supplémentaire.
        app = QApplication.instance()
        previous = app.desktopFileName()
        app.setDesktopFileName("jarvis-hud")
        try:
            super().show()
        finally:
            app.setDesktopFileName(previous)

    def showEvent(self, event):
        super().showEvent(event)
        self.pages[self.stack.currentIndex()].set_active(True)

    def hideEvent(self, event):
        for page in self.pages:
            page.set_active(False)
        self.animation.stop()
        self.effect.setOpacity(1)
        super().hideEvent(event)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if self.mini is not None:
            self.mini.show()

    @Slot(int)
    def navigate(self, index):
        if not 0 <= index < len(self.pages):
            return
        for i, page in enumerate(self.pages):
            page.set_active(i == index and self.isVisible())
        self.stack.setCurrentIndex(index)
        self.animation.stop()
        if self.context.preferences.animations and self.isVisible():
            self.animation.setStartValue(0.75)
            self.animation.setEndValue(1.0)
            self.animation.start()
        else:
            self.effect.setOpacity(1)

    @Slot()
    def refresh_current(self):
        if self.isVisible():
            self.pages[self.stack.currentIndex()].refresh()

    @Slot(object)
    def preferences_changed(self, value):
        if not value.animations:
            self.animation.stop()
            self.effect.setOpacity(1)

    @Slot(str)
    def monitor_failed(self, error):
        self.connection.setText(f"Mesures indisponibles ({error})")

    @Slot(object)
    def monitor_ready(self, snapshot):
        self.connection.setText("● Services locaux")

    @Slot()
    def show_mini(self):
        if self.mini is not None:
            self.mini.show()
            self.mini.raise_()
            self.mini.activateWindow()
        self.hide()
