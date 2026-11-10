"""Éditeur déclaratif : widgets typés, opérations métier dans les workers partagés."""
from copy import deepcopy

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from jarvis.interface.components import label, text_view
from jarvis.interface.pages.base import DataPage
from jarvis.scenarios.commands import readable
from jarvis.scenarios.engine import engine, format_preview, format_result
from jarvis.scenarios.model import FIELDS, new_action, new_scenario, validate


class ActionForm(QWidget):
    def __init__(self):
        super().__init__()
        self.form = QFormLayout(self)
        self.kind = QComboBox()
        self.kind.addItems(FIELDS)
        self.policy = QComboBox()
        self.policy.addItems(['stop', 'continue_on_error'])
        self.form.addRow('Type', self.kind)
        self.form.addRow('Sur erreur', self.policy)
        self.controls = {}
        self.kind.currentTextChanged.connect(self.rebuild)
        self.rebuild(self.kind.currentText())

    def rebuild(self, kind):
        while self.form.rowCount() > 2:
            self.form.removeRow(2)
        self.controls = {}
        for key, rule in FIELDS[kind].items():
            if isinstance(rule, tuple):
                widget = QComboBox()
                widget.addItems(rule)
            elif rule == 'workspace':
                widget = QSpinBox()
                widget.setRange(1, 9)
                widget.setValue(3)
            elif rule == 'bool':
                widget = QCheckBox('Réutiliser une fenêtre existante')
                widget.setChecked(True)
            else:
                widget = QLineEdit()
                widget.setPlaceholderText('Classe, titre ou adresse exacte ; ambiguïtés refusées')
            widget.setAccessibleName(key)
            self.controls[key] = widget
            self.form.addRow(key, widget)

    def read(self, key=None):
        parameters = {}
        for name, widget in self.controls.items():
            if isinstance(widget, QComboBox):
                value = widget.currentText()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            else:
                value = widget.text()
            parameters[name] = value
        action = new_action(self.kind.currentText(), **parameters)
        action['failure_policy'] = self.policy.currentText()
        if key:
            action['id'] = key
        return action

    def display(self, action):
        self.kind.setCurrentText(action['type'])
        self.policy.setCurrentText(action['failure_policy'])
        for name, value in action['parameters'].items():
            widget = self.controls[name]
            if isinstance(widget, QComboBox):
                widget.setCurrentText(value)
            elif isinstance(widget, QSpinBox):
                widget.setValue(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            else:
                widget.setText(value)


class ScenariosPage(DataPage):
    def __init__(self, context):
        super().__init__(context, 'Scénarios', 'Actions autorisées et ordonnées. Ne saisissez aucun secret. Enregistrez avant de lancer.')
        self.draft = None
        self.dirty = False
        self.rows = []
        self.operation_buttons = []
        self.search = QLineEdit()
        self.search.setPlaceholderText('Rechercher un scénario')
        self.search.textChanged.connect(self.filter)
        self.body.addWidget(self.search)
        self.library = QListWidget()
        self.library.setMaximumHeight(130)
        self.library.currentRowChanged.connect(self.select)
        self.body.addWidget(self.library)
        self.row_buttons([('Créer', self.create), ('Dupliquer', self.duplicate), ('Supprimer', self.delete)])
        self.name = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(80)
        self.enabled = QCheckBox('Scénario activé')
        form = QFormLayout()
        form.addRow('Nom', self.name)
        form.addRow('Description', self.description)
        form.addRow('', self.enabled)
        self.body.addLayout(form)
        self.name.textEdited.connect(self.mark_dirty)
        self.description.textChanged.connect(self.mark_dirty)
        self.enabled.clicked.connect(self.mark_dirty)
        self.steps = QListWidget()
        self.steps.setMaximumHeight(140)
        self.steps.currentRowChanged.connect(self.select_step)
        self.body.addWidget(self.steps)
        self.action_form = ActionForm()
        self.body.addWidget(self.action_form)
        self.row_buttons([('Ajouter étape', self.add_step), ('Appliquer à l’étape', self.edit_step),
                          ('Retirer étape', self.remove_step), ('↑', lambda: self.move_step(-1)), ('↓', lambda: self.move_step(1))])
        self.row_buttons([('Enregistrer', self.save), ('Prévisualiser', self.preview), ('Exécuter', self.run),
                          ('Annuler', lambda: context.commands.submit('annule scénario'))])
        self.output = text_view('Prévisualisation et progression')
        self.output.document().setMaximumBlockCount(500)
        self.body.addWidget(self.output)
        self.body.addWidget(label('Historique — 100 dernières exécutions', 'subheading'))
        self.history_selector = QComboBox()
        self.history_selector.setAccessibleName('Sélection d’une exécution passée')
        self.history_selector.currentIndexChanged.connect(self.select_history)
        self.body.addWidget(self.history_selector)
        self.history_runs = []
        self.history = text_view()
        self.body.addWidget(self.history)
        context.commands.scenario_progress.connect(self.progress)
        context.commands.result.connect(self.operation_result)
        context.commands.busy_changed.connect(self.busy_changed)
        self.busy_changed(context.commands.busy)
        self.create()

    def row_buttons(self, entries):
        row = QHBoxLayout()
        for title, callback in entries:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, fn=callback: fn())
            row.addWidget(button)
            if title != 'Annuler':
                self.operation_buttons.append(button)
        self.body.addLayout(row)

    def mark_dirty(self, *args):
        self.dirty = True

    def load(self):
        rows, errors = engine.store.list()
        try:
            history = engine.store.history()
        except (ValueError, OSError) as error:
            history = []
            errors.append(str(error))
        return rows, errors, history

    def render(self, value):
        rows, errors, history = value
        self.rows = rows
        self.library.blockSignals(True)
        self.library.clear()
        self.library.addItems([r['name'] + ' [' + r['id'][:8] + ']' + (' (désactivé)' if not r['enabled'] else '') for r in rows])
        selected = next((i for i, row in enumerate(rows) if self.draft and row['id'] == self.draft['id']), -1)
        self.library.setCurrentRow(selected)
        self.library.blockSignals(False)
        self.filter(self.search.text())
        self.state.setText('\n'.join(errors) if errors else (f'{len(rows)} scénario(s)' if rows else 'Aucun scénario enregistré. Créez le premier.'))
        self.history_runs = history
        self.history_selector.blockSignals(True)
        self.history_selector.clear()
        self.history_selector.addItems([f"{r['started_at']} · {r['name']} · {r['state']}" for r in history])
        self.history_selector.blockSignals(False)
        self.select_history(0)
        # Ne pas écraser un brouillon au rafraîchissement automatique.

    def filter(self, text):
        from jarvis.core.text import normalize_words
        for i, row in enumerate(self.rows):
            self.library.item(i).setHidden(normalize_words(text) not in normalize_words(row['name']))

    def discard_allowed(self):
        return not self.dirty or QMessageBox.question(self, 'Brouillon non enregistré', 'Abandonner les modifications non enregistrées ?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def create(self):
        if self.draft and not self.discard_allowed():
            return
        self.show_draft(new_scenario())
        self.is_new = True

    def show_draft(self, value):
        self.draft = deepcopy(value)
        self.name.setText(value['name'])
        self.description.setPlainText(value['description'])
        self.enabled.setChecked(value['enabled'])
        self.refresh_steps()
        self.dirty = False

    def select(self, index):
        if 0 <= index < len(self.rows) and self.discard_allowed():
            self.show_draft(self.rows[index])
            self.is_new = False

    def refresh_steps(self, selected=-1):
        self.steps.clear()
        self.steps.addItems([f"{n}. {a['type']} · {a['parameters']} · {a['failure_policy']}" for n, a in enumerate(self.draft['actions'], 1)])
        self.steps.setCurrentRow(selected)

    def select_step(self, index):
        if self.draft and 0 <= index < len(self.draft['actions']):
            self.action_form.display(self.draft['actions'][index])

    def add_step(self):
        try:
            action = self.action_form.read()
            if len(self.draft['actions']) >= 100:
                raise ValueError('Maximum 100 étapes.')
            self.draft['actions'].append(action)
            self.dirty = True
            self.refresh_steps(len(self.draft['actions']) - 1)
        except ValueError as error:
            self.state.setText(str(error))

    def edit_step(self):
        index = self.steps.currentRow()
        if index < 0:
            return
        try:
            self.draft['actions'][index] = self.action_form.read(self.draft['actions'][index]['id'])
            self.dirty = True
            self.refresh_steps(index)
        except ValueError as error:
            self.state.setText(str(error))

    def remove_step(self):
        index = self.steps.currentRow()
        if index >= 0:
            self.draft['actions'].pop(index)
            self.dirty = True
            self.refresh_steps(min(index, len(self.draft['actions']) - 1))

    def move_step(self, offset):
        index = self.steps.currentRow()
        destination = index + offset
        if index >= 0 and 0 <= destination < len(self.draft['actions']):
            actions = self.draft['actions']
            actions[index], actions[destination] = actions[destination], actions[index]
            self.dirty = True
            self.refresh_steps(destination)

    def value(self):
        value = deepcopy(self.draft)
        value.update(name=self.name.text(), description=self.description.toPlainText(), enabled=self.enabled.isChecked())
        return validate(value)

    def operation(self, fn):
        if not self.context.commands.submit_operation(readable(fn)):
            self.state.setText('Une commande est en cours. Réessayez après sa fin.')

    def save(self):
        try:
            value, create = self.value(), self.is_new
        except ValueError as error:
            self.state.setText(str(error))
            return
        # Le retour du worker transporte la nouvelle révision ; aucun widget hors GUI.
        self.context.commands.result.connect(self.saved)
        def save_operation():
            try:
                return {'scenario_saved': engine.store.save(value, create=create)}
            except Exception as error:
                return {'scenario_error': str(error) if isinstance(error, (ValueError, OSError)) else type(error).__name__}
        if not self.context.commands.submit_operation(save_operation):
            self.context.commands.result.disconnect(self.saved)
            self.state.setText('Commande en cours ; enregistrement non démarré.')

    @Slot(object)
    def saved(self, result):
        if not isinstance(result, dict) or not ({'scenario_saved', 'scenario_error'} & set(result)):
            return
        self.context.commands.result.disconnect(self.saved)
        if isinstance(result, dict) and 'scenario_saved' in result:
            self.show_draft(result['scenario_saved'])
            self.is_new = False
            self.state.setText('Scénario enregistré.')
        else:
            self.state.setText(result['scenario_error'])
            self.output.setPlainText(result['scenario_error'])

    def duplicate(self):
        if not self.discard_allowed():
            return
        try:
            value = self.value()
        except ValueError as error:
            self.state.setText(str(error))
            return
        from uuid import uuid4

        from jarvis.scenarios.model import now
        value.update(id=uuid4().hex, name=value['name'][:90] + ' — copie', created_at=now(), updated_at=now())
        self.show_draft(value)
        self.is_new = True
        self.dirty = True

    def delete(self):
        if self.is_new:
            self.state.setText('Ce brouillon n’est pas enregistré.')
            return
        if QMessageBox.question(self, 'Supprimer le scénario', f"Supprimer définitivement « {self.draft['name']} » ? L’historique sera conservé.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            key = self.draft['id']
            self.operation(lambda: (engine.store.delete(key, confirmed=True), 'Scénario supprimé.')[1])

    def preview(self):
        try:
            value = self.value()
        except ValueError as error:
            self.state.setText(str(error))
            return
        self.operation(lambda: format_preview(engine.preview(value)))

    def run(self):
        if self.is_new or self.dirty:
            self.state.setText('Enregistrez les modifications avant d’exécuter.')
            return
        self.context.commands.submit('lance scénario ' + self.draft['id'])

    @Slot(object)
    def progress(self, result):
        self.output.setPlainText(format_result(result))


    @Slot(bool)
    def busy_changed(self, busy):
        for widget in [*self.operation_buttons, self.library, self.name, self.description,
                       self.enabled, self.steps, self.action_form]:
            widget.setEnabled(not busy)

    @Slot(object)
    def operation_result(self, result):
        if self.active and isinstance(result, str):
            self.output.setPlainText(result)


    def select_history(self, index):
        self.history.setPlainText(format_result(self.history_runs[index]) if 0 <= index < len(self.history_runs) else 'Aucune exécution enregistrée.')
