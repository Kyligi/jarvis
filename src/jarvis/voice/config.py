"""Private, atomic voice preferences; never rewrite business/UI preferences."""
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import tempfile
import tomllib
from jarvis.config import settings

PATH = settings.data_dir / 'voice.toml'


@dataclass(frozen=True)
class VoiceConfig:
    enabled: bool = False
    push_to_talk_mode: str = 'toggle'
    microphone_device: str = ''
    output_device: str = ''
    stt_backend: str = 'whisper.cpp'
    stt_executable: str = 'whisper-cli'
    stt_model: str = ''
    tts_backend: str = 'piper'
    tts_executable: str = 'piper'
    tts_voice: str = ''
    spoken_responses: bool = False
    tts_speed: float = 1.0
    tts_volume: float = 0.7
    wake_word_enabled: bool = False
    wake_word_model: str = ''
    wake_word_threshold: float = 0.7
    max_recording_seconds: float = 12.0
    pre_recording_ms: float = 300.0
    adaptive_noise: bool = True
    vad_enabled: bool = False
    vad_model: str = ''
    whisper_prompt: str = ''
    compute_backend: str = 'cpu'
    gpu_executable: str = ''
    silence_seconds: float = 1.5
    silence_threshold: float = 0.015
    timeout_seconds: float = 60.0
    store_recordings: bool = False

    def __post_init__(self):
        for key in ('enabled', 'spoken_responses', 'wake_word_enabled', 'store_recordings', 'adaptive_noise', 'vad_enabled'):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f'{key} : booléen requis')
        for key, low, high in (
            ('tts_speed', .5, 2), ('tts_volume', 0, 1),
            ('wake_word_threshold', .1, 1), ('max_recording_seconds', 5, 30),
            ('silence_seconds', .3, 10), ('silence_threshold', .001, .5),
            ('timeout_seconds', 1, 300), ('pre_recording_ms', 0, 1000),
        ):
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{key} : valeur hors limites')
        for key, value in asdict(self).items():
            if isinstance(getattr(type(self), key, None), str):
                if not isinstance(value, str) or len(value) > 4096 or '\x00' in value or '\n' in value:
                    raise ValueError(f'{key} : texte invalide')
        if self.push_to_talk_mode != 'toggle' or self.stt_backend != 'whisper.cpp' or self.tts_backend != 'piper':
            raise ValueError('Backend ou mode non pris en charge')
        if self.compute_backend not in ('cpu', 'vulkan'):
            raise ValueError('Backend de calcul invalide')
        if len(self.whisper_prompt) > 256:
            raise ValueError('Contexte Whisper limité à 256 caractères')
        if self.store_recordings:
            raise ValueError('Le stockage persistant audio est désactivé en V1.4')
        if self.wake_word_enabled:
            raise ValueError('Wake word expérimental non validé : activation indisponible')
        if '.en.' in Path(self.stt_model).name or Path(self.stt_model).stem.endswith('.en'):
            raise ValueError('Choisir un modèle Whisper multilingue, pas .en')


def load(path=None):
    path = path or PATH
    if not path.exists():
        return VoiceConfig()
    return VoiceConfig(**tomllib.loads(path.read_text())['voice'])


def save(value, path=None):
    VoiceConfig(**asdict(value))
    path = path or PATH
    if path.exists():
        load(path)  # preserve invalid/unknown-version files
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.voice-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write('[voice]\n')
            for key, item in asdict(value).items():
                stream.write(f'{key} = {json.dumps(item, ensure_ascii=False)}\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
