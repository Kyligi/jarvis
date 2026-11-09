"""V1.4.2: real subprocess diagnostics and fail-closed Vulkan selection."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import subprocess
import threading
import time
from unittest.mock import Mock

import pytest

from jarvis.voice import backends as b
from jarvis.voice.config import VoiceConfig, save, load
from jarvis.voice.controller import VoiceController, State

REAL_POPEN = subprocess.Popen

@pytest.fixture
def python_child(monkeypatch):
    # Explicit exception to global isolation: only a throwaway Python child,
    # never microphone, Whisper, user data or a system command.
    def spawn(argv, **kwargs):
        assert argv[:2] == [sys.executable, '-c']
        return REAL_POPEN(argv, **kwargs)
    monkeypatch.setattr(b.subprocess, 'Popen', spawn)


EVIDENCE = ('whisper_model_load:      Vulkan0 total size = 1623.55 MB\n'
            'whisper_backend_init_gpu: using Vulkan0 backend\n')

@pytest.mark.parametrize('log,verified', [
    (EVIDENCE, True),
    ('ggml_vulkan: Found 1 Vulkan devices\n', False),
    ('whisper_backend_init_gpu: using Vulkan0 backend\n', False),
    (EVIDENCE + 'whisper_backend_init_gpu: no GPU found\n', False),
    (EVIDENCE + 'failed to initialize Vulkan0 backend\n', False),
    ('private text ' + EVIDENCE, False),
])
def test_actual_backend_evidence(log, verified, python_child):
    result = b.run([sys.executable, '-c', 'import sys; sys.stderr.write(' + repr(log) + ')'],
                   threading.Event(), 3, None, True)
    assert result.vulkan is verified
    assert result.seconds > 0 and result.peak_rss_bytes > 0
    assert 'private' not in repr(result)


def test_large_stderr_drained_without_deadlock(python_child):
    result = b.run([sys.executable, '-c', "import sys; sys.stderr.write('x'*1000000+'\\n'+" + repr(EVIDENCE) + ')'],
                   threading.Event(), 3, None, True)
    assert result.vulkan


@pytest.mark.parametrize('mode', ['timeout', 'cancel', 'error'])
def test_observed_process_failure_is_bounded_and_private(mode, python_child):
    cancel = threading.Event()
    timer = threading.Timer(.1, cancel.set) if mode == 'cancel' else None
    if timer:
        timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(b.Cancelled if mode == 'cancel' else b.VoiceError) as error:
            b.run([sys.executable, '-c', "import sys,time; sys.stderr.write('PRIVATE'); " +
                   ('sys.exit(1)' if mode == 'error' else 'time.sleep(10)')],
                  cancel, .2 if mode == 'timeout' else 3, None, True)
        assert 'PRIVATE' not in str(error.value)
        assert time.monotonic() - started < 2
    finally:
        if timer:
            timer.join()


@pytest.fixture
def engine(tmp_path, monkeypatch):
    model = tmp_path/'turbo.bin'
    model.touch()
    calls = []
    evidence = [b.Execution(True, .1, 1024)]
    def run(argv, *args):
        calls.append(argv)
        Path(argv[argv.index('-of')+1]+'.json').write_text(json.dumps({'transcription':[{'text':'aide'}]}))
        return evidence[0]
    monkeypatch.setattr(b, 'run', run)
    monkeypatch.setattr(b, 'executable', lambda name: name)
    return VoiceConfig(stt_model=str(model), stt_executable='cpu-cli', gpu_executable='vulkan-cli'), calls, evidence


def test_cpu_gpu_cpu_switch_preserves_binary_and_flags(engine):
    config, calls, _ = engine
    for backend in ('cpu', 'vulkan', 'cpu'):
        result = b.WhisperCLI().transcribe(b'\0\1'*160, replace(config, compute_backend=backend), threading.Event())
        assert result.backend == backend
    assert [a[0] for a in calls] == ['cpu-cli', 'vulkan-cli', 'cpu-cli']
    assert ['-ng' in a for a in calls] == [True, False, True]


def test_gpu_silent_cpu_fallback_rejected(engine):
    config, calls, evidence = engine
    evidence[0] = b.Execution(False)
    with pytest.raises(b.VoiceError, match='transcription rejetée'):
        b.WhisperCLI().transcribe(b'\0\1'*160, replace(config, compute_backend='vulkan'), threading.Event())
    assert len(calls) == 1 and calls[0][0] == 'vulkan-cli'


@pytest.mark.parametrize('backend', ['cpu', 'vulkan'])
def test_model_absent_never_starts_engine(engine, backend):
    config, calls, _ = engine
    with pytest.raises(b.VoiceError, match='Modèle local absent'):
        b.WhisperCLI().transcribe(b'00', replace(config, compute_backend=backend, stt_model='/absent/turbo.bin'), threading.Event())
    assert not calls


def test_missing_gpu_executable_never_uses_cpu(tmp_path):
    model = tmp_path/'model.bin'
    model.touch()
    with pytest.raises(b.VoiceError, match='Programme audio absent'):
        b.WhisperCLI().transcribe(b'00', VoiceConfig(stt_model=str(model), compute_backend='vulkan'), threading.Event())


def test_vulkan_error_cannot_leave_command_pending():
    capture, stt = Mock(), Mock()
    capture.capture.return_value = b'00'
    stt.transcribe.side_effect = b.VoiceError('GPU unavailable')
    controller = VoiceController(VoiceConfig(enabled=True, compute_backend='vulkan'), capture=capture, stt=stt)
    assert controller.toggle()
    controller.thread.join(2)
    assert controller.snapshot.state == State.ERROR
    assert 'choisir CPU' in controller.snapshot.message
    assert controller.take_pending() is None


def test_switch_blocked_while_awaiting_validation():
    controller = VoiceController()
    controller.emit(State.AWAITING_CONFIRMATION)
    with pytest.raises(b.VoiceError):
        controller.configure(VoiceConfig(compute_backend='vulkan'))


def test_vulkan_config_roundtrip(tmp_path):
    config = VoiceConfig(compute_backend='vulkan', gpu_executable='/separate/bin', stt_model='/models/turbo.bin')
    path = tmp_path/'voice.toml'
    save(config, path)
    assert load(path) == config


def test_loading_and_transcription_stay_off_caller_thread():
    caller = threading.get_ident()
    capture, stt = Mock(), Mock()
    capture.capture.return_value = b'00'
    def transcribe(*args):
        assert threading.get_ident() != caller
        return b.Transcript('aide', .99, execution=b.Execution(True, 2, 1024), backend='vulkan')
    stt.transcribe.side_effect = transcribe
    controller = VoiceController(VoiceConfig(enabled=True), capture=capture, stt=stt)
    controller.toggle()
    controller.thread.join(2)
    assert controller.snapshot.state == State.AWAITING_CONFIRMATION
    assert 'VULKAN' in controller.snapshot.engine
    assert controller.pending is not None  # recognition never executes the command


def test_hud_backend_model_and_telemetry(qapp):
    from jarvis.interface.context import AppContext
    from jarvis.interface.voice import VoicePage, VoiceControls
    from test_interface import pump
    context = AppContext(executor=Mock())
    try:
        page = VoicePage(context)
        controls = VoiceControls(context.voice)
        page.backend.setCurrentIndex(page.backend.findData('vulkan'))
        page.fields['gpu_executable'].setText('/separate/vulkan')
        page.fields['stt_model'].setText('/models/ggml-large-v3-turbo.bin')
        page.save()
        pump(qapp, lambda: context.voice.saver.task is None)
        assert context.voice.controller.config.compute_backend == 'vulkan'
        assert context.voice.controller.config.gpu_executable == '/separate/vulkan'
        assert load().stt_model == '/models/ggml-large-v3-turbo.bin'
        context.voice.controller.engine = 'VULKAN · ggml-large-v3-turbo.bin · 2.00 s'
        context.voice.controller.emit(State.IDLE)
        qapp.processEvents()
        assert 'VULKAN' in controls.engine.text()
        page.backend.setCurrentIndex(page.backend.findData('cpu'))
        page.save()
        pump(qapp, lambda: context.voice.saver.task is None)
        assert context.voice.controller.config.compute_backend == 'cpu'
        assert 'non vérifiée' in controls.engine.text()
    finally:
        context.shutdown()


@pytest.mark.parametrize('text', ['confirme scénario 1234abcd', 'confirme disposition 1234abcd', 'Aide-moi.', 'commande inventée'])
def test_vulkan_does_not_bypass_command_validation(text):
    capture, stt = Mock(), Mock()
    capture.capture.return_value = b'00'
    stt.transcribe.return_value = b.Transcript(text, 1, execution=b.Execution(True), backend='vulkan')
    controller = VoiceController(VoiceConfig(enabled=True, compute_backend='vulkan'), capture=capture, stt=stt)
    controller.toggle()
    controller.thread.join(2)
    assert controller.snapshot.state == State.ERROR
    assert controller.take_pending() is None


def test_vulkan_silence_never_calls_whisper():
    capture, stt = Mock(), Mock()
    capture.capture.return_value = b''
    controller = VoiceController(VoiceConfig(enabled=True, compute_backend='vulkan'), capture=capture, stt=stt)
    controller.toggle()
    controller.thread.join(2)
    stt.transcribe.assert_not_called()
    assert controller.pending is None


def test_exhausted_budget_never_launches_a_retry(monkeypatch):
    popen = Mock()
    monkeypatch.setattr(b.subprocess, 'Popen', popen)
    with pytest.raises(b.VoiceError, match='Délai'):
        b.run(['must-not-start'], threading.Event(), 0, None, True)
    popen.assert_not_called()
