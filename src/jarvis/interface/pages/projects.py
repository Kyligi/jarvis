from datetime import datetime

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from jarvis.interface.components import label, text_view
from jarvis.interface.pages.base import DataPage


class ProjectsPage(DataPage):
    def __init__(self, context):
        super().__init__(context, "Projets", "Rust & Python · sélectionnez un projet pour consulter Git")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un projet ou un langage…")
        self.search.setAccessibleName("Rechercher un projet")
        self.search.textChanged.connect(self.filter_rows)
        self.body.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Projet", "Langage", "Dernière utilisation", "Objectif"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.setMinimumHeight(180)
        self.body.addWidget(self.table)
        self.path_label = label("Aucun projet sélectionné", "muted")
        self.body.addWidget(self.path_label)
        self.details = text_view("Branche, dernier commit et modifications du projet sélectionné.")
        self.body.addWidget(self.details)
        row = QHBoxLayout()
        self.open_button = QPushButton("Ouvrir / reprendre le projet")
        self.git_button = QPushButton("Actualiser Git")
        self.open_button.clicked.connect(self.open_project)
        self.git_button.clicked.connect(self.load_details)
        row.addWidget(self.open_button)
        row.addWidget(self.git_button)
        self.body.insertLayout(4, row)
        self.entries = []
        self.selected = None
        self.detail_pending = False
        self.detail_runner = context.reader()
        self.detail_runner.result.connect(self.receive_details)
        self.detail_runner.failed.connect(self.detail_error)
        self.detail_runner.idle.connect(self.details_finished)
        self.selection_changed()

    def load(self):
        return self.context.service.projects()

    def render(self, entries):
        previous = self.selected["path"] if self.selected else None
        self.entries = entries
        self.table.blockSignals(True)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            last = datetime.fromtimestamp(entry["last_opened"]).strftime("%d/%m/%Y %H:%M") if entry["last_opened"] else "Jamais ouvert"
            for col, text in enumerate((entry["name"], entry["language"], last, entry["objective"] or "Non défini")):
                item = QTableWidgetItem(text)
                item.setToolTip(str(entry["path"]))
                self.table.setItem(row, col, item)
        self.table.clearSelection()
        self.table.blockSignals(False)
        self.filter_rows(self.search.text())
        if previous:
            for row, entry in enumerate(entries):
                if entry["path"] == previous and not self.table.isRowHidden(row):
                    self.table.selectRow(row)
                    break
        self.selection_changed()
        if not entries:
            self.state.setText("Aucun projet Rust/Python découvert.")

    @Slot(str)
    def filter_rows(self, text):
        for row, entry in enumerate(self.entries):
            self.table.setRowHidden(row, text.casefold() not in f"{entry['name']} {entry['language']}".casefold())
        self.selection_changed()

    @Slot()
    def selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        row = rows[0].row() if rows else -1
        self.selected = self.entries[row] if 0 <= row < len(self.entries) and not self.table.isRowHidden(row) else None
        self.open_button.setEnabled(self.selected is not None)
        self.git_button.setEnabled(self.selected is not None)
        self.path_label.setText(str(self.selected["path"]) if self.selected else "Aucun projet sélectionné")
        self.details.clear()
        if self.selected and self.active:
            self.load_details()

    @Slot()
    def load_details(self):
        if not self.active or not self.selected:
            return
        path = self.selected["path"]
        if self.detail_runner.start(lambda: (path, self.context.service.project_details(path))):
            self.details.setPlainText("Lecture Git…")
            self.detail_pending = False
        else:
            self.detail_pending = True

    @Slot(object)
    def receive_details(self, result):
        path, text = result
        if self.active and self.selected and self.selected["path"] == path:
            self.details.setPlainText(text)

    @Slot(str)
    def detail_error(self, error):
        if self.active:
            self.details.setPlainText(f"Git indisponible ({error}). Réessaie avec Actualiser Git.")

    @Slot()
    def details_finished(self):
        if self.detail_pending:
            self.load_details()

    @Slot()
    def open_project(self):
        if self.selected:
            self.context.commands.submit(f"ouvre projet {self.selected['name']}")
