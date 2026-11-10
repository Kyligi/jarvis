import json
import threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from jarvis.voice.backends import (
    Cancelled,
    PiperCLI,
    Transcript,
    VoiceError,
    WhisperCLI,
)
from jarvis.voice.config import VoiceConfig, load, save
from jarvis.voice.controller import State, VoiceController
from jarvis.voice.wake import WakeGate


def controller(text='Jarvis, aide', confidence=.9, **kwargs):
    capture = Mock()
    capture.capture.return_value = b'\0\1' * 16000
    stt = Mock()
    stt.transcribe.return_value = Transcript(text, confidence)
    return VoiceController(VoiceConfig(enabled=True), capture, stt, Mock(), **kwargs)


def listen(c):
    assert c.toggle()
    c.thread.join(2)
    assert not c.thread.is_alive()


def test_startup_never_opens_microphone():
    c = controller()
    c.capture.capture.assert_not_called()
    assert c.snapshot.state == State.IDLE
    assert not VoiceConfig().enabled
    assert not VoiceConfig().wake_word_enabled
    assert not VoiceConfig().store_recordings


def test_states_and_single_use_confirmation():
    events = []
    c = controller(listener=events.append)
    listen(c)
    assert [e.state for e in events] == [State.LISTENING, State.TRANSCRIBING, State.AWAITING_CONFIRMATION]
    assert c.take_pending() == 'Jarvis, aide'
    assert c.take_pending() is None
    c.completed('Résultat exact')
    assert c.last_response == 'Résultat exact'
    c.tts.speak.assert_not_called()


@pytest.mark.parametrize('text,expected', [('', State.IDLE), ('  ', State.IDLE), ('commande absente', State.ERROR),
    ('confirme scénario 1234abcd', State.ERROR), ('Jarvis, confirme disposition 1234abcd', State.ERROR)])
def test_empty_unknown_and_sensitive_confirmation(text, expected):
    c = controller(text)
    listen(c)
    assert c.snapshot.state == expected
    assert c.pending is None


@pytest.mark.parametrize('score', [None, .2])
def test_uncertainty_requires_visible_approval(score):
    c = controller(confidence=score)
    listen(c)
    assert c.snapshot.state == State.AWAITING_CONFIRMATION
    assert 'incertaine' in c.snapshot.message


def test_expiry_and_cancel():
    clock = Mock(return_value=0)
    c = controller(clock=clock)
    listen(c)
    clock.return_value = 31
    c.expire()
    assert c.pending is None
    assert c.take_pending() is None
    listen(c)
    c.cancel()
    assert c.pending is None


def test_capture_stop_cancel_and_shutdown():
    c = controller()
    started = threading.Event()
    def capture(config, stop, cancel, progress):
        started.set()
        assert stop.wait(2)
        if cancel.is_set():
            raise Cancelled()
        return b'\0\1'
    c.capture.capture.side_effect = capture
    assert c.toggle()
    assert started.wait(1)
    assert c.toggle()  # second press finishes capture
    c.thread.join(2)
    assert c.snapshot.state == State.AWAITING_CONFIRMATION
    c.cancel()
    assert c.toggle()
    c.shutdown()
    assert not c.thread.is_alive()
    assert c.snapshot.state == State.IDLE
    assert not c.toggle()


def test_cancel_during_stt_ignores_late_transcript():
    c = controller()
    entered = threading.Event()
    release = threading.Event()
    def transcribe(*args):
        entered.set()
        release.wait(2)
        return Transcript('aide', 1)
    c.stt.transcribe.side_effect = transcribe
    c.toggle()
    assert entered.wait(1)
    assert not c.toggle()
    c.cancel()
    release.set()
    c.thread.join(2)
    assert c.pending is None
    assert c.snapshot.state == State.IDLE


@pytest.mark.parametrize('stage', ['capture', 'stt'])
def test_errors_do_not_log_audio_or_transcript(stage, caplog):
    c = controller()
    getattr(c, stage).capture.side_effect = VoiceError('Microphone absent') if stage == 'capture' else None
    if stage == 'stt':
        c.stt.transcribe.side_effect = VoiceError('Modèle absent')
    listen(c)
    assert c.snapshot.state == State.ERROR
    assert not caplog.text


def test_tts_single_slot_interrupt_no_microphone():
    c = controller()
    entered = threading.Event()
    def speak(text, config, cancel):
        entered.set()
        assert cancel.wait(2)
        raise Cancelled()
    c.tts.speak.side_effect = speak
    assert c.speak('bonjour')
    assert entered.wait(1)
    assert not c.speak('second')
    assert not c.toggle()
    c.cancel()
    c.thread.join(2)
    assert c.snapshot.state == State.IDLE
    c.capture.capture.assert_not_called()


def test_long_result_is_not_invented_summary():
    c = controller()
    c.speak('x' * 241)
    c.thread.join(2)
    assert c.tts.speak.call_args.args[0] == 'Le résultat détaillé est affiché dans Jarvis.'


@pytest.mark.parametrize('kwargs', [{'store_recordings': True}, {'wake_word_enabled': True}, {'tts_volume': 2},
    {'max_recording_seconds': -1}, {'timeout_seconds': float('nan')}, {'stt_model': 'ggml-base.en.bin'},
    {'push_to_talk_mode': 'hold'}, {'enabled': 1}])
def test_config_rejects_unsafe_values(kwargs):
    with pytest.raises(ValueError):
        VoiceConfig(**kwargs)


def test_private_atomic_preferences(tmp_path):
    path = tmp_path / 'voice.toml'
    value = VoiceConfig(enabled=True, stt_model='/tmp/École/base.bin', microphone_device='mic')
    save(value, path)
    assert load(path) == value
    assert path.stat().st_mode & 0o077 == 0
    path.write_text('invalid toml !')
    with pytest.raises(ValueError):
        save(value, path)
    assert path.read_text() == 'invalid toml !'


def test_device_change_only_idle():
    c = controller()
    c.configure(replace(c.config, microphone_device='other'))
    assert c.config.microphone_device == 'other'
    listen(c)
    with pytest.raises(VoiceError):
        c.configure(VoiceConfig())


@pytest.mark.parametrize('backend,method,field', [(WhisperCLI, 'transcribe', 'stt_model'), (PiperCLI, 'speak', 'tts_voice')])
def test_missing_model_no_process(backend, method, field, tmp_path):
    config = replace(VoiceConfig(), **{field: str(tmp_path/'absent')})
    with pytest.raises(VoiceError, match='Modèle local absent'):
        getattr(backend(), method)(b'' if method == 'transcribe' else 'test', config, threading.Event())


def test_whisper_format_cpu_cleanup_and_confidence(tmp_path, monkeypatch):
    import wave

    from jarvis.voice import backends as b
    model = tmp_path / 'base.bin'
    model.touch()
    monkeypatch.setattr(b, 'executable', lambda name: name)
    seen = []
    def run(argv, *args):
        assert '-ng' in argv and argv[argv.index('-l')+1] == 'fr'
        audio = Path(argv[argv.index('-f')+1])
        seen.append(audio.parent)
        assert audio.parent.stat().st_mode & 0o077 == 0
        with wave.open(str(audio)) as stream:
            assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (1,2,16000)
        output = Path(argv[argv.index('-of')+1]+'.json')
        output.write_text(json.dumps({'transcription':[{'text':'aide', 'tokens':[{'text':'aide', 'p':.9}]}]}))
    monkeypatch.setattr(b, 'run', run)
    result = WhisperCLI().transcribe(b'\0\1'*100, replace(VoiceConfig(), stt_model=str(model)), threading.Event())
    assert result == Transcript('aide', .9)
    assert not seen[0].exists()


def test_wake_gate_opt_in_false_positive_cooldown():
    clock = Mock(return_value=0)
    gate = WakeGate(clock=clock)
    assert not any(gate.feed(1) for _ in range(5))
    gate.enabled = True
    assert not gate.feed(.9)
    assert not gate.feed(.1)
    assert not gate.feed(.9)
    assert not gate.feed(.9)
    assert gate.feed(.9)
    assert not any(gate.feed(.9) for _ in range(10))
    clock.return_value = 6
    assert gate.feed(.9)
    gate.disable()
    assert not gate.feed(1)


def test_historical_commands_preserved():
    from jarvis.registry import COMMANDS, help_text, resolve
    assert len([c for c in COMMANDS if not c.id.startswith(('voice.', 'ai.'))]) == 59
    assert len([c for c in COMMANDS if c.id.startswith('voice.')]) == 10
    for c in COMMANDS:
        if c.id.startswith('voice.'):
            assert resolve('Jarvis, ' + c.name).command.id == c.id
            assert c.name in help_text()


def test_punctuation_only_for_parameterless_commands():
    c = controller('Jarvis, aide.')
    listen(c)
    assert c.take_pending() == 'Jarvis, aide'
    c = controller('suis le fichier École/test.py')
    listen(c)
    assert c.take_pending() == 'suis le fichier École/test.py'


def test_devices_absent_and_disconnected(monkeypatch):
    from jarvis.voice import backends as b
    monkeypatch.setattr(b, 'devices', lambda: [])
    for kind in ('Audio/Sink', 'Audio/Source'):
        with pytest.raises(VoiceError, match='absent'):
            b.check_device('', kind)
    monkeypatch.setattr(b, 'devices', lambda: [('mic', 'Micro', 'Audio/Source')])
    b.check_device('mic', 'Audio/Source')
    with pytest.raises(VoiceError):
        b.check_device('old', 'Audio/Source')


def test_piper_arguments_no_text_in_argv_and_cleanup(tmp_path, monkeypatch):
    from jarvis.voice import backends as b
    model = tmp_path/'voice.onnx'
    model.touch()
    Path(str(model)+'.json').write_text('{}')
    monkeypatch.setattr(b, 'executable', lambda name: name)
    monkeypatch.setattr(b, 'check_device', Mock())
    run = Mock()
    monkeypatch.setattr(b, 'run', run)
    value = replace(VoiceConfig(), tts_voice=str(model), tts_speed=2, output_device='sink')
    b.PiperCLI().speak('contenu privé', value, threading.Event())
    args = run.call_args_list[0].args
    assert 'contenu privé' not in str(args[0])
    assert args[3] == 'contenu privé'.encode()
    assert args[0][-1] == '0.5'
    assert not Path(args[0][args[0].index('-f')+1]).parent.exists()
    assert '--target' in run.call_args_list[1].args[0]


def test_timeout_reaps_and_does_not_expose_stderr(monkeypatch):
    import subprocess

    from jarvis.voice import backends as b
    process = Mock()
    process.communicate.side_effect = subprocess.TimeoutExpired('private', .05)
    process.poll.return_value = None
    monkeypatch.setattr(b.subprocess, 'Popen', Mock(return_value=process))
    clock = iter([0, 0, 2])
    monkeypatch.setattr(b.time, 'monotonic', lambda: next(clock))
    with pytest.raises(VoiceError, match='Délai'):
        b.run(['local'], threading.Event(), 1)
    process.terminate.assert_called_once()
    assert process.wait.called


def test_cancel_before_process_creation(monkeypatch):
    from jarvis.voice import backends as b
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        b.run(['local'], cancel, 1)
    b.subprocess.Popen.assert_not_called()


def test_tts_failure_text_fallback():
    c = controller()
    c.config = replace(c.config, spoken_responses=True)
    c.tts.speak.side_effect = VoiceError('Sortie absente')
    c.completed('Texte complet conservé')
    c.thread.join(2)
    assert c.last_response == 'Texte complet conservé'
    assert c.snapshot.state == State.ERROR


def test_qt_bridge_confirmation_shares_bus(qapp, monkeypatch):
    from test_interface import pump

    from jarvis.interface.context import AppContext
    executor = Mock(return_value='Résultat réel')
    context = AppContext(executor=executor)
    try:
        bridge = context.voice
        bridge.controller = controller()
        bridge.controller.listener = bridge.changed.emit
        listen(bridge.controller)
        bridge.confirm()
        bridge.confirm()
        pump(qapp, lambda: not context.commands.busy)
        executor.assert_called_once_with('Jarvis, aide')
        assert bridge.controller.last_response == 'Résultat réel'
    finally:
        context.shutdown()


def test_no_qt_or_network_import_in_service():
    import ast
    root = Path(__file__).parents[1]/'src/jarvis/voice'
    for path in root.glob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or '']
            else:
                continue
            assert not any(m.startswith(('PySide', 'requests', 'urllib', 'http', 'socket')) for m in modules)


def test_stop_has_priority_over_late_command_response():
    c = controller()
    c.config = replace(c.config, spoken_responses=True)
    listen(c)
    assert c.take_pending()
    c.cancel()
    c.completed('Résultat après arrêt')
    c.tts.speak.assert_not_called()
    assert c.last_response == 'Résultat après arrêt'


def test_scenario_voice_keeps_existing_approval(monkeypatch):
    from jarvis.registry import resolve
    from jarvis.scenarios import storage
    from jarvis.scenarios.engine import engine
    from jarvis.scenarios.model import new_action, new_scenario
    value = new_scenario('Révisions', [new_action('apply_layout', layout='etudes', workspace=3)])
    storage.Store().save(value, create=True)
    fake = Mock()
    fake.check.return_value = 'Aperçu local'
    monkeypatch.setattr(engine, 'actions', fake)
    c = controller('Jarvis, lance scénario Révisions')
    listen(c)
    result = resolve(c.take_pending()).run()
    assert 'confirme scénario' in result.lower()
    fake.execute.assert_not_called()


def test_capture_simulated_pcm_and_resource_release(monkeypatch):
    from jarvis.voice import backends as b
    monkeypatch.setattr(b, 'check_device', Mock())
    monkeypatch.setattr(b, 'executable', lambda name: name)
    process = Mock()
    process.stdout.fileno.return_value = 42
    process.poll.return_value = None
    monkeypatch.setattr(b.subprocess, 'Popen', Mock(return_value=process))
    selector = Mock()
    selector.__enter__ = Mock(return_value=selector)
    selector.__exit__ = Mock(return_value=False)
    selector.select.return_value = [True]
    monkeypatch.setattr(b.selectors, 'DefaultSelector', Mock(return_value=selector))
    monkeypatch.setattr(b.os, 'read', Mock(return_value=b'\xff\x1f' * 1600))
    stop = threading.Event()
    frames = []
    def progress(rms, seconds):
        frames.append((rms, seconds))
        stop.set()
    pcm = b.PipeWireCapture().capture(VoiceConfig(), stop, threading.Event(), progress)
    assert len(pcm) == 3200 and frames[0][0] > .1
    assert frames[0][1] == .1
    argv = b.subprocess.Popen.call_args.args[0]
    assert argv[argv.index('--rate')+1] == '16000'
    assert '--raw' in argv
    process.terminate.assert_called_once()
    process.stdout.close.assert_called_once()


def test_ipc_rejects_hidden_start_and_unknown_payload(qapp):
    from jarvis.interface.voice_ipc import VoiceIPC
    obj = Mock()
    obj.bridge.controller.snapshot.state = State.IDLE
    socket = Mock()
    socket.readAll.return_value = b'exec anything\n'
    VoiceIPC.read(obj, socket)
    obj.bridge.toggle.assert_not_called()
    socket.readAll.return_value = b'toggle\n'
    VoiceIPC.read(obj, socket)
    obj.bridge.toggle.assert_not_called()
    obj.bridge.controller.snapshot.state = State.LISTENING
    VoiceIPC.read(obj, socket)
    obj.bridge.toggle.assert_called_once()
