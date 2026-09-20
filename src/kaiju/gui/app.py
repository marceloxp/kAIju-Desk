from __future__ import annotations

import contextlib
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from kaiju import __version__
from kaiju.cards import Card
from kaiju.errors import KaijuError
from kaiju.gui.recents import load_recents, remember_workspace
from kaiju.gui.session import (
    CANONICAL,
    FILTER_ALL,
    FILTER_BACKLOG,
    FILTER_CLOSED,
    FILTER_EPIC,
    FILTER_EPICS,
    FILTER_OPEN,
    TABLE_COLUMNS,
    TABLE_HEADINGS,
    FileNode,
    NavItem,
    Preview,
    Session,
    card_file_tree,
    is_canonical,
    read_preview,
    table_values,
)


def run_app(start: Path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise KaijuError(f"could not open display ({exc})") from exc
    _configure_fonts(root)
    App(root, start)
    root.mainloop()


class App:
    def __init__(self, root: tk.Tk, start: Path) -> None:
        self.root = root
        self.session = Session()
        self._current_card: Card | None = None
        self._texts: dict[str, ScrolledText] = {}
        self._extra: tuple[tk.Misc, ScrolledText] | None = None
        self._busy = False
        self._file_nodes: dict[str, FileNode] = {}
        self._build()
        self._open_path(start, warn=False)

    def _build(self) -> None:
        self.root.title("kAIju")
        self.root.minsize(800, 500)
        self.root.geometry("1100x700")
        self._build_menu()
        self._build_toolbar()
        self.status = ttk.Label(self.root, text="", anchor="w", padding=(8, 4), relief="sunken")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        self.outer = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.empty_body = ttk.Frame(self.root, padding=24)
        self._build_empty()

        nav_frame = ttk.Frame(self.outer, padding=4)
        right = ttk.Panedwindow(self.outer, orient=tk.VERTICAL)
        self.outer.add(nav_frame, weight=0)
        self.outer.add(right, weight=1)

        self.nav = ttk.Treeview(
            nav_frame,
            columns=("kind", "epic"),
            show="tree",
            selectmode="browse",
            displaycolumns=(),
        )
        self.nav.column("#0", stretch=True)
        nav_scroll = ttk.Scrollbar(nav_frame, orient=tk.VERTICAL, command=self.nav.yview)
        self.nav.configure(yscrollcommand=nav_scroll.set)
        self.nav.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nav_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.nav.bind("<<TreeviewSelect>>", self._on_nav_select)

        table_frame = ttk.Frame(right, padding=4)
        bottom = ttk.Panedwindow(right, orient=tk.HORIZONTAL)
        right.add(table_frame, weight=1)
        right.add(bottom, weight=1)
        self.bottom = bottom

        self.table = ttk.Treeview(
            table_frame,
            columns=TABLE_COLUMNS,
            show="headings",
            selectmode="browse",
        )
        widths = {
            "card": 90,
            "title": 280,
            "status": 100,
            "epic": 90,
            "parent": 90,
            "created_at": 100,
            "closed_at": 100,
        }
        for col in TABLE_COLUMNS:
            self.table.heading(col, text=TABLE_HEADINGS[col])
            self.table.column(col, width=widths[col], stretch=(col == "title"))
        table_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.table.yview)
        self.table.configure(yscrollcommand=table_scroll.set)
        self.table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.table.bind("<<TreeviewSelect>>", self._on_table_select)

        preview_frame = ttk.Frame(bottom, padding=4)
        files_frame = ttk.Frame(bottom, padding=4)
        bottom.add(preview_frame, weight=1)
        bottom.add(files_frame, weight=0)

        self.notebook = ttk.Notebook(preview_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        for name in CANONICAL:
            frame = ttk.Frame(self.notebook)
            text = _make_text(frame)
            text.pack(fill=tk.BOTH, expand=True)
            self.notebook.add(frame, text=name)
            self._texts[name] = text
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        ttk.Label(files_frame, text="Files").pack(anchor="w")
        files_body = ttk.Frame(files_frame)
        files_body.pack(fill=tk.BOTH, expand=True)
        self.files = ttk.Treeview(
            files_body,
            columns=("relpath", "isdir"),
            show="tree",
            selectmode="browse",
            displaycolumns=(),
        )
        self.files.column("#0", stretch=True)
        files_scroll = ttk.Scrollbar(files_body, orient=tk.VERTICAL, command=self.files.yview)
        self.files.configure(yscrollcommand=files_scroll.set)
        self.files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        files_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.files.bind("<<TreeviewSelect>>", self._on_file_select)

        self.root.bind("<Control-o>", lambda _e: self._choose_workspace())
        self.root.bind("<F5>", lambda _e: self._refresh())
        self.root.bind("<Control-q>", lambda _e: self.root.destroy())

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Open Workspace…",
            command=self._choose_workspace,
            accelerator="Ctrl+O",
        )
        self._recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Recent Workspaces", menu=self._recent_menu)
        file_menu.add_command(label="Refresh", command=self._refresh, accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About kAIju", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self._file_menu = file_menu
        self.root.config(menu=menubar)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(bar, text="Open Workspace…", command=self._choose_workspace).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        self._refresh_btn = ttk.Button(bar, text="Refresh", command=self._refresh)
        self._refresh_btn.pack(side=tk.LEFT)

    def _build_empty(self) -> None:
        ttk.Label(
            self.empty_body,
            text="No workspace open.",
        ).pack(anchor="w")
        ttk.Label(
            self.empty_body,
            text="Open a folder that contains kaiju.toml, or pick a recent workspace.",
        ).pack(anchor="w", pady=(4, 0))
        self.empty_recents = ttk.Frame(self.empty_body)
        self.empty_recents.pack(anchor="w", fill=tk.X, pady=(16, 0))

    def _place_sashes(self) -> None:
        try:
            self.outer.sashpos(0, 220)
            width = self.bottom.winfo_width()
            if width > 1:
                self.bottom.sashpos(0, max(200, width - 240))
        except tk.TclError:
            pass

    def _set_workspace_visible(self, show: bool) -> None:
        if show:
            self.empty_body.pack_forget()
            self.outer.pack(fill=tk.BOTH, expand=True)
            self._refresh_btn.state(["!disabled"])
            self._file_menu.entryconfig("Refresh", state=tk.NORMAL)
            self.root.after_idle(self._place_sashes)
        else:
            self.outer.pack_forget()
            self.empty_body.pack(fill=tk.BOTH, expand=True)
            self._refresh_btn.state(["disabled"])
            self._file_menu.entryconfig("Refresh", state=tk.DISABLED)

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.delete(0, tk.END)
        recents = load_recents()
        if not recents:
            self._recent_menu.add_command(label="(none)", state=tk.DISABLED)
            return
        for path in recents:
            self._recent_menu.add_command(
                label=path.as_posix(),
                command=lambda p=path: self._open_path(p, warn=True),
            )

    def _fill_empty_recents(self) -> None:
        for child in self.empty_recents.winfo_children():
            child.destroy()
        recents = load_recents()
        if not recents:
            return
        ttk.Label(self.empty_recents, text="Recent workspaces").pack(anchor="w")
        for path in recents:
            ttk.Button(
                self.empty_recents,
                text=path.as_posix(),
                command=lambda p=path: self._open_path(p, warn=True),
            ).pack(anchor="w", pady=(4, 0))

    def _about(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("About kAIju")
        win.transient(self.root)
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=16)
        frame.pack()
        img_path = Path(__file__).with_name("about.png")
        if img_path.is_file():
            try:
                photo = tk.PhotoImage(file=str(img_path))
            except tk.TclError:
                photo = None
            if photo is not None:
                win._about_photo = photo  # type: ignore[attr-defined]
                ttk.Label(frame, image=photo).pack(pady=(0, 12))
        ttk.Label(frame, text=f"kAIju-Desk {__version__}").pack()
        ttk.Label(
            frame,
            text="A work contract between human and AI that lives in the folder.",
            wraplength=320,
            justify="center",
        ).pack(pady=(4, 12))
        ttk.Button(frame, text="OK", command=win.destroy).pack()
        win.grab_set()

    def _choose_workspace(self) -> None:
        initial = (
            str(self.session.workspace.root)
            if self.session.workspace is not None
            else str(Path.cwd())
        )
        chosen = filedialog.askdirectory(parent=self.root, initialdir=initial)
        if not chosen:
            return
        self._open_path(Path(chosen), warn=True)

    def _open_path(self, start: Path, *, warn: bool) -> None:
        ok = self.session.open(start)
        if ok and self.session.workspace is not None:
            remember_workspace(self.session.workspace.root)
        if not ok and warn and self.session.error:
            messagebox.showerror("kAIju", self.session.error, parent=self.root)
        self._rebuild()

    def _refresh(self) -> None:
        selected = self._selected_card_code()
        self.session.refresh()
        self._rebuild(keep_card=selected)

    def _rebuild(self, keep_card: str | None = None) -> None:
        has_ws = self.session.workspace is not None
        self._set_workspace_visible(has_ws)
        self._rebuild_recent_menu()
        if not has_ws:
            self._fill_empty_recents()
            self.root.title("kAIju")
            self._set_status(self._default_status())
            return
        self._busy = True
        try:
            self._current_card = None
            self._clear_extra_tab()
            self._fill_nav()
            nav_key = self._nav_key()
            if self.nav.exists(nav_key):
                self.nav.selection_set(nav_key)
                self.nav.focus(nav_key)
            self._fill_table()
            self._clear_preview()
            self._clear_files()
            name = self.session.workspace.config.name
            self.root.title(f"kAIju — {name}")
            if self.session.filter_kind == FILTER_BACKLOG:
                self._show_backlog()
            else:
                card_code = keep_card
                if card_code is None:
                    cards = self.session.filtered_cards()
                    card_code = cards[0].code if cards else None
                if card_code:
                    self._select_card(card_code)
                else:
                    self._set_status(self._default_status())
        finally:
            self._busy = False

    def _nav_key(self) -> str:
        kind = self.session.filter_kind
        if kind == FILTER_EPIC and self.session.epic_code:
            return f"epic:{self.session.epic_code}"
        return {
            FILTER_ALL: "all",
            FILTER_OPEN: "open",
            FILTER_CLOSED: "closed",
            FILTER_EPICS: "epics",
            FILTER_BACKLOG: "backlog",
        }.get(kind, "all")

    def _fill_nav(self) -> None:
        self.nav.delete(*self.nav.get_children())
        tree = self.session.nav_tree()
        if tree is None:
            return
        self._insert_nav("", tree, open_=True)

    def _insert_nav(self, parent: str, item: NavItem, *, open_: bool) -> None:
        self.nav.insert(
            parent,
            "end",
            iid=item.key,
            text=item.label,
            values=(item.kind, item.epic_code),
            open=open_,
        )
        for child in item.children:
            self._insert_nav(item.key, child, open_=(child.key == "epics"))

    def _fill_table(self) -> None:
        self.table.delete(*self.table.get_children())
        for card in self.session.filtered_cards():
            self.table.insert("", "end", iid=card.code, values=table_values(card))

    def _on_nav_select(self, _event=None) -> None:
        if self._busy:
            return
        sel = self.nav.selection()
        if not sel:
            return
        iid = sel[0]
        kind, epic = self.nav.item(iid, "values")
        self.session.select_nav(kind, epic)
        self._busy = True
        try:
            self._fill_table()
            self._current_card = None
            self._clear_extra_tab()
            if kind == FILTER_BACKLOG:
                self._show_backlog()
            else:
                self._clear_preview()
                self._clear_files()
                cards = self.session.filtered_cards()
                if cards:
                    self.table.selection_set(cards[0].code)
                    self.table.focus(cards[0].code)
                    self._show_card(cards[0])
                else:
                    self._set_status(self._default_status())
        finally:
            self._busy = False

    def _on_table_select(self, _event=None) -> None:
        if self._busy:
            return
        code = self._selected_card_code()
        if not code:
            return
        card = self.session.card_by_code(code)
        if card is None:
            return
        self._show_card(card)

    def _selected_card_code(self) -> str | None:
        sel = self.table.selection()
        if not sel:
            return None
        return sel[0]

    def _select_card(self, code: str) -> None:
        if self.table.exists(code):
            self.table.selection_set(code)
            self.table.focus(code)
            self.table.see(code)
            card = self.session.card_by_code(code)
            if card is not None:
                self._show_card(card)

    def _show_card(self, card: Card) -> None:
        self._current_card = card
        self._clear_extra_tab()
        for name in CANONICAL:
            preview = read_preview(card.path / name)
            _set_text(self._texts[name], preview.text)
        self._fill_files(card)
        self.notebook.select(0)
        self._set_status(self._card_status(card))

    def _show_backlog(self) -> None:
        self._clear_preview()
        self._clear_files()
        path = self.session.backlog_path()
        if path is None:
            return
        preview = read_preview(path)
        self._set_extra_tab("BACKLOG.md", preview)
        self._set_status(self._compose_status("Backlog", preview.message))

    def _fill_files(self, card: Card) -> None:
        self.files.delete(*self.files.get_children())
        self._file_nodes = {}
        root = card_file_tree(card)
        self._insert_file("", root, open_=True)

    def _insert_file(self, parent: str, node: FileNode, *, open_: bool) -> str:
        iid = self.files.insert(
            parent,
            "end",
            text=node.name,
            values=(node.relpath, "1" if node.is_dir else "0"),
            open=open_,
        )
        self._file_nodes[iid] = node
        for child in node.children:
            self._insert_file(iid, child, open_=True)
        return iid

    def _on_file_select(self, _event=None) -> None:
        if self._busy or self._current_card is None:
            return
        sel = self.files.selection()
        if not sel:
            return
        node = self._file_nodes.get(sel[0])
        if node is None or node.is_dir:
            return
        relpath = node.relpath
        path = self._current_card.path / relpath
        if is_canonical(relpath):
            index = CANONICAL.index(relpath)
            self.notebook.select(index)
            self._set_status(self._card_status(self._current_card, tab=relpath))
            return
        preview = read_preview(path)
        if preview.text == "" and preview.message:
            self._set_status(self._card_status(self._current_card, extra=preview.message))
            return
        self._set_extra_tab(node.name, preview)
        self._set_status(self._card_status(self._current_card, extra=preview.message))

    def _on_tab_changed(self, _event=None) -> None:
        if self._busy:
            return
        if self._current_card is None:
            return
        tab = self._current_tab_name()
        if tab in CANONICAL:
            self._set_status(self._card_status(self._current_card, tab=tab))

    def _current_tab_name(self) -> str:
        try:
            frame = self.notebook.nametowidget(self.notebook.select())
        except tk.TclError:
            return ""
        return self.notebook.tab(frame, "text")

    def _set_extra_tab(self, title: str, preview: Preview) -> None:
        if self._extra is not None:
            frame, text = self._extra
            self.notebook.tab(frame, text=title)
            _set_text(text, preview.text)
            self.notebook.select(frame)
            return
        frame = ttk.Frame(self.notebook)
        text = _make_text(frame)
        text.pack(fill=tk.BOTH, expand=True)
        _set_text(text, preview.text)
        self.notebook.add(frame, text=title)
        self.notebook.select(frame)
        self._extra = (frame, text)

    def _clear_extra_tab(self) -> None:
        if self._extra is None:
            return
        frame, _text = self._extra
        self.notebook.forget(frame)
        frame.destroy()
        self._extra = None

    def _clear_preview(self) -> None:
        for text in self._texts.values():
            _set_text(text, "")

    def _clear_files(self) -> None:
        self.files.delete(*self.files.get_children())
        self._file_nodes = {}

    def _default_status(self) -> str:
        if self.session.workspace is None:
            return self.session.error or "No workspace — File > Open Workspace…"
        return self.session.workspace.config.name

    def _card_status(self, card: Card, *, tab: str | None = None, extra: str = "") -> str:
        bits = [self._workspace_name(), card.code, card.status]
        name = tab if tab is not None else self._current_tab_name()
        if name in CANONICAL:
            preview = read_preview(card.path / name)
            if preview.message:
                bits.append(preview.message)
        if extra:
            bits.append(extra)
        return self._join_status(bits)

    def _compose_status(self, current: str, message: str) -> str:
        bits = [self._workspace_name(), current]
        if message:
            bits.append(message)
        return self._join_status(bits)

    def _workspace_name(self) -> str:
        if self.session.workspace is None:
            return "kAIju"
        return self.session.workspace.config.name

    def _join_status(self, bits: list[str]) -> str:
        return " · ".join(bit for bit in bits if bit)

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)


def _make_text(parent: tk.Misc) -> ScrolledText:
    widget = ScrolledText(
        parent,
        wrap="word",
        font="TkFixedFont",
        borderwidth=0,
        highlightthickness=0,
        undo=False,
    )
    widget.bind("<Key>", _readonly_key)
    widget.bind("<<Paste>>", lambda _e: "break")
    widget.bind("<<Cut>>", lambda _e: "break")
    widget.bind("<<PasteSelection>>", lambda _e: "break")
    widget.bind("<Control-a>", _select_all)
    widget.bind("<Control-A>", _select_all)
    return widget


def _readonly_key(event: tk.Event) -> str | None:
    if event.keysym in {
        "Left",
        "Right",
        "Up",
        "Down",
        "Home",
        "End",
        "Prior",
        "Next",
        "Shift_L",
        "Shift_R",
        "Control_L",
        "Control_R",
        "Alt_L",
        "Alt_R",
        "Meta_L",
        "Meta_R",
        "Caps_Lock",
        "Num_Lock",
        "Tab",
        "ISO_Left_Tab",
        "Escape",
    }:
        return None
    if event.state & 0x4 and event.keysym.lower() in {"a", "c"}:
        return None
    return "break"


def _select_all(event: tk.Event) -> str:
    widget = event.widget
    widget.tag_add("sel", "1.0", "end-1c")
    widget.mark_set("insert", "1.0")
    widget.see("insert")
    return "break"


def _configure_fonts(root: tk.Tk) -> None:
    families = set(tkfont.families(root))
    ui = _first_family(
        families,
        ("DejaVu Sans", "Noto Sans", "Liberation Sans", "Ubuntu", "Cantarell", "Sans"),
    )
    mono = _first_family(
        families,
        ("DejaVu Sans Mono", "Noto Sans Mono", "Liberation Mono", "Ubuntu Mono", "Monospace"),
    )
    size = 10
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        try:
            tkfont.nametofont(name).configure(family=ui, size=size)
        except tk.TclError:
            continue
    with contextlib.suppress(tk.TclError):
        tkfont.nametofont("TkFixedFont").configure(family=mono, size=size)
    style = ttk.Style(root)
    rowheight = 24
    style.configure(".", font=(ui, size))
    style.configure("Treeview", font=(ui, size), rowheight=rowheight)
    style.configure("Treeview.Heading", font=(ui, size))
    style.configure("TLabel", font=(ui, size))
    style.configure("TButton", font=(ui, size))


def _first_family(families: set[str], wanted: tuple[str, ...]) -> str:
    available = {name.casefold(): name for name in families}
    for name in wanted:
        match = available.get(name.casefold())
        if match is not None:
            return match
    return wanted[-1]


def _set_text(widget: ScrolledText, content: str) -> None:
    widget.delete("1.0", "end")
    widget.insert("1.0", content)
