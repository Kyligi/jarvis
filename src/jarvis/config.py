"""Configuration locale TOML, chargée une fois au démarrage (aucune écriture)."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Settings:
    projects_root: Path = Path.home() / "Projects"
    data_dir: Path = Path.home() / ".local/share/jarvis"
    workspaces: dict[str, int] = field(default_factory=lambda: {
        "travail": 3, "gaming": 4, "etudes": 5,
    })
    editors: tuple[str, ...] = ("code", "codium", "cursor")
    rust_editors: tuple[str, ...] = ("code", "codium", "zed", "cursor")
    terminal: str = "foot"
    browsers: tuple[str, ...] = ("google-chrome-stable", "google-chrome", "chromium")
    gaming: str = "steam"
    desktop_launcher: str = "gtk-launch"
    notion_desktop: str = "notion"


def load_settings(path: Path | None = None) -> Settings:
    path = path or Path(os.environ.get(
        "JARVIS_CONFIG", str(Path.home() / ".config/jarvis/config.toml")
    ))
    if not path.exists():
        return Settings()
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    defaults = Settings()
    unknown = set(data) - set(Settings.__dataclass_fields__)
    if unknown:
        raise ValueError("Clés de configuration Jarvis inconnues")
    for key, value in data.items():
        if key in {"projects_root", "data_dir"}:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Chemin invalide : {key}")
            data[key] = Path(value).expanduser().resolve()
        elif key == "workspaces":
            if not isinstance(value, dict) or set(value) - set(defaults.workspaces):
                raise ValueError("Modes de configuration inconnus")
            if any(type(n) is not int or not 1 <= n <= 9 for n in value.values()):
                raise ValueError("Les workspaces doivent être des entiers entre 1 et 9")
            data[key] = defaults.workspaces | value
        elif key in {"editors", "rust_editors", "browsers"}:
            if not isinstance(value, list) or not value or not all(
                isinstance(item, str) and item and not any(c.isspace() for c in item)
                for item in value
            ):
                raise ValueError(f"Liste de programmes invalide : {key}")
            data[key] = tuple(value)
        elif not isinstance(value, str) or not value or any(c.isspace() for c in value):
            raise ValueError(f"Programme invalide : {key}")
    return Settings(**data)


settings = load_settings()
