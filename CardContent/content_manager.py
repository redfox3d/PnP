"""
content_manager.py – ContentManager: the main table window.
Handles loading, saving, filtering, sorting, column management.
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from CardContent.template_parser import (
    parse_template, render_content_text,
    make_default_stat, sync_item_template,
    collect_all_ids, has_broken_refs,
)
from CardContent.window_memory  import wm
from CardContent.content_editor import ContentEditor

# ── Config ─────────────────────────────────────────────────────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))
COLUMNS_FILE = os.path.join(_HERE, "manager_data", "column_config.json")

FILES = {
    "Effect":    os.path.join(_HERE, "cc_data", "effects.json"),
    "Trigger":   os.path.join(_HERE, "cc_data", "triggers.json"),
    "Condition": os.path.join(_HERE, "cc_data", "conditions.json"),
    "Cost":      os.path.join(_HERE, "cc_data", "costs.json"),
}

ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Meta", "Potion", "Skills"]


class ContentManager:

    def __init__(self, root):
        self.root = root
        # root can be a Tk window or an embedded Frame
        if hasattr(self.root, "title"):
            self.root.title("Card Content Manager")
            wm.restore(self.root, "main", "1100x650")

        self.data: dict = {}
        self.load_all()
        self.load_column_config()

        self.sort_directions:    dict       = {}
        self.active_sort_column: str | None = None
        self._drag_col:          str | None = None
        self._drag_col_index:    int | None = None

        self._build_ui()

    # ── Data I/O ───────────────────────────────────────────────────────────────

    def load_all(self):
        for key, filename in FILES.items():
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    self.data[key] = json.load(f).get(key, [])
            else:
                self.data[key] = []

        for items in self.data.values():
            for item in items:
                w = item.setdefault("element_weights", {})
                for el in ELEMENTS:
                    w.setdefault(el, 0)
                item.setdefault("content_box",     item.get("effect_text", ""))
                item.setdefault("content_text",    item.get("effect_text", ""))
                item.setdefault("reminder_text",   "")
                item.setdefault("rarity",          10)
                item.setdefault("complexity_base", 1.0)
                item.setdefault("variables",       {})
                item.setdefault("options",         {})
                item.setdefault("conditions",      {})

    def save_all(self):
        for key, filename in FILES.items():
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({key: self.data[key]}, f, indent=4, ensure_ascii=False)
        self._show_status("Gespeichert ✓")

    def load_column_config(self):
        if os.path.exists(COLUMNS_FILE):
            with open(COLUMNS_FILE, "r") as f:
                self.column_config = json.load(f)
        else:
            self.column_config = {
                "visible_columns": [], "column_order": [], "column_widths": {}
            }
        self.column_config.setdefault("column_order",  [])
        self.column_config.setdefault("column_widths", {})

    def save_column_config(self):
        os.makedirs(os.path.dirname(COLUMNS_FILE), exist_ok=True)
        with open(COLUMNS_FILE, "w") as f:
            json.dump(self.column_config, f, indent=4)

    # ── UI skeleton ────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_toolbar()
        self._build_table()

    def _build_toolbar(self):
        ff = tk.Frame(self.root)
        ff.pack(fill="x", padx=5, pady=4)

        tk.Label(ff, text="Type").pack(side="left")
        self.type_filter = ttk.Combobox(
            ff, values=["All"] + list(FILES.keys()), width=10)
        self.type_filter.set("All")
        self.type_filter.pack(side="left", padx=4)

        tk.Label(ff, text="Min Rarity").pack(side="left")
        self.rarity_filter = tk.Entry(ff, width=5)
        self.rarity_filter.pack(side="left", padx=4)

        tk.Label(ff, text="Search").pack(side="left")
        self.search_filter = tk.Entry(ff, width=22)
        self.search_filter.pack(side="left", padx=4)
        self.search_filter.bind("<Return>", lambda _: self.apply_filters())

        tk.Button(ff, text="Apply", command=self.apply_filters).pack(side="left", padx=4)

        bf = tk.Frame(self.root)
        bf.pack(fill="x", pady=3)

        tk.Button(bf, text="＋ New Content", command=self._open_create_editor,
                  bg="#1a6e3c", fg="white").pack(side="left", padx=6)
        tk.Button(bf, text="Add Column", command=self._add_column).pack(side="left", padx=6)
        tk.Button(bf, text="💾 Save All", command=self.save_all,
                  bg="#1a3e8e", fg="white").pack(side="right", padx=6)

        self.hidden_var  = tk.StringVar()
        self.hidden_menu = ttk.Combobox(bf, textvariable=self.hidden_var, width=16)
        self.hidden_menu.pack(side="left", padx=6)
        self.hidden_menu.bind("<<ComboboxSelected>>", self._unhide_column)
        tk.Label(bf, text="↑ Unhide column").pack(side="left")

    def _build_table(self):
        all_cols  = self._all_columns()
        saved_ord = self.column_config.get("column_order", [])

        if not self.column_config["visible_columns"]:
            self.column_config["visible_columns"] = all_cols

        if saved_ord:
            ordered = [c for c in saved_ord
                       if c in self.column_config["visible_columns"]]
            for c in self.column_config["visible_columns"]:
                if c not in ordered:
                    ordered.append(c)
            self.columns = ordered
        else:
            self.columns = [c for c in all_cols
                            if c in self.column_config["visible_columns"]]

        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(frame, columns=self.columns, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("broken", background="#4a1a1a", foreground="#ff8888")

        self._apply_col_widths()

        self.tree.bind("<Button-1>",        self._header_click)
        self.tree.bind("<Button-3>",        self._col_context_menu)
        self.tree.bind("<Double-1>",        self._open_editor)
        self.tree.bind("<ButtonPress-1>",   self._drag_start,   add="+")
        self.tree.bind("<B1-Motion>",       self._drag_motion,  add="+")
        self.tree.bind("<ButtonRelease-1>", self._drag_release, add="+")
        self.tree.bind("<ButtonRelease-1>", self._save_widths,  add="+")

        self.apply_filters()
        self._update_hidden_dropdown()

    # ── Column helpers ─────────────────────────────────────────────────────────

    def _all_columns(self) -> list:
        cols = ["type", "id", "rarity", "content_box", "content_text", "reminder_text"]
        for items in self.data.values():
            for item in items:
                for k in item:
                    if k not in cols:
                        cols.append(k)
        return cols

    def _compute_col_widths(self) -> dict:
        px, pad = 7, 20
        widths  = {}
        for col in self.columns:
            w = len(col) * px + pad
            for type_name, items in self.data.items():
                for item in items:
                    v = type_name if col == "type" else str(item.get(col, ""))
                    w = max(w, len(v) * px + pad)
            widths[col] = max(60, min(400, w))
        return widths

    def _apply_col_widths(self):
        auto  = self._compute_col_widths()
        saved = self.column_config.get("column_widths", {})
        for col in self.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=saved.get(col, auto.get(col, 120)), minwidth=40)

    # ── Filtering & sorting ────────────────────────────────────────────────────

    def apply_filters(self, sort_col: str | None = None):
        self.tree.delete(*self.tree.get_children())

        sel_type = self.type_filter.get()
        search   = self.search_filter.get().lower()
        try:    min_rar = int(self.rarity_filter.get())
        except: min_rar = None

        all_ids = collect_all_ids(self.data)

        rows = []
        for type_name, items in self.data.items():
            if sel_type != "All" and type_name != sel_type:
                continue
            for item in items:
                if min_rar is not None and item.get("rarity", 0) < min_rar:
                    continue
                if search and not any(
                    search in str(item.get(c, "")).lower()
                    for c in self.columns if c != "type"
                ):
                    continue
                row = [type_name if c == "type" else item.get(c, "")
                       for c in self.columns]
                rows.append((row, item))

        if sort_col and sort_col in self.columns:
            rev = not self.sort_directions.get(sort_col, True)
            ci  = self.columns.index(sort_col)
            def _key(entry):
                try:    return (0, float(entry[0][ci]))
                except: return (1, str(entry[0][ci]).lower())
            rows.sort(key=_key, reverse=rev)

        for row, item in rows:
            iid = self.tree.insert("", "end", values=row)
            if has_broken_refs(item, all_ids):
                self.tree.item(iid, tags=("broken",))

    # ── Sorting ────────────────────────────────────────────────────────────────

    def _header_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "heading":
            return
        ci = int(self.tree.identify_column(event.x).replace("#", "")) - 1
        if ci >= len(self.columns):
            return
        col = self.columns[ci]
        self.sort_directions[col] = not self.sort_directions.get(col, True)
        self.active_sort_column   = col
        self.apply_filters(sort_col=col)
        self._update_sort_headings()

    def _update_sort_headings(self):
        for col in self.columns:
            if col == self.active_sort_column:
                arrow = " ▲" if self.sort_directions.get(col, True) else " ▼"
                self.tree.heading(col, text=col + arrow)
            else:
                self.tree.heading(col, text=col)

    # ── Column drag & drop ─────────────────────────────────────────────────────

    def _drag_start(self, event):
        if self.tree.identify_region(event.x, event.y) != "heading":
            self._drag_col = None; return
        ci = int(self.tree.identify_column(event.x).replace("#", "")) - 1
        self._drag_col_index = ci
        self._drag_col       = self.columns[ci]

    def _drag_motion(self, event):
        if self._drag_col:
            self.tree.config(cursor="fleur")

    def _drag_release(self, event):
        if not self._drag_col:
            return
        self.tree.config(cursor="")
        if self.tree.identify_region(event.x, event.y) != "heading":
            self._drag_col = None; return
        ti = int(self.tree.identify_column(event.x).replace("#", "")) - 1
        if ti != self._drag_col_index and 0 <= ti < len(self.columns):
            col = self.columns.pop(self._drag_col_index)
            self.columns.insert(ti, col)
            self.tree.config(columns=self.columns)
            self._apply_col_widths()
            self.column_config["column_order"] = list(self.columns)
            self.save_column_config()
            self.apply_filters()
            self._update_sort_headings()
        self._drag_col = None

    def _save_widths(self, _=None):
        if not hasattr(self, "tree"):
            return
        self.column_config["column_widths"] = {
            col: self.tree.column(col, "width") for col in self.columns
        }
        self.save_column_config()

    # ── Column menu ────────────────────────────────────────────────────────────

    def _col_context_menu(self, event):
        if self.tree.identify_region(event.x, event.y) != "heading":
            return
        ci  = int(self.tree.identify_column(event.x).replace("#", "")) - 1
        col = self.columns[ci]
        m   = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Hide",   command=lambda: self._hide_col(col))
        m.add_command(label="Rename", command=lambda: self._rename_col(col))
        m.add_command(label="Delete", command=lambda: self._delete_col(col))
        m.post(event.x_root, event.y_root)

    def _hide_col(self, col):
        try: self.column_config["visible_columns"].remove(col)
        except ValueError: pass
        self.save_column_config()
        self._refresh_table()

    def _rename_col(self, old):
        new = simpledialog.askstring("Rename", f"New name for '{old}':")
        if not new or new == old:
            return
        for items in self.data.values():
            for item in items:
                if old in item:
                    item[new] = item.pop(old)
        for lst in ("visible_columns", "column_order"):
            cfg = self.column_config.get(lst, [])
            if old in cfg:
                cfg[cfg.index(old)] = new
        self.save_column_config()
        self._refresh_table()

    def _delete_col(self, col):
        if not messagebox.askyesno("Delete", f"Delete column '{col}'?"):
            return
        for items in self.data.values():
            for item in items:
                item.pop(col, None)
        for lst in ("visible_columns", "column_order"):
            try: self.column_config[lst].remove(col)
            except ValueError: pass
        self.save_column_config()
        self._refresh_table()

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        all_cols  = self._all_columns()
        saved_ord = self.column_config.get("column_order", [])
        if saved_ord:
            ordered = [c for c in saved_ord
                       if c in self.column_config["visible_columns"]]
            for c in self.column_config["visible_columns"]:
                if c not in ordered:
                    ordered.append(c)
            self.columns = ordered
        else:
            self.columns = [c for c in all_cols
                            if c in self.column_config["visible_columns"]]
        self.tree.config(columns=self.columns)
        self._apply_col_widths()
        self.apply_filters()
        self._update_hidden_dropdown()
        self._update_sort_headings()

    def _add_column(self):
        name = simpledialog.askstring("New Column", "Column name:")
        if not name:
            return
        for items in self.data.values():
            for item in items:
                item.setdefault(name, "")
        if name not in self.column_config["visible_columns"]:
            self.column_config["visible_columns"].append(name)
        self.column_config.setdefault("column_order", []).append(name)
        self.save_column_config()
        self._refresh_table()
        self.save_all()

    def _update_hidden_dropdown(self):
        all_cols = self._all_columns()
        self.hidden_menu["values"] = [
            c for c in all_cols
            if c not in self.column_config["visible_columns"]
        ]

    def _unhide_column(self, _=None):
        col = self.hidden_var.get()
        if not col:
            return
        if col not in self.column_config["visible_columns"]:
            self.column_config["visible_columns"].append(col)
        self.column_config.setdefault("column_order", []).append(col)
        self.save_column_config()
        self._refresh_table()
        self.hidden_var.set("")

    # ── Open editors ───────────────────────────────────────────────────────────

    def _open_editor(self, event):
        if self.tree.identify_region(event.x, event.y) == "heading":
            return
        sel = self.tree.focus()
        if not sel:
            return
        vals = self.tree.item(sel)["values"]
        if not vals or len(vals) < 2:
            return
        try:
            type_idx = self.columns.index("type")
            id_idx   = self.columns.index("id")
        except ValueError:
            return
        type_name = vals[type_idx]
        item_id   = str(vals[id_idx])
        try:
            item = next(i for i in self.data[type_name]
                        if str(i.get("id", "")) == item_id)
        except StopIteration:
            return
        ContentEditor(self.root, item, self.data,
                      on_save=lambda: (self._refresh_table(), self.save_all()))

    def _open_create_editor(self):
        win = tk.Toplevel(self.root)
        win.title("New Content")
        wm.restore(win, "create_editor", "560x360")
        win.columnconfigure(1, weight=1)

        fields = [
            ("ID",              "id",              ""),
            ("Content Box",     "content_box",     ""),
            ("Reminder Text",   "reminder_text",   ""),
            ("Rarity",          "rarity",          "10"),
            ("Complexity Base", "complexity_base", "1.0"),
        ]
        entries = {}
        for row, (label, key, default) in enumerate(fields):
            tk.Label(win, text=label).grid(
                row=row, column=0, sticky="w", padx=8, pady=4)
            e = tk.Entry(win, width=48)
            e.insert(0, default)
            e.grid(row=row, column=1, sticky="we", padx=8, pady=4)
            entries[key] = e

        r = len(fields)
        tk.Label(win, text="Type").grid(row=r, column=0, sticky="w", padx=8, pady=4)
        type_box = ttk.Combobox(win, values=list(FILES.keys()),
                                state="readonly", width=16)
        type_box.current(0)
        type_box.grid(row=r, column=1, sticky="w", padx=8, pady=4)

        def _create():
            type_name = type_box.get()
            item_id   = entries["id"].get().strip()
            if not item_id:
                messagebox.showerror("Error", "ID is required."); return
            for existing in self.data.get(type_name, []):
                if existing.get("id") == item_id:
                    messagebox.showerror("Error", "ID already exists."); return

            cb     = entries["content_box"].get()
            parsed = parse_template(cb)
            counter = [0]
            used    = set()

            # NEU:
            def _nid_var():
                while f"{item_id}.v{counter[0]}" in used:
                    counter[0] += 1
                sid = f"{item_id}.v{counter[0]}"
                used.add(sid);
                counter[0] += 1
                return sid

            def _nid_opt():
                while f"{item_id}.o{opt_counter[0]}" in used:
                    opt_counter[0] += 1
                sid = f"{item_id}.o{opt_counter[0]}"
                used.add(sid);
                opt_counter[0] += 1
                return sid

            new_item = {
                "id":              item_id,
                "content_box":     cb,
                "content_text":    render_content_text(cb, {}, {}),
                "reminder_text":   entries["reminder_text"].get(),
                "rarity":          int(entries["rarity"].get() or 10),
                "complexity_base": float(entries["complexity_base"].get() or 1.0),
                "element_weights": {el: 0 for el in ELEMENTS},
                "conditions":      {},
                "variables": {
                    v: make_default_stat(_nid_var()) for v in parsed["variables"]
                },
                "options": {
                    str(i): {
                        "choices": choices,
                        "per_choice": {
                            c: make_default_stat(_nid_opt()) for c in choices
                        },
                    }
                    for i, choices in enumerate(parsed["options"])
                },
            }
            self.data[type_name].append(new_item)
            self._refresh_table()
            self.save_all()
            win.destroy()
            # Direkt den vollen Editor öffnen
            ContentEditor(self.root, new_item, self.data,
                          on_save=lambda: (self._refresh_table(), self.save_all()))

        tk.Button(win, text="Create", command=_create,
                  bg="#1a6e3c", fg="white", width=16).grid(
            row=r + 1, column=0, columnspan=2, pady=14)

    # ── Status bar ─────────────────────────────────────────────────────────────

    def _show_status(self, msg: str, ms: int = 2000):
        bar = tk.Label(self.root, text=msg, bg="#1a6e3c", fg="white",
                       font=("Arial", 11, "bold"))
        bar.pack(side="top", fill="x")
        self.root.after(ms, bar.destroy)