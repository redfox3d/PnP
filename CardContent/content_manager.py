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
from CardContent.window_memory     import wm
from CardContent.content_editor    import ContentEditor
from CardContent.effect_type_panel import EffectTypePanel

# ── Config ─────────────────────────────────────────────────────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))
COLUMNS_FILE = os.path.join(_HERE, "manager_data", "column_config.json")

FILES = {
    "Effect":    os.path.join(_HERE, "cc_data", "effects.json"),
    "Trigger":   os.path.join(_HERE, "cc_data", "triggers.json"),
    "Condition": os.path.join(_HERE, "cc_data", "conditions.json"),
    "Cost":      os.path.join(_HERE, "cc_data", "costs.json"),
    "Insert":    os.path.join(_HERE, "cc_data", "inserts.json"),
}


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
                item.setdefault("element_weights", {})
                item.setdefault("sigil",           "")
                item.setdefault("content_text",    "")
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

        # I: Element filter — filters items whose element_weights have a non-zero
        #    weight for the chosen element. "All" disables the filter.
        tk.Label(ff, text="Element").pack(side="left")
        try:
            from card_builder.constants import ELEMENTS as _ELEMENTS
        except Exception:
            _ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Quinta"]
        self.element_filter = ttk.Combobox(
            ff, values=["All"] + list(_ELEMENTS), width=8, state="readonly")
        self.element_filter.set("All")
        self.element_filter.pack(side="left", padx=4)
        self.element_filter.bind("<<ComboboxSelected>>",
                                  lambda _: self.apply_filters())

        tk.Label(ff, text="Search").pack(side="left")
        self.search_filter = tk.Entry(ff, width=22)
        self.search_filter.pack(side="left", padx=4)
        self.search_filter.bind("<Return>", lambda _: self.apply_filters())

        tk.Button(ff, text="Apply", command=self.apply_filters).pack(side="left", padx=4)

        bf = tk.Frame(self.root)
        bf.pack(fill="x", pady=3)

        tk.Button(bf, text="＋ New Content", command=self._open_create_editor,
                  bg="#1a6e3c", fg="white").pack(side="left", padx=6)
        tk.Button(bf, text="🗑 Delete", command=self._delete_selected,
                  bg="#6e1a1a", fg="white").pack(side="left", padx=6)
        tk.Button(bf, text="Add Column", command=self._add_column).pack(side="left", padx=6)
        tk.Button(bf, text="Effekt Typen", command=self._open_effect_types,
                  bg="#3a1a5a", fg="#cc88ff",
                  font=("Arial", 8, "bold")).pack(side="left", padx=6)
        # B3: central sigil management (add/remove propagates everywhere)
        tk.Button(bf, text="Sigils…", command=self._open_sigil_manager,
                  bg="#1a3a5a", fg="#88ccff",
                  font=("Arial", 8, "bold")).pack(side="left", padx=6)
        # C2: damage-type ranking editor
        tk.Button(bf, text="Damage Types…", command=self._open_damage_types_manager,
                  bg="#5a1a1a", fg="#ff8888",
                  font=("Arial", 8, "bold")).pack(side="left", padx=6)
        # L: interactable registry editor
        tk.Button(bf, text="Interactables…",
                  command=self._open_interactable_manager,
                  bg="#1a4a3a", fg="#88eecc",
                  font=("Arial", 8, "bold")).pack(side="left", padx=6)
        # B): sigil rules editor (cross-sigil constraints)
        tk.Button(bf, text="Sigil Rules…",
                  command=self._open_sigil_rules_editor,
                  bg="#3a3a1a", fg="#ffcc66",
                  font=("Arial", 8, "bold")).pack(side="left", padx=6)
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
        cols = ["type", "id", "rarity", "sigil", "content_text", "reminder_text"]
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
        # I: element filter
        sel_elem = getattr(self, "element_filter", None)
        sel_elem = sel_elem.get() if sel_elem is not None else "All"

        all_ids = collect_all_ids(self.data)

        rows = []
        for type_name, items in self.data.items():
            if sel_type != "All" and type_name != sel_type:
                continue
            for item in items:
                if min_rar is not None and item.get("rarity", 0) < min_rar:
                    continue
                # I: element filter — keep only items whose element_weights
                #    for the chosen element are > 0 AND the element is not
                #    listed as disabled in element_enabled.
                if sel_elem and sel_elem != "All":
                    ew = item.get("element_weights", {})
                    if ew:
                        try:
                            if float(ew.get(sel_elem, 0)) <= 0:
                                continue
                        except (TypeError, ValueError):
                            continue
                    disabled = item.get("element_enabled", {})
                    if isinstance(disabled, dict) and \
                       disabled.get(sel_elem) is False:
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

    def _open_effect_types(self):
        EffectTypePanel(self.root, self.data,
                        on_save=lambda: (self.load_all(), self._refresh_table()))

    def _open_sigil_manager(self):
        """Full Sigil Manager: list of sigils on the left, properties /
        per-card-type weights / labels / incompatibility on the right.

        Single source of truth: ``cc_data/box_config.json``.
        """
        from CardContent.sigil_manager import SigilManagerDialog
        dlg = SigilManagerDialog(self.root,
                                  on_close=lambda: (self.load_all(),
                                                     self._refresh_table()))
        dlg.transient(self.root)

    # ── C2: Damage-Type Ranking Editor ────────────────────────────────────────
    def _open_damage_types_manager(self):
        """C2: Damage-Type editor.

        Left column  – list of damage types (add/remove).
        Right column – Notebook with one tab per Element and one for Prowess
                       Cards (sub-dropdown). Each tab shows a rank-grid
                       (rank 0 .. max_ranks-1); each rank holds any number of
                       {type, cv} entries with weight 1/2**k.
        """
        try:
            from CardContent import damage_registry as dreg
        except Exception as e:
            messagebox.showerror("Damage Types", f"Could not import damage_registry: {e}")
            return

        ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Quinta"]

        dlg = tk.Toplevel(self.root)
        dlg.title("Damage Types verwalten")
        dlg.geometry("780x520")
        dlg.transient(self.root)

        outer = tk.Frame(dlg); outer.pack(fill="both", expand=True, padx=6, pady=6)

        # ── Left: damage-type list ────────────────────────────────────────────
        left = tk.LabelFrame(outer, text="Damage Types")
        left.pack(side="left", fill="y", padx=4)

        lb = tk.Listbox(left, height=14, width=18, exportselection=False)
        lb.pack(side="top", fill="y", padx=4, pady=4)

        def _refresh_types():
            lb.delete(0, tk.END)
            for n in dreg.list_damage_types():
                lb.insert(tk.END, n)
        _refresh_types()

        type_entry_row = tk.Frame(left); type_entry_row.pack(fill="x", padx=4, pady=2)
        new_type_var = tk.StringVar()
        tk.Entry(type_entry_row, textvariable=new_type_var, width=12).pack(side="left")

        def _add_type():
            n = new_type_var.get().strip()
            if not n:
                return
            if dreg.add_type(n):
                new_type_var.set("")
                _refresh_types()
                _refresh_section()  # combobox lists may need refresh

        def _del_type():
            sel = lb.curselection()
            if not sel:
                return
            n = lb.get(sel[0])
            if not messagebox.askyesno("Damage Type löschen",
                                        f"'{n}' wirklich entfernen?\n"
                                        f"(wird aus allen Rankings gelöscht)"):
                return
            dreg.remove_type(n)
            _refresh_types()
            _refresh_section()

        type_btn_row = tk.Frame(left); type_btn_row.pack(fill="x", padx=4, pady=2)
        tk.Button(type_btn_row, text="+", width=3, command=_add_type,
                  bg="#1a6e3c", fg="white").pack(side="left", padx=2)
        tk.Button(type_btn_row, text="✕", width=3, command=_del_type,
                  bg="#6e1a1a", fg="white").pack(side="left", padx=2)

        # ── Range constraints for the selected damage type ────────────────────
        rng_box = tk.LabelFrame(left, text="Range gültig für")
        rng_box.pack(fill="x", padx=4, pady=(8, 4))

        rng_min_var = tk.StringVar()
        rng_max_var = tk.StringVar()

        rng_row = tk.Frame(rng_box); rng_row.pack(fill="x", padx=4, pady=2)
        tk.Label(rng_row, text="min:").pack(side="left")
        tk.Entry(rng_row, textvariable=rng_min_var, width=4
                  ).pack(side="left", padx=2)
        tk.Label(rng_row, text="max:").pack(side="left")
        tk.Entry(rng_row, textvariable=rng_max_var, width=4
                  ).pack(side="left", padx=2)
        tk.Label(rng_box, text="leer = ohne Begrenzung",
                  fg="#888", font=("Arial", 8, "italic")
                  ).pack(anchor="w", padx=4)

        def _on_lb_select(_e=None):
            sel = lb.curselection()
            if not sel:
                rng_min_var.set(""); rng_max_var.set(""); return
            t = lb.get(sel[0])
            mn, mx = dreg.get_range_for_type(t)
            rng_min_var.set("" if mn == 0 else str(mn))
            rng_max_var.set("" if mx == 99 else str(mx))
        lb.bind("<<ListboxSelect>>", _on_lb_select)

        def _save_range(*_):
            sel = lb.curselection()
            if not sel:
                return
            t = lb.get(sel[0])
            def _parse(s):
                s = s.strip()
                if not s: return None
                try: return int(s)
                except ValueError: return None
            dreg.set_range_for_type(t,
                                      _parse(rng_min_var.get()),
                                      _parse(rng_max_var.get()))
        rng_min_var.trace_add("write", _save_range)
        rng_max_var.trace_add("write", _save_range)

        # ── Right: per-element / per-prowess tabs ─────────────────────────────
        right = tk.Frame(outer); right.pack(side="left", fill="both", expand=True, padx=4)
        nb = ttk.Notebook(right); nb.pack(fill="both", expand=True)

        # State: { (section, key) : ranks_data }
        # ranks_data is list[list[dict{type,cv}]]; we mutate then save on demand.
        editing_state: dict = {}
        tab_widgets: dict = {}  # (section,key) -> rebuild callback

        def _make_section_tab(section: str, key: str, title: str | None = None):
            page = tk.Frame(nb)
            nb.add(page, text=title or key)
            ranks_var = list(dreg.get_rankings(key, section=section))
            # ensure list of lists of dicts
            ranks_var = [[dict(e) for e in rk] for rk in ranks_var]
            editing_state[(section, key)] = ranks_var

            grid_frame = tk.Frame(page); grid_frame.pack(fill="both", expand=True,
                                                         padx=6, pady=6)

            def _rebuild():
                for w in grid_frame.winfo_children():
                    w.destroy()
                max_rk = dreg.max_ranks()
                tk.Label(grid_frame,
                         text=f"Section: {section} / Key: {key}   "
                              f"(rank k → weight 1/2^k)",
                         font=("Arial", 9, "italic")).pack(anchor="w")

                ranks = editing_state[(section, key)]
                # pad to max_rk
                while len(ranks) < max_rk:
                    ranks.append([])

                for k in range(max_rk):
                    rk_frame = tk.LabelFrame(grid_frame,
                                             text=f"Rank {k}  (weight {1/(2**k):.4f})")
                    rk_frame.pack(fill="x", pady=3)

                    entries = ranks[k]
                    for idx, entry in enumerate(list(entries)):
                        row = tk.Frame(rk_frame); row.pack(fill="x", padx=4, pady=1)
                        type_var = tk.StringVar(value=entry.get("type", ""))
                        cv_var   = tk.StringVar(value=str(entry.get("cv", 1.0)))
                        cb = ttk.Combobox(row, textvariable=type_var, width=14,
                                          values=dreg.list_damage_types(),
                                          state="readonly")
                        cb.pack(side="left", padx=2)
                        tk.Label(row, text="cv:").pack(side="left")
                        ce = tk.Entry(row, textvariable=cv_var, width=6)
                        ce.pack(side="left", padx=2)

                        def _on_type_change(_e=None, kk=k, ii=idx, tv=type_var):
                            editing_state[(section, key)][kk][ii]["type"] = tv.get()
                        def _on_cv_change(_e=None, kk=k, ii=idx, cv=cv_var):
                            try:
                                editing_state[(section, key)][kk][ii]["cv"] = \
                                    float(cv.get())
                            except ValueError:
                                pass
                        cb.bind("<<ComboboxSelected>>", _on_type_change)
                        ce.bind("<FocusOut>", _on_cv_change)
                        ce.bind("<Return>",   _on_cv_change)

                        def _del_entry(kk=k, ii=idx):
                            editing_state[(section, key)][kk].pop(ii)
                            _rebuild()
                        tk.Button(row, text="✕", width=2,
                                  command=_del_entry,
                                  bg="#6e1a1a", fg="white").pack(side="left", padx=2)

                    def _add_entry(kk=k):
                        types = dreg.list_damage_types()
                        default_type = types[0] if types else ""
                        editing_state[(section, key)][kk].append(
                            {"type": default_type, "cv": 1.0})
                        _rebuild()
                    tk.Button(rk_frame, text="+ Eintrag", command=_add_entry,
                              bg="#1a6e3c", fg="white").pack(anchor="w",
                                                              padx=4, pady=2)

                # Save / reset row
                btns = tk.Frame(grid_frame); btns.pack(fill="x", pady=6)

                def _save():
                    # strip empty entries
                    ranks = [[e for e in rk
                              if e.get("type") and float(e.get("cv", 1)) != 0]
                             for rk in editing_state[(section, key)]]
                    # trim trailing empty ranks
                    while ranks and not ranks[-1]:
                        ranks.pop()
                    dreg.set_rankings(key, ranks, section=section)
                    messagebox.showinfo("Damage Types",
                                         f"{section}/{key}: gespeichert "
                                         f"({sum(len(r) for r in ranks)} entries).")

                def _reset_from_disk():
                    fresh = dreg.get_rankings(key, section=section)
                    editing_state[(section, key)] = \
                        [[dict(e) for e in rk] for rk in fresh]
                    _rebuild()

                tk.Button(btns, text="💾 Speichern", command=_save,
                          bg="#1a3e8e", fg="white").pack(side="left", padx=4)
                tk.Button(btns, text="↺ Reset", command=_reset_from_disk
                          ).pack(side="left", padx=4)

            tab_widgets[(section, key)] = _rebuild
            _rebuild()

        for el in ELEMENTS:
            _make_section_tab("elements", el, title=el)

        # ── Prowess tab — exactly the same shape as an Element tab ───────────
        # Single global ranking list used by Prowess card generation. Stored
        # under section="prowess_cards", key="Prowess" (kept for backward
        # compatibility with the previous per-card-id storage).
        _make_section_tab("prowess_cards", "Prowess", title="Prowess")

        # ── Refresh helpers (after type add/remove) ───────────────────────────
        def _refresh_section():
            for cb in tab_widgets.values():
                cb()

        # ── Bottom row: close ────────────────────────────────────────────────
        bottom = tk.Frame(dlg); bottom.pack(fill="x", padx=6, pady=4)
        tk.Button(bottom, text="Fertig", command=dlg.destroy).pack(side="right")

    # ── B): Sigil-Rules editor ───────────────────────────────────────────────
    def _open_sigil_rules_editor(self):
        """Edit cross-sigil rules stored in cc_data/sigil_rules.json.

        Each rule is a small if/require/or-fallback predicate evaluated
        against a generated card. See ``sigil_rules.py`` for schema."""
        try:
            from CardContent import sigil_rules as srules
        except Exception as e:
            messagebox.showerror("Sigil Rules", f"Could not import: {e}")
            return

        try:
            from CardContent.sigil_registry import get_sigil_names
            SIGILS = get_sigil_names()
        except Exception:
            SIGILS = []
        try:
            from card_builder.constants import (ELEMENTS,
                                                  SIGILS_FOR_CARD_TYPE)
            ELEMS = list(ELEMENTS)
            CARD_TYPES = list(SIGILS_FOR_CARD_TYPE.keys())
        except Exception:
            ELEMS, CARD_TYPES = [], []

        dlg = tk.Toplevel(self.root)
        dlg.title("Sigil Rules")
        dlg.geometry("780x540")
        dlg.transient(self.root)

        outer = tk.Frame(dlg)
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        tk.Label(outer,
                 text="Cross-Sigil-Regeln. Beispiel: 'Wenn Sacrifice auf "
                      "Spell-Karte → muss Concentration sein, oder Source als "
                      "Interactable'.",
                 fg="#888", font=("Arial", 8, "italic"),
                 wraplength=720, justify="left"
                 ).pack(anchor="w", pady=(0, 8))

        # Working copy of rules; only persisted on Save
        rules_state: list = [dict(r) for r in srules.list_rules()]

        list_frame = tk.Frame(outer); list_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(list_frame, highlightthickness=0)
        vsb    = ttk.Scrollbar(list_frame, orient="vertical",
                                command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        rows_frame = tk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        rows_frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))

        def _refresh():
            for w in rows_frame.winfo_children():
                w.destroy()
            for idx, rule in enumerate(rules_state):
                _make_rule_card(idx, rule)

        def _make_clause_picker(parent, label: str, clause: dict):
            """Render one clause editor (sigil OR card_type OR element OR
            interactable). The user picks ONE field per clause; the others
            stay empty."""
            row = tk.Frame(parent)
            row.pack(fill="x", padx=6, pady=1)
            tk.Label(row, text=label, width=14, anchor="w",
                     font=("Arial", 8, "bold"), fg="#ccc"
                     ).pack(side="left")

            # sigil
            sig_var = tk.StringVar(value=clause.get("sigil", ""))
            tk.Label(row, text="Sigil:", font=("Arial", 8)).pack(side="left")
            ttk.Combobox(row, textvariable=sig_var,
                         values=[""] + SIGILS, state="readonly",
                         width=12).pack(side="left", padx=2)

            # card_type
            ct_var = tk.StringVar(value=clause.get("card_type", ""))
            tk.Label(row, text="CardType:", font=("Arial", 8)).pack(side="left")
            ttk.Combobox(row, textvariable=ct_var,
                         values=[""] + CARD_TYPES, state="readonly",
                         width=10).pack(side="left", padx=2)

            # element
            el_var = tk.StringVar(value=clause.get("element", ""))
            tk.Label(row, text="Elem:", font=("Arial", 8)).pack(side="left")
            ttk.Combobox(row, textvariable=el_var,
                         values=[""] + ELEMS, state="readonly",
                         width=8).pack(side="left", padx=2)

            # interactable (free text)
            in_var = tk.StringVar(value=clause.get("interactable", ""))
            tk.Label(row, text="Inter:", font=("Arial", 8)).pack(side="left")
            tk.Entry(row, textvariable=in_var, width=12).pack(side="left", padx=2)

            def _commit(_=None):
                clause.clear()
                v = sig_var.get().strip()
                if v: clause["sigil"] = v
                v = ct_var.get().strip()
                if v: clause["card_type"] = v
                v = el_var.get().strip()
                if v: clause["element"] = v
                v = in_var.get().strip()
                if v: clause["interactable"] = v

            for var in (sig_var, ct_var, el_var, in_var):
                var.trace_add("write", lambda *_: _commit())

        def _make_rule_card(idx, rule):
            card = tk.LabelFrame(rows_frame,
                                  text=f"Rule #{idx+1}",
                                  fg="#ffcc66", font=("Arial", 9, "bold"))
            card.pack(fill="x", padx=4, pady=4)

            # ID + delete
            top = tk.Frame(card); top.pack(fill="x", padx=6, pady=4)
            tk.Label(top, text="ID:", font=("Arial", 8, "bold")
                     ).pack(side="left")
            id_var = tk.StringVar(value=rule.get("id", ""))
            tk.Entry(top, textvariable=id_var, width=24
                     ).pack(side="left", padx=4)
            id_var.trace_add("write",
                             lambda *_: rule.update({"id": id_var.get()}))

            tk.Label(top, text="Message:", font=("Arial", 8, "bold")
                     ).pack(side="left", padx=(12, 2))
            msg_var = tk.StringVar(value=rule.get("message", ""))
            tk.Entry(top, textvariable=msg_var, width=32
                     ).pack(side="left", padx=2, fill="x", expand=True)
            msg_var.trace_add("write",
                              lambda *_: rule.update({"message": msg_var.get()}))

            def _del(i=idx):
                rules_state.pop(i)
                _refresh()
            tk.Button(top, text="✕", fg="white", bg="#6e1a1a",
                      font=("Arial", 8, "bold"),
                      command=_del).pack(side="right")

            # IF clause
            if_clause = rule.setdefault("if", {})
            tk.Label(card, text="WENN  (eine Klausel)",
                     fg="#88ccff", font=("Arial", 8, "bold")
                     ).pack(anchor="w", padx=6, pady=(4, 0))
            _make_clause_picker(card, "if:", if_clause)

            # REQUIRE clauses
            req = rule.setdefault("require", [])
            tk.Label(card, text="MUSS  (alle erfüllen — AND)",
                     fg="#88ff88", font=("Arial", 8, "bold")
                     ).pack(anchor="w", padx=6, pady=(4, 0))
            for i, cl in enumerate(list(req)):
                _make_clause_picker(card, f"req[{i}]:", cl)
            def _add_req():
                req.append({}); _refresh()
            tk.Button(card, text="+ require Klausel",
                      command=_add_req,
                      bg="#1a3a1a", fg="white", font=("Arial", 8)
                      ).pack(anchor="w", padx=6, pady=(2, 4))

            # OR-satisfy clauses
            alt = rule.setdefault("or_satisfy_by", [])
            tk.Label(card, text="ODER  (eine reicht — OR-Fallback)",
                     fg="#ffcc88", font=("Arial", 8, "bold")
                     ).pack(anchor="w", padx=6, pady=(4, 0))
            for i, cl in enumerate(list(alt)):
                _make_clause_picker(card, f"alt[{i}]:", cl)
            def _add_alt():
                alt.append({}); _refresh()
            tk.Button(card, text="+ OR Klausel",
                      command=_add_alt,
                      bg="#3a2a1a", fg="white", font=("Arial", 8)
                      ).pack(anchor="w", padx=6, pady=(2, 6))

        _refresh()

        # bottom bar
        bar = tk.Frame(dlg); bar.pack(fill="x", padx=8, pady=6)

        def _add_rule():
            rules_state.append({"id": "", "message": "",
                                 "if": {}, "require": [],
                                 "or_satisfy_by": []})
            _refresh()

        def _save():
            srules.save_rules(rules_state)
            messagebox.showinfo("Sigil Rules",
                                  f"{len(rules_state)} Regeln gespeichert.")
            dlg.destroy()

        tk.Button(bar, text="+ Neue Regel", command=_add_rule,
                  bg="#1a6e3c", fg="white",
                  font=("Arial", 9, "bold")).pack(side="left", padx=4)
        tk.Button(bar, text="💾 Speichern", command=_save,
                  bg="#1a3e8e", fg="white",
                  font=("Arial", 9, "bold")).pack(side="right", padx=4)
        tk.Button(bar, text="Abbrechen", command=dlg.destroy
                  ).pack(side="right", padx=4)

    # ── L: Master Registry (formerly Interactable Manager) ───────────────────
    def _open_interactable_manager(self):
        """Master registry browser.

        One window with five tabs:
          • Custom         – editable interactables (the only tab with
                             add/edit/remove). Powers ``\\Interactable``.
          • Sigils         – read-only listing of all registered sigils.
          • Elements       – read-only listing of all elements.
          • Card Types     – read-only listing of all card types.
          • Marked Effects – read-only listing of every Content Item with
                             ``show_in_interactables: true`` (toggled in the
                             Content Editor checkbox).
        """
        try:
            from CardContent import interactable_registry as ireg
        except Exception as e:
            messagebox.showerror("Interactables",
                                  f"Could not import interactable_registry: {e}")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Master Registry")
        dlg.geometry("640x520")
        dlg.transient(self.root)

        nb = ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        # ── Tab: Custom interactables (editable) ────────────────────────────
        self._build_master_custom_tab(nb, ireg)
        # ── Tab: Sigils (read-only) ─────────────────────────────────────────
        self._build_master_readonly_tab(
            nb, "Sigils",
            getter=lambda: self._master_sigils(),
            color="#88ccff",
            help_text="Sigils stammen aus box_config.json und dem Sigil Manager.")
        # ── Tab: Elements (read-only) ───────────────────────────────────────
        self._build_master_readonly_tab(
            nb, "Elements",
            getter=lambda: self._master_elements(),
            color="#ffcc66",
            help_text="Elemente sind in card_builder/constants.py festgelegt.")
        # ── Tab: Card Types (read-only) ─────────────────────────────────────
        self._build_master_readonly_tab(
            nb, "Card Types",
            getter=lambda: self._master_card_types(),
            color="#cc88ff",
            help_text="Karten-Typen aus den Generator-Profilen.")
        # ── Tab: Marked Effects (read-only) ─────────────────────────────────
        self._build_master_readonly_tab(
            nb, "Marked Effects",
            getter=lambda: self._master_marked_effects(),
            color="#88eecc",
            help_text="Items mit Häkchen 'In Master-Liste anzeigen' im Content Editor.")

        bottom = tk.Frame(dlg); bottom.pack(fill="x", padx=8, pady=6)
        tk.Button(bottom, text="Fertig", command=dlg.destroy).pack(side="right")

    # ── master menu helpers ───────────────────────────────────────────────────

    def _master_sigils(self) -> list:
        try:
            from CardContent.sigil_registry import get_sigil_names
            return [{"id": s, "description": ""} for s in get_sigil_names()]
        except Exception:
            return []

    def _master_elements(self) -> list:
        try:
            from card_builder.constants import ELEMENTS
            return [{"id": el, "description": ""} for el in ELEMENTS]
        except Exception:
            return []

    def _master_card_types(self) -> list:
        try:
            from card_builder.constants import SIGILS_FOR_CARD_TYPE
            return [{"id": ct, "description": ""}
                    for ct in SIGILS_FOR_CARD_TYPE.keys()]
        except Exception:
            return [{"id": ct, "description": ""}
                    for ct in ("Spells", "Prowess", "Potions", "Equipment")]

    def _master_marked_effects(self) -> list:
        out: list = []
        for type_name in ("Effect", "Trigger", "Condition", "Cost", "Insert"):
            for it in (self.data.get(type_name) or []):
                if it.get("show_in_interactables"):
                    out.append({
                        "id": it.get("id", ""),
                        "description": f"[{type_name}]",
                    })
        return out

    def _build_master_readonly_tab(self, nb, title, getter,
                                    color="#cccccc", help_text=""):
        page = tk.Frame(nb)
        nb.add(page, text=title)

        if help_text:
            tk.Label(page, text=help_text, fg="#888",
                     font=("Arial", 8, "italic")
                     ).pack(anchor="w", padx=8, pady=(6, 0))

        list_frame = tk.Frame(page)
        list_frame.pack(fill="both", expand=True, padx=8, pady=6)

        lb = tk.Listbox(list_frame, font=("Consolas", 10),
                        bg="#1a1a1a", fg=color, selectbackground="#2a4a6e")
        sb = ttk.Scrollbar(list_frame, orient="vertical",
                            command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)

        def _refresh(_e=None):
            lb.delete(0, tk.END)
            items = getter() or []
            for it in items:
                iid  = it.get("id", "")
                desc = it.get("description", "")
                line = f"{iid:24}  {desc}" if desc else iid
                lb.insert(tk.END, line)
            if not items:
                lb.insert(tk.END, "(leer)")

        _refresh()
        # Refresh whenever the user switches to this tab
        nb.bind("<<NotebookTabChanged>>", _refresh, add="+")

    def _build_master_custom_tab(self, nb, ireg):
        """The original editable interactables list, hosted as a tab."""
        page = tk.Frame(nb)
        nb.add(page, text="Custom")

        tk.Label(page,
                 text=r"Editierbare Interactables — nutzbar via [\Interactable].",
                 fg="#888", font=("Arial", 9, "italic")
                 ).pack(anchor="w", padx=8, pady=(6, 0))

        # Header row
        hdr = tk.Frame(page); hdr.pack(fill="x", padx=8, pady=(4, 0))
        for txt, w in [("ID", 16), ("Weight", 8), ("Beschreibung", 30), ("", 4)]:
            tk.Label(hdr, text=txt, font=("Arial", 9, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2)

        # Scrollable list
        list_frame = tk.Frame(page)
        list_frame.pack(fill="both", expand=True, padx=8, pady=4)
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        vsb    = ttk.Scrollbar(list_frame, orient="vertical",
                                command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        rows_frame = tk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        rows_frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))

        def _refresh():
            for w in rows_frame.winfo_children():
                w.destroy()
            for it in ireg.get_interactables():
                _make_row(it)

        def _make_row(it):
            iid  = it.get("id", "")
            wval = it.get("weight", ireg.DEFAULT_WEIGHT)
            dval = it.get("description", "")

            row = tk.Frame(rows_frame, relief="groove", bd=1)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=iid, width=16, anchor="w",
                     fg="#88eecc", font=("Arial", 9, "bold")
                     ).pack(side="left", padx=4)

            wv = tk.StringVar(value=str(wval))
            we = tk.Entry(row, textvariable=wv, width=8)
            we.pack(side="left", padx=2)
            def _on_w_save(_e=None, name=iid, var=wv):
                try:    ireg.set_weight(name, float(var.get().strip()))
                except ValueError: pass
            we.bind("<FocusOut>", _on_w_save); we.bind("<Return>", _on_w_save)

            dv = tk.StringVar(value=dval)
            de = tk.Entry(row, textvariable=dv, width=30)
            de.pack(side="left", padx=2, fill="x", expand=True)
            def _on_d_save(_e=None, name=iid, var=dv):
                ireg.set_description(name, var.get())
            de.bind("<FocusOut>", _on_d_save); de.bind("<Return>", _on_d_save)

            def _del(name=iid):
                if messagebox.askyesno("Interactable löschen",
                                        f"'{name}' wirklich entfernen?"):
                    ireg.remove_interactable(name); _refresh()
            tk.Button(row, text="✕", width=2, fg="white", bg="#6e1a1a",
                      font=("Arial", 8, "bold"), command=_del
                      ).pack(side="left", padx=2)

        # Add row
        add_row = tk.Frame(page); add_row.pack(fill="x", padx=8, pady=4)
        new_id  = tk.StringVar()
        new_w   = tk.StringVar(value=str(ireg.DEFAULT_WEIGHT))
        new_d   = tk.StringVar()
        tk.Entry(add_row, textvariable=new_id, width=16).pack(side="left", padx=2)
        tk.Entry(add_row, textvariable=new_w,  width=8 ).pack(side="left", padx=2)
        tk.Entry(add_row, textvariable=new_d,  width=30
                  ).pack(side="left", padx=2, fill="x", expand=True)
        def _add():
            name = new_id.get().strip()
            if not name: return
            try:    w = float(new_w.get().strip() or ireg.DEFAULT_WEIGHT)
            except ValueError: w = ireg.DEFAULT_WEIGHT
            if not ireg.add_interactable(name, weight=w,
                                          description=new_d.get().strip()):
                messagebox.showerror("Interactables",
                                      f"'{name}' existiert bereits.")
                return
            new_id.set(""); new_w.set(str(ireg.DEFAULT_WEIGHT)); new_d.set("")
            _refresh()
        tk.Button(add_row, text="＋ Add", command=_add,
                  bg="#1a6e3c", fg="white",
                  font=("Arial", 9, "bold")).pack(side="left", padx=4)

        _refresh()

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

    def _delete_selected(self):
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
        if not messagebox.askyesno("Löschen?",
                                   f"'{item_id}' ({type_name}) wirklich löschen?"):
            return
        self.data[type_name] = [
            i for i in self.data.get(type_name, [])
            if str(i.get("id", "")) != item_id
        ]
        self._refresh_table()
        self.save_all()

    def _open_create_editor(self):
        """Show a minimal dialog (Type + ID only), then open ContentEditor directly."""
        win = tk.Toplevel(self.root)
        win.title("New Content")
        win.resizable(False, False)
        win.columnconfigure(1, weight=1)

        tk.Label(win, text="Type").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        type_box = ttk.Combobox(win, values=list(FILES.keys()),
                                state="readonly", width=20)
        type_box.current(0)
        type_box.grid(row=0, column=1, sticky="w", padx=8, pady=8)

        tk.Label(win, text="ID").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        id_entry = tk.Entry(win, width=36)
        id_entry.grid(row=1, column=1, sticky="we", padx=8, pady=8)

        tk.Label(win, text="Content Box").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        sigil_entry = tk.Entry(win, width=36)
        sigil_entry.grid(row=2, column=1, sticky="we", padx=8, pady=8)

        tk.Label(win, text="Content Text").grid(row=3, column=0, sticky="w", padx=8, pady=8)
        ct_entry = tk.Entry(win, width=36)
        ct_entry.grid(row=3, column=1, sticky="we", padx=8, pady=8)

        # Auto-fill Content Text from Sigil when Sigil loses focus
        def _auto_ct(*_):
            if not ct_entry.get():
                ct_entry.delete(0, "end")
                ct_entry.insert(0, sigil_entry.get())
        sigil_entry.bind("<FocusOut>", _auto_ct)
        sigil_entry.bind("<Tab>",      _auto_ct)

        err_lbl = tk.Label(win, text="", fg="red")
        err_lbl.grid(row=4, column=0, columnspan=2)

        def _open():
            type_name = type_box.get()
            item_id   = id_entry.get().strip()
            if not item_id:
                err_lbl.config(text="ID is required."); return
            for existing in self.data.get(type_name, []):
                if existing.get("id") == item_id:
                    err_lbl.config(text="ID already exists."); return

            sigil_val = sigil_entry.get()
            new_item = {
                "id":              item_id,
                "sigil":           sigil_val,
                "content_text":    ct_entry.get() or sigil_val,
                "reminder_text":   "",
                "rarity":          10,
                "complexity_base": 1.0,
                "cv1":             1.0,
                "cv2":             0.0,
                "cv3":             0.0,
                "element_weights": {},
                "conditions":      {},
                "variables":       {},
                "options":         {},
            }

            _added = [False]

            def _on_save():
                if not _added[0]:
                    self.data[type_name].append(new_item)
                    _added[0] = True
                self._refresh_table()
                self.save_all()

            win.destroy()
            ContentEditor(self.root, new_item, self.data, on_save=_on_save)

        tk.Button(win, text="Open Editor", command=_open,
                  bg="#1a6e3c", fg="white", width=16).grid(
            row=5, column=0, columnspan=2, pady=12)

        id_entry.bind("<Return>", lambda _: _open())
        id_entry.focus_set()

    # ── Status bar ─────────────────────────────────────────────────────────────

    def _show_status(self, msg: str, ms: int = 2000):
        bar = tk.Label(self.root, text=msg, bg="#1a6e3c", fg="white",
                       font=("Arial", 11, "bold"))
        bar.pack(side="top", fill="x")
        self.root.after(ms, bar.destroy)