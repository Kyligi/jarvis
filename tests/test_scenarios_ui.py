import threading
from unittest.mock import Mock
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMessageBox
from jarvis.scenarios.engine import engine
from jarvis.scenarios.model import new_scenario, new_action
from jarvis.modes import profiles
from test_hud import ui, select
from test_interface import pump


def test_scenario_editor_crud_and_forms(qapp, ui, monkeypatch):
    _, hud, context, _, _, _ = ui
    page = select(qapp, hud, 7)
    assert 'Aucun scénario' in page.state.text()
    page.name.setText('Révisions')
    page.action_form.kind.setCurrentText('switch_workspace')
    page.action_form.controls['workspace'].setValue(5)
    page.add_step()
    page.action_form.kind.setCurrentText('open_application')
    page.action_form.controls['application'].setCurrentText('notion')
    page.add_step()
    assert len(page.draft['actions']) == 2
    page.move_step(-1)
    assert page.draft['actions'][0]['type'] == 'open_application'
    page.action_form.controls['reuse'].setChecked(False)
    page.edit_step()
    assert not page.draft['actions'][0]['parameters']['reuse']
    page.save()
    pump(qapp, lambda: context.commands.runner.task is None and page.runner.task is None)
    assert not page.is_new and not page.dirty
    rows, errors = engine.store.list()
    assert not errors and len(rows) == 1
    assert rows[0]['name'] == 'Révisions'
    page.search.setText('absent')
    assert page.library.item(0).isHidden()
    page.search.setText('revisions')
    assert not page.library.item(0).isHidden()
    page.duplicate()
    assert page.is_new and page.dirty
    page.save()
    pump(qapp, lambda: context.commands.runner.task is None and page.runner.task is None)
    assert len(engine.store.list()[0]) == 2
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.No)
    page.delete()
    assert len(engine.store.list()[0]) == 2
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    page.delete()
    pump(qapp, lambda: context.commands.runner.task is None and page.runner.task is None)
    assert len(engine.store.list()[0]) == 1


def test_scenario_validation_draft_and_preview_worker(qapp, ui, monkeypatch):
    _, hud, context, _, _, _ = ui
    page = select(qapp, hud, 7)
    page.action_form.kind.setCurrentText('move_window')
    page.add_step()
    assert not page.draft['actions']
    assert 'Texte' in page.state.text()
    page.run()
    assert 'Enregistrez' in page.state.text()
    page.action_form.controls['target'].setText('Foot')
    page.add_step()
    threads = []
    def preview(value):
        threads.append(QThread.currentThread())
        return dict(name='Test', enabled=True, steps=[], confirmation_required=False)
    monkeypatch.setattr(engine, 'preview', preview)
    page.preview()
    pump(qapp, lambda: context.commands.runner.task is None)
    assert threads[0] != qapp.thread()
    assert 'Aucune action exécutée' in hud.console.output.toPlainText()


def test_cancel_command_bypasses_busy_bus_and_updates_gui(qapp, ui, monkeypatch):
    _, hud, context, _, _, _ = ui
    page = select(qapp, hud, 7)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def execute(action, cancelled):
        calls.append(action['id'])
        entered.set()
        release.wait(3)
        return 'Lancé'
    adapter = Mock(check=Mock(return_value='OK'), execute=execute)
    monkeypatch.setattr(engine, 'actions', adapter)
    value = new_scenario('Test', [new_action('switch_workspace', workspace=3), new_action('switch_workspace', workspace=4)])
    assert context.commands.submit_operation(lambda: engine.run(value))
    try:
        pump(qapp, entered.is_set)
        pump(qapp, lambda: 'running' in page.output.toPlainText())
        assert context.commands.submit('état scénario')
        assert context.commands.submit('annule scénario')
        assert not context.commands.submit('mode Gaming')
        hud.navigation.setCurrentRow(4)
        assert hud.stack.currentIndex() == 4
    finally:
        release.set()
        pump(qapp, lambda: context.commands.runner.task is None)
    assert len(calls) == 1
    assert engine.status()['steps'][1]['state'] == 'cancelled'
    assert 'cancelled' in page.output.toPlainText()


def test_open_commands_navigation_from_mini(qapp, ui):
    mini, hud, context, _, _, _ = ui
    hud.hide()
    assert context.commands.submit('ouvre scénarios')
    pump(qapp, lambda: context.commands.runner.task is None)
    assert hud.isVisible() and hud.stack.currentIndex() == 7
    assert context.commands.submit('configure mode Études')
    pump(qapp, lambda: context.commands.runner.task is None)
    assert hud.stack.currentIndex() == 4
    assert mini.hud is hud


def test_mode_editor_save_and_reset(qapp, ui):
    _, hud, context, _, _, _ = ui
    page = select(qapp, hud, 4)
    workspace, apps, reuse, layout, scenario = page.editors['etudes']
    assert workspace.value() == 5
    assert apps['notion'].isChecked() and apps['browser'].isChecked()
    workspace.setValue(8)
    layout.setCurrentText('etudes')
    page.save_mode('etudes')
    pump(qapp, lambda: context.commands.runner.task is None and page.runner.task is None)
    assert profiles.load()['etudes']['workspace'] == 8
    assert profiles.load()['etudes']['layout'] == 'etudes'
    page.reset_mode('etudes')
    pump(qapp, lambda: context.commands.runner.task is None and page.runner.task is None)
    assert workspace.value() == 5
    assert profiles.load() == profiles.defaults()


def test_invalid_scenario_and_permissions_visible(qapp, ui, monkeypatch):
    _, hud, context, _, _, _ = ui
    engine.store.root.mkdir(parents=True)
    (engine.store.root / 'invalid.json').write_text('{"schema_version":99}')
    page = select(qapp, hud, 7)
    assert 'invalid.json' in page.state.text()
    monkeypatch.setattr(engine.store, 'save', Mock(side_effect=PermissionError('Permission refusée')))
    page.save()
    pump(qapp, lambda: context.commands.runner.task is None)
    assert 'Permission' in page.output.toPlainText()
    assert page.is_new


def test_cancel_during_save_does_not_consume_save_result(qapp, ui, monkeypatch):
    _, hud, context, _, _, _ = ui
    page = select(qapp, hud, 7)
    entered, release = threading.Event(), threading.Event()
    original = engine.store.save
    def save(*args, **kwargs):
        entered.set()
        release.wait(3)
        return original(*args, **kwargs)
    monkeypatch.setattr(engine.store, 'save', save)
    page.save()
    try:
        pump(qapp, entered.is_set)
        assert context.commands.submit('annule scénario')
    finally:
        release.set()
        pump(qapp, lambda: context.commands.runner.task is None)
    assert not page.is_new
    assert engine.store.get(page.draft['id']) == page.draft


def test_failed_mode_save_preserves_edits(qapp, ui, monkeypatch):
    _, hud, context, _, _, _ = ui
    page = select(qapp, hud, 4)
    page.editors['etudes'][0].setValue(8)
    monkeypatch.setattr(profiles, 'save', Mock(side_effect=PermissionError('Permission refusée')))
    page.save_mode('etudes')
    pump(qapp, lambda: context.commands.runner.task is None and page.runner.task is None)
    assert page.editors['etudes'][0].value() == 8
    assert 'etudes' in page.dirty_modes
    assert 'Permission' in hud.console.output.toPlainText()
