"""Adaptateurs textuels du registre, également utilisables par le HUD."""
from functools import wraps

from .engine import engine, format_preview, format_result


def readable(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, OSError, RuntimeError) as error:
            return f'Scénarios : {error}'
    return wrapped


@readable
def library():
    rows, errors = engine.store.list()
    return '\n'.join([*(f"{r['name']} [{r['id']}] — {'activé' if r['enabled'] else 'désactivé'}" for r in rows), *errors]) or 'Aucun scénario. Utilisez ouvre scénarios pour en créer un.'


@readable
def preview(name):
    return format_preview(engine.preview(engine.store.resolve(name)))


@readable
def launch(name):
    return engine.request(engine.store.resolve(name))


@readable
def confirm(token):
    result = engine.confirm(token)
    state = engine.status()
    if state and state['state'] == 'success' and state['scenario_id'].startswith('mode_'):
        from jarvis.modes.manager import save_mode
        save_mode(state['scenario_id'][5:])
    return result


def cancel():
    return engine.cancel()


def status():
    return format_result(engine.status())


@readable
def history():
    return '\n\n'.join(r['started_at'] + '\n' + format_result(r) for r in engine.store.history()) or 'Aucun historique de scénarios.'


def open_page():
    return 'Ouverture de la page Scénarios du HUD.'


def configure(name):
    from jarvis.modes.profiles import defaults
    if name not in defaults():
        return 'Mode inconnu : Travail, Gaming ou Études.'
    return f'Configuration du mode {name} dans la page Modes du HUD.'
