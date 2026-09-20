import os
from pathlib import Path

from kaiju.gui.fonts import pick_mono_family, pick_ui_family
from kaiju.gui.recents import (
    MAX_RECENTS,
    load_recents,
    remember_workspace,
    usable_recents,
)
from kaiju.gui.session import (
    FILTER_ALL,
    FILTER_BACKLOG,
    FILTER_CLOSED,
    FILTER_EPIC,
    FILTER_EPICS,
    FILTER_OPEN,
    Session,
    is_canonical,
    list_file_tree,
    read_preview,
    table_values,
)
from kaiju.search import MAX_FILE_BYTES
from tests.helpers import add, init_ws, run


def _setup_cards(capsys, tmp_path: Path) -> None:
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Indices in created_at")
    add(capsys, tmp_path, "Migrate exceptions to 30-day retention", extra=["--as-epic"])
    add(capsys, tmp_path, "Purge job", extra=["--epic", "2"])
    add(capsys, tmp_path, "Purge scheduler", extra=["--epic", "MT-0002", "--parent", "3"])
    run(capsys, ["-C", str(tmp_path), "close", "1", "done"])
    sql = tmp_path / "MT-0001" / "sql"
    sql.mkdir()
    (sql / "explain.sql").write_text("SELECT 1;\n", encoding="utf-8")


def test_open_missing_workspace(tmp_path):
    session = Session()
    assert session.open(tmp_path) is False
    assert session.workspace is None
    assert session.error is not None
    assert "no kAIju workspace" in session.error
    assert session.nav_tree() is None
    assert session.filtered_cards() == []


def test_filters_all_open_closed_epic(capsys, tmp_path, today):
    _setup_cards(capsys, tmp_path)
    session = Session()
    assert session.open(tmp_path) is True
    assert session.workspace is not None
    assert session.workspace.config.name == "maintenance"

    codes = [card.code for card in session.filtered_cards()]
    assert codes == ["MT-0004", "MT-0003", "MT-0002", "MT-0001"]

    session.select_nav(FILTER_OPEN)
    assert [card.code for card in session.filtered_cards()] == ["MT-0004", "MT-0003", "MT-0002"]

    session.select_nav(FILTER_CLOSED)
    closed = session.filtered_cards()
    assert [card.code for card in closed] == ["MT-0001"]
    assert closed[0].closed_at == today

    session.select_nav(FILTER_EPIC, "MT-0002")
    assert [card.code for card in session.filtered_cards()] == ["MT-0004", "MT-0003", "MT-0002"]

    session.select_nav(FILTER_EPICS)
    assert [card.code for card in session.filtered_cards()] == ["MT-0002"]

    session.select_nav(FILTER_BACKLOG)
    assert session.filtered_cards() == []
    assert session.backlog_path() == tmp_path / "BACKLOG.md"

    session.select_nav(FILTER_ALL)
    card = session.card_by_code("MT-0004")
    assert card is not None
    row = table_values(card)
    assert row[0] == "MT-0004"
    assert row[1] == "Purge scheduler"
    assert row[3] == "MT-0002"
    assert row[4] == "MT-0003"


def test_nav_tree_lists_epics(capsys, tmp_path, today):
    _setup_cards(capsys, tmp_path)
    session = Session()
    session.open(tmp_path)
    tree = session.nav_tree()
    assert tree is not None
    assert tree.label == "maintenance"
    labels = [child.label for child in tree.children]
    assert labels == ["All", "Open", "Closed", "Epics", "Backlog"]
    epics = tree.children[3].children
    assert len(epics) == 1
    assert epics[0].key == "epic:MT-0002"
    assert epics[0].epic_code == "MT-0002"
    assert "Migrate" in epics[0].label


def test_list_file_tree_skips_hidden_and_dir_symlinks(capsys, tmp_path, today):
    _setup_cards(capsys, tmp_path)
    folder = tmp_path / "MT-0001"
    (folder / "ok.txt").write_text("visible\n", encoding="utf-8")
    (folder / ".secret.md").write_text("hidden\n", encoding="utf-8")
    nested = folder / ".oculta"
    nested.mkdir()
    (nested / "x.md").write_text("nested hidden\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "notes.md").write_text("outside\n", encoding="utf-8")
    (folder / "refs").symlink_to(outside, target_is_directory=True)
    (folder / "loop").symlink_to(folder, target_is_directory=True)

    names = _flatten_names(list_file_tree(folder))
    assert "ok.txt" in names
    assert "explain.sql" in names
    assert "sql" in names
    assert "README.md" in names
    assert ".secret.md" not in names
    assert ".oculta" not in names
    assert "x.md" not in names
    assert "refs" not in names
    assert "loop" not in names
    assert "notes.md" not in names


def test_read_preview_skips_binary_and_large(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Card")
    folder = tmp_path / "MT-0001"
    (folder / "ok.txt").write_text("hello\n", encoding="utf-8")
    (folder / "bin.dat").write_bytes(b"NEEDLE\0binary")
    (folder / "big.txt").write_bytes(b"x" * (MAX_FILE_BYTES + 1))

    ok = read_preview(folder / "ok.txt")
    assert ok.text == "hello\n"
    assert ok.message == ""

    missing = read_preview(folder / "nope.md")
    assert missing.text == ""
    assert "not found" in missing.message

    binary = read_preview(folder / "bin.dat")
    assert binary.text == ""
    assert "binary" in binary.message

    large = read_preview(folder / "big.txt")
    assert large.text == ""
    assert "1 MiB" in large.message

    names = _flatten_names(list_file_tree(folder))
    assert "bin.dat" in names
    assert "big.txt" in names


def test_is_canonical_only_root_names():
    assert is_canonical("README.md")
    assert is_canonical("MEMORY.md")
    assert is_canonical("DELIVERY.md")
    assert not is_canonical("sql/README.md")
    assert not is_canonical("notes.md")


def test_refresh_drops_missing_epic_filter(capsys, tmp_path, today):
    _setup_cards(capsys, tmp_path)
    session = Session()
    session.open(tmp_path)
    session.select_nav(FILTER_EPIC, "MT-0002")
    readme = tmp_path / "MT-0002" / "README.md"
    text = readme.read_text(encoding="utf-8")
    readme.write_text(text.replace("card: MT-0002", "card: NOPE"), encoding="utf-8")
    session.refresh()
    assert session.filter_kind == FILTER_ALL
    assert session.epic_code == ""


def test_gui_help(capsys):
    code, out, err = run(capsys, ["gui", "--help"])
    assert code == 0, err
    assert "read-only" in out.lower() or "viewer" in out.lower()
    assert err == ""


def test_gui_parent_returns_without_opening_display(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("os.fork", lambda: 99)

    def boom(_start: Path) -> None:
        raise AssertionError("parent process must not start the GUI")

    monkeypatch.setattr("kaiju.gui.run", boom)
    code, out, err = run(capsys, ["gui", str(tmp_path)])
    assert code == 0, err
    assert out == ""
    assert err == ""


def test_remember_workspaces_newest_first(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    remember_workspace(first)
    remember_workspace(second)
    remember_workspace(first)
    recents = load_recents()
    assert [path.resolve() for path in recents] == [first.resolve(), second.resolve()]


def test_remember_workspaces_caps_list(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    paths = []
    for index in range(MAX_RECENTS + 3):
        folder = tmp_path / f"ws{index}"
        folder.mkdir()
        paths.append(folder)
        remember_workspace(folder)
    recents = load_recents()
    assert len(recents) == MAX_RECENTS
    assert recents[0].resolve() == paths[-1].resolve()
    assert recents[-1].resolve() == paths[3].resolve()


def test_usable_recents_skips_missing_and_non_workspaces(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    alive = tmp_path / "alive"
    alive.mkdir()
    (alive / "kaiju.toml").write_text('name = "x"\n', encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    remember_workspace(alive)
    remember_workspace(empty)
    remember_workspace(tmp_path / "gone")
    recents = load_recents()
    assert len(recents) == 3
    usable = usable_recents()
    assert [path.resolve() for path in usable] == [alive.resolve()]


def test_pick_ui_family_skips_mono_and_matches_without_spaces():
    assert pick_ui_family({"DejaVu Sans Mono", "DejaVu Sans"}) == "DejaVu Sans"
    assert pick_ui_family({"Noto Sans Mono", "Liberation Sans"}) == "Liberation Sans"
    assert pick_ui_family({"DejaVuSans", "Courier"}) == "DejaVuSans"
    ui = pick_ui_family({"DejaVu Sans Mono", "Ubuntu Mono", "Noto Sans Mono"})
    assert "mono" not in ui.casefold()
    assert pick_mono_family({"DejaVu Sans", "DejaVu Sans Mono"}) == "DejaVu Sans Mono"


def test_about_png_is_png_and_small():
    path = Path(__file__).resolve().parents[1] / "kaiju" / "gui" / "about.png"
    assert path.is_file()
    assert path.stat().st_size < 20_000
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_maybe_reexec_is_noop_under_pytest():
    from kaiju.gui.native_tk import maybe_reexec_for_native_tk

    maybe_reexec_for_native_tk()


def test_import_path_points_at_kaiju_package():
    from kaiju.gui.native_tk import _import_path

    roots = _import_path().split(os.pathsep)
    assert any((Path(root) / "kaiju").is_dir() for root in roots)


def test_desired_nav_sash_restores_collapsed_pane():
    from kaiju.gui.app import NAV_SASH, desired_nav_sash

    assert desired_nav_sash(4, 1100) == NAV_SASH
    assert desired_nav_sash(0, 1100) == NAV_SASH
    assert desired_nav_sash(NAV_SASH, 1100) is None
    assert desired_nav_sash(180, 1100) is None
    assert desired_nav_sash(4, 1) is None


def test_desired_files_sash_restores_collapsed_pane():
    from kaiju.gui.app import FILES_SASH, desired_files_sash

    assert desired_files_sash(1090, 1100) == 1100 - FILES_SASH
    assert desired_files_sash(860, 1100) is None
    assert desired_files_sash(0, 1) is None


def test_grid_with_yscroll_keeps_scrollbar_when_parent_shrinks():
    import tkinter as tk
    from tkinter import ttk

    import pytest

    from kaiju.gui.app import _grid_with_yscroll

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.geometry("300x200+40+40")
    try:
        frame = ttk.Frame(root, width=220, height=160)
        frame.grid_propagate(False)
        frame.pack()
        tree = ttk.Treeview(frame, show="tree")
        for index in range(40):
            tree.insert("", "end", text=f"row {index}")
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        _grid_with_yscroll(frame, tree, scroll)
        root.update_idletasks()
        root.update()
        frame.configure(width=50, height=50)
        root.update_idletasks()
        root.update()
        assert scroll.winfo_width() >= 8
        assert scroll.winfo_height() >= 8
        assert tree.winfo_width() >= 8
    finally:
        root.destroy()


def _flatten_names(nodes) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        names.add(node.name)
        names.update(_flatten_names(node.children))
    return names
