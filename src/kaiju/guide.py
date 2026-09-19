from __future__ import annotations

from kaiju.cards import next_code, scan_cards
from kaiju.workspace import Workspace


def render_guide(ws: Workspace) -> str:
    cards = scan_cards(ws)
    n_open = sum(1 for card in cards if not card.is_closed)
    n_closed = sum(1 for card in cards if card.is_closed)
    nxt = next_code(ws)
    cfg = ws.config
    root = ws.root.resolve()
    lines = [
        f'# kAIju — workspace "{cfg.name}"',
        "",
        f"Root: {root}",
        f"Prefix: {cfg.prefix} · next card: {nxt}",
        f"Cards: {n_open} open · {n_closed} closed",
        "",
        "## The contract",
        "",
        f"Each card is a folder `{cfg.prefix}-NNNN/` at the workspace root, with three files:",
        "",
        "| File | Role | Who writes |",
        "|---|---|---|",
        "| `README.md` | the request: what we want and why; front-matter with the record | human defines, AI registers |",
        "| `MEMORY.md` | work trail: decisions, gotchas, where we stopped, dead ends | AI, unprompted |",
        "| `DELIVERY.md` | what was done, result, what was left out | AI, with human approval |",
        "",
        "- Don't duplicate content between the three. Delivery doesn't go in `README.md`; trail doesn't go in `DELIVERY.md`.",
        "- Any other supporting file (sql, csv, screenshots, plans) goes **inside the card's folder**. It's free.",
        "- No card within a card.",
        "- Always create cards with `kaiju add`. Never create the folder by hand.",
        "- The card's state is the front-matter of `README.md`. Change status with `kaiju status`/`close`/`reopen`, not by hand.",
        "",
        "## Record (front-matter)",
        "",
        "- `card`, `title`, `created_at`: set at creation.",
        "- `status`: one of the statuses below.",
        "- `closed_at`: empty = open; date = closed (`kaiju close`).",
        '- `epic`: code of the epic this card belongs to. A card is **epic** when `epic` is its own code (`kaiju add "…" --as-epic`).',
        "- `parent`: code of the card that this one is a part of.",
    ]
    if cfg.additional_fields:
        lines.append("- Fields in this workspace (edit directly in front-matter):")
        for key, desc in cfg.additional_fields.items():
            lines.append(f"  - `{key}`: {desc}")
    lines.extend(
        [
            "",
            "## Status",
            "",
        ]
    )
    first = True
    for name, desc in cfg.statuses.items():
        suffix = " (initial)" if first else ""
        first = False
        lines.append(f"- `{name}`{suffix}: {desc}")
    lines.extend(
        [
            "",
            "Closing requires nothing. Close when the human gives approval; if there's no DELIVERY, let it be a conscious choice.",
            "",
            "## Backlog (`BACKLOG.md`)",
            "",
            "- Findings that won't be done now go to the backlog, one line: what it is, where it was seen, `(seen on YYYY-MM-DD)`.",
            "- Findings that appear in the middle of a card go to the backlog. The current card doesn't grow because of it.",
            "- Every finding has one of two destinations:",
            "  - **becomes a card**: `kaiju add`, remove the line from the backlog and cite the origin in the `## Origin` section of the card's `README.md`;",
            "  - **dropped**: move the line to `## Dropped`, with the reason in a few words.",
            "- Edit `BACKLOG.md` directly; there's no command for it.",
            "",
            "## Commands",
            "",
            'kaiju add "title" [--epic X | --as-epic] [--parent X] [--set field=value]',
            "kaiju status CARD STATUS",
            "kaiju close CARD [STATUS]",
            "kaiju reopen CARD [STATUS]",
            "kaiju search REGEX [--status S] [--epic X] [--open|--closed] [--cards] [--limit N] [--page P]",
            'kaiju search "" --open          # lists open cards (paginated)',
            "",
            f"CARD accepts `{cfg.prefix}-0003` or just `3`. Use `search` to find; don't try to list everything.",
            'Regex starting with `-` goes after `--`: `kaiju search -- "-x"`.',
            "`reopen` without STATUS returns the card to the initial status.",
        ]
    )
    readme = ws.root / "README.md"
    if readme.is_file():
        content = readme.read_text(encoding="utf-8")
        lines.extend(
            [
                "",
                "## Workspace rules (README.md)",
                "",
                content.rstrip("\r\n"),
            ]
        )
    return "\n".join(lines) + "\n"
