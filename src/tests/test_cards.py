from tests.helpers import add, init_ws, run


def test_non_card_when_code_differs_or_missing_readme(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Real")
    fake = tmp_path / "MT-0099"
    fake.mkdir()
    (fake / "README.md").write_text(
        "---\ncard: MT-0001\ntitle: fake\nstatus: open\ncreated_at: 2026-09-19\n"
        "closed_at:\nepic:\nparent:\n---\n\n# x\n",
        encoding="utf-8",
    )
    empty = tmp_path / "MT-0100"
    empty.mkdir()
    hidden = tmp_path / ".oculta"
    hidden.mkdir()
    (hidden / "README.md").write_text(
        "---\ncard: .oculta\ntitle: no\nstatus: open\ncreated_at: 2026-09-19\n"
        "closed_at:\nepic:\nparent:\n---\n\n",
        encoding="utf-8",
    )
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", ""])
    assert code == 0, err
    assert "MT-0001" in out
    assert "MT-0099" not in out
    assert "MT-0100" not in out
    assert ".oculta" not in out


def test_foreign_prefix_is_card_but_skips_numbering(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    sp = tmp_path / "SP-0000"
    sp.mkdir()
    (sp / "README.md").write_text(
        "---\ncard: SP-0000\ntitle: Foreign\nstatus: open\n"
        "created_at: 2026-09-19\nclosed_at:\nepic:\nparent:\n---\n\n# x\n",
        encoding="utf-8",
    )
    code, out, err = add(capsys, tmp_path, "Native")
    assert code == 0, err
    assert "MT-0001" in out
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", ""])
    assert "SP-0000" in out
    assert "MT-0001" in out


def test_numbering_empty_invalid_folder_and_digits(capsys, tmp_path, tmp_path_factory, today):
    init_ws(capsys, tmp_path, digits=4)
    code, out, err = add(capsys, tmp_path, "First")
    assert code == 0, err
    assert "MT-0001" in out
    (tmp_path / "MT-0007").mkdir()
    code, out, err = add(capsys, tmp_path, "After invalid folder")
    assert code == 0, err
    assert "MT-0008" in out

    other = tmp_path_factory.mktemp("ws2")
    init_ws(capsys, other, prefix="AB", name="ab", digits=2)
    code, out, err = add(capsys, other, "Two digits")
    assert code == 0, err
    assert "AB-01" in out


def test_add_creates_three_files_and_frontmatter_order(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    code, out, err = add(
        capsys, tmp_path, "Indices in created_at", extra=["--set", "category=database"]
    )
    assert code == 0, err
    folder = tmp_path / "MT-0001"
    assert (folder / "README.md").is_file()
    assert (folder / "MEMORY.md").is_file()
    assert (folder / "DELIVERY.md").is_file()
    readme = (folder / "README.md").read_text(encoding="utf-8")
    expected_head = (
        "---\n"
        "card: MT-0001\n"
        "title: Indices in created_at\n"
        "status: open\n"
        "created_at: 2026-09-19\n"
        "closed_at:\n"
        "epic:\n"
        "parent:\n"
        "category: database\n"
        "branch:\n"
        "agent_resume:\n"
        "---\n"
    )
    assert readme.startswith(expected_head)
    assert "# MT-0001 — Indices in created_at\n" in readme
    memory = (folder / "MEMORY.md").read_text(encoding="utf-8")
    assert memory.startswith("# MT-0001 — memory\n")
    delivery = (folder / "DELIVERY.md").read_text(encoding="utf-8")
    assert delivery.startswith("# MT-0001 — delivery\n")
    assert readme.endswith("\n")
    assert "created" in out


def test_add_duplicate_title_case_accent_spaces_and_closed(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    assert add(capsys, tmp_path, "Index  in Created_At")[0] == 0
    code, _, err = add(capsys, tmp_path, "index in created_at")
    assert code == 1
    assert "card with this title already exists: MT-0001" in err
    run(capsys, ["-C", str(tmp_path), "close", "1"])
    code, _, err = add(capsys, tmp_path, "index in created_at")
    assert code == 1
    assert "MT-0001" in err


def test_add_epic_and_parent_rules(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    assert add(capsys, tmp_path, "Common")[0] == 0
    code, out, err = add(capsys, tmp_path, "Big epic", extra=["--as-epic"])
    assert code == 0, err
    epic_fm = (tmp_path / "MT-0002" / "README.md").read_text(encoding="utf-8")
    assert "epic: MT-0002\n" in epic_fm
    code, _, err = add(capsys, tmp_path, "Child", extra=["--epic", "2"])
    assert code == 0, err
    assert "epic: MT-0002\n" in (tmp_path / "MT-0003" / "README.md").read_text(encoding="utf-8")
    code, _, err = add(capsys, tmp_path, "Grandchild", extra=["--epic", "MT-0002", "--parent", "3"])
    assert code == 0, err
    text = (tmp_path / "MT-0004" / "README.md").read_text(encoding="utf-8")
    assert "epic: MT-0002\n" in text
    assert "parent: MT-0003\n" in text
    code, _, err = add(capsys, tmp_path, "Not epic", extra=["--epic", "1"])
    assert code == 1
    assert "is not epic" in err
    code, _, err = add(capsys, tmp_path, "Ghost epic", extra=["--epic", "99"])
    assert code == 1
    assert "epic MT-0099 not found" in err
    code, _, err = add(capsys, tmp_path, "Ghost parent", extra=["--parent", "99"])
    assert code == 1
    assert "parent card MT-0099 not found" in err
    code, _, err = add(capsys, tmp_path, "Conflict", extra=["--epic", "2", "--as-epic"])
    assert code == 2


def test_add_set_known_and_unknown_field(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    code, _, err = add(capsys, tmp_path, "With field", extra=["--set", "category=database"])
    assert code == 0, err
    assert "category: database\n" in (tmp_path / "MT-0001" / "README.md").read_text(
        encoding="utf-8"
    )
    code, _, err = add(capsys, tmp_path, "Bad field", extra=["--set", "foo=bar"])
    assert code == 1
    assert 'unknown field "foo"' in err
    assert "category" in err


def test_code_resolution(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    assert add(capsys, tmp_path, "One")[0] == 0
    assert add(capsys, tmp_path, "Two")[0] == 0
    assert add(capsys, tmp_path, "Three")[0] == 0
    for arg in ("3", "0003", "mt-0003", "MT-0003"):
        code, out, err = run(capsys, ["-C", str(tmp_path), "status", arg, "in-progress"])
        assert code == 0, (arg, err)
        assert "MT-0003" in out
    code, _, err = run(capsys, ["-C", str(tmp_path), "status", "9", "in-progress"])
    assert code == 1
    assert "card MT-0009 not found" in err
    code, _, err = run(capsys, ["-C", str(tmp_path), "status", "mt-0009", "in-progress"])
    assert code == 1
    assert "card MT-0009 not found" in err


def test_failed_add_leaves_no_orphan_folder(capsys, tmp_path, today, monkeypatch):
    init_ws(capsys, tmp_path)
    monkeypatch.setenv("KAIJU_TODAY", "invalid")
    code, out, err = add(capsys, tmp_path, "Card")
    assert code == 1
    assert "KAIJU_TODAY" in err
    assert not (tmp_path / "MT-0001").exists()
    monkeypatch.setenv("KAIJU_TODAY", "2026-09-19")
    code, out, err = add(capsys, tmp_path, "Card")
    assert code == 0, err
    assert "MT-0001" in out
