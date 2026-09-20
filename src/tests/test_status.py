from tests.helpers import add, init_ws, run


def _bytes(path):
    return path.read_bytes()


def test_status_unknown_lists_valid(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    code, _, err = run(capsys, ["-C", str(tmp_path), "status", "1", "nope"])
    assert code == 1
    assert 'status "nope" does not exist' in err
    assert "open" in err
    assert "in-progress" in err


def test_close_writes_today_and_keeps_original_on_second(capsys, tmp_path, today, monkeypatch):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    code, out, err = run(capsys, ["-C", str(tmp_path), "close", "1", "done"])
    assert code == 0, err
    assert "open → done" in out
    assert "closed_at: 2026-09-19" in out
    readme = (tmp_path / "MT-0001" / "README.md").read_text(encoding="utf-8")
    assert "closed_at: 2026-09-19\n" in readme
    assert "status: done\n" in readme
    monkeypatch.setenv("KAIJU_TODAY", "2026-09-20")
    code, out, err = run(capsys, ["-C", str(tmp_path), "close", "1"])
    assert code == 0, err
    assert "already closed" in out
    assert "closed_at: 2026-09-19" in out
    readme = (tmp_path / "MT-0001" / "README.md").read_text(encoding="utf-8")
    assert "closed_at: 2026-09-19\n" in readme
    assert "2026-09-20" not in readme


def test_close_without_delivery(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Sem entrega")
    (tmp_path / "MT-0001" / "DELIVERY.md").unlink()
    code, out, err = run(capsys, ["-C", str(tmp_path), "close", "1"])
    assert code == 0, err
    assert "closed_at: 2026-09-19" in out
    readme = (tmp_path / "MT-0001" / "README.md").read_text(encoding="utf-8")
    assert "closed_at: 2026-09-19\n" in readme
    assert "status: done\n" in readme
    assert not (tmp_path / "MT-0001" / "DELIVERY.md").exists()


def test_reopen_clears_closed_at(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    run(capsys, ["-C", str(tmp_path), "close", "1", "done"])
    code, out, err = run(capsys, ["-C", str(tmp_path), "reopen", "1", "open"])
    assert code == 0, err
    assert "done → open" in out
    assert "reopened" in out
    text = (tmp_path / "MT-0001" / "README.md").read_text(encoding="utf-8")
    assert "closed_at:\n" in text
    before = (tmp_path / "MT-0001" / "README.md").read_bytes()
    code, out, err = run(capsys, ["-C", str(tmp_path), "reopen", "1"])
    assert code == 0, err
    assert "already open" in out
    assert (tmp_path / "MT-0001" / "README.md").read_bytes() == before


def test_close_without_status_uses_on_close(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    code, out, err = run(capsys, ["-C", str(tmp_path), "close", "1"])
    assert code == 0, err
    assert "open → done" in out
    readme = (tmp_path / "MT-0001" / "README.md").read_text(encoding="utf-8")
    assert "status: done\n" in readme
    assert "closed_at: 2026-09-19\n" in readme


def test_second_close_without_status_does_not_reapply_on_close(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    run(capsys, ["-C", str(tmp_path), "close", "1", "cancelled"])
    code, out, err = run(capsys, ["-C", str(tmp_path), "close", "1"])
    assert code == 0, err
    assert "already closed" in out
    readme = (tmp_path / "MT-0001" / "README.md").read_text(encoding="utf-8")
    assert "status: cancelled\n" in readme


def test_on_mapping_is_used_not_first_status(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    toml = tmp_path / "kaiju.toml"
    text = toml.read_text(encoding="utf-8")
    text = text.replace('add    = "open"', 'add    = "in-progress"')
    text = text.replace('close  = "done"', 'close  = "cancelled"')
    text = text.replace('reopen = "open"', 'reopen = "in-progress"')
    toml.write_text(text, encoding="utf-8")
    add(capsys, tmp_path, "Custom")
    readme = tmp_path / "MT-0001" / "README.md"
    assert "status: in-progress\n" in readme.read_text(encoding="utf-8")
    code, out, err = run(capsys, ["-C", str(tmp_path), "close", "1"])
    assert code == 0, err
    assert "in-progress → cancelled" in out
    assert "status: cancelled\n" in readme.read_text(encoding="utf-8")
    code, out, err = run(capsys, ["-C", str(tmp_path), "reopen", "1"])
    assert code == 0, err
    assert "cancelled → in-progress" in out
    text = readme.read_text(encoding="utf-8")
    assert "status: in-progress\n" in text
    assert "closed_at:\n" in text


def test_reopen_without_status_uses_on_reopen(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    run(capsys, ["-C", str(tmp_path), "close", "1", "done"])
    code, out, err = run(capsys, ["-C", str(tmp_path), "reopen", "1"])
    assert code == 0, err
    assert "done → open  reopened" in out
    text = (tmp_path / "MT-0001" / "README.md").read_text(encoding="utf-8")
    assert "status: open\n" in text
    assert "closed_at:\n" in text


def test_status_close_reopen_do_not_touch_memory_delivery_or_body(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Immutable")
    folder = tmp_path / "MT-0001"
    (folder / "MEMORY.md").write_text("original memory\n", encoding="utf-8")
    (folder / "DELIVERY.md").write_text("original delivery\n", encoding="utf-8")
    readme = folder / "README.md"
    original = readme.read_text(encoding="utf-8")
    body = original.split("---", 2)[2]
    mem = _bytes(folder / "MEMORY.md")
    deliv = _bytes(folder / "DELIVERY.md")
    run(capsys, ["-C", str(tmp_path), "status", "1", "in-progress"])
    run(capsys, ["-C", str(tmp_path), "close", "1", "done"])
    run(capsys, ["-C", str(tmp_path), "reopen", "1", "open"])
    assert _bytes(folder / "MEMORY.md") == mem
    assert _bytes(folder / "DELIVERY.md") == deliv
    new_body = readme.read_text(encoding="utf-8").split("---", 2)[2]
    assert new_body == body
