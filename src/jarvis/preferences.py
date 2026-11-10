"""Préférences d'interface séparées du TOML métier, remplacées atomiquement."""
import os
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from jarvis.config import settings

PREFERENCES_PATH = settings.data_dir / "ui.toml"


@dataclass(frozen=True)
class Preferences:
    animations: bool = True
    refresh_seconds: int = 2

    def __post_init__(self):
        if type(self.animations) is not bool:
            raise ValueError("Animations : booléen requis")
        if type(self.refresh_seconds) is not int or not 1 <= self.refresh_seconds <= 30:
            raise ValueError("Rafraîchissement : entier de 1 à 30 secondes")


def load_preferences(path: Path | None = None) -> Preferences:
    path = path or PREFERENCES_PATH
    if not path.exists():
        return Preferences()
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    if set(data) - {"animations", "refresh_seconds"}:
        raise ValueError("Préférences inconnues")
    return Preferences(**data)


def save_preferences(value: Preferences, path: Path | None = None) -> None:
    # Valider même une instance provenant d'un autre appelant.
    Preferences(**asdict(value))
    path = path or PREFERENCES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".ui-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(f"animations = {str(value.animations).lower()}\nrefresh_seconds = {value.refresh_seconds}\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
