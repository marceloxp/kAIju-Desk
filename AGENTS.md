# AGENTS.md — kAIju-Desk

Read this first. Then `README.md` for the public contract, `src/README.md` for install. This file and the code are the source of truth for working on the tool.

## What this is

A work contract between human and coding agent that **lives in the folder**. No DB, server, or account in v0.

`kaiju` holds the convention so neither side has to remember it: a **workspace** is a directory with `kaiju.toml`; a **card** is an immediate child folder with three files; **state** is the front-matter of the card `README.md`. Copy the folder, you copied the task.

Successor of `vm`, without Jira. Name: Jira ← *Gojira*; this keeps the monster and puts **AI** in the middle.

## Repo map

```text
AGENTS.md  README.md  images/
examples/     sample workspace (`kaiju gui examples`)
.resources/   source art (gitignored; not product docs)
.sandbox/     manual tryouts (gitignored; tests must not use it)
.cursor/      local Cursor rules (gitignored)
src/          the whole product (pyproject.toml, kaiju/, tests/)
```

Install from repo root: `uv tool install --editable ./src`. Run `kaiju` or `python -m kaiju`. Python >= 3.10; runtime = stdlib + `tomli`. CLI is `argparse`. No click/typer/rich/PyYAML.

Do not invent commands, flags, fields, or dependencies. After v0, root docs are fair game when asked.

## Principles (do not violate)

1. **Folder is truth.** Card state is front-matter. No cache/DB in v0.
2. **Explained, not imposed.** Scaffold + `guide`. Close does not require `DELIVERY.md`. Refuse only at `add`: duplicate title, or missing epic/parent.
3. **Free where it can be.** Statuses and extra fields live in `kaiju.toml`; the tool does not interpret meaning.
4. **Context economy.** No “list everything”. Search pages (default 10).
5. **Out of pattern = invisible.** Non-cards are skipped, not fixed. No nested cards; relations are `epic:` / `parent:`.

## Convention

Typical *user* workspace (not this repo):

```text
.ai/maintenance/
├── kaiju.toml
├── README.md           workspace-specific rules (human writes; kaiju only reads)
├── BACKLOG.md          findings not yet cards (no CLI)
└── MT-0001/
    ├── README.md       request + record (front-matter)
    ├── MEMORY.md       trail: decisions, gotchas, dead ends
    ├── DELIVERY.md     what was done, result, left out
    └── sql/explain.sql free attachments; never leave the card folder
```

Do not duplicate across the three files. Delivery ≠ README; trail ≠ DELIVERY.

**Card:** child dir whose `README.md` front-matter `card:` equals the folder name. **Closed:** `closed_at` filled (a date), regardless of status name. **Epic:** `epic` equals own code (`--as-epic`); others use `--epic`. No nested epics. **Parent:** independent decomposition.

**Backlog:** never parsed, only searched. Suggested `## Open` / `## Dropped` with `###` findings. Mid-card discoveries go here; the current card does not grow. Become a card (`kaiju add`, cite `## Origin`) or move to Dropped with a reason.

**Statuses:** `[status]` names; `[on]` maps `add`/`close`/`reopen` to a status (CLI STATUS on close/reopen still wins). Template: `open`, `in-progress`, `done`, `cancelled`. **Core fields:** `card`, `title`, `status`, `created_at`, `closed_at`, `epic`, `parent`. Extras from `[additional_fields]` (template: `category`, `branch`, `agent_resume`).

## CLI (v0)

```text
kaiju init --prefix MT [--name NAME] [--digits 4] [DIR]
kaiju guide
kaiju add "title" [--epic X | --as-epic] [--parent X] [--set field=value]
kaiju status CARD STATUS
kaiju close CARD [STATUS]
kaiju reopen CARD [STATUS]
kaiju search REGEX [--status S] [--epic X] [--open|--closed] [--cards]
                 [--case-sensitive] [--limit N] [--page P]
kaiju search "" --open
kaiju gui [DIR]
```

`-C DIR` before the subcommand (like git). `CARD` is `MT-0003` or `3`. Discover by walking up to `kaiju.toml`.

- `init` refuses an existing workspace or a dir inside one. Writes `kaiju.toml` + `BACKLOG.md` (no overwrite of backlog; no workspace README). Suggests one line for the host repo’s `CLAUDE.md`/`AGENTS.md`.
- `guide` is the contract for the *using* agent (plus workspace README if present). Run it before changing cards.
- `add` = max `PREFIX-NNNN` folder + 1 (prefix-matching folders count even if not cards). Duplicate titles: ignore case, accents, repeated whitespace; includes closed cards. Status from `[on].add`.
- `status`/`close`/`reopen` patch front-matter only. Never touch MEMORY, DELIVERY, or README body. `close` sets `closed_at` to today and, without STATUS, `[on].close`; a second close keeps the original date and does not reapply `[on].close`. `reopen` with no STATUS → `[on].reopen`.
- `search` over the three files, text attachments, and (unless a card filter is on) BACKLOG + workspace README. Skip >1 MiB, binaries (NUL in first 8 KiB), hidden names, directory symlinks. Empty regex + filters = listing.
- `gui` opens a local Tk viewer (read-only). Discovers the workspace like other commands; without one, the window opens empty. Distinct from planned `serve`. Tkinter is imported only on this path. On Linux, if the current interpreter's Tk has no Xft (typical of uv-managed CPython), the GUI re-execs a system Python so fonts anti-alias.

Exit: `0` success (including empty search), `1` `KaijuError`, `2` argparse. Predicted failures: `error: …` on stderr, no traceback.

## Code

Entry: `kaiju.cli:main`. Version in `kaiju/__init__.py`.

**Layering:** `workspace`, `frontmatter`, `cards`, `search`, `guide` never print and never `sys.exit`. Return data or raise `KaijuError`. Only `cli.py` prints.

| Module                      | Owns                                                                        |
| --------------------------- | --------------------------------------------------------------------------- |
| `workspace.py`              | Config (incl. `[on]`), discovery, init, `today()`, `atomic_write`  |
| `frontmatter.py`            | parse (`key: value`, skip blank/`#`, first key wins); `set_fields` in place |
| `cards.py`                  | scan, numbering, add/status/close/reopen                                    |
| `search.py`                 | filters, regex hits, snippets, `--cards`                                    |
| `guide.py` / `templates.py` | contract text and scaffolds                                                 |
| `gui/`                      | Tk viewer (read-only); tkinter imported only when `kaiju gui` runs          |

`today()` honors `KAIJU_TODAY` (`YYYY-MM-DD`). Writes are UTF-8, `\n`, trailing newline, temp + `os.replace` in the same dir. `kaiju.toml` is never rewritten after init; unknown top-level keys ignored; table order preserved.

## How to work here

```bash
cd src && uv run pytest && uv run ruff check . && uv run ruff format .
```

Tests use tmp dirs, not `.sandbox/`. The sample workspace in `examples/` is versioned for humans; a small test only checks that it still opens. CLI, templates, and `guide` are English. Ruff line length 100; `guide.py` ignores E501.

Do not: add runtime deps; require DELIVERY to close; parse/rewrite backlog structure; auto-fix non-cards; follow dir symlinks; print from core. Failed `add` must leave no orphan folder.

## Later (do not start unless asked)

The Tk viewer is `kaiju gui`. `kaiju serve`: local browser viewer on `127.0.0.1`, no auth, disposable SQLite cache of front-matters. Filesystem stays truth. Still out of scope: Jira, FTS, sprints, web edits, public bind, backlog commands, validation that blocks work.
