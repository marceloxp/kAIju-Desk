# kaiju

CLI for the kAIju convention: one workspace (`kaiju.toml`), one card per folder, three files with owners.

## Installation

At the repository root:

```bash
uv tool install --editable ./src
kaiju --version
```

## Usage

```bash
kaiju init --prefix MT [--name NAME] [--digits 4] [DIR]
kaiju guide
kaiju add "title" [--epic X | --as-epic] [--parent X] [--set field=value]
kaiju status CARD STATUS
kaiju close CARD [STATUS]
kaiju reopen CARD [STATUS]
kaiju search REGEX [--status S] [--epic X] [--open|--closed] [--cards] [--limit N] [--page P]
kaiju search "" --open
```

`CARD` accepts the full code (`MT-0003`) or just the number (`3`). Discover the workspace with `kaiju guide` before making changes.

Tests: `cd src && uv run pytest`.

Lint and format: `uv run ruff check .` and `uv run ruff format .`.
