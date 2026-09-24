from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kaiju.cards import Card, scan_cards, sort_cards
from kaiju.cron import CronJob, scan_crons
from kaiju.errors import KaijuError
from kaiju.search import CANONICAL, HEAD_BYTES, MAX_FILE_BYTES
from kaiju.workspace import Workspace, find_workspace

FILTER_ALL = "all"
FILTER_OPEN = "open"
FILTER_CLOSED = "closed"
FILTER_EPIC = "epic"
FILTER_EPICS = "epics"
FILTER_BACKLOG = "backlog"
FILTER_CRONS = "crons"

TABLE_COLUMNS = ("card", "title", "status", "epic", "parent", "created_at", "closed_at")
TABLE_HEADINGS = {
    "card": "Card",
    "title": "Title",
    "status": "Status",
    "epic": "Epic",
    "parent": "Parent",
    "created_at": "Created",
    "closed_at": "Closed",
}
CRON_COLUMNS = ("card", "when", "title", "readable", "script")
CRON_HEADINGS = {
    "when": "When",
    "title": "Title",
    "readable": "Readable",
    "script": "Script",
    "card": "Card",
}


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    kind: str
    epic_code: str = ""
    children: tuple[NavItem, ...] = ()


@dataclass(frozen=True)
class FileNode:
    name: str
    relpath: str
    is_dir: bool
    children: tuple[FileNode, ...] = ()


@dataclass(frozen=True)
class Preview:
    text: str
    message: str


class Session:
    def __init__(self) -> None:
        self.workspace: Workspace | None = None
        self.error: str | None = None
        self.filter_kind: str = FILTER_ALL
        self.epic_code: str = ""
        self._cards: list[Card] = []
        self._crons: list[CronJob] = []

    def open(self, start: Path) -> bool:
        try:
            ws = find_workspace(start)
        except KaijuError as exc:
            self.workspace = None
            self._cards = []
            self._crons = []
            self.error = str(exc)
            self.filter_kind = FILTER_ALL
            self.epic_code = ""
            return False
        self.workspace = ws
        self._cards = sort_cards(scan_cards(ws))
        self._crons = scan_crons(ws)
        self.error = None
        self.filter_kind = FILTER_ALL
        self.epic_code = ""
        return True

    def refresh(self) -> None:
        if self.workspace is None:
            return
        self._cards = sort_cards(scan_cards(self.workspace))
        self._crons = scan_crons(self.workspace)
        if (
            self.filter_kind == FILTER_EPIC
            and self.epic_code
            and not any(c.code == self.epic_code and c.is_epic for c in self._cards)
        ):
            self.filter_kind = FILTER_ALL
            self.epic_code = ""

    def select_nav(self, kind: str, epic_code: str = "") -> None:
        self.filter_kind = kind
        self.epic_code = epic_code if kind == FILTER_EPIC else ""

    def cards(self) -> list[Card]:
        return list(self._cards)

    def epics(self) -> list[Card]:
        return [card for card in self._cards if card.is_epic]

    def filtered_cards(self) -> list[Card]:
        cards = self._cards
        kind = self.filter_kind
        if kind in (FILTER_BACKLOG, FILTER_CRONS):
            return []
        if kind == FILTER_OPEN:
            return [card for card in cards if not card.is_closed]
        if kind == FILTER_CLOSED:
            return [card for card in cards if card.is_closed]
        if kind == FILTER_EPIC:
            return [card for card in cards if card.epic == self.epic_code]
        if kind == FILTER_EPICS:
            return [card for card in cards if card.is_epic]
        return list(cards)

    def crons(self) -> list[CronJob]:
        return list(self._crons)

    def cron_by_key(self, key: str) -> CronJob | None:
        for job in self._crons:
            if job.key == key:
                return job
        return None

    def card_by_code(self, code: str) -> Card | None:
        for card in self._cards:
            if card.code == code:
                return card
        return None

    def nav_tree(self) -> NavItem | None:
        if self.workspace is None:
            return None
        epics = tuple(
            NavItem(
                key=f"epic:{card.code}",
                label=f"{card.code}  {card.title}",
                kind=FILTER_EPIC,
                epic_code=card.code,
            )
            for card in self.epics()
        )
        return NavItem(
            key="workspace",
            label=self.workspace.config.name,
            kind=FILTER_ALL,
            children=(
                NavItem(key="all", label="All", kind=FILTER_ALL),
                NavItem(key="open", label="Open", kind=FILTER_OPEN),
                NavItem(key="closed", label="Closed", kind=FILTER_CLOSED),
                NavItem(key="epics", label="Epics", kind=FILTER_EPICS, children=epics),
                NavItem(key="backlog", label="Backlog", kind=FILTER_BACKLOG),
                NavItem(key="crons", label="Crons", kind=FILTER_CRONS),
            ),
        )

    def backlog_path(self) -> Path | None:
        if self.workspace is None:
            return None
        return self.workspace.root / "BACKLOG.md"


def cron_values(job: CronJob) -> tuple[str, ...]:
    return (job.card, job.when, job.title, job.readable, job.script)


def table_values(card: Card) -> tuple[str, ...]:
    return (
        card.code,
        card.title,
        card.status,
        card.epic,
        card.parent,
        card.created_at,
        card.closed_at,
    )


def canonical_path(card: Card, name: str) -> Path:
    return card.path / name


def is_canonical(relpath: str) -> bool:
    return relpath in CANONICAL


def card_file_tree(card: Card) -> FileNode:
    return FileNode(
        name=card.code,
        relpath="",
        is_dir=True,
        children=list_file_tree(card.path),
    )


def list_file_tree(root: Path) -> tuple[FileNode, ...]:
    if not root.is_dir():
        return ()
    return _list_children(root, root)


def _list_children(root: Path, folder: Path) -> tuple[FileNode, ...]:
    try:
        entries = list(folder.iterdir())
    except OSError:
        return ()
    nodes: list[FileNode] = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_symlink() and entry.is_dir():
            continue
        try:
            rel = entry.relative_to(root).as_posix()
        except ValueError:
            continue
        if entry.is_dir():
            nodes.append(
                FileNode(
                    name=entry.name,
                    relpath=rel,
                    is_dir=True,
                    children=_list_children(root, entry),
                )
            )
        elif entry.is_file():
            nodes.append(FileNode(name=entry.name, relpath=rel, is_dir=False))
    nodes.sort(key=lambda node: (not node.is_dir, node.name.casefold()))
    return tuple(nodes)


def read_preview(path: Path) -> Preview:
    name = path.name
    try:
        is_file = path.is_file()
    except OSError:
        return Preview("", f"{name} not found")
    if not is_file:
        return Preview("", f"{name} not found")
    try:
        size = path.stat().st_size
    except OSError as exc:
        return Preview("", f"{name}: {exc}")
    if size > MAX_FILE_BYTES:
        return Preview("", f"{name}: skipped (larger than 1 MiB)")
    try:
        with path.open("rb") as handle:
            head = handle.read(HEAD_BYTES)
            if b"\0" in head:
                return Preview("", f"{name}: skipped (binary)")
            rest = handle.read()
    except OSError as exc:
        return Preview("", f"{name}: {exc}")
    text = (head + rest).decode("utf-8", errors="replace")
    return Preview(text, "")
