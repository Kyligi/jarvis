"""Catalogue fermé : fonctions métier autorisées, jamais de shell ou Lua libre."""
from dataclasses import dataclass
import json
from collections.abc import Callable
from .conversation import object_schema, validate


@dataclass(frozen=True)
class Tool:
    id: str
    description: str
    schema: dict
    handler: Callable
    source: str
    risk: str = 'read'
    confirmation: str = 'none'
    timeout: float = 30
    result_format: str = 'text/plain; source locale explicite'
    resolver: Callable = lambda args: None

    def validate(self, arguments):
        validate(arguments, self.schema)

    def resolve(self, arguments):
        self.validate(arguments)
        return self.resolver(arguments)


def project_target(args):
    from jarvis.projects import manager
    from jarvis.core.text import normalize_words
    rows = [p for p in manager.discover_projects() if normalize_words(p['name']) == normalize_words(args['name'])]
    if len(rows) != 1 or not rows[0]['path'].is_dir():
        raise ValueError('Projet absent ou ambigu ; préciser un nom unique.')
    return str(rows[0]['path'].resolve())


def window_target(args):
    from jarvis.services.windows import service
    rows = [w for w in service.windows() if w.address == args['address']]
    if len(rows) != 1 or rows[0].protected or rows[0].fullscreen:
        raise ValueError('Fenêtre absente ou protégée ; choisir une adresse de mes fenêtres.')
    return rows[0]


def scenario_target(args):
    from jarvis.scenarios.engine import engine, format_preview
    value = engine.store.get(args['id'])
    if not value['enabled']:
        raise ValueError('Scénario désactivé.')
    return engine.fingerprint(value) + '\n' + format_preview(engine.preview(value))


def mode_target(args):
    from jarvis.modes import profiles
    from jarvis.projects.manager import get_active_project
    from jarvis.scenarios.engine import engine, format_preview
    profile = profiles.load()[args['name']]
    scenario = profiles.scenario_for_mode(args['name'])
    plan = format_preview(engine.preview(scenario))
    active = get_active_project()
    return (json.dumps({'profile': profile, 'actions': scenario['actions']}, ensure_ascii=False, sort_keys=True)
            + '\nProjet : ' + str(active) + '\n' + plan)


def build_catalogue():
    from jarvis.projects import manager
    from jarvis.monitoring import system, diagnostics
    from jarvis.services import window_commands as windows
    from jarvis.scenarios import commands as scenarios
    from jarvis.modes import manager as modes
    from jarvis.modes.profiles import load
    empty = object_schema({})
    rows = []
    for key, description, handler, source in [
        ('list_projects', 'Lister les projets Rust et Python disponibles.', manager.list_projects, 'projects.manager'),
        ('get_active_project', 'Lire le projet actif et son objectif.', manager.active_project_text, 'projects.manager'),
        ('get_git_status', 'Lire branche, commit et état Git du projet actif.', manager.active_git, 'projects.manager / Git'),
        ('get_system_metrics', 'Lire CPU, RAM, disque et batterie réels.', system.system_status, 'monitoring.system / psutil'),
        ('get_diagnostics', 'Lire le diagnostic local de ralentissement.', diagnostics.explain_slowdown, 'monitoring.diagnostics'),
        ('list_workspaces', 'Lister les bureaux Hyprland présents.', windows.desktops, 'services.windows / Hyprland'),
        ('list_windows', 'Lister les fenêtres et leurs adresses exactes.', windows.inventory, 'services.windows / Hyprland'),
        ('list_modes', 'Lister les profils de modes configurés.', lambda: json.dumps(load(), ensure_ascii=False), 'modes.profiles'),
        ('list_scenarios', 'Lister les scénarios et leurs identifiants.', scenarios.library, 'scenarios.engine.store'),
        ('get_scenario_status', 'Lire le statut du dernier scénario.', scenarios.status, 'scenarios.engine'),
        ('get_recent_project_sessions', 'Lire les dix dernières sessions de projets.', manager.recent_sessions, 'projects.manager / SQLite'),
    ]:
        rows.append(Tool(key, description, empty, handler, source))
    text = {'type': 'string', 'minLength': 1, 'maxLength': 120, 'pattern': r'[^\x00-\x1f]+'}
    scenario = object_schema({'id': dict(text, pattern=r'[a-zA-Z0-9_-]+')})
    rows.extend([
        Tool('activate_mode', 'Activer le profil : changer de bureau et lancer ses applications ; déplacements soumis aux confirmations historiques.',
             object_schema({'name': {'type': 'string', 'enum': ['travail', 'gaming', 'etudes']}}),
             modes.activate_mode, 'modes.manager', 'action', 'explicit', 60, resolver=mode_target),
        Tool('focus_window', 'Donner le focus à la fenêtre indiquée, pouvant changer le bureau visible.',
             object_schema({'address': dict(text, pattern=r'0x[0-9a-f]+')}),
             lambda address: windows.action('focus', address), 'services.windows', 'action', 'explicit', resolver=window_target),
        Tool('switch_workspace', 'Afficher le bureau numéroté de 1 à 9 (y compris vide).',
             object_schema({'number': {'type': 'integer', 'minimum': 1, 'maximum': 9}}),
             windows.switch, 'services.windows', 'action', 'explicit', resolver=lambda a: a['number']),
        Tool('open_project', 'Ouvrir le projet dans un éditeur et enregistrer sa reprise comme projet actif.',
             object_schema({'name': text}), manager.open_named_project, 'projects.manager',
             'action', 'explicit', resolver=project_target),
        Tool('run_scenario', 'Exécuter les étapes prévisualisées ; lancement de programmes et changements de bureau possibles. Les déplacements exigent aussi le code scénario.',
             scenario, lambda id: scenarios.launch(id), 'scenarios.engine', 'reinforced', 'explicit+scenario', 300, resolver=scenario_target),
        Tool('preview_scenario', 'Prévisualiser un scénario sans effectuer ses actions.', scenario,
             lambda id: scenarios.preview(id), 'scenarios.engine', resolver=scenario_target),
    ])
    return {tool.id: tool for tool in rows}
