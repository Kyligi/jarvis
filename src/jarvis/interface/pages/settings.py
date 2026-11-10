from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
)

from jarvis import preferences
from jarvis.config import settings
from jarvis.interface.components import Card, label, text_view
from jarvis.interface.pages.base import DataPage
from jarvis.preferences import Preferences


class SettingsPage(DataPage):
    def __init__(self, context):
        super().__init__(context, "Paramètres", "Nebula · préférences d'interface appliquées aux deux fenêtres")
        self.refresh_button.hide()
        card = Card("APPARENCE & MONITORING")
        form = QFormLayout()
        self.animations = QCheckBox("Transitions discrètes (180 ms)")
        self.interval = QSpinBox()
        self.interval.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.interval.setToolTip("De 1 à 30 secondes ; saisie directe ou flèches haut/bas.")
        self.interval.setRange(1, 30)
        self.interval.setSuffix(" s")
        form.addRow("Animations", self.animations)
        form.addRow("Rafraîchissement", self.interval)
        card.body.addLayout(form)
        self.save_button = QPushButton("Enregistrer et appliquer")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        card.body.addWidget(self.save_button)
        self.body.addWidget(card)
        self.body.addWidget(label(f"J.A.R.V.I.S. {version('jarvis')} · PySide6 / Qt Widgets\nMini : SUPER + SHIFT + J\nHUD : bouton depuis Mini · commande globale : Ctrl+L\nLogs du lanceur : {Path.home() / '.local/state/jarvis.log'}\nPréférences : {preferences.PREFERENCES_PATH}", "muted"))
        self.body.addWidget(label("Configuration métier TOML · lecture seule dans le HUD", "subheading"))
        self.config = text_view()
        self.config.setPlainText("\n".join(f"{key} = {value}" for key, value in asdict(settings).items()))
        self.body.addWidget(self.config)
        self.body.addWidget(label("Modifier le TOML puis redémarrer pour changer les chemins ou programmes. Les préférences visuelles sont enregistrées séparément, sans réécrire ce fichier.", "muted"))
        context.preferences_changed.connect(self.render)
        context.preferences_saved.connect(self.saved)
        context.preferences_failed.connect(self.failure)
        context.preference_runner.idle.connect(lambda: self.save_button.setEnabled(True))
        self.render(context.preferences)

    def refresh(self):
        if self.active:
            self.state.setText(self.context.preference_warning or "Préférences actuelles")

    def set_active(self, active):
        self.active = active
        if active:
            self.render(self.context.preferences)
            self.state.setText(self.context.preference_warning or "Préférences actuelles")

    def render(self, value):
        self.animations.setChecked(value.animations)
        self.interval.setValue(value.refresh_seconds)

    @Slot()
    def save(self):
        value = Preferences(self.animations.isChecked(), self.interval.value())
        if self.context.save_preferences(value):
            self.save_button.setEnabled(False)
            self.state.setText("Enregistrement…")

    @Slot()
    def saved(self):
        self.state.setText("Préférences enregistrées et appliquées.")

    @Slot(str)
    def failure(self, error):
        self.state.setText(f"Enregistrement impossible ({error}). Préférences actuelles conservées.")
