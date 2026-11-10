"""Opt-in Ollama benchmark. No tool execution, downloads, prompts or replies saved."""
import argparse
from dataclasses import replace
import json
import threading
import time
from jarvis.ai.backend import OllamaBackend, decode
from jarvis.ai.config import AIConfig
from jarvis.ai.conversation import Conversation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Autoriser explicitement une inférence locale')
    parser.add_argument('--model', default='qwen3:4b')
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--timeout', type=float, default=90)
    args = parser.parse_args()
    config = AIConfig(enabled=True, model=args.model, endpoint=args.endpoint, request_timeout=args.timeout)
    backend = OllamaBackend()
    status = backend.inspect(config, threading.Event())
    print(json.dumps({'version': status['version'], 'model_installed': status['installed']}, ensure_ascii=False))
    if not args.run:
        print('Détection seule ; --run pour mesurer, sans téléchargement ni exécution d’outil.')
        return
    session = Conversation(config, backend)
    samples, errors = [], []
    done = threading.Event()
    def sample():
        while not done.is_set():
            try:
                rows = backend.get(replace(config, request_timeout=2), '/api/ps', done).get('models', [])
                samples.extend({k: row.get(k) for k in ('name', 'size', 'size_vram', 'context_length')}
                               for row in rows if row.get('name') == config.model)
            except Exception as error:
                errors.append(type(error).__name__)
            done.wait(.25)
    sampler = threading.Thread(target=sample, daemon=False)
    sampler.start()
    start = time.monotonic()
    try:
        raw = backend.generate(config, session.context('Affiche mes projets.'), session.schema(),
                               threading.Event(), lambda _: None)
        value = decode(raw)
        # Retain only protocol validity and expected tool identity; no private model text.
        correct = value.get('calls') == [{'tool': 'list_projects', 'arguments': {}}]
        report = {'model': config.model, 'version': status['version'], 'wall_seconds': time.monotonic() - start,
                  'metrics': backend.metrics, 'expected_intent': correct,
                  'memory_samples': samples, 'sampling_errors': sorted(set(errors)),
                  'vulkan_verified': False,
                  'note': 'size_vram mesure une allocation GPU, pas la preuve du backend Vulkan. Examiner les logs moteur.'}
    finally:
        done.set()
        sampler.join()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
