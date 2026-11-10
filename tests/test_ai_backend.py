"""HTTP simulé : aucun serveur, modèle, réseau ou GPU requis."""
import json
import threading
from io import BytesIO
from unittest.mock import Mock

import pytest

from jarvis.ai.backend import AIError, Cancelled, OllamaBackend
from jarvis.ai.config import AIConfig


class Response:
    def __init__(self, value, status=200):
        self.status = status
        self.stream = BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())

    def close(self):
        self.stream.close()

    def read(self, size):
        return self.stream.read(size)

    def readline(self, size):
        return self.stream.readline(size)


def transport(monkeypatch, responses):
    connections, requests = [], []
    def factory(host, port, timeout):
        connection = Mock()
        connection.request.side_effect = lambda *a, **kw: requests.append((a, kw))
        connection.getresponse.return_value = responses.pop(0)
        connections.append(connection)
        return connection
    monkeypatch.setattr('jarvis.ai.backend.http.client.HTTPConnection', factory)
    return connections, requests


def packets():
    return [Response({'version': '0.test'}), Response({'models': [{'name': 'qwen3:4b', 'size': 100}]}),
            Response({'models': [{'name': 'qwen3:4b', 'size': 100, 'size_vram': 80}]})]


def test_detection_and_metrics(monkeypatch):
    connections, requests = transport(monkeypatch, packets())
    status = OllamaBackend().inspect(AIConfig(), threading.Event())
    assert status['installed'] and status['version'] == '0.test'
    assert status['loaded'][0]['size_vram'] == 80
    assert [r[0][1] for r in requests] == ['/api/version', '/api/tags', '/api/ps']
    assert all(c.close.called for c in connections)


@pytest.mark.parametrize('models', [[], [{'name': 'qwen3:4b', 'size': 100, 'remote_host': 'cloud'}],
                                    [{'name': 'qwen3:4b', 'size': 0}]])
def test_missing_or_cloud_model_refused(monkeypatch, models):
    responses = packets()
    responses[1] = Response({'models': models})
    _, requests = transport(monkeypatch, responses)
    with pytest.raises(AIError, match='absent'):
        OllamaBackend().generate(AIConfig(), [], {}, threading.Event(), lambda _: None)
    assert not any(r[0][0] == 'POST' for r in requests)


@pytest.mark.parametrize('streaming', [True, False])
def test_streaming_and_generation_parameters(monkeypatch, streaming):
    reply = '{"reply":"Bonjour","calls":[]}'
    final = {'message': {'content': reply if not streaming else ''}, 'done': True,
             'eval_count': 10, 'eval_duration': 2_000_000_000}
    raw = (json.dumps({'message': {'content': reply}, 'done': False}) + '\n') if streaming else ''
    raw += json.dumps(final) + '\n'
    _, requests = transport(monkeypatch, packets() + [Response({'capabilities': ['thinking']}), Response(raw.encode())])
    backend = OllamaBackend()
    chunks = []
    value = backend.generate(AIConfig(streaming_enabled=streaming), [], {'type': 'object'}, threading.Event(), chunks.append)
    assert value == reply and ''.join(chunks) == reply
    assert backend.metrics['tokens_per_second'] == 5
    payload = json.loads(requests[-1][1]['body'])
    assert payload['keep_alive'] == 0 and payload['think'] is False
    assert payload['stream'] is streaming and payload['options']['num_predict'] == 768
    assert 'tools' not in payload  # JSON schema works without native tool calling.
    assert payload['format'] == {'type': 'object'}


def test_cloud_alias_show_refused(monkeypatch):
    _, requests = transport(monkeypatch, packets() + [Response({'remote_model': 'secret-cloud'})])
    with pytest.raises(AIError, match='distant'):
        OllamaBackend().generate(AIConfig(), [], {}, threading.Event(), lambda _: None)
    assert requests[-1][0][1] == '/api/show'


def test_server_unreachable(monkeypatch):
    connection = Mock()
    connection.request.side_effect = ConnectionRefusedError('private endpoint details')
    monkeypatch.setattr('jarvis.ai.backend.http.client.HTTPConnection', lambda *a, **k: connection)
    with pytest.raises(AIError, match='inaccessible') as error:
        OllamaBackend().inspect(AIConfig(), threading.Event())
    assert 'private' not in str(error.value)
    connection.close.assert_called_once()


def test_redirect_is_not_followed(monkeypatch):
    _, requests = transport(monkeypatch, [Response({}, 302)])
    with pytest.raises(AIError, match='302'):
        OllamaBackend().inspect(AIConfig(), threading.Event())
    assert len(requests) == 1


@pytest.mark.parametrize('raw', [b'{}\n', b'{"error":"private"}\n',
    b'{"message":{"content":"x"},"done":true,"done_reason":"length"}\n', b'x' * 65537])
def test_incomplete_error_oversized_stream(monkeypatch, raw):
    transport(monkeypatch, packets() + [Response({}), Response(raw)])
    with pytest.raises(AIError):
        OllamaBackend().generate(AIConfig(), [], {}, threading.Event(), lambda _: None)


def test_cancel_before_request(monkeypatch):
    connections, requests = transport(monkeypatch, [Response({})])
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(Cancelled):
        OllamaBackend().inspect(AIConfig(), cancelled)
    assert requests == []


@pytest.mark.parametrize('cancel', [True, False])
def test_blocked_socket_is_interrupted(monkeypatch, cancel):
    released = threading.Event()
    started = threading.Event()
    cancelled = threading.Event()
    connection = Mock()
    connection.sock.shutdown.side_effect = lambda *_: released.set()
    def wait_response():
        started.set()
        assert released.wait(2)
        raise OSError('closed')
    connection.getresponse.side_effect = wait_response
    monkeypatch.setattr('jarvis.ai.backend.http.client.HTTPConnection', lambda *a, **k: connection)
    timer = threading.Thread(target=lambda: (started.wait(1), cancelled.set())) if cancel else None
    if timer:
        timer.start()
    try:
        with pytest.raises(Cancelled if cancel else AIError):
            OllamaBackend().inspect(AIConfig(request_timeout=1), cancelled)
        connection.sock.shutdown.assert_called()
    finally:
        if timer:
            timer.join()
