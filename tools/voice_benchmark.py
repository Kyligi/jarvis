"""Offline paired benchmark; explicit WAV corpus only, never opens a microphone."""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
import wave

from jarvis.voice.backends import WhisperCLI, VoiceError
from jarvis.voice.config import VoiceConfig


def words(text):
    return re.findall(r"[^\W_]+", unicodedata.normalize('NFC', text).casefold())


def errors(reference, hypothesis):
    """Levenshtein word distance, including insertions on silence."""
    expected, actual = words(reference), words(hypothesis)
    row = list(range(len(actual) + 1))
    for i, left in enumerate(expected, 1):
        next_row = [i]
        for j, right in enumerate(actual, 1):
            next_row.append(min(row[j] + 1, next_row[-1] + 1,
                                row[j-1] + (left != right)))
        row = next_row
    return row[-1], len(expected)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def benchmark(manifest, models, config, repeats=1, adapter=None):
    adapter = adapter or WhisperCLI()
    items = json.loads(manifest.read_text())
    corpus = []
    for item in items:
        path = manifest.parent / item['file']
        if not isinstance(item['expected'], str):
            raise ValueError('expected doit être du texte')
        with wave.open(str(path)) as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) != (1, 2, 16000, 'NONE'):
                raise ValueError(f'{path}: WAV PCM mono 16 bits 16 kHz requis')
            if stream.getnframes() > 30 * 16000:
                raise ValueError('Extrait limité à 30 secondes')
            pcm = stream.readframes(stream.getnframes())
        corpus.append((item, pcm, digest(path)))
    rows = []
    for name, model in models.items():
        for vad in (False, True):
            for repeat in range(repeats):
                for item, pcm, sha in corpus:
                    row = dict(model=name, file=item['file'], sha256=sha,
                               expected=item['expected'], vad_requested=vad, repeat=repeat,
                               vad_used=False, failure=None, hypothesis=None,
                               hallucination=None, review_required=True)
                    started = time.perf_counter()
                    try:
                        result = adapter.transcribe(pcm, replace(config, stt_model=str(model), vad_enabled=vad), threading.Event())
                        distance, count = errors(item['expected'], result.text)
                        row.update(hypothesis=result.text, errors=distance, reference_words=count,
                                   wer=distance/count if count else None,
                                   vad_used=result.vad_used, warning=result.warning,
                                   hallucination=bool(words(result.text)) if not words(item['expected']) else None)
                    except (VoiceError, OSError) as error:
                        row['failure'] = str(error)
                    row['seconds'] = time.perf_counter() - started
                    rows.append(row)
    summaries = []
    for name in models:
        for vad in (False, True):
            group = [r for r in rows if r['model'] == name and r['vad_requested'] == vad]
            measured = [r for r in group if r['failure'] is None and r['vad_used'] == vad]
            count = sum(r['reference_words'] for r in measured)
            summaries.append(dict(model=name, vad_requested=vad, attempts=len(group),
                failures=sum(r['failure'] is not None for r in group),
                fallbacks=sum(r['failure'] is None and vad and not r['vad_used'] for r in group),
                measured=len(measured),
                wer=sum(r['errors'] for r in measured)/count if count else None,
                mean_seconds=sum(r['seconds'] for r in measured)/len(measured) if measured else None,
                silence_hallucinations=sum(r['hallucination'] is True for r in measured)))
    return dict(config=asdict(config), models={n: dict(path=str(p), sha256=digest(p) if Path(p).is_file() else None) for n,p in models.items()},
                normalization='NFC, casefold, words excluding punctuation; accents retained',
                timing='wall time including model loading and any fallback; no warm-up excluded',
                summaries=summaries, rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--small', required=True, type=Path)
    parser.add_argument('--vad-model', default='')
    parser.add_argument('--whisper', default='whisper-cli')
    parser.add_argument('--backend', choices=['cpu', 'vulkan'], default='cpu')
    parser.add_argument('--prompt', default='')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error('--repeats : 1 à 20')
    config = VoiceConfig(stt_executable=args.whisper, gpu_executable=args.whisper,
                         compute_backend=args.backend, vad_model=args.vad_model,
                         whisper_prompt=args.prompt)
    # Reserve output before expensive processing; never overwrite a report.
    with args.output.open('x', encoding='utf-8') as stream:
        report = benchmark(args.manifest, {'base': args.base, 'small': args.small}, config, args.repeats)
        import shutil
        resolved = shutil.which(args.whisper)
        report['binary'] = dict(path=resolved, sha256=digest(resolved) if resolved else None)
        stream.write(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report['summaries'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
