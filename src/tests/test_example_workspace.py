from pathlib import Path

from kaiju.cards import scan_cards
from kaiju.workspace import find_workspace
from tests.helpers import run


def example_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples"


def test_example_workspace_is_a_valid_sample():
    ws = find_workspace(example_root())
    assert ws.config.name == "example"
    assert ws.config.prefix == "MT"
    cards = {card.code: card for card in scan_cards(ws)}
    assert set(cards) == {"MT-0001", "MT-0002", "MT-0003", "MT-0004"}
    assert cards["MT-0001"].is_closed
    assert cards["MT-0002"].is_epic
    assert cards["MT-0003"].epic == "MT-0002"
    assert not cards["MT-0003"].is_closed
    assert cards["MT-0004"].parent == "MT-0003"
    assert (ws.root / "MT-0001" / "sql" / "explain.sql").is_file()
    assert (ws.root / "BACKLOG.md").is_file()
    assert (ws.root / "README.md").is_file()


def test_example_workspace_lists_via_cli(capsys):
    code, out, err = run(capsys, ["-C", str(example_root()), "search", ""])
    assert code == 0, err
    assert "MT-0001" in out
    assert "MT-0002" in out
    assert "(epic)" in out
    assert "[closed " in out
    code, out, err = run(capsys, ["-C", str(example_root()), "search", "", "--open"])
    assert code == 0, err
    assert "MT-0001" not in out
    assert "MT-0002" in out
