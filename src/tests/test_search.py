from tests.helpers import add, init_ws, run


def _setup_tree(capsys, tmp_path):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Indices in created_at")
    add(capsys, tmp_path, "Migrate exceptions to 30-day retention", extra=["--as-epic"])
    add(capsys, tmp_path, "Purge job", extra=["--epic", "2"])
    add(capsys, tmp_path, "Purge scheduler", extra=["--epic", "MT-0002", "--parent", "3"])
    run(capsys, ["-C", str(tmp_path), "close", "1", "done"])
    mem = tmp_path / "MT-0001" / "MEMORY.md"
    mem.write_text(
        mem.read_text(encoding="utf-8") + "Investigate DATA_FREE of table\n",
        encoding="utf-8",
    )
    sql = tmp_path / "MT-0001" / "sql"
    sql.mkdir()
    (sql / "explain.sql").write_text(
        "SELECT DATA_FREE FROM information_schema.TABLES;\n",
        encoding="utf-8",
    )
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        backlog.read_text(encoding="utf-8")
        + "- DATA_FREE of ~14 GB in exceptions (seen on 2026-09-19)\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# local rules\nDATA_FREE also here\n",
        encoding="utf-8",
    )


def test_listing_order_notes_and_filters(capsys, tmp_path, today):
    _setup_tree(capsys, tmp_path)
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", ""])
    assert code == 0, err
    lines = [ln for ln in out.splitlines() if ln and not ln.startswith("--")]
    codes = [ln.split()[0] for ln in lines]
    assert codes == ["MT-0004", "MT-0003", "MT-0002", "MT-0001"]
    assert "(epic MT-0002, parent MT-0003)" in out
    assert "(epic)" in out
    assert "[closed 2026-09-19]" in out

    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "", "--open"])
    assert "MT-0001" not in out
    assert "MT-0002" in out
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "", "--closed"])
    assert "MT-0001" in out
    assert "MT-0002" not in out
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "", "--status", "done"])
    assert "MT-0001" in out
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "", "--epic", "2"])
    assert "MT-0002" in out
    assert "MT-0003" in out
    assert "MT-0004" in out
    assert "MT-0001" not in out


def test_search_finds_all_locations(capsys, tmp_path, today):
    _setup_tree(capsys, tmp_path)
    (tmp_path / "MT-0002" / "DELIVERY.md").write_text(
        "# MT-0002 — delivery\n\nDATA_FREE in delivery\n",
        encoding="utf-8",
    )
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "data_free"])
    assert code == 0, err
    assert "MEMORY.md:" in out
    assert "sql/explain.sql:" in out
    assert "BACKLOG.md:" in out
    assert "WORKSPACE" in out
    assert "DELIVERY.md:" in out


def test_root_files_hidden_when_card_filter(capsys, tmp_path, today):
    _setup_tree(capsys, tmp_path)
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "data_free", "--open"])
    assert code == 0, err
    assert "BACKLOG" not in out
    assert "WORKSPACE" not in out


def test_ignores_large_binary_and_hidden(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    folder = tmp_path / "MT-0001"
    (folder / "big.txt").write_bytes(b"NEEDLE " + b"x" * 1_048_576)
    (folder / "bin.dat").write_bytes(b"NEEDLE\0binary")
    (folder / ".secret.md").write_text("NEEDLE hidden\n", encoding="utf-8")
    nested = folder / ".oculta"
    nested.mkdir()
    (nested / "x.md").write_text("NEEDLE nested hidden\n", encoding="utf-8")
    (folder / "ok.txt").write_text("NEEDLE visible\n", encoding="utf-8")
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "NEEDLE"])
    assert code == 0, err
    assert "ok.txt:" in out
    assert "big.txt" not in out
    assert "bin.dat" not in out
    assert ".secret.md" not in out
    assert ".oculta" not in out


def test_case_sensitivity(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    (tmp_path / "MT-0001" / "MEMORY.md").write_text("AbCdE unique\n", encoding="utf-8")
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "abcde"])
    assert code == 0, err
    assert "AbCdE" in out
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "abcde", "--case-sensitive"])
    assert code == 0, err
    assert "no results" in out


def test_cards_aggregates_counts(capsys, tmp_path, today):
    _setup_tree(capsys, tmp_path)
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "data_free", "--cards"])
    assert code == 0, err
    assert "occurrence" in out
    assert "MT-0001" in out
    assert "BACKLOG" in out
    assert "Indices in created_at" in out


def test_pagination_footer_and_past_end(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    for i in range(12):
        add(capsys, tmp_path, f"Card number {i}")
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "", "--limit", "5", "--page", "2"])
    assert code == 0, err
    assert "-- 6-10 of 12 · next: --page 3 --" in out
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "", "--limit", "5", "--page", "3"])
    assert code == 0, err
    assert "-- 11-12 of 12 --" in out
    assert "next" not in out
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "", "--limit", "5", "--page", "9"])
    assert code == 0, err
    assert "no results on this page (total: 12)" in out


def test_invalid_regex_and_no_results(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    code, _, err = run(capsys, ["-C", str(tmp_path), "search", "["])
    assert code == 1
    assert "invalid regex" in err
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "xyzzy-does-not-exist"])
    assert code == 0, err
    assert out.strip() == "no results"


def test_long_snippet_is_trimmed(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    long = "aaa " + ("x" * 80) + " NEEDLE " + ("y" * 80)
    (tmp_path / "MT-0001" / "MEMORY.md").write_text(long + "\n", encoding="utf-8")
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "NEEDLE"])
    assert code == 0, err
    line = [ln for ln in out.splitlines() if "NEEDLE" in ln][0]
    snippet = line.split("MEMORY.md:")[1]
    snippet = snippet.split(" ", 1)[1]
    assert "…" in snippet
    assert "NEEDLE" in snippet


def test_does_not_follow_directory_symlinks(capsys, tmp_path, today):
    ws = tmp_path / "ws"
    ws.mkdir()
    init_ws(capsys, ws)
    add(capsys, ws, "Card")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "notes.md").write_text("needle outside card\n", encoding="utf-8")
    (ws / "MT-0001" / "refs").symlink_to(outside, target_is_directory=True)
    (ws / "MT-0001" / "loop").symlink_to(ws / "MT-0001", target_is_directory=True)
    code, out, err = run(capsys, ["-C", str(ws), "search", "needle"])
    assert code == 0, err
    assert out.strip() == "no results"


def test_regex_starting_with_dash_after_double_dash(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    (tmp_path / "MT-0001" / "MEMORY.md").write_text("valor -x aqui\n", encoding="utf-8")
    code, out, err = run(capsys, ["-C", str(tmp_path), "search", "--", "-x"])
    assert code == 0, err
    assert "MEMORY.md:1" in out
