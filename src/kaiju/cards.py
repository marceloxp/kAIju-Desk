from __future__ import annotations

import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from kaiju import frontmatter, templates
from kaiju.errors import KaijuError
from kaiju.workspace import (
    CORE_FIELDS,
    Workspace,
    atomic_write,
    today,
)

FOLDER_CODE_RE = re.compile(r"^([A-Z][A-Z0-9]*)-(\d+)$")
NUMERIC_RE = re.compile(r"^\d+$")


@dataclass(frozen=True)
class Card:
    code: str
    path: Path
    fields: dict[str, str]

    @property
    def title(self) -> str:
        return self.fields.get("title", "")

    @property
    def status(self) -> str:
        return self.fields.get("status", "")

    @property
    def created_at(self) -> str:
        return self.fields.get("created_at", "")

    @property
    def closed_at(self) -> str:
        return self.fields.get("closed_at", "")

    @property
    def epic(self) -> str:
        return self.fields.get("epic", "")

    @property
    def parent(self) -> str:
        return self.fields.get("parent", "")

    @property
    def is_closed(self) -> bool:
        return self.closed_at != ""

    @property
    def is_epic(self) -> bool:
        return self.epic == self.code

    @property
    def readme_path(self) -> Path:
        return self.path / "README.md"


def scan_cards(ws: Workspace) -> list[Card]:
    cards: list[Card] = []
    try:
        entries = list(ws.root.iterdir())
    except OSError:
        return cards
    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        card = _card_from_dir(entry)
        if card is not None:
            cards.append(card)
    return cards


def _card_from_dir(path: Path) -> Card | None:
    readme = path / "README.md"
    if not readme.is_file():
        return None
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fields = frontmatter.parse(text)
    if fields is None:
        return None
    code = fields.get("card", "")
    if code != path.name:
        return None
    return Card(code=code, path=path, fields=fields)


def format_code(prefix: str, number: int, digits: int) -> str:
    width = digits if number < 10**digits else len(str(number))
    return f"{prefix}-{number:0{width}d}"


def next_code(ws: Workspace) -> str:
    pattern = re.compile(rf"^{re.escape(ws.config.prefix)}-(\d+)$")
    highest = 0
    found = False
    try:
        entries = list(ws.root.iterdir())
    except OSError:
        entries = []
    for entry in entries:
        if not entry.is_dir():
            continue
        match = pattern.fullmatch(entry.name)
        if match:
            found = True
            highest = max(highest, int(match.group(1)))
    number = highest + 1 if found else 1
    return format_code(ws.config.prefix, number, ws.config.digits)


CODE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-(\d+)$")


def resolve_code(ws: Workspace, arg: str) -> str:
    arg = arg.strip()
    if arg == "":
        raise KaijuError("empty card code")
    if NUMERIC_RE.fullmatch(arg):
        return format_code(ws.config.prefix, int(arg), ws.config.digits)
    wanted = arg.casefold()
    for card in scan_cards(ws):
        if card.code.casefold() == wanted:
            return card.code
    match = CODE_RE.fullmatch(arg)
    if match and match.group(1).casefold() == ws.config.prefix.casefold():
        return format_code(ws.config.prefix, int(match.group(2)), ws.config.digits)
    return arg


def get_card(ws: Workspace, arg: str) -> Card:
    code = resolve_code(ws, arg)
    for card in scan_cards(ws):
        if card.code == code or card.code.casefold() == code.casefold():
            return card
    raise KaijuError(f"card {code} not found")


def normalize_title(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    folded = stripped.casefold()
    return " ".join(folded.split())


def add_card(
    ws: Workspace,
    title: str,
    epic: str | None = None,
    as_epic: bool = False,
    parent: str | None = None,
    extra: dict[str, str] | None = None,
) -> Card:
    title = title.strip()
    if title == "":
        raise KaijuError("empty title")
    if "\n" in title or "\r" in title:
        raise KaijuError("title cannot contain line break")

    extra = extra or {}
    known = ws.config.additional_fields
    unknown = [key for key in extra if key not in known]
    if unknown:
        listing = ", ".join(known) if known else "(none)"
        raise KaijuError(f'unknown field "{unknown[0]}" (fields: {listing})')
    for key in extra:
        if key in CORE_FIELDS:
            listing = ", ".join(known) if known else "(none)"
            raise KaijuError(f'unknown field "{key}" (fields: {listing})')
        if "\n" in extra[key] or "\r" in extra[key]:
            raise KaijuError("field value cannot contain line break")

    cards = scan_cards(ws)
    wanted = normalize_title(title)
    for card in cards:
        if normalize_title(card.title) == wanted:
            raise KaijuError(f'card with this title already exists: {card.code} "{card.title}"')

    epic_code = ""
    if epic is not None:
        try:
            target = get_card(ws, epic)
        except KaijuError:
            raise KaijuError(f"epic {resolve_code(ws, epic)} not found") from None
        if not target.is_epic:
            shown = target.epic if target.epic else "empty"
            raise KaijuError(f"{target.code} is not epic (epic: {shown})")
        epic_code = target.code

    parent_code = ""
    if parent is not None:
        try:
            target = get_card(ws, parent)
        except KaijuError:
            raise KaijuError(f"parent card {resolve_code(ws, parent)} not found") from None
        parent_code = target.code

    code = next_code(ws)
    if as_epic:
        epic_code = code

    ordered_extra = {key: extra.get(key, "") for key in known}
    # Everything that can fail is computed before the folder exists, so a
    # failed add never leaves an orphan folder that consumes the number.
    files = {
        "README.md": templates.card_readme(
            code=code,
            title=title,
            status=initial_status(ws),
            created_at=today(),
            epic=epic_code,
            parent=parent_code,
            extra=ordered_extra,
        ),
        "MEMORY.md": templates.card_memory(code=code),
        "DELIVERY.md": templates.card_delivery(code=code),
    }

    folder = ws.root / code
    try:
        folder.mkdir()
    except FileExistsError as exc:
        raise KaijuError(f"folder {folder} already exists") from exc
    try:
        for name, content in files.items():
            atomic_write(folder / name, content)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    card = _card_from_dir(folder)
    if card is None:
        raise KaijuError(f"failed to create card {code}")
    return card


def set_status(ws: Workspace, arg: str, status: str) -> tuple[Card, Card]:
    _require_status(ws, status)
    before = get_card(ws, arg)
    frontmatter.set_fields(before.readme_path, {"status": status})
    after = get_card(ws, before.code)
    return before, after


def close_card(ws: Workspace, arg: str, status: str | None = None) -> tuple[Card, Card]:
    before = get_card(ws, arg)
    updates: dict[str, str] = {}
    if status is not None:
        _require_status(ws, status)
        updates["status"] = status
    if before.closed_at == "":
        updates["closed_at"] = today()
    if updates:
        frontmatter.set_fields(before.readme_path, updates)
    after = get_card(ws, before.code)
    return before, after


def reopen_card(ws: Workspace, arg: str, status: str | None = None) -> tuple[Card, Card]:
    """Without STATUS, a closed card goes back to the initial status."""
    if status is not None:
        _require_status(ws, status)
    before = get_card(ws, arg)
    updates: dict[str, str] = {}
    if before.is_closed:
        updates["closed_at"] = ""
        updates["status"] = status if status is not None else initial_status(ws)
    elif status is not None:
        updates["status"] = status
    if updates:
        frontmatter.set_fields(before.readme_path, updates)
    after = get_card(ws, before.code)
    return before, after


def initial_status(ws: Workspace) -> str:
    return next(iter(ws.config.statuses))


def _require_status(ws: Workspace, status: str) -> None:
    if status not in ws.config.statuses:
        listing = ", ".join(ws.config.statuses)
        raise KaijuError(f'status "{status}" does not exist (status: {listing})')


def sort_cards(cards: list[Card]) -> list[Card]:
    return sorted(cards, key=_sort_key)


def _sort_key(card: Card) -> tuple[str, int]:
    match = FOLDER_CODE_RE.fullmatch(card.code)
    if match:
        return match.group(1), -int(match.group(2))
    return card.code, 0
