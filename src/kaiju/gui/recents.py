from __future__ import annotations

import os
from pathlib import Path

from kaiju.workspace import atomic_write

MAX_RECENTS = 10


def recents_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "kaiju" / "recent-workspaces"


def is_workspace(path: Path) -> bool:
    try:
        return path.is_dir() and (path / "kaiju.toml").is_file()
    except OSError:
        return False


def usable_recents() -> list[Path]:
    """Recents whose folder still exists and is a kAIju workspace."""
    return [path for path in load_recents() if is_workspace(path)]


def load_recents() -> list[Path]:
    path = recents_path()
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    seen: list[Path] = []
    found: set[str] = set()
    for line in text.splitlines():
        raw = line.strip()
        if raw == "" or raw.startswith("#"):
            continue
        if raw in found:
            continue
        found.add(raw)
        seen.append(Path(raw))
    return seen


def remember_workspace(root: Path) -> None:
    resolved = root.resolve()
    key = resolved.as_posix()
    items = [path for path in load_recents() if path.as_posix() != key]
    items.insert(0, resolved)
    text = "".join(f"{path.as_posix()}\n" for path in items[:MAX_RECENTS])
    atomic_write(recents_path(), text)
