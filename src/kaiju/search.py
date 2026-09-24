from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kaiju.cards import Card, get_card, resolve_code, scan_cards, sort_cards
from kaiju.errors import KaijuError
from kaiju.workspace import Workspace

MAX_FILE_BYTES = 1_048_576
HEAD_BYTES = 8192
CANONICAL = ("README.md", "MEMORY.md", "DELIVERY.md")


@dataclass(frozen=True)
class Hit:
    label: str
    status: str
    relpath: str
    line_no: int
    snippet: str
    title: str


def search(
    ws: Workspace,
    pattern: str,
    *,
    status: str | None = None,
    epic: str | None = None,
    open_: bool | None = None,
    cards_only: bool = False,
    case_sensitive: bool = False,
) -> list[Card] | list[Hit]:
    cards = _filtered_cards(ws, status=status, epic=epic, open_=open_)
    if pattern == "":
        return cards

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        raise KaijuError(f"invalid regex: {exc}") from exc

    hits: list[Hit] = []
    for card in cards:
        hits.extend(_hits_in_card(card, regex))

    card_filter = status is not None or epic is not None or open_ is not None
    if not card_filter:
        hits.extend(_hits_in_root(ws, regex))

    return hits


def _filtered_cards(
    ws: Workspace,
    *,
    status: str | None,
    epic: str | None,
    open_: bool | None,
) -> list[Card]:
    cards = sort_cards(scan_cards(ws))
    if status is not None:
        cards = [c for c in cards if c.status == status]
    if epic is not None:
        epic_code = resolve_code(ws, epic)
        try:
            found = get_card(ws, epic)
            epic_code = found.code
        except KaijuError:
            pass
        cards = [c for c in cards if c.epic == epic_code]
    if open_ is True:
        cards = [c for c in cards if not c.is_closed]
    elif open_ is False:
        cards = [c for c in cards if c.is_closed]
    return cards


def _hits_in_card(card: Card, regex: re.Pattern[str]) -> list[Hit]:
    hits: list[Hit] = []
    seen: set[Path] = set()
    for name in CANONICAL:
        path = card.path / name
        hits.extend(
            _hits_in_file(
                path,
                regex,
                label=card.code,
                status=card.status,
                relpath=name,
                title=card.title,
            )
        )
        if path.exists():
            try:
                seen.add(path.resolve())
            except OSError:
                seen.add(path)

    extras: list[Path] = []
    for path in _iter_files(card.path):
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        extras.append(path)
    extras.sort(key=lambda p: p.relative_to(card.path).as_posix())
    for path in extras:
        rel = path.relative_to(card.path).as_posix()
        hits.extend(
            _hits_in_file(
                path,
                regex,
                label=card.code,
                status=card.status,
                relpath=rel,
                title=card.title,
            )
        )
    return hits


def _hits_in_root(ws: Workspace, regex: re.Pattern[str]) -> list[Hit]:
    hits: list[Hit] = []
    for name, label in (("BACKLOG.md", "BACKLOG"), ("README.md", "WORKSPACE")):
        path = ws.root / name
        hits.extend(
            _hits_in_file(
                path,
                regex,
                label=label,
                status="",
                relpath=name,
                title="",
            )
        )
    cron_dir = ws.root / "cron"
    if cron_dir.is_dir() and not cron_dir.is_symlink():
        for path in _iter_files(cron_dir):
            hits.extend(
                _hits_in_file(
                    path,
                    regex,
                    label="CRON",
                    status="",
                    relpath=path.relative_to(ws.root).as_posix(),
                    title="",
                )
            )
    return hits


def _hits_in_file(
    path: Path,
    regex: re.Pattern[str],
    *,
    label: str,
    status: str,
    relpath: str,
    title: str,
) -> list[Hit]:
    if not path.is_file() or path.name.startswith("."):
        return []
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size > MAX_FILE_BYTES:
        return []
    try:
        with path.open("rb") as handle:
            head = handle.read(HEAD_BYTES)
            if b"\0" in head:
                return []
            rest = handle.read()
    except OSError:
        return []
    text = (head + rest).decode("utf-8", errors="replace")
    hits: list[Hit] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if regex.search(line) is None:
            continue
        hits.append(
            Hit(
                label=label,
                status=status,
                relpath=relpath,
                line_no=line_no,
                snippet=make_snippet(line, regex),
                title=title,
            )
        )
    return hits


def make_snippet(line: str, regex: re.Pattern[str]) -> str:
    text = line.replace("\t", " ").strip()
    if len(text) <= 100:
        return text
    match = regex.search(text)
    pos = match.start() if match is not None else 0
    start = max(0, pos - 50)
    end = start + 100
    if end > len(text):
        end = len(text)
        start = max(0, end - 100)
    chunk = text[start:end]
    if start > 0:
        chunk = "…" + chunk
    if end < len(text):
        chunk = chunk + "…"
    return chunk


def _iter_files(root: Path):
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError:
        return
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_symlink() and entry.is_dir():
            # Never follow directory links: they may leave the card or loop.
            continue
        if entry.is_dir():
            yield from _iter_files(entry)
        elif entry.is_file():
            yield entry


def aggregate_hits(hits: list[Hit]) -> list[tuple[Hit, int]]:
    order: list[str] = []
    counts: dict[str, int] = {}
    first: dict[str, Hit] = {}
    for hit in hits:
        if hit.label not in counts:
            order.append(hit.label)
            counts[hit.label] = 0
            first[hit.label] = hit
        counts[hit.label] += 1
    return [(first[label], counts[label]) for label in order]
