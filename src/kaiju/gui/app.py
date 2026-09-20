from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from kaiju.cards import Card
from kaiju.errors import KaijuError
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
        self.outer.pack(fill=tk.BOTH, expand=True)

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
        self.root.after_idle(self._place_sashes)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Open Workspace…",
            command=self._choose_workspace,
            accelerator="Ctrl+O",
        )
        file_menu.add_command(label="Refresh", command=self._refresh, accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Refresh", command=self._refresh, accelerator="F5")
        menubar.add_cascade(label="View", menu=view_menu)
        self.root.config(menu=menubar)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(bar, text="Open Workspace…", command=self._choose_workspace).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(bar, text="Refresh", command=self._refresh).pack(side=tk.LEFT)

    def _place_sashes(self) -> None:
        try:
            self.outer.sashpos(0, 220)
            width = self.bottom.winfo_width()
            if width > 1:
                self.bottom.sashpos(0, max(200, width - 240))
        except tk.TclError:
            pass

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
        if not ok and warn and self.session.error:
            messagebox.showerror("kAIju", self.session.error, parent=self.root)
        self._rebuild()

    def _refresh(self) -> None:
        selected = self._selected_card_code()
        self.session.refresh()
        self._rebuild(keep_card=selected)

    def _rebuild(self, keep_card: str | None = None) -> None:
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
            name = self.session.workspace.config.name if self.session.workspace else "kAIju"
            self.root.title(f"kAIju — {name}" if self.session.workspace else "kAIju")
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
        state="disabled",
        font="TkFixedFont",
        borderwidth=0,
        highlightthickness=0,
    )
    return widget


def _set_text(widget: ScrolledText, content: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", content)
    widget.configure(state="disabled")
