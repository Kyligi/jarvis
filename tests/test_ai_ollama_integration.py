"""Opt-in only: never downloads a model or executes a desktop action."""
import os
import threading
import pytest
from jarvis.ai.backend import OllamaBackend, decode
from jarvis.ai.config import AIConfig
from jarvis.ai.conversation import Conversation


@pytest.mark.skipif(os.environ.get('JARVIS_TEST_OLLAMA') != '1', reason='Ollama réel facultatif, activation explicite')
def test_real_ollama_french_intent():
    config = AIConfig(enabled=True, model=os.environ.get('JARVIS_TEST_MODEL', 'qwen3:4b'))
    backend = OllamaBackend()
    status = backend.inspect(config, threading.Event())
    assert status['installed'], 'Installer volontairement le modèle avant ce test.'
    session = Conversation(config, backend)
    chunks = []
    raw = backend.generate(config, session.context('Affiche mes projets.'), session.schema(), threading.Event(), chunks.append)
    value = decode(raw)
    assert set(value) == {'reply', 'calls'}
    assert value['calls'] == [{'tool': 'list_projects', 'arguments': {}}]
    assert ''.join(chunks) == raw
    assert backend.metrics['tokens'] > 0
