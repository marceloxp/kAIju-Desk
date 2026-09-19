from kaiju.frontmatter import parse, set_fields

SAMPLE = """---
card: MT-0001
title: Indices in created_at: exceptions
status: open
created_at: 2026-09-18
closed_at:
epic:
parent:
# a comment
category: "database"
branch: 'main'
agent_resume:
title: IGNORED
line without colon
hash: value with # inside
---

# body
don't touch
"""


def test_parse_empty_colon_quotes_repeat_and_hash():
    fields = parse(SAMPLE)
    assert fields is not None
    assert fields["card"] == "MT-0001"
    assert fields["title"] == "Indices in created_at: exceptions"
    assert fields["closed_at"] == ""
    assert fields["epic"] == ""
    assert fields["category"] == "database"
    assert fields["branch"] == "main"
    assert fields["agent_resume"] == ""
    assert fields["hash"] == "value with # inside"
    assert "line without colon" not in fields


def test_parse_missing_frontmatter_or_closing():
    assert parse("# sem\n") is None
    assert parse("---\ncard: X\n") is None
    assert parse("card: X\n---\n") is None


def test_parse_bom_and_crlf():
    text = "\ufeff---\r\ncard: MT-0001\r\n---\r\n\r\nbody\r\n"
    fields = parse(text)
    assert fields == {"card": "MT-0001"}


def test_set_fields_changes_only_requested_line(tmp_path):
    path = tmp_path / "README.md"
    original = SAMPLE.encode("utf-8")
    path.write_bytes(original)
    set_fields(path, {"status": "in-progress"})
    new = path.read_bytes()
    old_lines = original.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    changed = [(a, b) for a, b in zip(old_lines, new_lines, strict=False) if a != b]
    assert len(old_lines) == len(new_lines)
    assert len(changed) == 1
    assert changed[0][1] == b"status: in-progress\n"
    assert b"# body\n" in new
    assert b"don't touch\n" in new
    assert b"# a comment\n" in new


def test_set_fields_inserts_missing_key_before_closing(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(SAMPLE, encoding="utf-8")
    set_fields(path, {"new": "xyz"})
    text = path.read_text(encoding="utf-8")
    assert "new: xyz\n---\n" in text
    assert "# body\ndon't touch\n" in text


def test_set_fields_empty_value(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(SAMPLE, encoding="utf-8")
    set_fields(path, {"status": ""})
    assert "status:\n" in path.read_text(encoding="utf-8")
    assert "status: \n" not in path.read_text(encoding="utf-8")
