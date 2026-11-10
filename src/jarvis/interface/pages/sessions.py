from PySide6.QtWidgets import QHBoxLayout, QPushButton

from jarvis.interface.components import Card, text_view
from jarvis.interface.pages.base import DataPage


class SessionsPage(DataPage):
    def __init__(self, context):
        super().__init__(context, "Sessions", "Retrouver votre contexte de travail, sans modifier les fichiers source.")
        self.views = {}
        for key, title in [("project", "PROJET ACTIF"), ("saved", "DERNIÈRE SAUVEGARDE"),
                           ("files", "FICHIERS SUIVIS"), ("history", "HISTORIQUE DES REPRISES")]:
            card = Card(title)
            view = text_view()
            card.body.addWidget(view)
            self.views[key] = view
            self.body.addWidget(card)
        actions = QHBoxLayout()
        for title, command in [("Sauvegarder la session", "sauvegarde ma session"),
                               ("Restaurer la session", "reprends ma session")]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, text=command: context.commands.submit(text))
            actions.addWidget(button)
        self.body.insertLayout(3, actions)

    def load(self):
        return self.context.service.session()

    def render(self, value):
        for key, view in self.views.items():
            view.setPlainText(value[key])
