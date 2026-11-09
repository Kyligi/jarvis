"""Bounded local CLI adapters; subprocesses owned and reaped in finally blocks."""
from array import array
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import wave


class VoiceError(RuntimeError):
    pass


class Cancelled(VoiceError):
    pass


def executable(name):
    result = shutil.which(name)
    if not result:
        raise VoiceError('Programme audio absent : installer le backend configuré.')
    return result


def model_file(name):
    path = Path(name).expanduser()
    if not name or not path.is_file():
        raise VoiceError('Modèle local absent : choisir un fichier déjà téléchargé.')
    return path.resolve()


def reap(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=.3)
        except subprocess.TimeoutExpired:
            process.kill()
    process.wait()


def run(argv, cancel, timeout, data=None):
    """No shell, no transcript in argv/stderr/logs; cancel checked every 50 ms."""
    if cancel.is_set():
        raise Cancelled()
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    started = time.monotonic()
    try:
        first = True
        while True:
            if cancel.is_set():
                raise Cancelled()
            if time.monotonic() - started >= timeout:
                raise VoiceError('Délai du moteur audio dépassé.')
            try:
                process.communicate(input=data if first else None, timeout=.05)
                break
            except subprocess.TimeoutExpired:
                first = False
        if process.returncode:
            raise VoiceError('Échec audio : vérifier modèle, périphérique et permissions.')
    finally:
        reap(process)
        if process.stdin:
            process.stdin.close()


def devices():
    """Stable PipeWire node names rather than ephemeral numeric IDs."""
    try:
        result = subprocess.run(['pw-dump'], capture_output=True, text=True, timeout=5, check=True)
        nodes = json.loads(result.stdout)
        return [(p['node.name'], p.get('node.description', p['node.name']), p['media.class'])
                for node in nodes if (p := node.get('info', {}).get('props', {}))
                and p.get('media.class') in ('Audio/Source', 'Audio/Sink') and 'node.name' in p]
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise VoiceError('PipeWire indisponible : vérifier la session audio.') from error


def check_device(name, kind):
    available = [d for d in devices() if d[2] == kind]
    if not available or (name and name not in {d[0] for d in available}):
        raise VoiceError('Périphérique audio absent ou déconnecté.')


def level(pcm):
    samples = array('h', pcm[:len(pcm) // 2 * 2])
    if sys.byteorder != 'little':
        samples.byteswap()
    return math.sqrt(sum(x*x for x in samples) / max(1, len(samples))) / 32768


class PipeWireCapture:
    def capture(self, config, stop, cancel, progress):
        check_device(config.microphone_device, 'Audio/Source')
        argv = [executable('pw-record'), '--raw', '--format', 's16', '--rate', '16000', '--channels', '1']
        if config.microphone_device:
            argv += ['--target', config.microphone_device]
        argv += ['-']
        if cancel.is_set():
            raise Cancelled()
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, bufsize=0)
        audio = bytearray()
        started = time.monotonic()
        last_data = started
        last_speech = None
        limit = int(config.max_recording_seconds * 32000)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while not stop.is_set():
                    now = time.monotonic()
                    if cancel.is_set():
                        raise Cancelled()
                    if now - started >= config.max_recording_seconds or len(audio) >= limit:
                        break
                    if now - last_data > 2:
                        raise VoiceError('Microphone sans flux : vérifier connexion et permissions.')
                    if not selector.select(.05):
                        continue
                    chunk = os.read(process.stdout.fileno(), 3200)
                    if not chunk:
                        raise VoiceError('Microphone déconnecté ou capture refusée.')
                    last_data = now
                    audio.extend(chunk[:limit-len(audio)])
                    rms = level(chunk)
                    progress(rms, len(audio)/32000)
                    if rms >= config.silence_threshold:
                        last_speech = now
                    elif last_speech is not None and now - last_speech >= config.silence_seconds:
                        break
        finally:
            reap(process)
            process.stdout.close()
        if cancel.is_set():
            raise Cancelled()
        return bytes(audio[:len(audio)//2*2]) if last_speech is not None else b''


@dataclass(frozen=True)
class Transcript:
    text: str
    confidence: float | None = None


class WhisperCLI:
    def transcribe(self, pcm, config, cancel):
        model = model_file(config.stt_model)
        binary = executable(config.stt_executable)
        with tempfile.TemporaryDirectory(prefix='jarvis-stt-') as directory:
            audio = Path(directory) / 'input.wav'
            with wave.open(str(audio), 'wb') as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(pcm)
            output = Path(directory) / 'result'
            run([binary, '-m', str(model), '-f', str(audio), '-l', 'fr', '-ng',
                 '-ojf', '-of', str(output)], cancel, config.timeout_seconds)
            try:
                data = json.loads(output.with_suffix('.json').read_text())
                segments = data['transcription']
                text = ''.join(s['text'] for s in segments).strip()
                scores = [t['p'] for s in segments for t in s.get('tokens', [])
                          if not t.get('text', '').startswith('[_') and isinstance(t.get('p'), (float, int))]
                confidence = sum(scores)/len(scores) if scores else None
                return Transcript(text, confidence)
            except (OSError, KeyError, TypeError, ValueError) as error:
                raise VoiceError('Réponse Whisper illisible ou incompatible.') from error


class PiperCLI:
    def speak(self, text, config, cancel):
        model = model_file(config.tts_voice)
        model_file(str(model) + '.json')
        binary = executable(config.tts_executable)
        player = executable('pw-play')
        check_device(config.output_device, 'Audio/Sink')
        with tempfile.TemporaryDirectory(prefix='jarvis-tts-') as directory:
            audio = str(Path(directory) / 'response.wav')
            run([binary, '-m', str(model), '-f', audio, '--length-scale', str(1/config.tts_speed)],
                cancel, config.timeout_seconds, text.encode('utf-8'))
            argv = [player, '--volume', str(config.tts_volume)]
            if config.output_device:
                argv += ['--target', config.output_device]
            run(argv + [audio], cancel, config.timeout_seconds)
