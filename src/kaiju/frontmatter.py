from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from kaiju.errors import KaijuError


def parse(text: str) -> dict[str, str] | None:
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    fields: dict[str, str] = {}
    closed = False
    for line in lines[1:]:
        if line == "---":
            closed = True
            break
        if line.strip() == "" or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key not in fields:
            fields[key] = value
    if not closed:
        return None
    return fields


def set_fields(path: Path, updates: dict[str, str]) -> None:
    for value in updates.values():
        if "\n" in value or "\r" in value:
            raise KaijuError("field value cannot contain line break")

    raw = path.read_bytes()
    bom = b""
    if raw.startswith(b"\xef\xbb\xbf"):
        bom = raw[:3]
        raw = raw[3:]
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or _body(lines[0]) != "---":
        raise KaijuError(f"{path} has no front-matter")

    close_idx = None
    for index in range(1, len(lines)):
        if _body(lines[index]) == "---":
            close_idx = index
            break
    if close_idx is None:
        raise KaijuError(f"{path} has no front-matter")

    key_at: dict[str, int] = {}
    for index in range(1, close_idx):
        line = _body(lines[index])
        if line.strip() == "" or line.startswith("#") or ":" not in line:
            continue
        key = line.partition(":")[0].strip()
        if key and key not in key_at:
            key_at[key] = index

    for key, value in updates.items():
        rendered = _render_field(key, value)
        if key in key_at:
            index = key_at[key]
            lines[index] = rendered + _ending(lines[index])
        else:
            lines.insert(close_idx, rendered + _ending(lines[close_idx]))
            key_at[key] = close_idx
            close_idx += 1

    new_text = "".join(lines)
    data = new_text.encode("utf-8")
    if bom:
        data = bom + data
    _atomic_write_bytes(path, data)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".kaiju-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _body(line: str) -> str:
    return line.rstrip("\r\n")


def _ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return "\n"


def _render_field(key: str, value: str) -> str:
    if value == "":
        return f"{key}:"
    return f"{key}: {value}"
