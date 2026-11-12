"""Exécution synchrone à placer dans un worker ; état et annulation thread-safe."""
import hashlib
import json
import secrets
import threading
import time
from copy import deepcopy
from uuid import uuid4

from .actions import Actions
from .model import now, validate
from .storage import Store, file_lock


class Engine:
    def __init__(self, store=None, actions=None):
        self.store = store or Store()
        self.actions = actions or Actions()
        self._lock = threading.RLock()
        self._running = False
        self._cancel = threading.Event()
        self._state = None
        self._approval = None
        self.listeners = []

    def status(self):
        with self._lock:
            return deepcopy(self._state)

    def confirmation_pending(self) -> bool:
        """Indique si un scénario attend une confirmation valide.

        Ne révèle jamais le jeton de confirmation.
        """
        with self._lock:
            approval = self._approval

            if approval is None:
                return False

            return time.monotonic() <= approval[1]

    def cancel(self):
        with self._lock:
            self._approval = None
            if self._running:
                self._cancel.set()
                return 'Annulation demandée : aucune nouvelle étape ; les actions terminées restent appliquées.'
        return 'Aucun scénario en cours. Confirmation en attente annulée.'

    def publish(self, result):
        with self._lock:
            self._state = deepcopy(result)
        for listener in tuple(self.listeners):
            try:
                listener(deepcopy(result))
            except Exception:
                # Un observateur ne doit pas interrompre les actions ni la journalisation.
                pass

    def preview(self, value):
        value = validate(value)
        rows = []
        for action in value['actions']:
            kind = action['type']
            effects = []
            if kind in {'open_application', 'resume_project', 'restore_session'}:
                effects.append('peut lancer un programme')
            if kind in {'move_window', 'apply_layout'}:
                effects.append('peut déplacer des fenêtres ; Jarvis et plein écran protégés')
            if kind in {'switch_workspace', 'restore_session'}:
                effects.append('peut changer de workspace')
            try:
                note = self.actions.check(action)
                available = True
            except (OSError, ValueError, RuntimeError) as error:
                available, note = False, str(error)
            rows.append(dict(id=action['id'], type=kind, parameters=deepcopy(action['parameters']),
                             failure_policy=action['failure_policy'], available=available,
                             note=note, effects=effects))
        return dict(id=value['id'], name=value['name'], enabled=value['enabled'], steps=rows,
                    confirmation_required=any(a['type'] in {'move_window', 'apply_layout'} for a in value['actions']))

    @staticmethod
    def fingerprint(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def request(self, value):
        value = validate(value)
        if not value['enabled']:
            raise ValueError('Scénario désactivé.')
        plan = self.preview(value)
        if plan['confirmation_required']:
            token = secrets.token_hex(4)
            with self._lock:
                if self._running:
                    raise ValueError('Un scénario est déjà en cours.')
                self._approval = (token, time.monotonic() + 60, deepcopy(value), self.fingerprint(value))
            return format_preview(plan) + f'\nConfirmer ces actions sur les fenêtres admissibles au moment de chaque étape : confirme scénario {token}\nValable 60 s ; annule scénario pour abandonner.'
        return format_result(self.run(value))

    def confirm(self, token):
        with self._lock:
            approval, self._approval = self._approval, None
        if not approval or token != approval[0] or time.monotonic() > approval[1]:
            raise ValueError('Confirmation absente, invalide ou expirée.')
        value = approval[2]
        # Scénarios persistants : toute édition ou suppression invalide l’accord.
        if not value['id'].startswith('mode_'):
            current = self.store.get(value['id'])
            if self.fingerprint(current) != approval[3]:
                raise ValueError('Scénario modifié : recommencez la prévisualisation.')
        else:
            from jarvis.modes.profiles import scenario_for_mode
            current = scenario_for_mode(value['id'][5:])
            if current['actions'] != value['actions']:
                raise ValueError('Mode modifié : recommencez la prévisualisation.')
        return format_result(self.run(value, confirmed=True))

    def run(self, value, *, confirmed=False):
        value = validate(value)
        if not value['enabled']:
            raise ValueError('Scénario désactivé.')
        if any(a['type'] in {'move_window', 'apply_layout'} for a in value['actions']) and confirmed is not True:
            raise ValueError('Confirmation explicite requise avant les déplacements.')
        with self._lock:
            if self._running:
                raise ValueError('Un scénario est déjà en cours ; ressources du bureau sérialisées.')
            self._running = True
            self._approval = None
            self._cancel.clear()
        result = dict(id=uuid4().hex, scenario_id=value['id'], name=value['name'], started_at=now(),
                      finished_at=None, state='pending', steps=[dict(id=a['id'], type=a['type'], state='pending', message='') for a in value['actions']])
        try:
            with file_lock(self.store.root / '.execution.lock', blocking=False):
                # Vérifier le journal avant la première mutation. Un journal inconnu reste intact.
                self.store.history()
                self.publish(result)
                result['state'] = 'running'
                self.publish(result)
                failed = False
                stopped = False
                for action, step in zip(value['actions'], result['steps']):
                    if self._cancel.is_set():
                        step['state'] = 'cancelled'
                    elif stopped:
                        step['state'] = 'skipped'
                        step['message'] = 'Non commencée après échec.'
                    else:
                        step['state'] = 'running'
                        self.publish(result)
                        try:
                            response = self.actions.execute(action, self._cancel.is_set)
                            if isinstance(response, tuple):
                                step['state'], step['message'] = response
                            else:
                                step.update(state='success', message=str(response))
                        except Exception as error:
                            # Détails connus seulement ; les erreurs inattendues peuvent contenir des secrets.
                            message = str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__
                            step.update(state='failed', message=message[:2000])
                            failed = True
                            stopped = action['failure_policy'] == 'stop'
                    self.publish(result)
                result['state'] = 'failed' if failed else ('cancelled' if any(s['state'] == 'cancelled' for s in result['steps']) else 'success')
                result['finished_at'] = now()
                # Pas de contenu d’objectif, chemin ou titre dans le journal durable.
                durable = deepcopy(result)
                for step in durable['steps']:
                    step['message'] = 'Voir le résultat en mémoire ; détails privés non conservés.'
                try:
                    self.store.record(durable)
                except (OSError, ValueError) as error:
                    result['history_warning'] = f'Historique non enregistré ({type(error).__name__}), actions non annulées.'
                self.publish(result)
                return result
        finally:
            with self._lock:
                self._running = False


def format_preview(plan):
    lines = [f"Prévisualisation — {plan['name']} ({'activé' if plan['enabled'] else 'désactivé'})"]
    for n, step in enumerate(plan['steps'], 1):
        lines.append(f"{n}. {step['type']} {step['parameters']} — {step['failure_policy']}\n   {'Disponible' if step['available'] else 'Potentiellement indisponible'} : {step['note']}\n   " + ', '.join(step['effects']))
    return '\n'.join(lines) + '\nAucune action exécutée. Les préconditions peuvent changer entre les étapes.'


def format_result(result):
    if not result:
        return 'Aucune exécution dans cette session.'
    return f"{result['name']} — {result['state']}\n" + '\n'.join(
        f"{n}. {s['type']} : {s['state']} — {s['message']}" for n, s in enumerate(result['steps'], 1)
    ) + ('\n' + result['history_warning'] if result.get('history_warning') else '')


engine = Engine()
