
"""Page HUD de gestion des souvenirs personnels de Jarvis."""

import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
)

from jarvis.interface.pages.base import DataPage


class MemoryPage(DataPage):
    """Affichage, recherche, ajout et suppression de souvenirs."""

    def __init__(self, context):
        super().__init__(
            context,
            "Mémoire personnelle",
            "Souvenirs locaux · SQLite · Recherche FTS5",
        )

        self.query = ""

        # Recherche
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Rechercher dans les souvenirs (FTS5)…"
        )
        self.search.setAccessibleName(
            "Rechercher un souvenir personnel"
        )

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)

        self.search.textChanged.connect(
            self.search_changed
        )
        self.search_timer.timeout.connect(
            self.apply_search
        )

        self.body.addWidget(self.search)

        # Filtre par catégorie
        self.category_filter = QComboBox()
        self.category_filter.addItem(
            "Toutes les catégories",
            "all",
        )

        categories = (
            "general",
            "preferences",
            "projects",
            "habits",
            "instructions",
        )

        for category in categories:
            self.category_filter.addItem(
                category.capitalize(),
                category,
            )

        self.category_filter.currentIndexChanged.connect(
            self.filter_category
        )

        self.body.addWidget(self.category_filter)

        # Tableau
        self.table = QTableWidget(0, 3)

        self.table.setHorizontalHeaderLabels([
            "ID",
            "Catégorie",
            "Souvenir",
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(300)
        self.table.setWordWrap(True)

        self.body.addWidget(self.table)

        # Suppression
        delete_row = QHBoxLayout()

        self.delete_button = QPushButton(
            "Supprimer le souvenir sélectionné"
        )
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(
            self.delete_selected_memory
        )

        delete_row.addWidget(self.delete_button)
        delete_row.addStretch()

        self.body.addLayout(delete_row)

        self.table.itemSelectionChanged.connect(
            self.update_delete_button
        )

        # Formulaire d'ajout
        self.body.addWidget(
            QLabel("AJOUTER UN SOUVENIR")
        )

        self.new_content = QTextEdit()
        self.new_content.setPlaceholderText(
            "Exemple : Je préfère programmer en Rust."
        )
        self.new_content.setAccessibleName(
            "Contenu du nouveau souvenir"
        )
        self.new_content.setMaximumHeight(100)

        self.body.addWidget(self.new_content)

        form_row = QHBoxLayout()
        self.new_category = QComboBox()

        for category in categories:
            self.new_category.addItem(
                category.capitalize(),
                category,
            )

        form_row.addWidget(self.new_category)

        self.add_button = QPushButton(
            "Enregistrer le souvenir"
        )
        self.add_button.clicked.connect(
            self.add_memory
        )

        form_row.addWidget(self.add_button)
        self.body.addLayout(form_row)

    # --------------------------------------------
    # Chargement SQLite
    # --------------------------------------------

    def load(self):
        service = self.context.commands.memory_service
        query = self.query.strip()

        if query:
            return service.search_memories(
                query,
                limit=50,
            )

        return service.list_memories()

    # --------------------------------------------
    # Affichage
    # --------------------------------------------

    def render(self, memories):
        self.table.setRowCount(len(memories))

        for row, memory in enumerate(memories):
            values = (
                str(memory.id),
                memory.category,
                memory.content,
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                item.setFlags(
                    item.flags()
                    & ~Qt.ItemFlag.ItemIsEditable
                )

                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        memory.id,
                    )

                item.setToolTip(value)
                self.table.setItem(
                    row,
                    column,
                    item,
                )

        self.table.resizeRowsToContents()
        self.table.clearSelection()
        self.update_delete_button()
        self.filter_category()

    # --------------------------------------------
    # Recherche
    # --------------------------------------------

    def search_changed(self, text):
        self.search_timer.start()

    def apply_search(self):
        self.query = self.search.text().strip()
        self.refresh()

    # --------------------------------------------
    # Filtrage
    # --------------------------------------------

    def filter_category(self, *args):
        category = self.category_filter.currentData()
        visible_count = 0

        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)

            visible = (
                category == "all"
                or (
                    item is not None
                    and item.text() == category
                )
            )

            self.table.setRowHidden(
                row,
                not visible,
            )

            if visible:
                visible_count += 1

        self.update_delete_button()

        if visible_count:
            self.state.setText(
                f"{visible_count} souvenir(s) affiché(s)"
            )
        elif self.query:
            self.state.setText(
                "Aucun souvenir ne correspond à la recherche."
            )
        elif category != "all":
            self.state.setText(
                "Aucun souvenir dans cette catégorie."
            )
        else:
            self.state.setText(
                "Aucun souvenir enregistré."
            )

    # --------------------------------------------
    # Ajout explicite
    # --------------------------------------------

    def add_memory(self):
        content = self.new_content.toPlainText().strip()

        if not content:
            self.state.setText(
                "Saisis un souvenir avant de l'enregistrer."
            )
            return

        category = self.new_category.currentData()
        service = self.context.commands.memory_service

        try:
            memory = service.add_memory(
                content,
                category=category,
                source="explicit",
            )
        except (ValueError, OSError, sqlite3.Error) as error:
            self.state.setText(
                "Enregistrement impossible "
                f"({type(error).__name__})."
            )
            return

        self.new_content.clear()

        self.search_timer.stop()
        self.search.clear()
        self.query = ""

        self.category_filter.setCurrentIndex(0)

        self.state.setText(
            f"Souvenir n° {memory.id} enregistré."
        )

        self.refresh()

    # --------------------------------------------
    # Sélection
    # --------------------------------------------

    def selected_memory(self):
        """Retourne (id, catégorie, contenu), ou None."""

        row = self.table.currentRow()

        if row < 0 or self.table.isRowHidden(row):
            return None

        id_item = self.table.item(row, 0)
        category_item = self.table.item(row, 1)
        content_item = self.table.item(row, 2)

        if not all((
            id_item,
            category_item,
            content_item,
        )):
            return None

        memory_id = id_item.data(
            Qt.ItemDataRole.UserRole
        )

        return (
            int(memory_id),
            category_item.text(),
            content_item.text(),
        )

    def update_delete_button(self):
        self.delete_button.setEnabled(
            self.selected_memory() is not None
        )

    # --------------------------------------------
    # Suppression sécurisée
    # --------------------------------------------

    def delete_selected_memory(self):
        selected = self.selected_memory()

        if selected is None:
            return

        memory_id, category, content = selected

        # Confirmation initiale.
        answer = QMessageBox.question(
            self,
            "Supprimer un souvenir",
            (
                f"Souvenir n° {memory_id}\n"
                f"Catégorie : {category}\n\n"
                f"{content}\n\n"
                "Demander sa suppression ?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        conversation = self.context.commands.conversation

        # Le moteur gère le code et son expiration.
        try:
            instructions = (
                conversation.request_delete_memory(
                    memory_id
                )
            )
        except (ValueError, RuntimeError) as error:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                str(error),
            )
            return

        # Afficher les instructions retournées
        # par le moteur, sans générer un second code.
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
            result = (
                conversation.confirm_delete_memory(
                    code
                )
            )
        except (ValueError, RuntimeError) as error:
            QMessageBox.warning(
                self,
                "Suppression refusée",
                str(error),
            )
            return

        # Vérifier l'état réel de SQLite.
        # Ne jamais annoncer une réussite uniquement
        # parce que l'appel de confirmation a répondu.
        try:
            remaining = (
                self.context.commands.memory_service
                .list_memories()
            )
            deleted = not any(
                memory.id == memory_id
                for memory in remaining
            )
        except (OSError, sqlite3.Error) as error:
            QMessageBox.warning(
                self,
                "Vérification impossible",
                str(error),
            )
            return

        if not deleted:
            QMessageBox.warning(
                self,
                "Suppression non effectuée",
                (
                    "Le souvenir existe toujours.\n\n"
                    f"Réponse du moteur : {result}"
                ),
            )
            return

        QMessageBox.information(
            self,
            "Souvenir supprimé",
            f"Le souvenir n° {memory_id} a été supprimé.",
        )

        self.table.clearSelection()
        self.refresh()
