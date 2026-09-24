from kaiju.cron import scan_crons
from kaiju.gui.session import FILTER_CRONS, Session, cron_values
from kaiju.search import search
from kaiju.workspace import find_workspace
from tests.helpers import add, init_ws


def test_scan_workspace_and_card_crons(capsys, tmp_path):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "Purge job")
    root = tmp_path / "cron"
    root.mkdir()
    (root / "queue-check.md").write_text(
        "---\nwhen: 30 8 * * *\nscript: queue-check.sh\ntitle: Queue check\n"
        "readable: Send the queue size\n---\n\nbody\n",
        encoding="utf-8",
    )
    (root / "queue-check.sh").write_text("echo queue\n", encoding="utf-8")
    (root / ".hidden.md").write_text("---\ntitle: no\n---\n", encoding="utf-8")
    card = tmp_path / "MT-0001" / "cron"
    card.mkdir()
    (card / "daily-stand.md").write_text(
        "---\nwhen: 0 9 * * *\nscript: daily-stand.sh\ntitle: Daily stand\n---\n",
        encoding="utf-8",
    )
    (card / "notes.txt").write_text("not a job\n", encoding="utf-8")

    jobs = scan_crons(find_workspace(tmp_path))
    assert [(job.card, job.title, job.when, job.readable, job.script) for job in jobs] == [
        ("", "Queue check", "30 8 * * *", "Send the queue size", "queue-check.sh"),
        ("MT-0001", "Daily stand", "0 9 * * *", "", "daily-stand.sh"),
    ]
    assert jobs[0].key == "cron/queue-check.md"


def test_scan_skips_symlink_dir_and_uses_stem(capsys, tmp_path):
    init_ws(capsys, tmp_path)
    add(capsys, tmp_path, "A card")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.md").write_text(
        "---\ntitle: leak\nwhen: * * * * *\nscript: x.sh\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "cron").symlink_to(outside, target_is_directory=True)
    card = tmp_path / "MT-0001" / "cron"
    card.mkdir()
    (card / "no-front.md").write_text("just text\n", encoding="utf-8")

    jobs = scan_crons(find_workspace(tmp_path))
    assert [(job.card, job.title, job.when, job.readable, job.script) for job in jobs] == [
        ("MT-0001", "no-front", "", "", ""),
    ]


def test_session_lists_crons(capsys, tmp_path):
    init_ws(capsys, tmp_path)
    folder = tmp_path / "cron"
    folder.mkdir()
    (folder / "once.md").write_text(
        "---\nwhen: 30 8 25 9 *\nscript: once.sh\ntitle: Tomorrow\n---\n",
        encoding="utf-8",
    )
    session = Session()
    assert session.open(tmp_path) is True
    labels = [child.label for child in session.nav_tree().children]
    assert "Crons" in labels
    session.select_nav(FILTER_CRONS)
    assert session.filtered_cards() == []
    jobs = session.crons()
    assert len(jobs) == 1
    assert cron_values(jobs[0]) == ("", "30 8 25 9 *", "Tomorrow", "", "once.sh")
    assert session.cron_by_key("cron/once.md") is jobs[0]


def test_search_finds_workspace_cron(capsys, tmp_path):
    init_ws(capsys, tmp_path)
    folder = tmp_path / "cron"
    folder.mkdir()
    (folder / "queue-check.md").write_text("queue needle\n", encoding="utf-8")
    hits = search(find_workspace(tmp_path), "needle")
    assert any(hit.label == "CRON" and hit.relpath == "cron/queue-check.md" for hit in hits)
