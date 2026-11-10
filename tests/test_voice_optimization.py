import importlib.util
import json
import threading
import wave
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_voice import controller, listen

from jarvis.voice import backends as b
from jarvis.voice.config import VoiceConfig
from jarvis.voice.controller import State


def pcm(value, frames=1):
    return int(value).to_bytes(2, 'little', signed=True) * 320 * frames


def test_preroll_retains_exact_last_300ms_and_tail():
    buffer = b.CaptureBuffer(VoiceConfig(silence_seconds=.3))
    buffer.feed(pcm(10, 30))
    assert len(buffer.pre) == 9600 and not buffer.audio
    buffer.feed(pcm(1000, 2))
    buffer.feed(pcm(0, 15))
    assert buffer.done
    assert buffer.finish() == pcm(10, 15) + pcm(1000, 2) + pcm(0, 15)


@pytest.mark.parametrize('pre', [0, 100, 1000])
def test_configurable_preroll(pre):
    buffer = b.CaptureBuffer(VoiceConfig(pre_recording_ms=pre))
    buffer.feed(pcm(1, 100))
    buffer.feed(pcm(1000))
    assert buffer.finish() == pcm(1, pre//20) + pcm(1000)


def test_fragmented_reads_and_short_word():
    data = pcm(0, 10) + pcm(1100, 5) + pcm(0, 75)
    normal = b.CaptureBuffer(VoiceConfig())
    fragmented = b.CaptureBuffer(VoiceConfig())
    normal.feed(data)
    for offset in range(0, len(data), 137):
        fragmented.feed(data[offset:offset+137])
    assert normal.done and fragmented.done
    assert fragmented.finish() == normal.finish() == data


@pytest.mark.parametrize('seconds', [5, 12, 30])
def test_long_capture_bounded(seconds):
    buffer = b.CaptureBuffer(VoiceConfig(max_recording_seconds=seconds))
    for _ in range(int(seconds*50) + 10):
        buffer.feed(pcm(1000))
    assert len(buffer.finish()) == seconds*32000
    assert buffer.done


def test_silence_and_stationary_background_do_not_trigger():
    buffer = b.CaptureBuffer(VoiceConfig(max_recording_seconds=5))
    buffer.feed(pcm(400, 250))
    assert buffer.done and not buffer.finish()
    assert buffer.noise > 0


def test_hysteresis_preserves_quiet_syllables():
    buffer = b.CaptureBuffer(VoiceConfig(silence_seconds=.3))
    buffer.feed(pcm(1000))
    buffer.feed(pcm(350, 30))
    assert not buffer.done
    buffer.feed(pcm(0, 15))
    assert buffer.done


@pytest.mark.parametrize('kwargs', [{'max_recording_seconds':4}, {'max_recording_seconds':31},
    {'pre_recording_ms':-1}, {'pre_recording_ms':1001}, {'vad_enabled':1},
    {'compute_backend':'cuda'}, {'whisper_prompt':'a'*257}])
def test_new_config_validation(kwargs):
    with pytest.raises(ValueError):
        VoiceConfig(**kwargs)


@pytest.fixture
def whisper(tmp_path, monkeypatch):
    model = tmp_path/'base.bin'
    model.touch()
    monkeypatch.setattr(b, 'executable', lambda value: value)
    calls = []
    def run(argv, *args):
        calls.append(argv)
        Path(argv[argv.index('-of')+1]+'.json').write_text(json.dumps({'transcription':[{'text':'aide'}]}))
        return b.Execution(vulkan='-ng' not in argv)
    monkeypatch.setattr(b, 'run', run)
    return replace(VoiceConfig(), stt_model=str(model)), calls


def test_missing_vad_degrades_and_prompt_opt_in(whisper):
    config, calls = whisper
    result = b.WhisperCLI().transcribe(pcm(1000), replace(config, vad_enabled=True), threading.Event())
    assert not result.vad_used and 'absent' in result.warning
    assert '--vad' not in calls[0] and '--prompt' not in calls[0]
    prompt = 'Jarvis, Omarchy, Hyprland, Rust, Python, Git, Steam, Notion.'
    b.WhisperCLI().transcribe(pcm(1000), replace(config, whisper_prompt=prompt), threading.Event())
    assert calls[-1][calls[-1].index('--prompt')+1] == prompt


def test_vad_success_and_gpu_separate_binary(whisper, tmp_path):
    config, calls = whisper
    vad = tmp_path/'vad.bin'
    vad.touch()
    result = b.WhisperCLI().transcribe(pcm(1000), replace(config, vad_enabled=True,
        vad_model=str(vad), compute_backend='vulkan', gpu_executable='/opt/whisper-vulkan'), threading.Event())
    assert result.vad_used and not result.warning
    assert calls[0][0] == '/opt/whisper-vulkan' and '-ng' not in calls[0]
    assert '--vad' in calls[0]


@pytest.mark.parametrize('cancel', [False, True])
def test_vad_failure_fallback_but_never_retry_cancellation(whisper, monkeypatch, cancel):
    config, calls = whisper
    original = b.run
    def run(argv, *args):
        if '--vad' in argv:
            raise b.Cancelled() if cancel else b.VoiceError('failed')
        original(argv, *args)
    monkeypatch.setattr(b, 'run', run)
    config = replace(config, vad_enabled=True, vad_model=config.stt_model)
    if cancel:
        with pytest.raises(b.Cancelled):
            b.WhisperCLI().transcribe(pcm(1000), config, threading.Event())
        assert not calls
    else:
        result = b.WhisperCLI().transcribe(pcm(1000), config, threading.Event())
        assert not result.vad_used and 'Échec' in result.warning and len(calls) == 1


@pytest.mark.parametrize('text', ['Aide-moi.', 'aides', 'Jarvis, ouvre Steem', 'aide\x00', 'x'*2049])
def test_never_approximate_or_execute_invalid_transcripts(text):
    c = controller(text)
    listen(c)
    assert c.snapshot.state == State.ERROR and c.pending is None


def test_all_command_names_and_help_preserved():
    from jarvis.registry import COMMANDS, help_text, resolve
    assert len([c for c in COMMANDS if not c.id.startswith('ai.')]) == 69
    for command in COMMANDS:
        assert command.name in help_text()
        match = resolve(command.name)
        # Commands with required arguments need their registered examples instead.
        if match:
            assert match.command.id == command.id


@pytest.mark.parametrize('mode', ['cancel', 'disconnect', 'progress_error'])
def test_capture_always_releases_microphone(monkeypatch, mode):
    monkeypatch.setattr(b, 'check_device', Mock())
    monkeypatch.setattr(b, 'executable', lambda name: name)
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr(b.subprocess, 'Popen', Mock(return_value=process))
    selector = Mock()
    selector.__enter__ = Mock(return_value=selector)
    selector.__exit__ = Mock(return_value=False)
    selector.select.return_value = [True]
    monkeypatch.setattr(b.selectors, 'DefaultSelector', lambda: selector)
    cancel = threading.Event()
    def read(*args):
        if mode == 'cancel':
            cancel.set()
        return b'' if mode == 'disconnect' else pcm(1000)
    monkeypatch.setattr(b.os, 'read', read)
    def progress(*args):
        if mode == 'progress_error':
            raise RuntimeError('callback')
    with pytest.raises((b.VoiceError, RuntimeError)):
        b.PipeWireCapture().capture(VoiceConfig(), threading.Event(), cancel, progress)
    process.terminate.assert_called_once()
    process.wait.assert_called()
    process.stdout.close.assert_called_once()


def test_benchmark_wer_silence_failures_and_fallbacks(tmp_path):
    spec = importlib.util.spec_from_file_location('voice_benchmark', Path(__file__).parents[1]/'tools/voice_benchmark.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.errors('Aide !', 'aide moi') == (1, 1)
    assert module.errors('état système', 'état') == (1, 2)
    assert module.errors('', 'bonjour') == (1, 0)
    audio = tmp_path/'input.wav'
    with wave.open(str(audio), 'wb') as stream:
        stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        stream.writeframes(pcm(0))
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps([{'file':'input.wav', 'expected':''}]))
    adapter = Mock()
    adapter.transcribe.side_effect = [b.Transcript('bonjour'), b.Transcript('bonjour', warning='fallback'), b.VoiceError('missing'), b.VoiceError('missing')]
    result = module.benchmark(manifest, {'base':audio, 'small':tmp_path/'missing'}, VoiceConfig(), adapter=adapter)
    assert result['summaries'][0]['silence_hallucinations'] == 1
    assert result['summaries'][1]['fallbacks'] == 1
    assert result['summaries'][1]['measured'] == 0
    assert result['summaries'][2]['failures'] == 1


def test_fractional_limit_and_partial_final_frame():
    buffer = b.CaptureBuffer(VoiceConfig(max_recording_seconds=5.01))
    buffer.feed(pcm(1000, 260))
    assert len(buffer.finish()) == int(5.01*16000)*2
    short = b.CaptureBuffer(VoiceConfig())
    short.feed(pcm(1000)[:200])
    assert len(short.finish()) == 200


@pytest.mark.parametrize('payload', [{'transcription':None}, {'transcription':[{'text':None}]},
                                    {'transcription':[{'text':'aide\x00'}]}, {}])
def test_malformed_whisper_json_rejected(whisper, monkeypatch, payload):
    config, _ = whisper
    folders = []
    def run(argv, *args):
        output = Path(argv[argv.index('-of')+1]+'.json')
        folders.append(output.parent)
        output.write_text(json.dumps(payload))
    monkeypatch.setattr(b, 'run', run)
    with pytest.raises(b.VoiceError):
        b.WhisperCLI().transcribe(pcm(1000), config, threading.Event())
    assert not folders[0].exists()


def test_new_preferences_roundtrip(tmp_path):
    from jarvis.voice.config import load, save
    config = VoiceConfig(pre_recording_ms=500, vad_enabled=True, vad_model='/local/vad.bin',
                         whisper_prompt='Omarchy, Hyprland.', compute_backend='vulkan',
                         gpu_executable='/local/vulkan', adaptive_noise=False)
    path = tmp_path/'voice.toml'
    save(config, path)
    assert load(path) == config
