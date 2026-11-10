"""Ollama HTTP local sans proxy, redirection, pull ni API cloud."""
import http.client
import json
import socket
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager

from .config import endpoint_parts


class AIError(RuntimeError):
    pass


class Cancelled(AIError):
    pass


class Backend(ABC):
    @abstractmethod
    def inspect(self, config, cancelled): ...

    @abstractmethod
    def generate(self, config, messages, schema, cancelled, on_chunk): ...


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Clé dupliquée.')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nombre invalide.')))


class OllamaBackend(Backend):
    def __init__(self):
        self.metrics = {}
        self.local = threading.local()

    @contextmanager
    def request(self, config, path, cancelled, payload=None):
        url = endpoint_parts(config.endpoint)
        timeout = min(config.request_timeout, 5) if payload is None else config.request_timeout
        deadline = min(time.monotonic() + timeout, getattr(self.local, 'deadline', float('inf')))
        timeout = deadline - time.monotonic()
        if timeout <= 0:
            raise AIError('Délai Ollama dépassé.')
        connection = http.client.HTTPConnection(url.hostname, url.port, timeout=timeout)
        finished = threading.Event()
        active_socket = [None]
        response = None
        def watch():
            while not finished.wait(.05):
                if cancelled.is_set() or time.monotonic() >= deadline:
                    sock = connection.sock or active_socket[0]
                    if sock:
                        try:
                            sock.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                    return
        watcher = threading.Thread(target=watch, daemon=True)
        try:
            if cancelled.is_set():
                raise Cancelled('Génération annulée.')
            watcher.start()
            connection.request('GET' if payload is None else 'POST', path,
                               body=None if payload is None else json.dumps(payload),
                               headers={'Content-Type': 'application/json'})
            active_socket[0] = connection.sock
            response = connection.getresponse()
            if response.status != 200:
                raise AIError(f'Ollama : HTTP {response.status}. Vérifier serveur et modèle local.')
            yield response
            if cancelled.is_set():
                raise Cancelled('Génération annulée.')
            if time.monotonic() >= deadline:
                raise AIError('Délai Ollama dépassé.')
        except (OSError, http.client.HTTPException) as error:
            if cancelled.is_set():
                raise Cancelled('Génération annulée.') from error
            raise AIError('Ollama inaccessible ou délai dépassé ; vérifier le serveur local.') from error
        finally:
            finished.set()
            if response is not None:
                response.close()
            connection.close()
            if watcher.ident:
                watcher.join()

    def get(self, config, path, cancelled):
        with self.request(config, path, cancelled) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise AIError('Réponse Ollama trop volumineuse.')
        value = decode(raw)
        if not isinstance(value, dict):
            raise AIError('Réponse Ollama invalide.')
        return value

    def inspect(self, config, cancelled):
        version = self.get(config, '/api/version', cancelled).get('version', 'inconnue')
        models = self.get(config, '/api/tags', cancelled).get('models', [])
        # Remote aliases can exist on a local server: exclude them before inference.
        local = [m for m in models if not m.get('remote_host') and not m.get('remote_model')
                 and 'cloud' not in m.get('name', '').lower() and m.get('size', 0) > 0]
        names = [m['name'] for m in local]
        loaded = self.get(config, '/api/ps', cancelled).get('models', [])
        return {'version': version, 'models': names, 'installed': config.model in names,
                'loaded': loaded, 'metrics': dict(self.metrics)}

    def generate(self, config, messages, schema, cancelled, on_chunk):
        started = time.monotonic()
        self.local.deadline = started + config.request_timeout
        try:
            result = self._generate(config, messages, schema, cancelled, on_chunk)
            self.metrics['request_total_seconds'] = time.monotonic() - started
            return result
        finally:
            del self.local.deadline

    def _generate(self, config, messages, schema, cancelled, on_chunk):
        status = self.inspect(config, cancelled)
        if not status['installed']:
            raise AIError('Modèle local absent. Installation volontaire requise ; aucun téléchargement effectué.')
        # /api/show also detects aliases redirecting inference to a cloud model.
        with self.request(config, '/api/show', cancelled, {'model': config.model}) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise AIError('Métadonnées modèle trop volumineuses.')
        details = decode(raw)
        if not isinstance(details, dict):
            raise AIError('Métadonnées modèle invalides.')
        if details.get('remote_host') or details.get('remote_model'):
            raise AIError('Modèle distant refusé.')
        payload = {'model': config.model, 'messages': messages, 'format': schema,
                   'stream': config.streaming_enabled, 'keep_alive': config.keep_alive,
                   'options': {'temperature': config.temperature, 'num_ctx': config.context_limit,
                               'num_predict': config.max_output_tokens}}
        if 'thinking' in details.get('capabilities', []):
            payload['think'] = False
        start = time.monotonic()
        self.metrics = {}
        chunks, total, done = [], 0, False
        with self.request(config, '/api/chat', cancelled, payload) as response:
            while True:
                if cancelled.is_set():
                    raise Cancelled('Génération annulée.')
                raw = response.readline(65537)
                if not raw:
                    break
                total += len(raw)
                if len(raw) > 65536 or total > 262144:
                    raise AIError('Réponse Ollama trop volumineuse.')
                packet = decode(raw)
                if not isinstance(packet, dict) or not isinstance(packet.get('message', {}), dict):
                    raise AIError('Paquet Ollama invalide.')
                if packet.get('error'):
                    raise AIError('Erreur du moteur Ollama local.')
                chunk = packet.get('message', {}).get('content', '')
                if not isinstance(chunk, str):
                    raise AIError('Fragment invalide.')
                if chunk:
                    self.metrics.setdefault('first_token_seconds', time.monotonic() - start)
                    chunks.append(chunk)
                    on_chunk(chunk)
                if packet.get('done'):
                    if packet.get('done_reason') == 'length':
                        raise AIError('Réponse tronquée : reformuler une demande plus courte.')
                    done = True
                    duration = packet.get('eval_duration', 0)
                    self.metrics.update(total_seconds=time.monotonic() - start,
                                        tokens=packet.get('eval_count', 0),
                                        tokens_per_second=packet.get('eval_count', 0) * 1e9 / duration if duration else None)
                    break
        if not done:
            raise AIError('Réponse Ollama interrompue ou délai dépassé.')
        return ''.join(chunks)
