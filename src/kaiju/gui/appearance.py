from __future__ import annotations

import contextlib
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from kaiju.gui.fonts import pick_mono_family, pick_ui_family
from kaiju.gui.prefs import (
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    THEME_DARK,
    THEME_LIGHT,
    Prefs,
)


@dataclass(frozen=True)
class Palette:
    bg: str
    fg: str
    field: str
    heading: str
    select_bg: str
    select_fg: str
    text_bg: str
    text_fg: str
    button: str
    border: str
    disabled: str


LIGHT = Palette(
    bg="#f0f0f0",
    fg="#1c1c1c",
    field="#ffffff",
    heading="#e4e4e4",
    select_bg="#4a90d9",
    select_fg="#ffffff",
    text_bg="#ffffff",
    text_fg="#1c1c1c",
    button="#e8e8e8",
    border="#c0c0c0",
    disabled="#808080",
)

DARK = Palette(
    bg="#2d2d2d",
    fg="#e8e8e8",
    field="#1e1e1e",
    heading="#3a3a3a",
    select_bg="#3d6ea8",
    select_fg="#ffffff",
    text_bg="#1e1e1e",
    text_fg="#e8e8e8",
    button="#3a3a3a",
    border="#555555",
    disabled="#888888",
)


def palette_for(prefs: Prefs) -> Palette:
    return DARK if prefs.theme == THEME_DARK else LIGHT


def apply_appearance(root: tk.Tk, prefs: Prefs) -> None:
    _configure_ttk_theme(root)
    _configure_fonts(root, prefs.font_size)
    palette = palette_for(prefs)
    _apply_palette(root, palette)


def show_preferences(
    parent: tk.Tk,
    prefs: Prefs,
    on_apply: Callable[[Prefs], None],
) -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.withdraw()
    win.title("Preferences")
    win.transient(parent)
    win.resizable(False, False)
    win.configure(bg=palette_for(prefs).bg)
    parent.update_idletasks()
    win.geometry(f"+{parent.winfo_rootx() + 80}+{parent.winfo_rooty() + 80}")

    body = ttk.Frame(win, padding=16)
    body.pack(fill=tk.BOTH, expand=True)

    appearance = ttk.LabelFrame(body, text="Appearance", padding=12)
    appearance.pack(fill=tk.X)

    theme_var = tk.StringVar(master=win, value=prefs.theme)
    size_var = tk.StringVar(master=win, value=str(prefs.font_size))

    def emit() -> None:
        prefs = Prefs(theme=theme_var.get(), font_size=_as_size(size_var.get()))
        if theme_var.get() != prefs.theme:
            theme_var.set(prefs.theme)
        if size_var.get() != str(prefs.font_size):
            size_var.set(str(prefs.font_size))
        on_apply(prefs)

    ttk.Label(appearance, text="Theme").grid(row=0, column=0, sticky="w", padx=(0, 16))
    theme_row = ttk.Frame(appearance)
    theme_row.grid(row=0, column=1, sticky="w")
    ttk.Radiobutton(
        theme_row,
        text="Light",
        value=THEME_LIGHT,
        variable=theme_var,
        command=emit,
    ).pack(side=tk.LEFT, padx=(0, 12))
    ttk.Radiobutton(
        theme_row,
        text="Dark",
        value=THEME_DARK,
        variable=theme_var,
        command=emit,
    ).pack(side=tk.LEFT)

    ttk.Label(appearance, text="Font size").grid(
        row=1, column=0, sticky="w", padx=(0, 16), pady=(10, 0)
    )
    size = ttk.Spinbox(
        appearance,
        from_=FONT_SIZE_MIN,
        to=FONT_SIZE_MAX,
        textvariable=size_var,
        width=5,
        command=emit,
    )
    size.grid(row=1, column=1, sticky="w", pady=(10, 0))
    size.bind("<Return>", lambda _e: emit())
    size.bind("<FocusOut>", lambda _e: emit())

    ttk.Button(body, text="Close", command=win.destroy).pack(anchor="e", pady=(16, 0))
    win.bind("<Escape>", lambda _e: win.destroy())
    win.update_idletasks()
    win.deiconify()
    win.lift()
    return win


def _as_size(raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        return FONT_SIZE_MIN


def _configure_ttk_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    available = {name.casefold(): name for name in style.theme_names()}
    for name in ("clam", "alt", "default"):
        actual = available.get(name)
        if actual is not None:
            style.theme_use(actual)
            return


def _configure_fonts(root: tk.Tk, size: int) -> None:
    families = set(tkfont.families(root))
    ui = pick_ui_family(families)
    mono = pick_mono_family(families)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        try:
            tkfont.nametofont(name).configure(family=ui, size=size)
        except tk.TclError:
            continue
    with contextlib.suppress(tk.TclError):
        tkfont.nametofont("TkFixedFont").configure(family=mono, size=size)
    style = ttk.Style(root)
    style.configure(".", font="TkDefaultFont")
    style.configure("Treeview", font="TkDefaultFont", rowheight=_rowheight(root))
    style.configure("Treeview.Heading", font="TkHeadingFont")
    style.configure("TLabel", font="TkDefaultFont")
    style.configure("TButton", font="TkDefaultFont")


def _rowheight(root: tk.Tk) -> int:
    try:
        return int(tkfont.nametofont("TkDefaultFont").metrics("linespace")) + 8
    except tk.TclError:
        return 24


def _apply_palette(root: tk.Tk, palette: Palette) -> None:
    root.configure(bg=palette.bg)
    style = ttk.Style(root)
    style.configure(
        ".",
        background=palette.bg,
        foreground=palette.fg,
        fieldbackground=palette.field,
        bordercolor=palette.bg,
        darkcolor=palette.bg,
        lightcolor=palette.bg,
        troughcolor=palette.field,
        arrowcolor=palette.fg,
        relief="flat",
        borderwidth=0,
    )
    style.map(
        ".",
        background=[("disabled", palette.bg), ("active", palette.heading)],
        foreground=[("disabled", palette.disabled)],
        selectbackground=[("!focus", palette.select_bg)],
        selectforeground=[("!focus", palette.select_fg)],
    )
    style.configure(
        "TFrame",
        background=palette.bg,
        bordercolor=palette.bg,
        lightcolor=palette.bg,
        darkcolor=palette.bg,
    )
    style.configure(
        "TLabel",
        background=palette.bg,
        foreground=palette.fg,
        bordercolor=palette.bg,
        lightcolor=palette.bg,
        darkcolor=palette.bg,
    )
    style.configure(
        "TButton",
        background=palette.button,
        foreground=palette.fg,
        bordercolor=palette.button,
        lightcolor=palette.button,
        darkcolor=palette.button,
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", palette.select_bg), ("pressed", palette.select_bg)],
        foreground=[("active", palette.select_fg), ("pressed", palette.select_fg)],
    )
    style.configure(
        "TLabelframe",
        background=palette.bg,
        foreground=palette.fg,
        bordercolor=palette.border,
        lightcolor=palette.bg,
        darkcolor=palette.bg,
    )
    style.configure("TLabelframe.Label", background=palette.bg, foreground=palette.fg)
    style.configure("TRadiobutton", background=palette.bg, foreground=palette.fg)
    style.map("TRadiobutton", background=[("active", palette.bg)])
    style.configure(
        "TSpinbox",
        fieldbackground=palette.field,
        foreground=palette.fg,
        background=palette.bg,
        arrowcolor=palette.fg,
        bordercolor=palette.border,
        lightcolor=palette.field,
        darkcolor=palette.field,
    )
    style.configure(
        "TNotebook",
        background=palette.bg,
        bordercolor=palette.bg,
        lightcolor=palette.bg,
        darkcolor=palette.bg,
        tabmargins=[0, 0, 0, 0],
    )
    style.configure(
        "TNotebook.Tab",
        background=palette.heading,
        foreground=palette.fg,
        padding=[8, 4],
        bordercolor=palette.heading,
        lightcolor=palette.heading,
        darkcolor=palette.heading,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", palette.field)],
        foreground=[("selected", palette.fg)],
        lightcolor=[("selected", palette.field)],
        darkcolor=[("selected", palette.field)],
        bordercolor=[("selected", palette.field)],
    )
    style.configure(
        "Treeview",
        background=palette.field,
        fieldbackground=palette.field,
        foreground=palette.fg,
        bordercolor=palette.field,
        lightcolor=palette.field,
        darkcolor=palette.field,
        relief="flat",
        borderwidth=0,
        focuscolor=palette.select_bg,
        focusthickness=0,
        rowheight=_rowheight(root),
    )
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.configure(
        "Treeview.Heading",
        background=palette.heading,
        foreground=palette.fg,
        bordercolor=palette.heading,
        lightcolor=palette.heading,
        darkcolor=palette.heading,
        relief="flat",
        borderwidth=0,
    )
    style.layout(
        "Treeview.Heading",
        [
            ("Treeheading.cell", {"sticky": "nswe"}),
            (
                "Treeheading.padding",
                {
                    "sticky": "nswe",
                    "children": [
                        ("Treeheading.image", {"side": "right", "sticky": ""}),
                        ("Treeheading.text", {"sticky": "we"}),
                    ],
                },
            ),
        ],
    )
    style.map(
        "Treeview",
        background=[("selected", palette.select_bg)],
        foreground=[("selected", palette.select_fg)],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", palette.select_bg)],
        foreground=[("active", palette.select_fg)],
    )
    style.configure(
        "TPanedwindow",
        background=palette.bg,
        bordercolor=palette.bg,
        lightcolor=palette.bg,
        darkcolor=palette.bg,
    )
    style.configure(
        "Sash",
        sashthickness=6,
        gripcount=0,
        background=palette.heading,
        lightcolor=palette.heading,
        darkcolor=palette.heading,
        bordercolor=palette.heading,
    )
    _configure_scrollbars(style, palette)
    _colorize_tree(root, palette)


def _configure_scrollbars(style: ttk.Style, palette: Palette) -> None:
    trough = palette.field
    thumb = palette.border
    hover = palette.disabled
    kwargs = {
        "background": thumb,
        "troughcolor": trough,
        "bordercolor": thumb,
        "darkcolor": thumb,
        "lightcolor": thumb,
        "arrowcolor": palette.fg,
        "width": 12,
        "arrowsize": 12,
        "relief": "flat",
        "borderwidth": 0,
        "gripcount": 0,
    }
    maps = {
        "background": [("pressed", hover), ("active", hover), ("disabled", trough)],
        "darkcolor": [("pressed", hover), ("active", hover), ("disabled", trough)],
        "lightcolor": [("pressed", hover), ("active", hover), ("disabled", trough)],
        "bordercolor": [("pressed", hover), ("active", hover), ("disabled", trough)],
        "troughcolor": [("disabled", trough)],
        "arrowcolor": [("disabled", palette.fg)],
    }
    for name in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(name, **kwargs)
        style.map(name, **maps)


def _colorize_tree(widget: tk.Misc, palette: Palette) -> None:
    cls = widget.winfo_class()
    if cls in {"Text", "Listbox", "Entry"}:
        _colorize_text(widget, palette)
    elif cls == "Menu":
        _colorize_menu(widget, palette)
    elif cls in {"Toplevel", "Tk"}:
        with contextlib.suppress(tk.TclError):
            widget.configure(bg=palette.bg)
    try:
        children = widget.winfo_children()
    except tk.TclError:
        return
    for child in children:
        _colorize_tree(child, palette)
    if cls in {"Toplevel", "Tk"}:
        with contextlib.suppress(tk.TclError):
            menu_name = str(widget.cget("menu"))
            if menu_name:
                _colorize_menu(widget.nametowidget(menu_name), palette)


def _colorize_text(widget: tk.Misc, palette: Palette) -> None:
    with contextlib.suppress(tk.TclError):
        widget.configure(
            background=palette.text_bg,
            foreground=palette.text_fg,
            insertbackground=palette.text_fg,
            selectbackground=palette.select_bg,
            selectforeground=palette.select_fg,
            highlightbackground=palette.text_bg,
            highlightcolor=palette.text_bg,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
        )


def _colorize_menu(menu: tk.Misc, palette: Palette) -> None:
    with contextlib.suppress(tk.TclError):
        menu.configure(
            background=palette.bg,
            foreground=palette.fg,
            activebackground=palette.select_bg,
            activeforeground=palette.select_fg,
            selectcolor=palette.fg,
            borderwidth=0,
            relief="flat",
        )
    try:
        end = menu.index("end")
    except tk.TclError:
        return
    if end is None:
        return
    for index in range(int(end) + 1):
        try:
            if menu.type(index) != "cascade":
                continue
            name = str(menu.entrycget(index, "menu"))
        except tk.TclError:
            continue
        if not name:
            continue
        with contextlib.suppress(tk.TclError):
            _colorize_menu(menu.nametowidget(name), palette)
