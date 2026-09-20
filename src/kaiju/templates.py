from __future__ import annotations


def toml_basic_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def kaiju_toml(*, name: str, prefix: str, digits: int) -> str:
    return (
        "# kAIju Workspace — run `kaiju guide` to see the contract.\n"
        f"name   = {toml_basic_string(name)}\n"
        f"prefix = {toml_basic_string(prefix)}\n"
        f"digits = {digits}\n"
        "\n"
        "# Free status: name = description.\n"
        '# "Closed" means having closed_at filled (kaiju close), whatever the status.\n'
        "[status]\n"
        'open        = "request registered, work not yet started"\n'
        'in-progress = "work in progress; MEMORY.md being written"\n'
        'done        = "delivered, with human approval"\n'
        'cancelled   = "will not be done; reason in DELIVERY.md"\n'
        "\n"
        "# Event → status when the command has no STATUS argument. Edit freely.\n"
        "[on]\n"
        'add    = "open"\n'
        'close  = "done"\n'
        'reopen = "open"\n'
        "\n"
        "# Extra fields for card front-matter: name = description.\n"
        "[additional_fields]\n"
        'category     = "free classification of the card (e.g.: database, code, infra)"\n'
        'branch       = "git branch where the work happens"\n'
        'agent_resume = "command to resume the agent session (e.g.: claude --resume <id>)"\n'
    )


def backlog_md() -> str:
    return (
        "# Backlog\n"
        "\n"
        "> Findings that are not cards yet. Rules: `kaiju guide`.\n"
        "\n"
        "## Open\n"
        "\n"
        "## Dropped\n"
    )


def _field_line(key: str, value: str) -> str:
    if value == "":
        return f"{key}:"
    return f"{key}: {value}"


def card_readme(
    *,
    code: str,
    title: str,
    status: str,
    created_at: str,
    epic: str,
    parent: str,
    extra: dict[str, str],
) -> str:
    lines = [
        "---",
        _field_line("card", code),
        _field_line("title", title),
        _field_line("status", status),
        _field_line("created_at", created_at),
        "closed_at:",
        _field_line("epic", epic),
        _field_line("parent", parent),
    ]
    for key, value in extra.items():
        lines.append(_field_line(key, value))
    lines.extend(
        [
            "---",
            "",
            f"# {code} — {title}",
            "",
            "## What we want",
            "",
            "## Why",
            "",
            "## Origin",
            "",
        ]
    )
    return "\n".join(lines)


def card_memory(*, code: str) -> str:
    return (
        f"# {code} — memory\n"
        "\n"
        "> Work trail: decisions, gotchas, where we stopped, paths that didn't work.\n"
    )


def card_delivery(*, code: str) -> str:
    return f"# {code} — delivery\n\n## What was done\n\n## Result\n\n## What was left out\n"
