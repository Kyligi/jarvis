"""Surcharges versionnées séparées du TOML et de l’état historique des modes."""
from copy import deepcopy
from jarvis.scenarios.model import APPLICATIONS, LAYOUTS, new_scenario, new_action, identifier
from jarvis.scenarios.storage import read_json, atomic_json, file_lock


def path():
    from .manager import STATE_PATH
    return STATE_PATH.parent / 'modes.json'


def defaults():
    from .manager import MODES
    apps = {'travail': ['editor', 'terminal'], 'gaming': ['steam'], 'etudes': ['browser', 'notion']}
    return {name: dict(workspace=p['workspace'], applications=apps[name], layout=None, reuse=True, scenario=None)
            for name, p in MODES.items()}


def validate(profile):
    if not isinstance(profile, dict) or set(profile) != {'workspace', 'applications', 'layout', 'reuse', 'scenario'}:
        raise ValueError('Champs du profil invalides.')
    if type(profile['workspace']) is not int or not 1 <= profile['workspace'] <= 9:
        raise ValueError('Workspace attendu : 1–9.')
    apps = profile['applications']
    if not isinstance(apps, list) or any(not isinstance(a, str) or a not in APPLICATIONS for a in apps) or len(set(apps)) != len(apps):
        raise ValueError('Applications non autorisées ou dupliquées.')
    if profile['layout'] is not None and profile['layout'] not in LAYOUTS:
        raise ValueError('Disposition non autorisée.')
    if type(profile['reuse']) is not bool:
        raise ValueError('Réutilisation : booléen attendu.')
    if profile['scenario'] is not None:
        identifier(profile['scenario'])
    return deepcopy(profile)


def load():
    result = defaults()
    if not path().exists():
        return result
    value = read_json(path())
    if not isinstance(value, dict) or set(value) != {'schema_version', 'profiles'} or type(value['schema_version']) is not int or value['schema_version'] != 1 or not isinstance(value['profiles'], dict):
        raise ValueError('Configuration des modes invalide ou version inconnue ; fichier conservé.')
    if set(value['profiles']) - set(result):
        raise ValueError('Mode inconnu ; fichier conservé.')
    for name, profile in value['profiles'].items():
        result[name] = validate(profile)
    return result


def save(name, profile):
    if name not in defaults():
        raise ValueError('Mode inconnu.')
    profile = validate(profile)
    with file_lock(path().with_suffix('.lock')):
        values = load()
        values[name] = profile
        atomic_json(path(), dict(schema_version=1, profiles=values))
    return 'Paramètres du mode enregistrés.'


def reset(name):
    if name not in defaults():
        raise ValueError('Mode inconnu.')
    return save(name, defaults()[name])


def scenario_for_mode(name):
    from jarvis.scenarios.engine import engine
    p = load()[name]
    actions = [new_action('switch_workspace', workspace=p['workspace'])]
    actions += [new_action('open_application', application=a, reuse=p['reuse']) for a in p['applications']]
    if p['layout']:
        actions.append(new_action('apply_layout', layout=p['layout'], workspace=p['workspace']))
    if p['scenario']:
        associated = engine.store.get(p['scenario'])
        if not associated['enabled']:
            raise ValueError('Scénario associé désactivé.')
        actions += associated['actions']
    # Identités déterministes pour comparer un mode lors de sa confirmation.
    for n, action in enumerate(actions):
        action['id'] = f'step_{n}'
    value = new_scenario('Mode ' + name, actions)
    value['id'] = 'mode_' + name
    return value
