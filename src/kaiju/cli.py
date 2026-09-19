from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kaiju import __version__
from kaiju.cards import (
    Card,
    add_card,
    close_card,
    reopen_card,
    set_status,
)
from kaiju.errors import KaijuError
from kaiju.guide import render_guide
from kaiju.search import Hit, aggregate_hits, search
from kaiju.workspace import find_git_root, find_workspace, init_workspace


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    try:
        return _dispatch(parser, args)
    except KaijuError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaiju",
        description="Work contract between human and AI living in the folder.",
    )
    parser.add_argument(
        "-C",
        dest="start_dir",
        metavar="DIR",
        help="starting directory (like in git)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
    )
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="creates a kAIju workspace in this directory")
    p_init.add_argument("--prefix", required=True, help="card prefix (e.g.: MT)")
    p_init.add_argument("--name", default=None, help="workspace name")
    p_init.add_argument(
        "--digits",
        type=int,
        default=4,
        help="digits in numbering (default 4)",
    )
    p_init.add_argument(
        "dir",
        nargs="?",
        default=None,
        help="workspace directory (default: current directory)",
    )

    sub.add_parser("guide", help="prints this workspace's contract")

    p_add = sub.add_parser("add", help="creates a card")
    p_add.add_argument("title", help="card title")
    epic_group = p_add.add_mutually_exclusive_group()
    epic_group.add_argument("--epic", metavar="X", help="code of existing epic")
    epic_group.add_argument(
        "--as-epic",
        action="store_true",
        help="creates the card as epic",
    )
    p_add.add_argument("--parent", metavar="X", help="code of parent card")
    p_add.add_argument(
        "--set",
        action="append",
        default=[],
        dest="sets",
        metavar="FIELD=VALUE",
        help="fills an additional field",
    )

    p_status = sub.add_parser("status", help="changes a card's status")
    p_status.add_argument("card")
    p_status.add_argument("status")

    p_close = sub.add_parser("close", help="closes a card (writes closed_at)")
    p_close.add_argument("card")
    p_close.add_argument("status", nargs="?", default=None)

    p_reopen = sub.add_parser("reopen", help="reopens a card (clears closed_at)")
    p_reopen.add_argument("card")
    p_reopen.add_argument("status", nargs="?", default=None)

    p_search = sub.add_parser("search", help="searches or lists cards")
    p_search.add_argument("regex", help='regex; use "" to list')
    p_search.add_argument("--status", metavar="S", help="filters by status")
    p_search.add_argument("--epic", metavar="X", help="filters by epic")
    open_group = p_search.add_mutually_exclusive_group()
    open_group.add_argument("--open", action="store_true", help="open cards only")
    open_group.add_argument("--closed", action="store_true", help="closed cards only")
    p_search.add_argument(
        "--cards",
        action="store_true",
        dest="cards_only",
        help="aggregates occurrences by card",
    )
    p_search.add_argument(
        "--case-sensitive",
        action="store_true",
        help="respects case difference in regex",
    )
    p_search.add_argument("--limit", type=int, default=10, metavar="N")
    p_search.add_argument("--page", type=int, default=1, metavar="P")

    return parser


def _dispatch(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if not args.command:
        parser.print_help()
        return 0
    start = _start_dir(args)
    if args.command == "init":
        return cmd_init(args, start)
    ws = find_workspace(start)
    if args.command == "guide":
        sys.stdout.write(render_guide(ws))
        return 0
    if args.command == "add":
        return cmd_add(args, ws)
    if args.command == "status":
        return cmd_status(args, ws)
    if args.command == "close":
        return cmd_close(args, ws)
    if args.command == "reopen":
        return cmd_reopen(args, ws)
    if args.command == "search":
        return cmd_search(args, ws)
    parser.print_help()
    return 0


def _start_dir(args: argparse.Namespace) -> Path:
    if args.start_dir:
        return Path(args.start_dir)
    return Path.cwd()


def cmd_init(args: argparse.Namespace, start: Path) -> int:
    start = start if start.is_absolute() else Path.cwd() / start
    if args.dir:
        target = Path(args.dir)
        if not target.is_absolute():
            target = start / target
    else:
        target = start
    ws = init_workspace(target, args.prefix, args.name, args.digits)
    root = ws.root.resolve()
    print(f'Workspace "{ws.config.name}" created at {root} (prefix {ws.config.prefix}).')
    print()
    print("Suggestion for the repository's CLAUDE.md / AGENTS.md:")
    print(
        f"  `{_suggest_path(root)}` is a kAIju workspace; "
        "run `kaiju guide` in this folder before making changes."
    )
    return 0


def _suggest_path(root: Path) -> str:
    git_root = find_git_root(root)
    if git_root is None:
        return str(root)
    try:
        return root.relative_to(git_root).as_posix()
    except ValueError:
        return str(root)


def cmd_add(args: argparse.Namespace, ws) -> int:
    extra: dict[str, str] = {}
    for item in args.sets:
        if "=" not in item:
            raise KaijuError("--set expects FIELD=VALUE")
        key, _, value = item.partition("=")
        if key == "":
            raise KaijuError("--set expects FIELD=VALUE")
        extra[key] = value
    card = add_card(
        ws,
        args.title,
        epic=args.epic,
        as_epic=args.as_epic,
        parent=args.parent,
        extra=extra,
    )
    print(f"{card.code}  created  {_rel_dir(card.path)}")
    return 0


def _rel_dir(path: Path) -> str:
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(Path.cwd().resolve())
        text = rel.as_posix()
    except ValueError:
        text = resolved.as_posix()
    if not text.endswith("/"):
        text += "/"
    return text


def cmd_status(args: argparse.Namespace, ws) -> int:
    before, after = set_status(ws, args.card, args.status)
    print(f"{after.code}  {before.status} → {after.status}")
    return 0


def cmd_close(args: argparse.Namespace, ws) -> int:
    before, after = close_card(ws, args.card, args.status)
    if before.status != after.status:
        line = f"{after.code}  {before.status} → {after.status}  closed_at: {after.closed_at}"
    else:
        line = f"{after.code}  {after.status}  closed_at: {after.closed_at}"
    if before.is_closed:
        line += "  (already closed)"
    print(line)
    return 0


def cmd_reopen(args: argparse.Namespace, ws) -> int:
    before, after = reopen_card(ws, args.card, args.status)
    if before.is_closed:
        if before.status != after.status:
            print(f"{after.code}  {before.status} → {after.status}  reopened")
        else:
            print(f"{after.code}  {after.status}  reopened")
    else:
        print(f"{after.code}  {after.status}  (already open)")
    return 0


def cmd_search(args: argparse.Namespace, ws) -> int:
    if args.limit < 1:
        raise KaijuError("--limit must be >= 1")
    if args.page < 1:
        raise KaijuError("--page must be >= 1")
    open_: bool | None
    if args.open:
        open_ = True
    elif args.closed:
        open_ = False
    else:
        open_ = None

    result = search(
        ws,
        args.regex,
        status=args.status,
        epic=args.epic,
        open_=open_,
        cards_only=args.cards_only,
        case_sensitive=args.case_sensitive,
    )

    if args.regex == "":
        rows = [_list_row(card) for card in result]  # type: ignore[arg-type]
    elif args.cards_only:
        rows = [
            _cards_row(hit, count)
            for hit, count in aggregate_hits(result)  # type: ignore[arg-type]
        ]
    else:
        rows = [_hit_row(hit) for hit in result]  # type: ignore[arg-type]

    return _print_page(rows, limit=args.limit, page=args.page)


def _list_row(card: Card) -> list[str]:
    note = _list_note(card)
    cells = [card.code, card.status, card.created_at, card.title]
    if note:
        cells.append(note)
    return cells


def _list_note(card: Card) -> str:
    extras: list[str] = []
    if card.is_epic:
        extras.append("epic")
    elif card.epic:
        extras.append(f"epic {card.epic}")
    if card.parent:
        extras.append(f"parent {card.parent}")
    bits: list[str] = []
    if extras:
        bits.append(f"({', '.join(extras)})")
    if card.is_closed:
        bits.append(f"[closed {card.closed_at}]")
    return " ".join(bits)


def _hit_row(hit: Hit) -> list[str]:
    return [hit.label, hit.status, f"{hit.relpath}:{hit.line_no}", hit.snippet]


def _cards_row(hit: Hit, count: int) -> list[str]:
    word = "occurrence" if count == 1 else "occurrences"
    cells = [hit.label, hit.status, f"{count} {word}"]
    if hit.title:
        cells.append(hit.title)
    return cells


def _print_page(rows: list[list[str]], *, limit: int, page: int) -> int:
    total = len(rows)
    if total == 0:
        print("no results")
        return 0
    n_pages = (total + limit - 1) // limit
    start = (page - 1) * limit
    if start >= total:
        print(f"no results on this page (total: {total})")
        return 0
    chunk = rows[start : start + limit]
    for line in _align(chunk):
        print(line)
    if n_pages > 1:
        end = min(start + limit, total)
        first = start + 1
        if page >= n_pages:
            print(f"-- {first}-{end} of {total} --")
        else:
            print(f"-- {first}-{end} of {total} · next: --page {page + 1} --")
    return 0


def _align(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    col_widths = [max((len(row[i]) for row in padded), default=0) for i in range(width)]
    lines: list[str] = []
    for row in padded:
        parts = []
        for index, cell in enumerate(row):
            if index == width - 1:
                parts.append(cell)
            else:
                parts.append(cell.ljust(col_widths[index]))
        lines.append("  ".join(parts).rstrip())
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
