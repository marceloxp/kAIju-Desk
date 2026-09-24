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
    for name, desc in cfg.statuses.items():
        lines.append(f"- `{name}`: {desc}")
    lines.extend(
        [
            "",
            "Without a STATUS argument, `add`/`close`/`reopen` use `[on]`:",
            "",
            f"- `add` → `{cfg.on['add']}`",
            f"- `close` → `{cfg.on['close']}`",
            f"- `reopen` → `{cfg.on['reopen']}`",
            "",
            "Closing requires nothing. Close when the human gives approval; if there's no DELIVERY, let it be a conscious choice.",
            "",
            "## Backlog (`BACKLOG.md`)",
            "",
            "Findings that are not cards yet. The suggested shape is two sections, `## Open` and `## Dropped`, with one `###` heading per finding and the description below it:",
            "",
            "    ## Open",
            "",
            "    ### Short title of the finding",
            "",
            "    What it is and where it was seen, in a few lines.",
            "",
            "- A finding that shows up in the middle of a card goes to the backlog. The current card doesn't grow because of it.",
            "- Every finding has one of two destinations:",
            "  - **becomes a card**: `kaiju add`, remove the section from the backlog and cite the origin in the `## Origin` section of the card's `README.md`;",
            "  - **dropped**: move the section under `## Dropped` and add the reason in a few words.",
            "- The shape above is a suggestion: `kaiju` never reads the backlog, it only searches it. This workspace's `README.md` wins over it.",
            "- Edit `BACKLOG.md` directly; there's no command for it.",
            "",
            "## Cron (`cron/`)",
            "",
            "Scheduled jobs live in the folder. There is no command for them. The agent writes the files and installs or removes the crontab line. `kaiju gui` lists the jobs; it does not read the crontab.",
            "",
            "- Workspace jobs: `cron/` at the workspace root.",
            "- Card jobs: `CARD/cron/`.",
            "- Each job is one `*.md` plus the script beside it. The markdown front-matter is the record the GUI reads:",
            "",
            "    ---",
            "    when: 30 8 * * *",
            "    script: run.sh",
            "    title: Dev queue",
            "    readable: Every day at 08:30, send the dev queue size on Telegram",
            "    ---",
            "",
            "- `when` is a crontab schedule (five fields). A one-shot date uses the day and month fields (`30 8 25 9 *`).",
            "- `script` is the file name next to the markdown. The agent writes that file in whatever language the job needs (shell, PHP, `claude -p`, anything else).",
            "- `title` is the short name in the GUI list.",
            "- `readable` is free text. Write the intention in words a person understands without reading the schedule or the script. The GUI shows it; kaiju does not interpret it.",
            "- Credentials live in `.env` at the workspace root: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. `kaiju init` does not create `.env`. The name starts with a dot, so search skips it. Keep it out of git.",
            "- The script reads that `.env` from the workspace root. A Telegram send is a `curl` to `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage` with `chat_id` and `text`.",
            "- The crontab line runs the script by its absolute path. The agent adds the line, comments it, and deletes it. Comparing the folders with `crontab -l` answers which jobs are installed.",
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
            "`close`/`reopen` without STATUS use `[on]`; an explicit STATUS wins.",
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
