from pathlib import Path

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


def _flatten_names(nodes) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        names.add(node.name)
        names.update(_flatten_names(node.children))
    return names
