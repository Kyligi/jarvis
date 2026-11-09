"""Explicit local French corpus generation/benchmark. Never runs during pytest.

Run: uv run python tools/voice_corpus.py --voice /absolute/fr_FR-voice.onnx
Optional: --model /absolute/ggml-base.bin to measure STT including model loading.
The four original test sentences below are dedicated to CC0-1.0 by this project.
Audio redistribution remains subject to the chosen voice's model card.
"""
import argparse
import json
from pathlib import Path
import threading
import time
import wave
from dataclasses import replace
from jarvis.voice.config import VoiceConfig
from jarvis.voice.backends import executable, model_file, run, WhisperCLI

BENCHMARK_SENTENCES = ('aide', 'état système', 'mes projets', 'Jarvis, aide',
    'Je développe avec Python et Rust sur Omarchy.', 'Hyprland, Git, Steam et Notion.', '')

SENTENCES = ('Jarvis, aide', 'État système', 'Mes projets', 'Arrête de parler')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voice', required=True)
    parser.add_argument('--piper', default='piper')
    parser.add_argument('--model')
    parser.add_argument('--benchmark-suite', action='store_true',
                        help='Sept extraits, dont silence, convertis en WAV 16 kHz')
    parser.add_argument('--whisper', default='whisper-cli')
    parser.add_argument('--output', type=Path, default=Path('voice-corpus'))
    args = parser.parse_args()
    voice = model_file(args.voice)
    model_file(str(voice)+'.json')
    binary = executable(args.piper)
    # Exclusive directory: never overwrite an existing recording or corpus.
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = []
    cancel = threading.Event()
    for index, text in enumerate(BENCHMARK_SENTENCES if args.benchmark_suite else SENTENCES):
        path = args.output / f'fr-{index+1}.wav'
        started = time.perf_counter()
        if text:
            run([binary, '-m', str(voice), '-f', str(path)], cancel, 120, text.encode())
        else:
            with wave.open(str(path), 'wb') as stream:
                stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                stream.writeframes(bytes(64000))
        item = dict(file=path.name, expected=text, tts_seconds=time.perf_counter()-started)
        if args.model or args.benchmark_suite:
            # Explicit external resampling; originals preserved for listening tests.
            converted = args.output/f'fr-{index+1}-16k.wav'
            run([executable('ffmpeg'), '-nostdin', '-i', str(path), '-ar', '16000',
                 '-ac', '1', '-c:a', 'pcm_s16le', str(converted)], cancel, 30)
            item['file'] = converted.name
        if args.model:
            with wave.open(str(converted)) as stream:
                pcm = stream.readframes(stream.getnframes())
            started = time.perf_counter()
            result = WhisperCLI().transcribe(pcm, replace(VoiceConfig(), stt_model=args.model,
                                              stt_executable=args.whisper), cancel)
            item.update(recognized=result.text, confidence=result.confidence,
                        stt_seconds=time.perf_counter()-started)
        report.append(item)
    (args.output/'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
