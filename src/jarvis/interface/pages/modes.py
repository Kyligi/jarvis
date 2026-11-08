from PySide6.QtWidgets import QPushButton, QHBoxLayout
from jarvis.config import settings
from jarvis.modes.manager import MODES
from jarvis.interface.pages.base import DataPage
from jarvis.interface.components import Card, label


class ModesPage(DataPage):
    def __init__(self, context):
        super().__init__(context, "Modes", "Trois environnements familiers. Aucune application n'est fermée automatiquement.")
        self.current = label("Aucun mode enregistré", "status")
        self.body.addWidget(self.current)
        self.requested = label("Aucune demande de mode dans cette exécution.", "muted")
        self.body.addWidget(self.requested)
        context.commands.started.connect(self.update_requested)
        programs = {
            "travail": "Éditeur : " + " / ".join(settings.editors) + f" · Terminal : {settings.terminal}",
            "gaming": settings.gaming,
            "etudes": "Navigateur : " + " / ".join(settings.browsers) + f" · Notion : {settings.desktop_launcher} {settings.notion_desktop}",
        }
        self.buttons = {}
        cards = QHBoxLayout()
        for name, display in [("travail", "Travail"), ("gaming", "Gaming"), ("etudes", "Études")]:
            profile = MODES[name]
            card = Card(f"{display.upper()}  /  WORKSPACE {profile['workspace']}")
            card.body.addWidget(label(profile["description"], "subheading"))
            card.body.addWidget(label(programs[name], "muted"))
            button = QPushButton(f"Activer {display}")
            button.clicked.connect(lambda checked=False, text=display: context.commands.submit(f"mode {text}"))
            context.commands.busy_changed.connect(lambda busy, b=button: b.setEnabled(not busy))
            button.setEnabled(not context.commands.busy)
            self.buttons[name] = button
            card.body.addWidget(button)
            cards.addWidget(card, 1)
        self.body.addLayout(cards)
        self.body.addWidget(label("Réactiver le même mode affiche son workspace sans relancer les applications. Le statut indique le dernier mode enregistré.", "muted"))
        self.body.addStretch()

    def load(self):
        return self.context.service.modes()

    def render(self, value):
        self.current.setText("Dernier mode enregistré : " + (value.get("mode") or "aucun").capitalize())

    def update_requested(self, identifier):
        name = self.context.commands.last_requested_mode
        if name:
            self.requested.setText(f"Dernière demande dans cette exécution : {name.capitalize()}")
