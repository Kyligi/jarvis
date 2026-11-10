"""Inventaire réel et actions ciblées ; toutes les lectures/actions sur workers."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from jarvis.interface.components import label
from jarvis.interface.pages.base import DataPage
from jarvis.services.windows import WindowError, service


class WindowsPage(DataPage):
    def __init__(self, context):
        super().__init__(context, "Fenêtres", "Sélectionnez une fenêtre réelle. Les dispositions demandent confirmation dans la console.")
        self.summary = label("Aucun inventaire chargé", "muted")
        self.body.addWidget(self.summary)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Application / bureau", "Titre", "État", "Adresse"])
        self.tree.setMinimumHeight(230)
        self.tree.setAccessibleName("Fenêtres par workspace")
        self.tree.currentItemChanged.connect(self.select)
        self.body.addWidget(self.tree)
        self.selection = label("Aucune fenêtre sélectionnée", "muted")
        self.body.addWidget(self.selection)
        self.target = None
        row = QHBoxLayout()
        self.actions = []
        self.destination = QComboBox()
        self.destination.addItems([str(i) for i in range(1, 10)])
        self.destination.setAccessibleName("Bureau de destination")
        row.addWidget(self.destination)
        for title, action in (("Focus", "focus"), ("Déplacer", "move"), ("Flottante", "float"), ("Mosaïque", "tile"), ("Centrer", "center")):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, action=action: self.perform(action))
            row.addWidget(button)
            self.actions.append(button)
        self.body.addLayout(row)
        layouts = QHBoxLayout()
        for title, command in (("Développement", "disposition développement"), ("Études", "disposition études"), ("Gaming", "disposition gaming"), ("Organiser", "organise mon bureau")):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, command=command: context.commands.submit(command))
            layouts.addWidget(button)
        self.body.addLayout(layouts)
        context.commands.busy_changed.connect(self.update_actions)
        self.update_actions()

    def load(self):
        return service.snapshot()

    def render(self, value):
        old = self.target
        self.tree.clear()
        self.target = None
        monitors = ", ".join(m["name"] for m in value["monitors"]) or "aucun"
        self.summary.setText(f"Bureau courant : {value['current'].get('name', 'aucun')} · Moniteurs : {monitors}")
        groups = {}
        for ws in value["workspaces"]:
            groups[ws["id"]] = QTreeWidgetItem(self.tree, ["Bureau " + ws["name"]])
        for w in value["windows"]:
            if w.workspace not in groups:
                groups[w.workspace] = QTreeWidgetItem(self.tree, ["Bureau " + w.workspace_name])
            item = QTreeWidgetItem(groups[w.workspace], [w.app, w.title, ("Protégée · " if w.protected else "") + ("Flottante" if w.floating else "Mosaïque"), w.address])
            item.setData(0, Qt.ItemDataRole.UserRole, w)
            if old and (old.address, old.pid, old.app) == (w.address, w.pid, w.app):
                self.tree.setCurrentItem(item)
        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)
        if not value["windows"]:
            self.state.setText("Aucune fenêtre ouverte")
        self.select(self.tree.currentItem(), None)

    def failure(self, error):
        super().failure(error)
        self.cached = None
        self.tree.clear()
        self.target = None
        self.select(None, None)

    def select(self, item, previous):
        self.target = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.selection.setText(self.target.describe() if self.target else "Aucune fenêtre sélectionnée")
        self.update_actions()

    def update_actions(self, *args):
        enabled = self.target is not None and not self.target.protected and not self.context.commands.busy
        for button in self.actions:
            button.setEnabled(enabled)

    def perform(self, action):
        target = self.target
        number = int(self.destination.currentText())
        if target is None:
            return
        def run():
            try:
                service.act(action, target, *((number,) if action == "move" else ()))
                return "Action effectuée : " + target.describe()
            except WindowError as error:
                return str(error)
        self.context.commands.submit_operation(run)
