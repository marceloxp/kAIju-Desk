from kaiju.workspace import load_config
from tests.helpers import init_ws, run


def test_init_creates_toml_and_backlog_not_readme(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    assert (tmp_path / "kaiju.toml").is_file()
    assert (tmp_path / "BACKLOG.md").is_file()
    assert not (tmp_path / "README.md").exists()
    text = (tmp_path / "kaiju.toml").read_text(encoding="utf-8")
    assert 'prefix = "MT"' in text
    assert 'name   = "maintenance"' in text
    assert "[on]" in text
    assert 'add    = "open"' in text
    assert 'close  = "done"' in text
    assert 'reopen = "open"' in text
    backlog = (tmp_path / "BACKLOG.md").read_text(encoding="utf-8")
    assert backlog.startswith("# Backlog\n")
    assert backlog.endswith("\n")


def test_init_does_not_overwrite_existing_backlog(capsys, tmp_path, today):
    (tmp_path / "BACKLOG.md").write_text("keep me\n", encoding="utf-8")
    init_ws(capsys, tmp_path)
    assert (tmp_path / "BACKLOG.md").read_text(encoding="utf-8") == "keep me\n"


def test_init_refuses_existing_workspace(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    code, _, err = run(capsys, ["-C", str(tmp_path), "init", "--prefix", "MT"])
    assert code == 1
    assert "is already a kAIju workspace" in err
    assert err.startswith("error: ")


def test_init_refuses_directory_inside_workspace(capsys, tmp_path, today):
    init_ws(capsys, tmp_path)
    nested = tmp_path / "inside"
    code, _, err = run(
        capsys,
        ["-C", str(tmp_path), "init", "--prefix", "XX", "--name", "x", str(nested)],
    )
    assert code == 1
    assert "is inside workspace" in err


def test_init_invalid_prefix(capsys, tmp_path, today):
    for prefix in ("mt", "1A"):
        target = tmp_path / prefix
        code, _, err = run(
            capsys,
            ["init", "--prefix", prefix, "--name", "x", str(target)],
        )
        assert code == 1, prefix
        assert "prefix invalid" in err


def test_discovery_walks_up_from_card_subdir(capsys, tmp_path, today):
    from tests.helpers import add

    init_ws(capsys, tmp_path)
    code, _, err = add(capsys, tmp_path, "Um card")
    assert code == 0, err
    card_dir = tmp_path / "MT-0001"
    code, out, err = run(capsys, ["-C", str(card_dir), "search", "", "--open"])
    assert code == 0, err
    assert "MT-0001" in out


def test_dash_c_and_outside_workspace(capsys, tmp_path, today):
    empty = tmp_path / "empty"
    empty.mkdir()
    code, _, err = run(capsys, ["-C", str(empty), "guide"])
    assert code == 1
    assert "no kAIju workspace found" in err
    assert "kaiju init" in err


def test_invalid_config_missing_status(capsys, tmp_path, today):
    (tmp_path / "kaiju.toml").write_text(
        'name = "x"\nprefix = "MT"\ndigits = 4\n',
        encoding="utf-8",
    )
    code, _, err = run(capsys, ["-C", str(tmp_path), "guide"])
    assert code == 1
    assert "status" in err
    assert str(tmp_path / "kaiju.toml") in err


def test_invalid_config_digits_zero(capsys, tmp_path, today):
    (tmp_path / "kaiju.toml").write_text(
        'name = "x"\nprefix = "MT"\ndigits = 0\n[status]\naberto = "a"\n',
        encoding="utf-8",
    )
    code, _, err = run(capsys, ["-C", str(tmp_path), "guide"])
    assert code == 1
    assert "digits" in err


def test_invalid_config_additional_core_field(capsys, tmp_path, today):
    (tmp_path / "kaiju.toml").write_text(
        'name = "x"\nprefix = "MT"\ndigits = 4\n'
        '[status]\nopen = "a"\n'
        '[on]\nadd = "open"\nclose = "open"\nreopen = "open"\n'
        '[additional_fields]\nstatus = "nope"\n',
        encoding="utf-8",
    )
    code, _, err = run(capsys, ["-C", str(tmp_path), "guide"])
    assert code == 1
    assert "core" in err


def test_invalid_config_missing_on(capsys, tmp_path, today):
    (tmp_path / "kaiju.toml").write_text(
        'name = "x"\nprefix = "MT"\ndigits = 4\n[status]\nopen = "a"\n',
        encoding="utf-8",
    )
    code, _, err = run(capsys, ["-C", str(tmp_path), "guide"])
    assert code == 1
    assert "missing [on] table" in err


def test_invalid_config_on_unknown_status(capsys, tmp_path, today):
    (tmp_path / "kaiju.toml").write_text(
        'name = "x"\nprefix = "MT"\ndigits = 4\n'
        '[status]\nopen = "a"\n'
        '[on]\nadd = "open"\nclose = "nope"\nreopen = "open"\n',
        encoding="utf-8",
    )
    code, _, err = run(capsys, ["-C", str(tmp_path), "guide"])
    assert code == 1
    assert '[on].close status "nope" does not exist' in err


def test_load_config_preserves_status_order(tmp_path):
    (tmp_path / "kaiju.toml").write_text(
        'name = "x"\nprefix = "MT"\ndigits = 4\n'
        '[status]\nzebra = "z"\nopen = "a"\n'
        '[on]\nadd = "zebra"\nclose = "open"\nreopen = "zebra"\n',
        encoding="utf-8",
    )
    cfg = load_config(tmp_path / "kaiju.toml")
    assert list(cfg.statuses) == ["zebra", "open"]
    assert cfg.on == {"add": "zebra", "close": "open", "reopen": "zebra"}
