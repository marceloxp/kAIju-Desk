from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from kaiju.workspace import atomic_write

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEMES = (THEME_LIGHT, THEME_DARK)

FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 18
FONT_SIZE_DEFAULT = 10


@dataclass(frozen=True)
class Prefs:
    theme: str = THEME_LIGHT
    font_size: int = FONT_SIZE_DEFAULT

    def __post_init__(self) -> None:
        theme = str(self.theme).strip().casefold()
        if theme not in THEMES:
            theme = THEME_LIGHT
        size = _as_int(self.font_size, FONT_SIZE_DEFAULT)
        size = min(FONT_SIZE_MAX, max(FONT_SIZE_MIN, size))
        object.__setattr__(self, "theme", theme)
        object.__setattr__(self, "font_size", size)


def prefs_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "kaiju" / "gui.toml"


def load_prefs() -> Prefs:
    path = prefs_path()
    if not path.is_file():
        return Prefs()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return Prefs()
    return parse_prefs(text)


def save_prefs(prefs: Prefs) -> None:
    atomic_write(prefs_path(), render_prefs(prefs))


def parse_prefs(text: str) -> Prefs:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return Prefs()
    if not isinstance(data, dict):
        return Prefs()
    theme = data.get("theme", THEME_LIGHT)
    size = data.get("font_size", FONT_SIZE_DEFAULT)
    if not isinstance(theme, str):
        theme = THEME_LIGHT
    return Prefs(theme=theme, font_size=_as_int(size, FONT_SIZE_DEFAULT))


def render_prefs(prefs: Prefs) -> str:
    return f'theme = "{prefs.theme}"\nfont_size = {prefs.font_size}\n'


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
        return default
    return value
