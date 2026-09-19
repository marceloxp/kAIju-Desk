from __future__ import annotations

import contextlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from kaiju import templates
from kaiju.errors import KaijuError

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

CORE_FIELDS = ("card", "title", "status", "created_at", "closed_at", "epic", "parent")

PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]*$")
STATUS_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ADDITIONAL_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Config:
    name: str
    prefix: str
    digits: int
    statuses: dict[str, str]
    additional_fields: dict[str, str]


@dataclass(frozen=True)
class Workspace:
    root: Path
    config: Config


def today() -> str:
    raw = os.environ.get("KAIJU_TODAY")
    if raw is not None:
        if not DATE_RE.fullmatch(raw):
            raise KaijuError(f'KAIJU_TODAY invalid "{raw}" (use YYYY-MM-DD)')
        return raw
    return date.today().isoformat()


def atomic_write(path: Path, content: str) -> None:
    if not content.endswith("\n"):
        content += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kaiju-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def find_workspace(start: Path) -> Workspace:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    origin = current
    while True:
        candidate = current / "kaiju.toml"
        if candidate.is_file():
            return Workspace(root=current, config=load_config(candidate))
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise KaijuError(f'no kAIju workspace found starting from {origin} (run "kaiju init")')


def find_enclosing_workspace(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    while True:
        parent = current.parent
        if parent == current:
            return None
        if (parent / "kaiju.toml").is_file():
            return parent
        current = parent


def load_config(path: Path) -> Config:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KaijuError(f"{path}: could not read: {exc}") from exc
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise KaijuError(f"{path}: invalid TOML: {exc}") from exc
    if not isinstance(data, dict):
        raise KaijuError(f"{path}: invalid TOML: root is not a table")

    name = _require_str(path, data, "name")
    if name == "":
        raise KaijuError(f'{path}: "name" cannot be empty')

    prefix = _require_str(path, data, "prefix")
    if not PREFIX_RE.fullmatch(prefix):
        raise KaijuError(f'{path}: "prefix" invalid "{prefix}" (must match {PREFIX_RE.pattern})')

    if "digits" not in data:
        raise KaijuError(f'{path}: missing "digits"')
    digits = data["digits"]
    if not isinstance(digits, int) or isinstance(digits, bool):
        raise KaijuError(f'{path}: "digits" must be an integer between 1 and 9')
    if digits < 1 or digits > 9:
        raise KaijuError(f'{path}: "digits" must be an integer between 1 and 9')

    if "status" not in data:
        raise KaijuError(f"{path}: missing [status] table")
    statuses_raw = data["status"]
    if not isinstance(statuses_raw, dict):
        raise KaijuError(f"{path}: [status] must be a table")
    if not statuses_raw:
        raise KaijuError(f"{path}: [status] needs at least one entry")
    statuses: dict[str, str] = {}
    for key, value in statuses_raw.items():
        if not STATUS_KEY_RE.fullmatch(key):
            raise KaijuError(f'{path}: status "{key}" invalid (must match {STATUS_KEY_RE.pattern})')
        if not isinstance(value, str):
            raise KaijuError(f'{path}: description of status "{key}" must be string')
        statuses[key] = value

    additional: dict[str, str] = {}
    if "additional_fields" in data:
        extra_raw = data["additional_fields"]
        if not isinstance(extra_raw, dict):
            raise KaijuError(f"{path}: [additional_fields] must be a table")
        for key, value in extra_raw.items():
            if not ADDITIONAL_KEY_RE.fullmatch(key):
                raise KaijuError(
                    f'{path}: additional field "{key}" invalid '
                    f"(must match {ADDITIONAL_KEY_RE.pattern})"
                )
            if key in CORE_FIELDS:
                raise KaijuError(f'{path}: additional field "{key}" collides with a core field')
            if not isinstance(value, str):
                raise KaijuError(f'{path}: description of additional field "{key}" must be string')
            additional[key] = value

    return Config(
        name=name,
        prefix=prefix,
        digits=digits,
        statuses=statuses,
        additional_fields=additional,
    )


def _require_str(path: Path, data: dict, key: str) -> str:
    if key not in data:
        raise KaijuError(f'{path}: missing "{key}"')
    value = data[key]
    if not isinstance(value, str):
        raise KaijuError(f'{path}: "{key}" must be string')
    return value


def validate_prefix(prefix: str) -> None:
    if not PREFIX_RE.fullmatch(prefix):
        raise KaijuError(f'prefix invalid "{prefix}" (must match {PREFIX_RE.pattern})')


def validate_digits(digits: int) -> None:
    if digits < 1 or digits > 9:
        raise KaijuError("digits must be an integer between 1 and 9")


def init_workspace(
    dir: Path,
    prefix: str,
    name: str | None,
    digits: int,
) -> Workspace:
    validate_prefix(prefix)
    validate_digits(digits)
    dir = dir.resolve()
    toml_path = dir / "kaiju.toml"
    if toml_path.is_file():
        raise KaijuError(f"{dir} is already a kAIju workspace")
    enclosing = find_enclosing_workspace(dir)
    if enclosing is not None:
        raise KaijuError(f"{dir} is inside workspace {enclosing}")
    dir.mkdir(parents=True, exist_ok=True)
    resolved_name = name if name else dir.name
    if resolved_name == "":
        raise KaijuError("name cannot be empty")
    atomic_write(
        toml_path,
        templates.kaiju_toml(name=resolved_name, prefix=prefix, digits=digits),
    )
    backlog = dir / "BACKLOG.md"
    if not backlog.exists():
        atomic_write(backlog, templates.backlog_md())
    return Workspace(root=dir, config=load_config(toml_path))
