"""Configuration IA indépendante ; aucune conversation sur disque."""
import ipaddress
import json
import math
import os
import re
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

from jarvis.config import settings

PATH = settings.data_dir / 'ai.toml'


def endpoint_parts(value):
    if not isinstance(value, str):
        raise ValueError('Endpoint local invalide.')
    url = urlsplit(value)
    try:
        local = ipaddress.ip_address(url.hostname or '').is_loopback
    except ValueError:
        local = False
    if (not local or url.scheme != 'http' or url.username or url.password
            or url.path not in ('', '/') or url.query or url.fragment or not url.port):
        raise ValueError('Endpoint HTTP loopback numérique avec port requis ; distant interdit.')
    return url


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    backend: str = 'ollama'
    model: str = 'qwen3:4b'
    endpoint: str = 'http://127.0.0.1:11434'
    temperature: float = 0.2
    context_limit: int = 8192
    max_output_tokens: int = 768
    request_timeout: float = 90.0
    tool_call_limit: int = 3
    conversation_persistence: bool = False
    streaming_enabled: bool = True
    retain_context: bool = True
    keep_alive: int = 0

    def __post_init__(self):
        endpoint_parts(self.endpoint)
        if self.backend != 'ollama':
            raise ValueError('Backend non pris en charge.')
        if not isinstance(self.model, str) or not re.fullmatch(r'[a-zA-Z0-9_.:/-]{1,120}', self.model) or 'cloud' in self.model.lower():
            raise ValueError('Nom de modèle local invalide.')
        for key in ('enabled', 'conversation_persistence', 'streaming_enabled', 'retain_context'):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f'{key} : booléen requis.')
        if self.conversation_persistence:
            raise ValueError('Persistance des conversations indisponible en V1.5.')
        for key, low, high in [('context_limit', 4096, 32768), ('max_output_tokens', 128, 2048),
                               ('tool_call_limit', 1, 4), ('keep_alive', 0, 300)]:
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{key} hors limites.')
        for key, low, high in [('temperature', 0, 1), ('request_timeout', 1, 300)]:
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{key} hors limites.')


def load(path=None):
    path = Path(path or PATH)
    if not path.exists():
        return AIConfig()
    if path.stat().st_size > 16384:
        raise ValueError('Configuration trop longue.')
    data = tomllib.loads(path.read_text())
    if set(data) != {'ai'}:
        raise ValueError('Section ai requise exclusivement.')
    return AIConfig(**data['ai'])


def save(value, path=None):
    value = AIConfig(**asdict(value))
    path = Path(path or PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.ai-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('[ai]\n')
            for key, val in asdict(value).items():
                stream.write(f'{key} = {json.dumps(val)}\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
