import json
import threading
from copy import deepcopy
from unittest.mock import Mock

import pytest

from jarvis import registry
from jarvis.modes import manager as modes
from jarvis.modes import profiles
from jarvis.scenarios import actions, commands
from jarvis.scenarios.actions import Actions, open_application
from jarvis.scenarios.engine import Engine, engine
from jarvis.scenarios.model import (
    FIELDS,
    new_action,
    new_scenario,
    validate,
    validate_action,
)
from jarvis.scenarios.storage import Store, atomic_json
from jarvis.services.windows import Window, WindowError, service


def scenario(*kinds):
    defaults = {
        'switch_workspace': dict(workspace=3),
        'open_application': dict(application='browser', reuse=True),
        'focus_window': dict(target='Foot'),
        'move_window': dict(target='Foot', workspace=3),
        'apply_layout': dict(layout='developpement', workspace=3),
        'resume_project': dict(language='Rust'),
        'restore_session': {}, 'show_project_objective': {},
    }
    return new_scenario('Révisions', [new_action(k, **defaults[k]) for k in kinds])


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / 'scenarios')


@pytest.fixture
def fake_actions():
    return Mock(check=Mock(return_value='OK'), execute=Mock(return_value='OK'))


def test_crud_roundtrip_and_optimistic_revision(store):
    initial = scenario('switch_workspace')
    saved = store.save(initial, create=True)
    assert store.get(initial['id']) == saved
    changed = deepcopy(saved)
    changed['name'] = 'Développement'
    updated = store.save(changed)
    assert updated['created_at'] == initial['created_at']
    assert updated['updated_at'] != saved['updated_at']
    with pytest.raises(ValueError, match='ailleurs'):
        store.save(changed)
    with pytest.raises(ValueError):
        store.save(initial, create=True)
    copy = store.duplicate(initial['id'])
    assert copy['id'] != initial['id'] and copy['actions'] == initial['actions']
    with pytest.raises(ValueError, match='Confirmation'):
        store.delete(copy['id'])
    store.delete(copy['id'], confirmed=True)
    assert len(store.list()[0]) == 1
    store.delete(initial['id'], confirmed=True)
    with pytest.raises(ValueError, match='supprimé'):
        store.save(updated)


@pytest.mark.parametrize('change', [
    lambda s: s.update(schema_version=2), lambda s: s.update(schema_version=True),
    lambda s: s.update(shell='ls'), lambda s: s.update(enabled='yes'),
    lambda s: s.update(id='../escape'), lambda s: s.update(name=''),
    lambda s: s.update(created_at='yesterday'), lambda s: s.update(actions='shell'),
    lambda s: s['actions'].append(s['actions'][0]),
])
def test_strict_schema(change):
    value = scenario('switch_workspace')
    change(value)
    with pytest.raises((ValueError, TypeError)):
        validate(value)


@pytest.mark.parametrize('change', [
    lambda a: a.update(type='shell'), lambda a: a.update(type=[]),
    lambda a: a.update(parameters={}), lambda a: a['parameters'].update(command='rm'),
    lambda a: a['parameters'].update(workspace=True), lambda a: a['parameters'].update(workspace=10),
    lambda a: a['parameters'].update(workspace='3});evil()'),
    lambda a: a.update(failure_policy='ignore'), lambda a: a.update(id=''),
])
def test_strict_action(change):
    action = new_action('switch_workspace', workspace=3)
    change(action)
    with pytest.raises(ValueError):
        validate_action(action)


@pytest.mark.parametrize(('kind', 'params'), [
    ('open_application', dict(application='/bin/bash', reuse=True)),
    ('open_application', dict(application='notion', reuse='yes')),
    ('move_window', dict(target='', workspace=3)),
    ('resume_project', dict(language='shell')),
    ('apply_layout', dict(layout='evil', workspace=3)),
    ('restore_session', dict(command='ls')),
])
def test_typed_parameters(kind, params):
    with pytest.raises(ValueError):
        new_action(kind, **params)


def test_unknown_files_preserved_and_reported(store):
    saved = store.save(scenario(), create=True)
    path = store.path(saved['id'])
    saved['schema_version'] = 99
    atomic_json(path, saved)
    before = path.read_bytes()
    rows, errors = store.list()
    assert not rows and 'Version' in errors[0]
    with pytest.raises(ValueError):
        store.save(dict(saved, schema_version=1))
    assert path.read_bytes() == before
    path.write_text('{"id": "a", "id": "b"}')
    assert 'dupliquée' in store.list()[1][0]


def test_atomic_failure_preserves_previous(store, monkeypatch):
    value = store.save(scenario(), create=True)
    before = store.path(value['id']).read_bytes()
    monkeypatch.setattr('jarvis.scenarios.storage.os.replace', Mock(side_effect=PermissionError()))
    with pytest.raises(PermissionError):
        store.save(dict(value, name='changed'))
    assert store.path(value['id']).read_bytes() == before
    assert not list(store.root.glob('.*.json*'))


def test_ambiguous_names_no_launch(store, monkeypatch):
    first = store.save(scenario(), create=True)
    second = store.save(dict(scenario(), name='revisions'), create=True)
    monkeypatch.setattr(engine, 'store', store)
    launch = Mock()
    monkeypatch.setattr(engine, 'request', launch)
    assert 'ambigu' in commands.launch('Révisions')
    launch.assert_not_called()
    assert store.resolve(first['id']) == first
    assert store.resolve(second['id']) == second


def test_preview_no_side_effects_or_database_creation(tmp_path, monkeypatch):
    from jarvis.projects import manager
    mutate = Mock(side_effect=AssertionError('Mutation pendant preview'))
    for method in ('act', 'half', 'switch'):
        monkeypatch.setattr(service, method, mutate)
    monkeypatch.setattr(service, 'read', lambda _: {'id': 3, 'name': '3'})
    monkeypatch.setattr(actions.shutil, 'which', lambda _: None)
    monkeypatch.setattr(manager, 'resume', mutate)
    monkeypatch.setattr(actions.sessions, 'restore_session', mutate)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    report = Engine(Store(tmp_path / 'absent')).preview(scenario(*FIELDS))
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert before == after
    assert not manager.DB_PATH.exists()
    assert report['confirmation_required']
    assert len(report['steps']) == 8
    assert any(not s['available'] for s in report['steps'])
    mutate.assert_not_called()


def test_preview_existing_database_unchanged(project, monkeypatch):
    from jarvis.projects import manager
    before = manager.DB_PATH.read_bytes()
    monkeypatch.setattr(actions.shutil, 'which', lambda _: '/usr/bin/code')
    report = Engine().preview(scenario('show_project_objective', 'restore_session'))
    assert report['steps'][0]['available']
    assert not report['steps'][1]['available']
    assert manager.DB_PATH.read_bytes() == before


def test_execution_order_events_and_history(store, fake_actions):
    value = scenario('switch_workspace', 'open_application', 'show_project_objective')
    runner = Engine(store, fake_actions)
    events = []
    runner.listeners.append(events.append)
    result = runner.run(value)
    assert result['state'] == 'success'
    assert [call.args[0]['type'] for call in fake_actions.execute.call_args_list] == [a['type'] for a in value['actions']]
    assert events[0]['state'] == 'pending'
    assert events[1]['state'] == 'running'
    assert events[-1]['state'] == 'success'
    assert all(s['state'] == 'pending' for s in events[0]['steps'])
    assert store.history()[0]['id'] == result['id']
    assert 'OK' not in json.dumps(store.history())


@pytest.mark.parametrize(('policy', 'expected', 'calls'), [('stop', 'skipped', 1), ('continue_on_error', 'success', 2)])
def test_failure_policy(store, fake_actions, policy, expected, calls):
    value = scenario('switch_workspace', 'open_application')
    value['actions'][0]['failure_policy'] = policy
    fake_actions.execute.side_effect = [ValueError('indisponible'), 'OK']
    result = Engine(store, fake_actions).run(value)
    assert result['state'] == 'failed'
    assert result['steps'][1]['state'] == expected
    assert fake_actions.execute.call_count == calls


def test_cancel_running_step_finishes_and_next_not_started(store, fake_actions):
    runner = Engine(store, fake_actions)
    def execute(*args):
        runner.cancel()
        return 'Déjà lancé'
    fake_actions.execute.side_effect = execute
    result = runner.run(scenario('switch_workspace', 'open_application'))
    assert [s['state'] for s in result['steps']] == ['success', 'cancelled']
    assert result['state'] == 'cancelled'
    assert fake_actions.execute.call_count == 1
    fake_actions.execute.side_effect = None
    assert runner.run(scenario('switch_workspace'))['state'] == 'success'


def test_concurrent_execution_rejected(store, fake_actions):
    runner = Engine(store, fake_actions)
    entered, release = threading.Event(), threading.Event()
    def execute(*args):
        entered.set()
        release.wait(3)
        return 'OK'
    fake_actions.execute.side_effect = execute
    thread = threading.Thread(target=runner.run, args=(scenario('switch_workspace'),))
    thread.start()
    try:
        assert entered.wait(2)
        with pytest.raises(ValueError, match='déjà'):
            runner.run(scenario())
        other = Engine(store, Mock())
        with pytest.raises(ValueError, match='ressources'):
            other.run(scenario())
        assert runner.status()['state'] == 'running'
        runner.cancel()
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive()


def test_confirmation_bound_to_revision_one_use_and_expiry(store, fake_actions, monkeypatch):
    runner = Engine(store, fake_actions)
    value = store.save(scenario('move_window'), create=True)
    with pytest.raises(ValueError, match='Confirmation'):
        runner.run(value)
    assert 'confirme scénario' in runner.request(value)
    fake_actions.execute.assert_not_called()
    token = runner._approval[0]
    value = store.save(dict(value, name='Modifié'))
    with pytest.raises(ValueError, match='modifié'):
        runner.confirm(token)
    runner.request(value)
    token = runner._approval[0]
    assert 'success' in runner.confirm(token)
    with pytest.raises(ValueError):
        runner.confirm(token)
    runner.request(value)
    token, _, saved, fingerprint = runner._approval
    runner._approval = (token, 0, saved, fingerprint)
    with pytest.raises(ValueError, match='expirée'):
        runner.confirm(token)
    runner.request(value)
    token = runner._approval[0]
    runner.cancel()
    with pytest.raises(ValueError):
        runner.confirm(token)


def test_disabled_and_unknown_action_never_execute(store, fake_actions):
    runner = Engine(store, fake_actions)
    value = scenario('switch_workspace')
    value['enabled'] = False
    with pytest.raises(ValueError, match='désactivé'):
        runner.request(value)
    value['enabled'] = True
    value['actions'][0]['type'] = 'shell'
    with pytest.raises(ValueError):
        runner.run(value)
    fake_actions.execute.assert_not_called()


def test_bounded_history_and_invalid_history_preserved(store, fake_actions):
    runner = Engine(store, fake_actions)
    for _ in range(105):
        runner.run(scenario())
    assert len(store.history()) == 100
    path = store.root / 'journal/runs.json'
    path.write_text('{"schema_version": 99, "runs": []}')
    before = path.read_bytes()
    with pytest.raises(ValueError):
        runner.run(scenario('switch_workspace'))
    assert path.read_bytes() == before
    fake_actions.execute.assert_not_called()


def test_history_write_failure_reported(store, fake_actions, monkeypatch):
    monkeypatch.setattr(store, 'record', Mock(side_effect=PermissionError()))
    result = Engine(store, fake_actions).run(scenario('switch_workspace'))
    assert result['state'] == 'success'
    assert 'non enregistré' in result['history_warning']


@pytest.mark.parametrize('app,workspace_name', [('jarvis', '3'), ('jarvis-hud', '3'), ('foot', 'special:jarvis')])
def test_jarvis_protection(app, workspace_name, monkeypatch):
    w = Window('0x123', app, 'title', 3, workspace_name, 0, False, 42)
    monkeypatch.setattr(service, 'windows', lambda: [w])
    dispatch = Mock()
    monkeypatch.setattr(service, '_run', dispatch)
    for kind in ('focus_window', 'move_window'):
        params = dict(target='0x123')
        if kind == 'move_window':
            params['workspace'] = 4
        with pytest.raises(WindowError, match='protégée'):
            Actions().execute(new_action(kind, **params))
    dispatch.assert_not_called()


def test_real_adapter_workspace_and_missing_program(monkeypatch):
    switch = Mock()
    monkeypatch.setattr(service, 'switch', switch)
    monkeypatch.setattr(service, 'read', lambda _: {})
    Actions().execute(new_action('switch_workspace', workspace=5))
    switch.assert_called_once_with(5)
    monkeypatch.setattr(actions.shutil, 'which', lambda _: None)
    with pytest.raises(ValueError, match='indisponible'):
        Actions().execute(new_action('open_application', application='steam', reuse=True))


def test_notion_launcher_and_reuse(tmp_path, monkeypatch):
    import subprocess
    root = tmp_path / 'share/applications'
    root.mkdir(parents=True)
    (root / 'notion.desktop').write_text('[Desktop Entry]\n')
    monkeypatch.setenv('XDG_DATA_HOME', str(root.parent))
    monkeypatch.setattr(actions.shutil, 'which', lambda app: '/usr/bin/' + app)
    launch = Mock()
    monkeypatch.setattr(subprocess, 'Popen', launch)
    open_application('notion')
    assert launch.call_args.args[0] == ['/usr/bin/gtk-launch', 'notion']
    assert not launch.call_args.kwargs.get('shell')
    launch.reset_mock()
    w = Window('0x1', 'chrome-www.notion.so__-Default', 'Notion', 5, '5', 0, False, 42)
    monkeypatch.setattr(service, 'windows', lambda: [w])
    assert 'réutilisée' in open_application('notion')
    launch.assert_not_called()
    open_application('notion', reuse=False)
    launch.assert_called_once()


def test_inventory_failure_no_duplicate(monkeypatch):
    monkeypatch.setattr(service, 'windows', Mock(side_effect=WindowError('indisponible')))
    with pytest.raises(WindowError):
        open_application('steam')


def test_modes_non_destructive_persistence_reset_and_association(store, monkeypatch):
    modes.STATE_PATH.write_text('{"mode":"travail"}')
    before = modes.STATE_PATH.read_bytes()
    assert profiles.load()['etudes']['applications'] == ['browser', 'notion']
    assert [p['workspace'] for p in profiles.load().values()] == [3, 4, 5]
    value = dict(profiles.load()['etudes'], workspace=7, layout='etudes', reuse=False)
    profiles.save('etudes', value)
    assert profiles.load()['etudes'] == value
    assert modes.STATE_PATH.read_bytes() == before
    monkeypatch.setattr(engine, 'store', store)
    saved = store.save(scenario('show_project_objective'), create=True)
    profiles.save('etudes', dict(value, scenario=saved['id']))
    built = profiles.scenario_for_mode('etudes')
    assert built['actions'][0]['parameters']['workspace'] == 7
    assert built['actions'][-1]['type'] == 'show_project_objective'
    profiles.reset('etudes')
    assert profiles.load() == profiles.defaults()
    assert modes.STATE_PATH.read_bytes() == before


def test_invalid_mode_configuration_preserved():
    profiles.path().write_text('{"schema_version":99, "profiles":{}}')
    before = profiles.path().read_bytes()
    with pytest.raises(ValueError):
        profiles.reset('etudes')
    assert 'non activé' in modes.activate_mode('etudes')
    assert profiles.path().read_bytes() == before


def test_custom_mode_routes_to_same_engine(monkeypatch):
    profiles.save('gaming', dict(profiles.defaults()['gaming'], workspace=7))
    request = Mock(return_value='test')
    monkeypatch.setattr(engine, 'request', request)
    assert modes.activate_mode('gaming') == 'test'
    assert request.call_args.args[0]['actions'][0]['parameters']['workspace'] == 7


@pytest.mark.parametrize('text,identifier', [
    ('Jarvis, lance scénario ouvre un terminal', 'scenarios.run'),
    ('prévisualise scénario reprends mon projet rust', 'scenarios.preview'),
    ('lancer le scenario Etudes', 'scenarios.run'),
    ('SIMULE SCÉNARIO A', 'scenarios.preview'),
    ('configure le mode Études', 'modes.configure'),
    ('historique des scénarios', 'scenarios.history'),
])
def test_registry_aliases_collisions(text, identifier):
    assert registry.resolve(text).command.id == identifier
    assert registry.resolve(text).command.name in registry.help_text()


def test_layout_skips_protected_fullscreen_and_cancels_between_windows(monkeypatch):
    from jarvis.services import window_commands as layouts
    rows = [Window('0x1', 'code', 'Code', 3, '3', 0, False, 1),
            Window('0x2', 'foot', 'Foot', 3, '3', 0, False, 2),
            Window('0x3', 'jarvis', 'Jarvis', 3, '3', 0, False, 3)]
    monkeypatch.setattr(service, 'windows', lambda: rows)
    act, half = Mock(), Mock()
    monkeypatch.setattr(service, 'act', act)
    monkeypatch.setattr(service, 'half', half)
    plan = layouts.build_plan('developpement', 7)
    assert len(plan.steps) == 2
    assert all(s[1] == 7 for s in plan.steps)
    cancelled = iter([False, True])
    response = layouts.execute_plan(plan, lambda: next(cancelled))
    assert response[0] == 'cancelled'
    act.assert_called_once_with('move', rows[0], 7)
    half.assert_called_once_with(rows[0], 'gauche')
    rows[0] = Window('0x1', 'steam', 'Steam', 4, '4', 0, False, 1, 1)
    assert not layouts.build_plan('gaming').steps


def test_layout_error_is_structured_failure_not_text_success(store, monkeypatch):
    w = Window('0x1', 'steam', 'Steam', 4, '4', 0, False, 1)
    monkeypatch.setattr(service, 'windows', lambda: [w])
    monkeypatch.setattr(service, 'act', Mock(side_effect=WindowError('Refus Hyprland')))
    value = new_scenario('Gaming', [new_action('apply_layout', layout='gaming', workspace=4)])
    result = Engine(store).run(value, confirmed=True)
    assert result['state'] == 'failed'
    assert 'Refus' in result['steps'][0]['message']


def test_layout_empty_skipped(store):
    value = new_scenario('Gaming', [new_action('apply_layout', layout='gaming', workspace=4)])
    result = Engine(store).run(value, confirmed=True)
    assert result['steps'][0]['state'] == 'skipped'


def test_project_and_session_text_errors_are_failures(store, monkeypatch):
    adapter = Actions()
    monkeypatch.setattr(adapter, 'check', lambda _: None)
    monkeypatch.setattr(actions, 'select_project', lambda _: {})
    monkeypatch.setattr(actions.manager, 'resume', lambda _: 'Projet refusé')
    monkeypatch.setattr(actions.sessions, 'restore_session', lambda: 'Impossible d’ouvrir le workspace')
    for kind in ('resume_project', 'restore_session'):
        result = Engine(store, adapter).run(scenario(kind))
        assert result['state'] == 'failed'


def test_modified_mode_invalidates_confirmation(store, fake_actions):
    runner = Engine(store, fake_actions)
    profiles.save('gaming', dict(profiles.defaults()['gaming'], layout='gaming'))
    value = profiles.scenario_for_mode('gaming')
    runner.request(value)
    token = runner._approval[0]
    profiles.save('gaming', dict(profiles.load()['gaming'], workspace=7))
    with pytest.raises(ValueError, match='modifié'):
        runner.confirm(token)
    fake_actions.execute.assert_not_called()


def test_history_strict_entries(store):
    atomic_json(store.root / 'journal/runs.json', {'schema_version': 1, 'runs': [{'state': 'success'}]})
    with pytest.raises(ValueError, match='invalide'):
        store.history()


def test_metadata_ids_cannot_use_mode_namespace(store):
    value = scenario()
    value['id'] = 'mode_gaming'
    with pytest.raises(ValueError, match='réservé'):
        store.save(value, create=True)


def test_full_capacity_history_remains_readable(store, fake_actions):
    value = new_scenario('Cent étapes', [new_action('switch_workspace', workspace=3) for _ in range(100)])
    Engine(store, fake_actions).run(value)
    run = store.history()[0]
    runs = [dict(deepcopy(run), id=f'run_{i}') for i in range(100)]
    path = store.root / 'journal/runs.json'
    atomic_json(path, {'schema_version': 1, 'runs': runs})
    assert path.stat().st_size > 2_000_000
    assert len(store.history()) == 100
