"""Bounded local CLI adapters; subprocesses owned and reaped in finally blocks."""
import json
import math
import os
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from array import array
from dataclasses import dataclass, field
from pathlib import Path

import psutil


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


@dataclass(frozen=True)
class Execution:
    vulkan: bool = False
    seconds: float = 0
    peak_rss_bytes: int = 0


def run_observed(argv, cancel, timeout):
    """Drain stderr without retaining transcripts; retain only backend evidence.

    RSS is sampled every <=50 ms and excludes separately allocated GPU memory.
    No diagnostic text leaves this function, including on failure.
    """
    if cancel.is_set():
        raise Cancelled()
    if timeout <= 0:
        raise VoiceError('Délai du moteur audio dépassé.')
    started = time.monotonic()
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, bufsize=0)
    pending = b''
    selected = allocated = failed = False
    peak = 0
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stderr, selectors.EVENT_READ)
            while selector.get_map() or process.poll() is None:
                if cancel.is_set():
                    raise Cancelled()
                if time.monotonic() - started >= timeout:
                    raise VoiceError('Délai du moteur audio dépassé.')
                try:
                    peak = max(peak, psutil.Process(process.pid).memory_info().rss)
                except psutil.Error:
                    pass
                for key, _ in selector.select(.05):
                    chunk = os.read(key.fd, 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    pending += chunk
                    lines = pending.split(b'\n')
                    pending = lines.pop()[-4096:]
                    for line in lines:
                        selected |= bool(re.search(rb'^whisper_backend_init_gpu: using Vulkan[0-9]+ backend\r?$', line))
                        allocated |= bool(re.search(rb'^whisper_model_load: +Vulkan[0-9]+ total size = +[1-9][0-9.]* MB', line))
                        failed |= b'failed to initialize' in line or b'no GPU found' in line
                if not selector.get_map() and process.poll() is None:
                    cancel.wait(.01)
        if process.wait():
            raise VoiceError('Échec audio : vérifier modèle, périphérique et permissions.')
        return Execution(selected and allocated and not failed, time.monotonic()-started, peak)
    finally:
        reap(process)
        process.stderr.close()


def run(argv, cancel, timeout, data=None, observe=False):
    """No shell, no transcript in argv/stderr/logs; cancel checked every 50 ms."""
    if observe:
        return run_observed(argv, cancel, timeout)
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


class CaptureBuffer:
    """Session-only pre-roll, sample-clock silence and bounded PCM memory.

    The microphone is never opened before explicit activation. Hysteresis keeps
    quiet endings; the noise estimate only follows sub-threshold idle frames.
    """
    def __init__(self, config):
        self.config = config
        self.pre = bytearray()
        self.audio = bytearray()
        self.pending = b''
        self.total = 0
        self.quiet = 0
        self.speech = False
        self.noise = 0.0
        self.done = False

    def feed(self, chunk):
        if self.done:
            return
        self.pending += chunk
        # Fixed 20 ms frames, independent of PipeWire read boundaries.
        while len(self.pending) >= 640 and not self.done:
            frame, self.pending = self.pending[:640], self.pending[640:]
            self._frame(frame)
        if self.done:
            self.pending = b''

    def _frame(self, frame):
        limit = int(self.config.max_recording_seconds * 16000) * 2
        frame = frame[:max(0, limit - self.total)]
        self.total += len(frame)
        rms = level(frame)
        threshold = max(self.config.silence_threshold, self.noise * 2.5)
        active = rms >= threshold * (.6 if self.speech else 1)
        if not self.speech and not active and self.config.adaptive_noise:
            self.noise = .95 * self.noise + .05 * rms
        if not self.speech:
            if active:
                self.speech = True
                self.audio.extend(self.pre)
                self.pre.clear()
            else:
                self.pre.extend(frame)
                keep = int(self.config.pre_recording_ms * 32) // 2 * 2
                if len(self.pre) > keep:
                    del self.pre[:len(self.pre)-keep]
        if self.speech:
            self.audio.extend(frame)
            self.quiet = 0 if active else self.quiet + len(frame)
        self.done = (self.total >= limit
                     or self.speech and self.quiet >= self.config.silence_seconds * 32000)

    def finish(self):
        if self.pending and not self.done:
            self._frame(self.pending[:len(self.pending)//2*2])
            self.pending = b''
        return bytes(self.audio) if self.speech else b''


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
        buffer = CaptureBuffer(config)
        started = time.monotonic()
        last_data = started
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while not stop.is_set():
                    now = time.monotonic()
                    if cancel.is_set():
                        raise Cancelled()
                    if now - started >= config.max_recording_seconds or buffer.done:
                        break
                    if now - last_data > 2:
                        raise VoiceError('Microphone sans flux : vérifier connexion et permissions.')
                    if not selector.select(.05):
                        continue
                    chunk = os.read(process.stdout.fileno(), 3200)
                    if not chunk:
                        raise VoiceError('Microphone déconnecté ou capture refusée.')
                    last_data = now
                    buffer.feed(chunk)
                    progress(level(chunk), buffer.total/32000)
        finally:
            reap(process)
            process.stdout.close()
        if cancel.is_set():
            raise Cancelled()
        return buffer.finish()


@dataclass(frozen=True)
class Transcript:
    text: str
    confidence: float | None = None
    vad_used: bool = False
    warning: str = ''
    execution: Execution | None = field(default=None, compare=False)
    backend: str = field(default='cpu', compare=False)


class WhisperCLI:
    def transcribe(self, pcm, config, cancel):
        deadline = time.monotonic() + config.timeout_seconds
        model = model_file(config.stt_model)
        binary = executable(config.stt_executable if config.compute_backend == 'cpu' else config.gpu_executable)
        with tempfile.TemporaryDirectory(prefix='jarvis-stt-') as directory:
            audio = Path(directory) / 'input.wav'
            with wave.open(str(audio), 'wb') as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(pcm)
            output = Path(directory) / 'result'
            argv = [binary, '-m', str(model), '-f', str(audio), '-l', 'fr',
                    '-ojf', '-of', str(output)]
            if config.compute_backend == 'cpu':
                argv += ['-ng']
            if config.whisper_prompt:
                argv += ['--prompt', config.whisper_prompt]
            vad_used, warning = False, ''
            if config.vad_enabled:
                try:
                    vad = model_file(config.vad_model)
                except VoiceError:
                    warning = 'VAD absent : transcription sans VAD.'
                else:
                    try:
                        execution = run(argv + ['--vad', '--vad-model', str(vad),
                                    '--vad-speech-pad-ms', '300',
                                    '--vad-min-speech-duration-ms', '100'],
                            cancel, max(0, deadline-time.monotonic()), None, True)
                        vad_used = True
                    except Cancelled:
                        raise
                    except VoiceError:
                        warning = 'Échec VAD : transcription sans VAD.'
                        output.with_suffix('.json').unlink(missing_ok=True)
            if not vad_used:
                execution = run(argv, cancel, max(0, deadline-time.monotonic()), None, True)
            if config.compute_backend == 'vulkan' and (not execution or not execution.vulkan):
                raise VoiceError('Vulkan non confirmé : transcription rejetée. Choisir CPU dans Voix, enregistrer puis refaire une capture.')
            try:
                data = json.loads(output.with_suffix('.json').read_text())
                segments = data['transcription']
                if not isinstance(segments, list) or any(not isinstance(s, dict) or not isinstance(s.get('text'), str) for s in segments):
                    raise ValueError('segments')
                text = ''.join(s['text'] for s in segments).strip()
                if len(text) > 2048 or any(ord(c) < 32 and c not in '\n\t' for c in text):
                    raise ValueError('transcription invalide')
                scores = [t['p'] for s in segments for t in s.get('tokens', [])
                          if not t.get('text', '').startswith('[_') and type(t.get('p')) in (float, int) and math.isfinite(t['p']) and 0 <= t['p'] <= 1]
                confidence = sum(scores)/len(scores) if scores else None
                return Transcript(text, confidence, vad_used, warning, execution, config.compute_backend)
            except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
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
