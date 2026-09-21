import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

from kaiju.gui.appearance import DARK, LIGHT, apply_appearance, palette_for, show_preferences
from kaiju.gui.prefs import (
    FONT_SIZE_DEFAULT,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    THEME_DARK,
    THEME_LIGHT,
    Prefs,
    load_prefs,
    parse_prefs,
    prefs_path,
    render_prefs,
    save_prefs,
)


def test_prefs_defaults():
    prefs = Prefs()
    assert prefs.theme == THEME_LIGHT
    assert prefs.font_size == FONT_SIZE_DEFAULT


def test_prefs_normalizes_theme_and_clamps_font_size():
    assert Prefs(theme="DARK", font_size=99).theme == THEME_DARK
    assert Prefs(theme="DARK", font_size=99).font_size == FONT_SIZE_MAX
    assert Prefs(theme="nope", font_size=2).theme == THEME_LIGHT
    assert Prefs(theme="nope", font_size=2).font_size == FONT_SIZE_MIN


def test_parse_prefs_reads_known_keys_and_ignores_the_rest():
    prefs = parse_prefs('theme = "dark"\nfont_size = 12\nunknown = "x"\n[extra]\nfoo = 1\n')
    assert prefs == Prefs(theme=THEME_DARK, font_size=12)


def test_parse_prefs_falls_back_on_invalid_values():
    assert parse_prefs("not toml") == Prefs()
    assert parse_prefs('theme = 1\nfont_size = "huge"\n') == Prefs()
    assert parse_prefs('theme = "dark"\nfont_size = "14"\n') == Prefs(
        theme=THEME_DARK, font_size=14
    )
    assert parse_prefs("font_size = 12.0\n") == Prefs(font_size=12)


def test_render_prefs_roundtrips_through_parse():
    prefs = Prefs(theme=THEME_DARK, font_size=16)
    assert parse_prefs(render_prefs(prefs)) == prefs


def test_load_and_save_prefs_use_xdg_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert prefs_path() == tmp_path / "cfg" / "kaiju" / "gui.toml"
    assert load_prefs() == Prefs()
    save_prefs(Prefs(theme=THEME_DARK, font_size=14))
    assert load_prefs() == Prefs(theme=THEME_DARK, font_size=14)
    text = Path(prefs_path()).read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert 'theme = "dark"' in text


def test_load_prefs_missing_or_unreadable_returns_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    path = prefs_path()
    path.parent.mkdir(parents=True)
    path.write_text("{{{", encoding="utf-8")
    assert load_prefs() == Prefs()


def test_palette_for_theme():
    assert palette_for(Prefs(theme=THEME_LIGHT)) is LIGHT
    assert palette_for(Prefs(theme=THEME_DARK)) is DARK


def test_apply_appearance_switches_theme_and_font_size():
    import pytest

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    try:
        apply_appearance(root, Prefs(theme=THEME_DARK, font_size=14))
        style = ttk.Style(root)
        assert style.lookup("TFrame", "background").casefold() == DARK.bg.casefold()
        assert tkfont.nametofont("TkDefaultFont").cget("size") == 14
        text = tk.Text(root)
        text.pack()
        apply_appearance(root, Prefs(theme=THEME_LIGHT, font_size=9))
        assert style.lookup("TFrame", "background").casefold() == LIGHT.bg.casefold()
        assert tkfont.nametofont("TkDefaultFont").cget("size") == 9
        assert str(text.cget("background")).casefold() == LIGHT.text_bg.casefold()
    finally:
        root.destroy()


def test_scrollbar_disabled_state_stays_on_palette():
    import pytest

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    try:
        apply_appearance(root, Prefs(theme=THEME_DARK, font_size=10))
        style = ttk.Style(root)
        clam_frame = "#dcdad5"
        for name in ("TScrollbar", "Vertical.TScrollbar"):
            disabled_bg = style.lookup(name, "background", ["disabled"]).casefold()
            disabled_trough = style.lookup(name, "troughcolor", ["disabled"]).casefold()
            assert disabled_bg != clam_frame
            assert disabled_trough != clam_frame
            assert disabled_trough == DARK.field.casefold()
            enabled_trough = style.lookup(name, "troughcolor").casefold()
            enabled_arrow = style.lookup(name, "arrowcolor").casefold()
            disabled_arrow = style.lookup(name, "arrowcolor", ["disabled"]).casefold()
            assert enabled_trough == disabled_trough
            assert enabled_arrow == disabled_arrow
            thumb = style.lookup(name, "background").casefold()
            assert style.lookup(name, "lightcolor").casefold() == thumb
            assert style.lookup(name, "darkcolor").casefold() == thumb
            assert style.lookup(name, "bordercolor").casefold() == thumb
            assert str(style.lookup(name, "gripcount")) in {"", "0"}
    finally:
        root.destroy()


def test_dark_theme_avoids_clam_light_bevels():
    import pytest

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    try:
        apply_appearance(root, Prefs(theme=THEME_DARK, font_size=10))
        style = ttk.Style(root)
        light = {"#ffffff", "white", "#dcdad5", "#eeebe7"}
        for name in ("Treeview", "Treeview.Heading", "TNotebook", "Sash", "TFrame"):
            for opt in ("lightcolor", "darkcolor", "bordercolor"):
                value = style.lookup(name, opt).casefold()
                assert value not in light, f"{name} {opt}={value}"
    finally:
        root.destroy()


def test_show_preferences_places_near_parent():
    import pytest

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.geometry("400x300+100+80")
    root.update_idletasks()
    try:
        win = show_preferences(root, Prefs(), lambda _prefs: None)
        _, x_str, y_str = win.geometry().rsplit("+", 2)
        assert abs(int(x_str) - (root.winfo_rootx() + 80)) <= 8
        assert abs(int(y_str) - (root.winfo_rooty() + 80)) <= 8
        assert win.state() != "withdrawn"
        win.destroy()
    finally:
        root.destroy()


def test_show_preferences_applies_theme_change():
    import pytest

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    seen: list[Prefs] = []
    try:
        win = show_preferences(root, Prefs(), seen.append)
        labels: list[str] = []
        radios: dict[str, ttk.Radiobutton] = {}

        def walk(widget: tk.Misc) -> None:
            cls = widget.winfo_class()
            if cls in {"TLabel", "TRadiobutton", "TLabelframe", "TButton"}:
                text = str(widget.cget("text"))
                labels.append(text)
                if cls == "TRadiobutton":
                    radios[text] = widget
            for child in widget.winfo_children():
                walk(child)

        walk(win)
        assert "Theme" in labels
        assert "Font size" in labels
        assert "Light" in radios and "Dark" in radios
        radios["Dark"].invoke()
        assert seen[-1] == Prefs(theme=THEME_DARK, font_size=FONT_SIZE_DEFAULT)
        win.destroy()
    finally:
        root.destroy()
