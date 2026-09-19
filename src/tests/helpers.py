from __future__ import annotations

from pathlib import Path

from kaiju.cli import main


def run(capsys, argv: list[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def init_ws(
    capsys,
    tmp_path: Path,
    *,
    prefix: str = "MT",
    name: str = "maintenance",
    digits: int = 4,
) -> Path:
    argv = [
        "-C",
        str(tmp_path),
        "init",
        "--prefix",
        prefix,
        "--name",
        name,
        "--digits",
        str(digits),
    ]
    code, out, err = run(capsys, argv)
    assert code == 0, err
    assert "Workspace" in out
    return tmp_path


def add(
    capsys,
    ws: Path,
    title: str,
    extra: list[str] | None = None,
) -> tuple[int, str, str]:
    argv = ["-C", str(ws), "add", title]
    if extra:
        argv.extend(extra)
    return run(capsys, argv)
