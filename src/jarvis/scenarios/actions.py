"""Adaptateurs des services existants. Préconditions strictement en lecture seule."""
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from jarvis.config import settings
from jarvis.projects import manager, sessions
from jarvis.services import window_commands
from jarvis.services.windows import existing_application, service

from .model import validate_action


def applications():
    return {'editor': settings.editors, 'terminal': [settings.terminal],
            'browser': settings.browsers, 'notion': ['notion'], 'steam': [settings.gaming]}


def project_read(language=None):
    # Les helpers historiques initialisent leur schéma : preview utilise une connexion RO.
    if not manager.DB_PATH.exists():
        return None
    with closing(sqlite3.connect(manager.DB_PATH.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
        try:
            if language:
                row = db.execute('SELECT path, language, objective FROM projects WHERE language=? ORDER BY last_opened DESC LIMIT 1', (language,)).fetchone()
            else:
                row = db.execute('SELECT path, language, objective FROM projects WHERE last_opened>0 ORDER BY last_opened DESC LIMIT 1').fetchone()
        except sqlite3.OperationalError:
            return None
    return dict(path=Path(row[0]), language=row[1], objective=row[2]) if row else None


def select_project(language):
    candidates = [p for p in manager.discover_projects() if p['language'] == language]
    previous = project_read(language)
    if previous:
        matches = [p for p in candidates if p['path'] == previous['path']]
        if matches:
            return matches[0]
    if len(candidates) != 1:
        raise ValueError('Projet absent ou ambigu : ouvrez explicitement un projet auparavant.')
    return candidates[0]


def session_read():
    project = project_read()
    if not project or project['path'].resolve() not in {p['path'] for p in manager.discover_projects()}:
        raise ValueError('Aucun projet actif reconnu.')
    with closing(sqlite3.connect(manager.DB_PATH.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
        try:
            row = db.execute('SELECT files_json FROM saved_sessions WHERE project_path=?', (str(project['path']),)).fetchone()
        except sqlite3.OperationalError:
            row = None
    if not row:
        raise ValueError('Aucune session sauvegardée pour le projet actif.')
    sessions.parse_files(row[0])
    return project


def target(query):
    rows = service.search(query)
    if len(rows) != 1:
        raise ValueError('Fenêtre absente ou ambiguë : précisez son adresse.')
    return service.validate(rows[0])


def executable(app):
    candidates = [settings.desktop_launcher] if app == 'notion' else applications()[app]
    found = next((path for name in candidates if (path := shutil.which(name))), None)
    if not found:
        raise ValueError(f'Application indisponible : {app}.')
    if app == 'notion':
        import os
        roots = [Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))]
        roots += [Path(p) for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')]
        desktop = settings.notion_desktop.removesuffix('.desktop') + '.desktop'
        if not any((root / 'applications' / desktop).is_file() for root in roots):
            raise ValueError('Lanceur notion.desktop introuvable.')
    return found


def open_application(app, reuse=True):
    """Lanceur autorisé partagé par les profils personnalisés et les scénarios."""
    import subprocess
    if reuse and existing_application(applications()[app]):
        return 'Fenêtre existante réutilisée, position conservée.'
    program = executable(app)
    args = [settings.notion_desktop] if app == 'notion' else []
    if app in {'editor', 'terminal'}:
        path = sessions.active_path()
        if path:
            args = [str(path)] if app == 'editor' else ['--working-directory', str(path)]
    subprocess.Popen([program, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return f'{app} : lancement demandé (apparition de fenêtre non garantie).'


class Actions:
    def check(self, action):
        validate_action(action)
        kind, p = action['type'], action['parameters']
        if kind == 'switch_workspace':
            service.read('activeworkspace')
        elif kind == 'open_application':
            if not (p['reuse'] and existing_application(applications()[p['application']])):
                executable(p['application'])
        elif kind in {'focus_window', 'move_window'}:
            window = target(p['target'])
            if kind == 'move_window' and window.fullscreen:
                raise ValueError('Plein écran préservé.')
        elif kind == 'apply_layout':
            plan = window_commands.build_plan(p['layout'], p['workspace'])
            return '\n'.join([*(f'{w.describe()} → bureau {number}, {kind}' for w, number, kind in plan.steps), *plan.notes])
        elif kind == 'resume_project':
            select_project(p['language'])
            if not any(shutil.which(app) for app in (*settings.editors, 'xdg-open')):
                raise ValueError('Éditeur indisponible.')
        elif kind == 'restore_session':
            session_read()
            executable('editor')
            executable('terminal')
        elif kind == 'show_project_objective' and not project_read():
            raise ValueError('Aucun projet actif ; peut être établi par une étape précédente.')
        return 'Préconditions accessibles vérifiées ; elles seront relues à l’exécution.'

    def execute(self, action, cancelled=lambda: False):
        kind, p = action['type'], action['parameters']
        self.check(action)
        if kind == 'switch_workspace':
            service.switch(p['workspace'])
        elif kind == 'open_application':
            return open_application(p['application'], p['reuse'])
        elif kind in {'focus_window', 'move_window'}:
            service.act('focus' if kind == 'focus_window' else 'move', target(p['target']),
                        *(() if kind == 'focus_window' else (p['workspace'],)))
        elif kind == 'apply_layout':
            plan = window_commands.build_plan(p['layout'], p['workspace'])
            if not plan.steps:
                return ('skipped', 'Aucune fenêtre admissible. ' + '\n'.join(plan.notes))
            return window_commands.execute_plan(plan, cancelled)
        elif kind == 'resume_project':
            result = manager.resume(select_project(p['language']))
            if 'SESSION REPRISE' not in result or 'éditeur indisponible' in result:
                raise ValueError(result)
            return result
        elif kind == 'restore_session':
            result = sessions.restore_session()
            if 'SESSION RESTAURÉE' not in result or any(word in result for word in ('indisponible', 'Erreur', 'Aucun éditeur')):
                raise ValueError(result)
            return result
        elif kind == 'show_project_objective':
            project = project_read()
            return project['objective'] or 'Aucun objectif mémorisé.'
        return 'Action effectuée.'
