import json
import subprocess
from dataclasses import replace
from unittest.mock import Mock

import pytest

from jarvis import registry
from jarvis.services import window_commands as commands
from jarvis.services.windows import (
    Window,
    WindowError,
    WindowService,
    build_action,
    parse_windows,
    service,
)


def window(**kwargs):
    return replace(Window('0x123', 'foot', 'École', 3, '3', 0, False, 42), **kwargs)


def row():
    return dict(address='0x123', **{'class': 'foot'}, title='École', workspace={'id': 3, 'name': '3'}, monitor=0, floating=False, pid=42)


@pytest.mark.parametrize('bad', [{}, [None], [{'address': 'evil'}], [dict(row(), floating='false')], [dict(row(), pid=True)]])
def test_invalid_inventory(bad):
    with pytest.raises(WindowError):
        parse_windows(bad)


def test_inventory_and_json(monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps([row()]), ''))
    monkeypatch.setattr(subprocess, 'run', run)
    assert WindowService().windows() == [window()]
    assert run.call_args.args[0] == ['hyprctl', 'clients', '-j']
    run.return_value.stdout = '{broken'
    with pytest.raises(WindowError, match='JSON'):
        WindowService().windows()


def test_search_title_class_address_and_workspace(monkeypatch):
    rows = [window(), window(address='0x456', title='autre', workspace=5), window(address='0x789', app='chrome', title='Foot manuel')]
    monkeypatch.setattr(service, 'windows', lambda: rows)
    assert len(service.search('FOOT')) == 3
    assert service.search('ecole') == [rows[0]]
    assert service.search('0x456') == [rows[1]]
    assert service.in_workspace(5) == [rows[1]]


def test_ambiguity_never_acts(monkeypatch):
    monkeypatch.setattr(service, 'windows', lambda: [window(), window(address='0x456')])
    act = Mock()
    monkeypatch.setattr(service, 'act', act)
    assert 'Plusieurs fenêtres' in commands.action('focus', 'foot')
    act.assert_not_called()
    commands.action('focus', '0x456')
    assert act.call_args.args[1].address == '0x456'


@pytest.mark.parametrize('rows', [[], [window(pid=99)], [window(app='other')]])
def test_stale_target(rows, monkeypatch):
    monkeypatch.setattr(service, 'windows', lambda: rows)
    run = Mock()
    monkeypatch.setattr(service, '_run', run)
    with pytest.raises(WindowError, match='fermée ou remplacée'):
        service.act('move', window(), 5)
    run.assert_not_called()


@pytest.mark.parametrize('target', [window(app='jarvis'), window(app='jarvis-hud'), window(workspace_name='special:jarvis')])
def test_jarvis_protected(target, monkeypatch):
    monkeypatch.setattr(service, 'windows', lambda: [target])
    run = Mock()
    monkeypatch.setattr(service, '_run', run)
    with pytest.raises(WindowError, match='protégée'):
        service.act('move', target, 5)
    run.assert_not_called()


@pytest.mark.parametrize('action,values,fragment', [('focus', (), 'hl.dsp.focus'), ('move', (3,), 'workspace="3",follow=false'), ('float', (), 'action="on"'), ('tile', (), 'action="off"'), ('center', (), '.center'), ('resize', (400, 500), 'x=400,y=500,relative=false'), ('position', (-100, 50), 'x=-100,y=50,relative=false')])
def test_allowed_lua(action, values, fragment):
    result = build_action(action, '0x123', *values)
    assert fragment in result
    assert 'window="address:0x123"' in result


@pytest.mark.parametrize('action,target,values', [('kill', '0x123', ()), ('focus', '0x123"});evil()', ()), ('move', '0x123', (True,)), ('move', '0x123', (10,)), ('resize', '0x123', (0, 5)), ('position', '0x123', ('20', 5)), ('float', '0x123', (1,))])
def test_reject_actions(action, target, values):
    with pytest.raises(WindowError):
        build_action(action, target, *values)


def test_revalidate_each_half_step(monkeypatch):
    current = [window()]
    monkeypatch.setattr(service, 'windows', lambda: current)
    monkeypatch.setattr(service, 'read', lambda _: [dict(id=0, width=1920, height=1080, scale=1.5, x=-1280, y=0, reserved=[0, 30, 0, 0])])
    calls = []
    def run(*args):
        calls.append(args)
        current[:] = [window(floating=True)]
    monkeypatch.setattr(service, '_run', run)
    service.half(window(), 'droite')
    assert 'x=640,y=690' in calls[1][1]
    assert 'x=-640,y=30' in calls[2][1]
    calls.clear()
    def close(*args):
        calls.append(args)
        current.clear()
    monkeypatch.setattr(service, '_run', close)
    with pytest.raises(WindowError):
        service.half(window(), 'gauche')
    assert len(calls) == 1


def test_center_requires_floating_and_errors(monkeypatch):
    monkeypatch.setattr(service, 'windows', lambda: [window()])
    with pytest.raises(WindowError, match='flottante'):
        service.act('center', window())
    monkeypatch.setattr(subprocess, 'run', Mock(return_value=subprocess.CompletedProcess([], 0, 'error: bad', '')))
    with pytest.raises(WindowError, match='refusée'):
        service.act('focus', window())


def test_active_empty_and_workspace_step(monkeypatch):
    monkeypatch.setattr(service, 'read', lambda _: {})
    assert commands.active() == 'Aucune fenêtre active.'
    run = Mock()
    monkeypatch.setattr(service, '_run', run)
    service.step(-1)
    assert 'm-1' in run.call_args.args[1]
    with pytest.raises(WindowError):
        service.step(True)


def test_typed_registry():
    assert registry.resolve('bureau 3').arguments == (3,)
    assert registry.resolve('déplace Éditeur au bureau 5').arguments == ('editeur', 5)
    assert registry.resolve('déplace Foot au bureau 20') is None


def test_layout_confirmation_and_protection(monkeypatch):
    rows = [window(app='code'), window(address='0x456'), window(address='0x789', app='jarvis')]
    monkeypatch.setattr(service, 'windows', lambda: rows)
    act, half = Mock(), Mock()
    monkeypatch.setattr(service, 'act', act)
    monkeypatch.setattr(service, 'half', half)
    assert 'confirme disposition' in commands.preview('developpement')
    act.assert_not_called()
    token = commands.pending.token
    assert 'appliqué' in commands.confirm(token)
    assert act.call_count == 2
    assert [call.args[1] for call in half.call_args_list] == ['gauche', 'droite']
    assert 'invalide' in commands.confirm(token)


def test_layout_ambiguous_missing_fullscreen(monkeypatch):
    monkeypatch.setattr(service, 'windows', lambda: [window(app='code'), window(app='code', address='0x456')])
    result = commands.preview('developpement')
    assert 'plusieurs fenêtres' in result and 'absente' in result
    assert commands.pending is None
    monkeypatch.setattr(service, 'windows', lambda: [window(app='steam', fullscreen=2)])
    assert 'plein écran préservé' in commands.preview('gaming')
    assert commands.pending is None


def test_layout_expired_changed_and_partial(monkeypatch):
    rows = [window(app='notion'), window(address='0x456', app='google-chrome')]
    monkeypatch.setattr(service, 'windows', lambda: rows)
    commands.preview('etudes')
    commands.pending = replace(commands.pending, expires=0)
    assert 'expirée' in commands.confirm(commands.pending.token)
    commands.preview('etudes')
    rows[0] = replace(rows[0], workspace=2)
    assert 'Organisation modifiée' in commands.confirm(commands.pending.token)
    commands.preview('etudes')
    monkeypatch.setattr(service, 'act', Mock())
    monkeypatch.setattr(service, 'half', Mock(side_effect=WindowError('fermée')))
    assert 'échec partiel' in commands.confirm(commands.pending.token)
    assert service.act.call_count == 1


def test_organize_skips_protected_and_fullscreen(monkeypatch):
    rows = [window(), window(app='jarvis', address='0x456'), window(app='game', address='0x789', fullscreen=2)]
    monkeypatch.setattr(service, 'windows', lambda: rows)
    monkeypatch.setattr(service, 'read', lambda _: {'id': 3})
    commands.preview('bureau')
    assert commands.pending.steps == ((rows[0], 3, 'tile'),)
    commands.cancel()
    assert commands.pending is None


def test_mode_reuses_exact_class_not_title(monkeypatch):
    from jarvis.modes import manager
    monkeypatch.setattr(service, 'windows', lambda: [window(app='steam'), window(app='chrome', title='notion')])
    assert 'déjà ouvert' in manager.launch(['steam'])
    popen = Mock()
    monkeypatch.setattr(subprocess, 'Popen', popen)
    monkeypatch.setattr(manager.shutil, 'which', lambda x: '/usr/bin/' + x)
    manager.launch(['notion'])
    popen.assert_called_once()


def test_windows_page_refresh_selection_errors_and_worker(qapp, monkeypatch):
    from PySide6.QtCore import QThread
    from test_interface import pump

    from jarvis.interface.context import AppContext
    from jarvis.interface.pages.windows import WindowsPage
    from jarvis.monitoring.collector import Snapshot
    target = window()
    state = {'windows': [target], 'workspaces': [{'id': 3, 'name': '3'}], 'monitors': [{'name': 'test'}], 'current': {'name': '3'}}
    def load():
        assert QThread.currentThread() != qapp.thread()
        return state
    monkeypatch.setattr(service, 'snapshot', load)
    context = AppContext(collector=Mock(collect=Mock(return_value=Snapshot(1, 2, 3, None, {}))))
    page = WindowsPage(context)
    try:
        page.set_active(True)
        pump(qapp, lambda: page.runner.task is None)
        assert 'test' in page.summary.text()
        page.tree.setCurrentItem(page.tree.topLevelItem(0).child(0))
        assert page.target == target
        assert all(b.isEnabled() for b in page.actions)
        def act(action, selected, *values):
            assert QThread.currentThread() != qapp.thread()
            assert selected == target
            raise WindowError('Fenêtre fermée')
        monkeypatch.setattr(service, 'act', act)
        results = []
        context.commands.result.connect(results.append)
        page.perform('focus')
        assert not context.commands.submit('aide')
        pump(qapp, lambda: not context.commands.busy)
        assert results == ['Fenêtre fermée']
        state['windows'] = []
        page.refresh()
        pump(qapp, lambda: page.runner.task is None)
        assert page.target is None
        assert 'Aucune fenêtre' in page.state.text()
        assert not any(b.isEnabled() for b in page.actions)
        monkeypatch.setattr(service, 'snapshot', Mock(side_effect=WindowError('indisponible')))
        page.refresh()
        pump(qapp, lambda: page.runner.task is None)
        assert 'Lecture impossible' in page.state.text()
        assert page.cached is None
    finally:
        context.shutdown()
        page.close()
        page.tree.clear()
        qapp.processEvents()
        page.deleteLater()
        context.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_protected_page_selection_and_preservation(qapp):
    from jarvis.interface.context import AppContext
    from jarvis.interface.pages.windows import WindowsPage
    from jarvis.monitoring.collector import Snapshot
    context = AppContext(collector=Mock(collect=Mock(return_value=Snapshot(1, 2, 3, None, {}))))
    page = WindowsPage(context)
    try:
        state = {'windows': [window(app='jarvis')], 'workspaces': [], 'monitors': [], 'current': {}}
        page.render(state)
        page.tree.setCurrentItem(page.tree.topLevelItem(0).child(0))
        assert not any(b.isEnabled() for b in page.actions)
        page.render(state)
        assert page.target.app == 'jarvis'
    finally:
        context.shutdown()
        page.close()
        page.tree.clear()
        qapp.processEvents()
        page.deleteLater()
        context.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_notion_webapp_class_reuse_and_studies(monkeypatch):
    from jarvis.modes import manager
    from jarvis.services.windows import existing_application
    notion = window(app='chrome-www.notion.so__-Default')
    monkeypatch.setattr(service, 'windows', lambda: [notion])
    assert existing_application(['notion']) == [notion]
    assert existing_application(['google-chrome']) == []
    assert 'confirme disposition' in commands.preview('etudes')
    assert commands.pending.steps == ((notion, 5, 'gauche'),)
    monkeypatch.setattr(manager, 'switch_workspace', Mock())
    monkeypatch.setattr(manager, 'launch', Mock(return_value='Chrome'))
    monkeypatch.setattr(manager.shutil, 'which', lambda _: '/usr/bin/gtk-launch')
    assert 'Notion déjà ouvert' in manager.activate_mode('etudes')


def test_fullscreen_changes_never_move(monkeypatch):
    monkeypatch.setattr(service, 'windows', lambda: [window(fullscreen=2)])
    with pytest.raises(WindowError, match='plein écran'):
        service.act('move', window(), 4)


@pytest.mark.parametrize('resource,payload', [('workspaces', {}), ('workspaces', [{'id': True, 'name': '3'}]), ('activeworkspace', []), ('monitors', [{'id': 0, 'name': 'test', 'x': 0, 'y': 0, 'width': 100, 'height': 100, 'scale': 0}])])
def test_malformed_resources(resource, payload, monkeypatch):
    monkeypatch.setattr(service, '_run', lambda *args: json.dumps(payload))
    with pytest.raises(WindowError):
        service.read(resource)


def test_service_timeout_and_unexpected_dispatch_response(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', Mock(side_effect=subprocess.TimeoutExpired('hyprctl', 5)))
    with pytest.raises(WindowError, match='délai'):
        WindowService().read('clients')
    monkeypatch.setattr(subprocess, 'run', Mock(return_value=subprocess.CompletedProcess([], 0, 'unknown request', '')))
    with pytest.raises(WindowError, match='refusée'):
        WindowService()._run('dispatch', build_action('focus', '0x123'))
