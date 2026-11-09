"""JSON atomique, verrou interprocessus, fichiers invalides conservés."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4
from jarvis.config import settings
from jarvis.core.text import normalize_words
from .model import validate, identifier, now, text
from datetime import datetime

ROOT = settings.data_dir / 'scenarios'


def read_json(path):
    if path.stat().st_size > 2_000_000:
        raise ValueError('Fichier trop volumineux, conservé.')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Clé JSON dupliquée.')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def file_lock(path, blocking=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as error:
            raise ValueError('Une exécution utilise déjà les ressources du bureau.') from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class Store:
    def __init__(self, root=None):
        self._root = Path(root) if root else None

    @property
    def root(self):
        return self._root or ROOT

    def path(self, key):
        return self.root / (identifier(key) + '.json')

    def get(self, key):
        value = validate(read_json(self.path(key)))
        if value['id'] != key:
            raise ValueError('Identité du fichier incohérente.')
        return value

    def list(self):
        rows, errors = [], []
        for path in sorted(self.root.glob('*.json')):
            try:
                rows.append(self.get(path.stem))
            except (OSError, ValueError, TypeError) as error:
                errors.append(f'{path.name} : {error}')
        return rows, errors

    def resolve(self, name):
        rows, _ = self.list()
        matches = [row for row in rows if row['id'] == name or normalize_words(row['name']) == normalize_words(name)]
        if len(matches) != 1:
            raise ValueError('Scénario introuvable ou nom ambigu. Correspondances : ' +
                             ', '.join(f"{r['name']} [{r['id']}]" for r in matches))
        return matches[0]

    def save(self, value, create=False):
        value = validate(value)
        if value['id'].startswith('mode_'):
            raise ValueError('Préfixe mode_ réservé aux profils.')
        with file_lock(self.root / '.storage.lock'):
            path = self.path(value['id'])
            if path.exists():
                if create:
                    raise ValueError('Identifiant déjà utilisé.')
                previous = self.get(value['id'])  # Ne jamais écraser un schéma inconnu.
                if value['updated_at'] != previous['updated_at']:
                    raise ValueError('Scénario modifié ailleurs : actualisez avant d’enregistrer.')
                value['created_at'] = previous['created_at']
            elif not create:
                raise ValueError('Scénario supprimé ailleurs : créez une copie.')
            value['updated_at'] = now()
            atomic_json(path, value)
        return value

    def duplicate(self, key):
        value = deepcopy(self.get(key))
        value.update(id=uuid4().hex, name=(value['name'][:90] + ' — copie'), created_at=now(), updated_at=now())
        return self.save(value, create=True)

    def delete(self, key, *, confirmed=False):
        if confirmed is not True:
            raise ValueError('Confirmation de suppression requise.')
        with file_lock(self.root / '.storage.lock'):
            self.get(key)
            self.path(key).unlink()

    def history(self):
        path = self.root / 'journal' / 'runs.json'
        if not path.exists():
            return []
        value = read_json(path)
        if not isinstance(value, dict) or value.get('schema_version') != 1 or not isinstance(value.get('runs'), list):
            raise ValueError('Historique invalide ; fichier conservé.')
        if len(value['runs']) > 100 or set(value) != {'schema_version', 'runs'} or type(value['schema_version']) is not int:
            raise ValueError('Historique invalide ; fichier conservé.')
        for run in value['runs']:
            validate_run(run)
        return value['runs']

    def record(self, result):
        validate_run(result)
        with file_lock(self.root / '.storage.lock'):
            rows = self.history()
            atomic_json(self.root / 'journal' / 'runs.json', {'schema_version': 1, 'runs': [result, *rows][:100]})


def validate_run(run):
    states = ('pending', 'running', 'success', 'skipped', 'failed', 'cancelled')
    if not isinstance(run, dict) or set(run) != {'id', 'scenario_id', 'name', 'started_at', 'finished_at', 'state', 'steps'}:
        raise ValueError('Entrée d’historique invalide ; fichier conservé.')
    identifier(run['id'])
    identifier(run['scenario_id'])
    text(run['name'], 100)
    if run['state'] not in states or not isinstance(run['steps'], list) or len(run['steps']) > 100:
        raise ValueError('États d’historique invalides.')
    for key in ('started_at', 'finished_at'):
        value = run[key]
        if not isinstance(value, str) or datetime.fromisoformat(value).tzinfo is None:
            raise ValueError('Date d’historique invalide.')
    for step in run['steps']:
        if not isinstance(step, dict) or set(step) != {'id', 'type', 'state', 'message'}:
            raise ValueError('Étape d’historique invalide.')
        identifier(step['id'])
        text(step['type'], 64)
        text(step['message'], 2000, True)
        if step['state'] not in states:
            raise ValueError('État d’étape invalide.')
