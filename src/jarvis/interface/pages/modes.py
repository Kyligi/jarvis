from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
    QTabWidget,
)

from jarvis.config import settings
from jarvis.interface.components import Card, label
from jarvis.interface.pages.base import DataPage
from jarvis.modes import profiles
from jarvis.modes.manager import MODES
from jarvis.scenarios.commands import readable
from jarvis.scenarios.engine import engine, format_preview
from jarvis.scenarios.model import APPLICATIONS, LAYOUTS


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
        self.editors = {}
        self.dirty_modes = set()
        self.tabs = QTabWidget()
        self.mode_names = ["travail", "gaming", "etudes"]
        for name, display in [("travail", "Travail"), ("gaming", "Gaming"), ("etudes", "Études")]:
            profile = MODES[name]
            card = Card(display.upper())
            card.body.addWidget(label(profile["description"], "subheading"))
            card.body.addWidget(label(programs[name], "muted"))
            button = QPushButton(f"Activer {display}")
            button.clicked.connect(lambda checked=False, text=display: context.commands.submit(f"mode {text}"))
            context.commands.busy_changed.connect(lambda busy, b=button: b.setEnabled(not busy))
            button.setEnabled(not context.commands.busy)
            self.buttons[name] = button
            card.body.addWidget(button)
            form = QFormLayout()
            workspace = QSpinBox()
            workspace.setRange(1, 9)
            workspace.valueChanged.connect(lambda _, n=name: self.dirty_modes.add(n))
            form.addRow("Workspace", workspace)
            applications = {}
            for app in APPLICATIONS:
                check = QCheckBox(app)
                check.clicked.connect(lambda _, n=name: self.dirty_modes.add(n))
                applications[app] = check
                form.addRow(check)
            reuse = QCheckBox("Réutiliser les fenêtres")
            reuse.clicked.connect(lambda _, n=name: self.dirty_modes.add(n))
            form.addRow(reuse)
            layout = QComboBox()
            layout.addItems(['aucune', *LAYOUTS])
            layout.activated.connect(lambda _, n=name: self.dirty_modes.add(n))
            form.addRow("Disposition", layout)
            scenario = QComboBox()
            scenario.addItem('aucun', None)
            scenario.activated.connect(lambda _, n=name: self.dirty_modes.add(n))
            form.addRow("Scénario associé", scenario)
            card.body.addLayout(form)
            save = QPushButton("Enregistrer le mode")
            save.clicked.connect(lambda _, n=name: self.save_mode(n))
            card.body.addWidget(save)
            reset = QPushButton("Restaurer les paramètres par défaut")
            reset.clicked.connect(lambda _, n=name: self.reset_mode(n))
            card.body.addWidget(reset)
            self.editors[name] = (workspace, applications, reuse, layout, scenario)
            preview = QPushButton("Prévisualiser le mode enregistré")
            preview.clicked.connect(lambda _, n=name: context.commands.submit_operation(readable(lambda: format_preview(engine.preview(profiles.scenario_for_mode(n))))))
            card.body.addWidget(preview)
            self.tabs.addTab(card, display)
        self.body.addWidget(self.tabs)
        context.commands.busy_changed.connect(self.busy_changed)
        context.commands.result.connect(self.operation_result)
        self.busy_changed(context.commands.busy)
        self.body.addWidget(label("Les profils historiques gardent leur comportement. Les profils personnalisés appliquent leur politique de réutilisation à chaque activation. Enregistrez avant d’activer ; les déplacements nécessitent confirmation.", "muted"))
        self.body.addStretch()

    def load(self):
        value = self.context.service.modes()
        try:
            value['profiles'] = profiles.load()
            value['scenarios'], errors = engine.store.list()
            value['warning'] = '\n'.join(errors)
        except (ValueError, OSError) as error:
            value['warning'] = str(error)
        return value

    def render(self, value):
        self.current.setText("Dernier mode enregistré : " + (value.get("mode") or "aucun").capitalize())

        if value.get('warning'):
            self.state.setText(value['warning'])
        for name, profile in value.get('profiles', {}).items():
            if name in self.dirty_modes:
                continue
            workspace, apps, reuse, layout, scenario = self.editors[name]
            workspace.blockSignals(True)
            workspace.setValue(profile['workspace'])
            workspace.blockSignals(False)
            for app, check in apps.items():
                check.setChecked(app in profile['applications'])
            reuse.setChecked(profile['reuse'])
            layout.setCurrentText(profile['layout'] or 'aucune')
            scenario.clear()
            scenario.addItem('aucun', None)
            for row in value.get('scenarios', []):
                scenario.addItem(row['name'] + ' [' + row['id'][:8] + ']', row['id'])
            index = scenario.findData(profile['scenario'])
            if index < 0:
                scenario.addItem('Scénario manquant : ' + profile['scenario'], profile['scenario'])
                index = scenario.count() - 1
            scenario.setCurrentIndex(index)

    def save_mode(self, name):
        workspace, apps, reuse, layout, scenario = self.editors[name]
        value = dict(workspace=workspace.value(), applications=[a for a, c in apps.items() if c.isChecked()],
                     reuse=reuse.isChecked(), layout=None if layout.currentIndex() == 0 else layout.currentText(),
                     scenario=scenario.currentData())
        self.mutate(name, lambda: profiles.save(name, value))

    def reset_mode(self, name):
        self.mutate(name, lambda: profiles.reset(name))

    def mutate(self, name, operation):
        def run():
            try:
                return {'mode_saved': name, 'message': operation()}
            except Exception as error:
                return {'mode_error': name, 'message': str(error) if isinstance(error, (ValueError, OSError)) else type(error).__name__}
        if not self.context.commands.submit_operation(run):
            self.state.setText('Commande en cours : paramètres non enregistrés.')

    @Slot(object)
    def operation_result(self, result):
        if isinstance(result, dict) and 'mode_saved' in result:
            self.dirty_modes.discard(result['mode_saved'])
        elif isinstance(result, dict) and 'mode_error' in result:
            self.dirty_modes.add(result['mode_error'])
            self.state.setText(result['message'])

    @Slot(bool)
    def busy_changed(self, busy):
        self.tabs.setEnabled(not busy)

    def update_requested(self, identifier):
        name = self.context.commands.last_requested_mode
        if name:
            self.requested.setText(f"Dernière demande dans cette exécution : {name.capitalize()}")
