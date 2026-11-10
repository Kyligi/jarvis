
"""Page HUD des conversations IA persistantes de Jarvis."""

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
)

from jarvis.interface.pages.base import DataPage


class ConversationsPage(DataPage):
    """Consulter, créer, reprendre et supprimer les conversations."""

    def __init__(self, context):
        super().__init__(
            context,
            "Conversations IA",
            "Historique local · SQLite · Conversations persistantes",
        )

        self.selected_id = None

        self.body.addWidget(QLabel("CONVERSATIONS ENREGISTRÉES"))

        self.conversation_list = QListWidget()
        self.conversation_list.setAccessibleName(
            "Liste des conversations enregistrées"
        )
        self.conversation_list.setMinimumHeight(180)

        self.conversation_list.itemSelectionChanged.connect(
            self.selection_changed
        )

        self.body.addWidget(self.conversation_list)

        # Actions
        actions = QHBoxLayout()

        self.new_button = QPushButton(
            "Nouvelle conversation"
        )
        self.new_button.clicked.connect(
            self.create_conversation
        )
        actions.addWidget(self.new_button)

        self.resume_button = QPushButton(
            "Reprendre"
        )
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(
            self.resume_selected
        )
        actions.addWidget(self.resume_button)

        self.delete_button = QPushButton(
            "Supprimer"
        )
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(
            self.delete_selected
        )
        actions.addWidget(self.delete_button)

        self.body.addLayout(actions)

        # Messages de la conversation sélectionnée
        self.body.addWidget(QLabel("HISTORIQUE DES MESSAGES"))

        self.messages = QTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setMinimumHeight(260)
        self.messages.setPlaceholderText(
            "Sélectionne une conversation pour voir ses messages."
        )
        self.messages.setAccessibleName(
            "Historique de la conversation sélectionnée"
        )

        self.body.addWidget(self.messages)

    # --------------------------------------------
    # Accès aux services
    # --------------------------------------------

    @property
    def store(self):
        return self.context.commands.conversation_store

    @property
    def session(self):
        return self.context.commands.conversation

    # --------------------------------------------
    # Lecture SQLite asynchrone
    # --------------------------------------------

    def load(self):
        """Appelé par le worker de DataPage."""

        selected_id = self.selected_id
        conversations = self.store.list_conversations()

        messages = []

        if selected_id is not None:
            if any(
                record.id == selected_id
                for record in conversations
            ):
                messages = self.store.get_messages(selected_id)

        return selected_id, conversations, messages

    # --------------------------------------------
    # Affichage
    # --------------------------------------------

    def render(self, value):
        requested_id, conversations, messages = value

        # Un résultat ancien ne doit pas écraser
        # une sélection plus récente.
        if requested_id != self.selected_id:
            return

        self.conversation_list.blockSignals(True)
        self.conversation_list.clear()

        selected_row = -1

        for row, record in enumerate(conversations):
            item = QListWidgetItem(
                f"#{record.id} — {record.title}\n"
                f"Modifiée : {record.updated_at}"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                record.id,
            )

            self.conversation_list.addItem(item)

            if record.id == self.selected_id:
                selected_row = row

        if selected_row >= 0:
            self.conversation_list.setCurrentRow(selected_row)
        else:
            self.selected_id = None

        self.conversation_list.blockSignals(False)

        self.update_buttons()

        if self.selected_id is None:
            self.messages.clear()

            if conversations:
                self.state.setText(
                    f"{len(conversations)} conversation(s). "
                    "Sélectionne une conversation."
                )
            else:
                self.state.setText(
                    "Aucune conversation enregistrée."
                )

            return

        lines = []

        for message in messages:
            role = {
                "user": "VOUS",
                "assistant": "JARVIS",
                "system": "SYSTÈME",
            }.get(
                message.role,
                message.role.upper(),
            )

            lines.append(
                f"{role}\n{message.content}"
            )

        self.messages.setPlainText(
            "\n\n--------------------\n\n".join(lines)
        )

        self.state.setText(
            f"{len(messages)} message(s) · "
            f"{len(conversations)} conversation(s)"
        )

    # --------------------------------------------
    # Sélection
    # --------------------------------------------

    def selection_changed(self):
        selected = self.conversation_list.selectedItems()

        if selected:
            self.selected_id = selected[0].data(
                Qt.ItemDataRole.UserRole
            )
        else:
            self.selected_id = None

        self.messages.clear()
        self.update_buttons()
        self.refresh()

    def update_buttons(self):
        selected = self.selected_id is not None

        self.resume_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)

    def selected_conversation(self):
        selected = self.conversation_list.selectedItems()

        if not selected:
            return None

        item = selected[0]

        return (
            item.data(Qt.ItemDataRole.UserRole),
            item.text().split("\n", 1)[0],
        )

    # --------------------------------------------
    # Nouvelle conversation
    # --------------------------------------------

    def create_conversation(self):
        title, accepted = QInputDialog.getText(
            self,
            "Nouvelle conversation",
            "Nom de la conversation :",
            QLineEdit.EchoMode.Normal,
            "Nouvelle conversation",
        )

        if not accepted:
            return

        title = title.strip()

        if not title:
            QMessageBox.warning(
                self,
                "Nom manquant",
                "Le nom ne peut pas être vide.",
            )
            return

        try:
            record = self.session.start_persistent_conversation(
                title
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "Création impossible",
                str(error),
            )
            return

        if record is None:
            QMessageBox.warning(
                self,
                "Stockage indisponible",
                "La conversation n'a pas été créée.",
            )
            return

        self.selected_id = record.id
        self.refresh()

        QMessageBox.information(
            self,
            "Conversation créée",
            f"Conversation n° {record.id} créée.",
        )

    # --------------------------------------------
    # Reprise
    # --------------------------------------------

    def resume_selected(self):
        selected = self.selected_conversation()

        if selected is None:
            return

        conversation_id, title = selected

        try:
            restored = self.session.resume_conversation(
                conversation_id
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "Reprise impossible",
                str(error),
            )
            return

        if not restored:
            QMessageBox.warning(
                self,
                "Conversation introuvable",
                "La conversation n'a pas pu être reprise.",
            )
            return

        QMessageBox.information(
            self,
            "Conversation reprise",
            (
                f"{title}\n\n"
                "Le contexte de la conversation a été "
                "restauré dans le moteur IA.\n"
                "Tu peux poursuivre depuis l'Assistant."
            ),
        )

    # --------------------------------------------
    # Suppression sécurisée
    # --------------------------------------------

    def delete_selected(self):
        selected = self.selected_conversation()

        if selected is None:
            return

        conversation_id, title = selected

        answer = QMessageBox.question(
            self,
            "Supprimer une conversation",
            (
                f"{title}\n\n"
                "Supprimer définitivement cette conversation "
                "et tous ses messages ?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            instructions = (
                self.session.request_delete_conversation(
                    conversation_id
                )
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                str(error),
            )
            return

        code, accepted = QInputDialog.getText(
            self,
            "Confirmation de suppression",
            (
                f"{instructions}\n\n"
                "Saisis le code de confirmation :"
            ),
            QLineEdit.EchoMode.Normal,
        )

        if not accepted:
            return

        code = code.strip()

        if not code:
            QMessageBox.warning(
                self,
                "Code manquant",
                "Aucun code de confirmation saisi.",
            )
            return

        try:
            result = self.session.confirm_delete_conversation(
                code
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "Suppression refusée",
                str(error),
            )
            return

        # La réponse du moteur est du texte :
        # vérifier SQLite avant d'annoncer un succès.
        try:
            remaining = self.store.get_conversation(
                conversation_id
            )
        except (ValueError, OSError, sqlite3.Error) as error:
            QMessageBox.warning(
                self,
                "Vérification impossible",
                str(error),
            )
            return

        if remaining is not None:
            QMessageBox.warning(
                self,
                "Suppression refusée",
                (
                    "La conversation existe toujours.\n\n"
                    f"Réponse du moteur : {result}"
                ),
            )
            return

        self.selected_id = None
        self.messages.clear()
        self.refresh()

        QMessageBox.information(
            self,
            "Conversation supprimée",
            f"Conversation n° {conversation_id} supprimée.",
        )
