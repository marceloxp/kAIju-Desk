from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kaiju.cards import scan_cards, sort_cards
from kaiju.frontmatter import parse
from kaiju.search import HEAD_BYTES, MAX_FILE_BYTES
from kaiju.workspace import Workspace


@dataclass(frozen=True)
class CronJob:
    key: str
    title: str
    when: str
    script: str
    readable: str
    card: str
    md_path: Path


def scan_crons(ws: Workspace) -> list[CronJob]:
    jobs: list[CronJob] = []
    jobs.extend(_scan_dir(ws.root, ws.root / "cron", card=""))
    for card in sort_cards(scan_cards(ws)):
        jobs.extend(_scan_dir(ws.root, card.path / "cron", card=card.code))
    jobs.sort(key=lambda job: (job.card, job.when, job.title.casefold(), job.key))
    return jobs


def _scan_dir(root: Path, folder: Path, *, card: str) -> list[CronJob]:
    if folder.is_symlink() or not folder.is_dir():
        return []
    try:
        entries = list(folder.iterdir())
    except OSError:
        return []
    jobs: list[CronJob] = []
    for entry in entries:
        if entry.name.startswith(".") or entry.suffix.lower() != ".md":
            continue
        if entry.is_symlink() or not entry.is_file():
            continue
        try:
            key = entry.relative_to(root).as_posix()
        except ValueError:
            continue
        fields = _read_fields(entry)
        title = fields.get("title") or entry.stem
        jobs.append(
            CronJob(
                key=key,
                title=title,
                when=fields.get("when", ""),
                script=fields.get("script", ""),
                readable=fields.get("readable", ""),
                card=card,
                md_path=entry,
            )
        )
    return jobs


def _read_fields(path: Path) -> dict[str, str]:
    try:
        size = path.stat().st_size
    except OSError:
        return {}
    if size > MAX_FILE_BYTES:
        return {}
    try:
        with path.open("rb") as handle:
            head = handle.read(HEAD_BYTES)
            if b"\0" in head:
                return {}
            rest = handle.read()
    except OSError:
        return {}
    text = (head + rest).decode("utf-8", errors="replace")
    return parse(text) or {}
