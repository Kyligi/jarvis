"""Explicit Turbo-only CPU/Vulkan comparison, no microphone or command execution."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import threading
import time
import wave

from voice_benchmark import digest, errors
from jarvis.voice.backends import WhisperCLI, VoiceError
from jarvis.voice.config import VoiceConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--cpu', required=True, type=Path)
    parser.add_argument('--vulkan', required=True, type=Path)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error('repeats: 1..20')
    corpus = []
    for item in json.loads(args.manifest.read_text()):
        path = args.manifest.parent / item['file']
        with wave.open(str(path)) as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) != (1, 2, 16000, 'NONE') or stream.getnframes() > 30*16000:
                raise ValueError('WAV PCM16 mono 16 kHz, maximum 30 s requis')
            pcm = stream.readframes(stream.getnframes())
        corpus.append((item, pcm, digest(path)))
    report = dict(model=dict(path=str(args.model), sha256=digest(args.model)),
                  binaries={name: dict(path=str(path), sha256=digest(path))
                            for name, path in [('cpu', args.cpu), ('vulkan', args.vulkan)]},
                  timing='wall time including loading; alternating backend order per repeat; no warm-up excluded',
                  memory='process RSS sampled every <=50ms; not total GPU/shared memory; lower bound on peak',
                  corpus='synthetic Piper fr_FR-siwis-medium; does not establish human accuracy',
                  rows=[], summaries=[])
    with args.output.open('x') as output:
        for repeat in range(args.repeats):
            for backend in (('cpu', 'vulkan') if repeat % 2 == 0 else ('vulkan', 'cpu')):
                config = VoiceConfig(stt_model=str(args.model), stt_executable=str(args.cpu),
                                     gpu_executable=str(args.vulkan), compute_backend=backend, timeout_seconds=300)
                for item, pcm, sha in corpus:
                    row = dict(backend=backend, repeat=repeat, file=item['file'], sha256=sha,
                               expected=item['expected'], failure=None)
                    start = time.perf_counter()
                    try:
                        result = WhisperCLI().transcribe(pcm, config, threading.Event())
                        distance, count = errors(item['expected'], result.text)
                        row.update(hypothesis=result.text, errors=distance, words=count,
                                   execution=asdict(result.execution), silence_insertion=not item['expected'] and bool(result.text))
                    except (VoiceError, OSError) as error:
                        row['failure'] = str(error)
                    row['seconds'] = time.perf_counter()-start
                    report['rows'].append(row)
                    print(f'{backend} repeat={repeat} {item["file"]}: {row["seconds"]:.2f}s {row["failure"] or "OK"}', flush=True)
        for backend in ('cpu', 'vulkan'):
            rows = [r for r in report['rows'] if r['backend'] == backend]
            ok = [r for r in rows if r['failure'] is None]
            count = sum(r['words'] for r in ok)
            report['summaries'].append(dict(backend=backend, attempts=len(rows), failures=len(rows)-len(ok),
                wer=sum(r['errors'] for r in ok)/count if count else None,
                mean_seconds=sum(r['seconds'] for r in ok)/len(ok) if ok else None,
                peak_rss_bytes=max((r['execution']['peak_rss_bytes'] for r in ok), default=0),
                silence_insertions=sum(r['silence_insertion'] for r in ok)))
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(json.dumps(report['summaries'], indent=2))


if __name__ == '__main__':
    main()
