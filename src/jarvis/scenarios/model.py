"""Schéma fermé : aucune commande, chemin exécutable ou expression libre."""
import re
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

APPLICATIONS = ('editor', 'terminal', 'browser', 'notion', 'steam')
LAYOUTS = ('developpement', 'etudes', 'gaming')
# Le catalogue décrit aussi les formulaires HUD. Ajouter un type exige un adaptateur.
FIELDS = {
    'switch_workspace': {'workspace': 'workspace'},
    'open_application': {'application': APPLICATIONS, 'reuse': 'bool'},
    'focus_window': {'target': 'target'},
    'move_window': {'target': 'target', 'workspace': 'workspace'},
    'apply_layout': {'layout': LAYOUTS, 'workspace': 'workspace'},
    'resume_project': {'language': ('Rust', 'Python')},
    'restore_session': {},
    'show_project_objective': {},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value):
        raise ValueError('Identifiant invalide.')
    return value


def text(value, maximum, empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()) or any(ord(c) < 32 and c != '\n' for c in value):
        raise ValueError('Texte vide, trop long ou invalide.')


def validate_action(action):
    if not isinstance(action, dict) or set(action) != {'id', 'type', 'parameters', 'failure_policy'}:
        raise ValueError('Champs d’action invalides.')
    identifier(action['id'])
    kind = action['type']
    if not isinstance(kind, str) or kind not in FIELDS:
        raise ValueError('Action inconnue ou interdite.')
    if action['failure_policy'] not in ('stop', 'continue_on_error'):
        raise ValueError('Politique d’échec invalide.')
    params = action['parameters']
    if not isinstance(params, dict) or set(params) != set(FIELDS[kind]):
        raise ValueError('Paramètres manquants ou inconnus.')
    for key, rule in FIELDS[kind].items():
        value = params[key]
        if isinstance(rule, tuple):
            if value not in rule:
                raise ValueError(f'{key} non autorisé.')
        elif rule == 'workspace':
            if type(value) is not int or not 1 <= value <= 9:
                raise ValueError('Workspace attendu : entier 1–9.')
        elif rule == 'bool':
            if type(value) is not bool:
                raise ValueError('Booléen attendu.')
        else:
            text(value, 256)
    return deepcopy(action)


def validate(value):
    required = {'id', 'name', 'description', 'schema_version', 'enabled', 'actions', 'created_at', 'updated_at'}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError('Champs du scénario invalides.')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Version de schéma non prise en charge ; fichier conservé.')
    identifier(value['id'])
    text(value['name'], 100)
    text(value['description'], 2000, True)
    if type(value['enabled']) is not bool:
        raise ValueError('État activé invalide.')
    for key in ('created_at', 'updated_at'):
        if not isinstance(value[key], str) or datetime.fromisoformat(value[key]).tzinfo is None:
            raise ValueError('Date ISO avec fuseau attendue.')
    if not isinstance(value['actions'], list) or len(value['actions']) > 100:
        raise ValueError('Maximum 100 étapes.')
    ids = []
    for action in value['actions']:
        validate_action(action)
        ids.append(action['id'])
    if len(set(ids)) != len(ids):
        raise ValueError('Identifiants d’étapes dupliqués.')
    return deepcopy(value)


def new_action(kind='switch_workspace', **parameters):
    return validate_action(dict(id=uuid4().hex, type=kind, parameters=parameters, failure_policy='stop'))


def new_scenario(name='Nouveau scénario', actions=None):
    return validate(dict(id=uuid4().hex, name=name, description='', schema_version=1,
                         enabled=True, actions=actions or [], created_at=now(), updated_at=now()))
