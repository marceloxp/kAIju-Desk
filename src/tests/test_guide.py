from tests.helpers import add, init_ws, run


def test_guide_contents(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Open")
    add(capsys, tmp_path, "Will close")
    run(capsys, ["-C", str(tmp_path), "close", "2"])
    (tmp_path / "README.md").write_text(
        "# specific rules\nOnly in this workspace.\n",
        encoding="utf-8",
    )
    code, out, err = run(capsys, ["-C", str(tmp_path), "guide"])
    assert code == 0, err
    assert 'workspace "maintenance"' in out
    assert "Prefix: MT" in out
    assert "next card: MT-0003" in out
    assert "1 open" in out
    assert "1 closed" in out
    assert "`open`:" in out
    assert "`in-progress`:" in out
    assert "`add` → `open`" in out
    assert "`close` → `done`" in out
    assert "`reopen` → `open`" in out
    assert "`category`:" in out
    assert "free classification of the card" in out
    assert "## Workspace rules (README.md)" in out
    assert "Only in this workspace." in out
    assert 'kaiju search "" --open' in out
    assert "## Cron (`cron/`)" in out
    assert "TELEGRAM_BOT_TOKEN" in out
    assert "There is no command for them." in out
    assert "`readable` is free text." in out
    assert "`close`/`reopen` without STATUS use `[on]`" in out


def test_guide_omits_workspace_readme_section_when_absent(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    code, out, err = run(capsys, ["-C", str(tmp_path), "guide"])
    assert code == 0, err
    assert "## Workspace rules" not in out


def test_no_command_prints_help(capsys, today):
    code, out, err = run(capsys, [])
    assert code == 0
    assert "usage:" in out.lower() or "kaiju" in out
    assert err == ""


def test_version(capsys, today):
    code, out, err = run(capsys, ["--version"])
    assert code == 0
    assert out.strip() == "0.1.0"
