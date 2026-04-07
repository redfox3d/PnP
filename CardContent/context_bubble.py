"""
context_bubble.py – Context Bubble window for Enchant / Curse content types.

Layout:
  ┌──────────────┬─────────────────────────────────────────────┐
  │  Item-Liste  │  Detail / Einstellungen                     │
  │  (links)     │  (rechts, scrollbar)                        │
  └──────────────┴─────────────────────────────────────────────┘

Features:
  • CRUD für Enchant- oder Curse-Items (über ContentEditor)
  • Wahrscheinlichkeit / Häufigkeit pro Item (für Random Builder)
  • Erlaubte Sigil-Typen konfigurierbar
  • Effekte & deren Häufigkeiten innerhalb des Items
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

_HERE = os.path.dirname(os.path.abspath(__file__))

_FILES = {
    "Enchant": os.path.join(_HERE, "cc_data", "enchants.json"),
    "Curse":   os.path.join(_HERE, "cc_data", "curses.json"),
}

SIGIL_TYPES = [
    "Play", "Excavate", "Hand", "Concentration", "Enchantment",
    "Equipped", "Exhausted", "Discard", "Forgotten", "Lost",
]


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _load(type_name: str) -> list:
    path = _FILES.get(type_name, "")
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get(type_name, [])


def _save(type_name: str, items: list):
    path = _FILES.get(type_name, "")
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({type_name: items}, f, indent=2, ensure_ascii=False)


# ── Context Bubble ────────────────────────────────────────────────────────────

class ContextBubble(tk.Toplevel):
    """
    Floating window for Enchant or Curse content management.
    type_name: "Enchant" | "Curse"
    """

    _ICONS = {"Enchant": "✨", "Curse": "💀"}
    _ACCENT = {"Enchant": "#3399cc", "Curse": "#cc3333"}
    _BG2    = {"Enchant": "#0d1a22", "Curse": "#1a0d0d"}

    def __init__(self, parent, type_name: str):
        super().__init__(parent)
        self.type_name = type_name
        icon   = self._ICONS.get(type_name, "◆")
        accent = self._ACCENT.get(type_name, "#888888")
        bg2    = self._BG2.get(type_name, "#111111")

        self.title(f"{icon}  {type_name} Bubble")
        self.configure(bg="#1a1a1a")
        self.geometry("880x560")
        self.minsize(700, 420)

        self._accent = accent
        self._bg2    = bg2
        self._items: list = _load(type_name)
        self._selected_idx: int | None = None

        # load all cc_data so ContentEditor can reference IDs from other types
        self._all_data = self._load_all_content()

        self._build()
        self._refresh_list()

    # ── Data ─────────────────────────────────────────────────────────────────

    def _load_all_content(self) -> dict:
        result = {}
        for key, fname in [
            ("Effect",    "effects.json"),
            ("Trigger",   "triggers.json"),
            ("Condition", "conditions.json"),
            ("Cost",      "costs.json"),
            ("Insert",    "inserts.json"),
            ("Enchant",   "enchants.json"),
            ("Curse",     "curses.json"),
        ]:
            path = os.path.join(_HERE, "cc_data", fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                result[key] = raw.get(key, [])
            except Exception:
                result[key] = []
        return result

    def _save_items(self):
        _save(self.type_name, self._items)

    def _item_by_idx(self, idx) -> dict | None:
        if idx is None or idx < 0 or idx >= len(self._items):
            return None
        return self._items[idx]

    # ── UI Build ──────────────────────────────────────────────────────────────

    def _build(self):
        # ── Top title bar ─────────────────────────────────────────────────────
        top = tk.Frame(self, bg="#0d0d0d", pady=6)
        top.pack(fill="x")
        tk.Label(
            top,
            text=f"{self._ICONS.get(self.type_name, '◆')}  {self.type_name} Bubble",
            bg="#0d0d0d", fg=self._accent,
            font=("Palatino Linotype", 13, "bold"),
        ).pack(side="left", padx=12)

        # ── Main 2-column body ────────────────────────────────────────────────
        body = tk.Frame(self, bg="#1a1a1a")
        body.pack(fill="both", expand=True)

        # Left list panel
        left = tk.Frame(body, bg="#1a1a1a", width=220)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        ttk.Separator(body, orient="vertical").pack(side="left", fill="y")

        # Right detail panel
        right = tk.Frame(body, bg="#1a1a1a")
        right.pack(side="left", fill="both", expand=True)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent):
        tk.Label(parent, text="Items:", bg="#1a1a1a", fg="#888",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 2))

        list_f = tk.Frame(parent, bg="#1a1a1a")
        list_f.pack(fill="both", expand=True, padx=4)
        vsb = tk.Scrollbar(list_f, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._lb = tk.Listbox(
            list_f, yscrollcommand=vsb.set,
            bg=self._bg2, fg="white",
            selectbackground=self._accent,
            font=("Consolas", 9), relief="flat",
            activestyle="dotbox",
        )
        self._lb.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._lb.yview)
        self._lb.bind("<<ListboxSelect>>", self._on_select)

        btn_f = tk.Frame(parent, bg="#1a1a1a")
        btn_f.pack(fill="x", padx=4, pady=6)
        tk.Button(btn_f, text="+ Neu", command=self._new_item,
                  bg="#1a4a1a", fg="white", font=("Arial", 9),
                  relief="flat", cursor="hand2").pack(side="left", padx=2)
        tk.Button(btn_f, text="✕ Löschen", command=self._delete_item,
                  bg="#4a1a1a", fg="#ff8888", font=("Arial", 9),
                  relief="flat", cursor="hand2").pack(side="left", padx=2)

    def _build_right(self, parent):
        # Scrollable detail area
        outer = tk.Frame(parent, bg="#1a1a1a")
        outer.pack(fill="both", expand=True)
        vsb = tk.Scrollbar(outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(outer, yscrollcommand=vsb.set,
                           bg="#1a1a1a", highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=canvas.yview)
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._detail_frame = tk.Frame(canvas, bg="#1a1a1a")
        win = canvas.create_window((0, 0), window=self._detail_frame, anchor="nw")
        self._detail_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))

        self._show_empty_detail()

    # ── List helpers ──────────────────────────────────────────────────────────

    def _refresh_list(self, keep_selection: int | None = None):
        self._lb.delete(0, "end")
        for item in self._items:
            prob = item.get("probability", 1.0)
            self._lb.insert("end", f"{item.get('id', '?'):<22}  {prob:.2f}")
        if keep_selection is not None and 0 <= keep_selection < len(self._items):
            self._lb.selection_set(keep_selection)
            self._lb.see(keep_selection)
            self._selected_idx = keep_selection
            self._show_detail(self._items[keep_selection])

    def _on_select(self, _event=None):
        sel = self._lb.curselection()
        if not sel:
            return
        idx = sel[0]
        self._selected_idx = idx
        item = self._item_by_idx(idx)
        if item:
            self._show_detail(item)

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _show_empty_detail(self):
        for w in self._detail_frame.winfo_children():
            w.destroy()
        tk.Label(self._detail_frame, text="← Item auswählen",
                 bg="#1a1a1a", fg="#444",
                 font=("Arial", 11, "italic")).pack(pady=40)

    def _show_detail(self, item: dict):
        for w in self._detail_frame.winfo_children():
            w.destroy()
        f = self._detail_frame
        pad = {"padx": 12, "pady": 3}

        # ── Header ────────────────────────────────────────────────────────────
        tk.Label(f, text=item.get("id", "?"),
                 bg="#1a1a1a", fg=self._accent,
                 font=("Palatino Linotype", 13, "bold")).pack(
            anchor="w", padx=12, pady=(10, 2))

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=4)

        # ── Probability ───────────────────────────────────────────────────────
        self._sep_label(f, "Häufigkeit (Random Builder)")
        prob_row = tk.Frame(f, bg="#1a1a1a")
        prob_row.pack(fill="x", **pad)
        tk.Label(prob_row, text="Wahrscheinlichkeit:", bg="#1a1a1a", fg="#ccc",
                 font=("Arial", 9)).pack(side="left")
        prob_var = tk.DoubleVar(value=float(item.get("probability", 1.0)))
        prob_entry = tk.Spinbox(prob_row, from_=0.0, to=1.0, increment=0.05,
                                textvariable=prob_var, width=7,
                                bg="#2a2a2a", fg="white",
                                buttonbackground="#333",
                                font=("Arial", 9))
        prob_entry.pack(side="left", padx=6)
        tk.Label(prob_row, text="(0 = nie, 1 = immer)",
                 bg="#1a1a1a", fg="#555", font=("Arial", 8)).pack(side="left")

        def _save_prob(*_):
            try:
                item["probability"] = round(float(prob_var.get()), 3)
                self._save_items()
                self._refresh_list(keep_selection=self._selected_idx)
            except Exception:
                pass

        prob_var.trace_add("write", _save_prob)

        # ── Allowed Sigil Types ───────────────────────────────────────────────
        self._sep_label(f, "Erlaubte Sigil-Typen")
        tk.Label(f, text="(leer = alle erlaubt)",
                 bg="#1a1a1a", fg="#555", font=("Arial", 8, "italic")).pack(
            anchor="w", padx=12)

        allowed = item.setdefault("conditions", {}).setdefault("allowed_box_types", [])
        sig_f = tk.Frame(f, bg="#1a1a1a")
        sig_f.pack(fill="x", padx=12, pady=4)
        self._sigil_vars: dict[str, tk.BooleanVar] = {}
        for i, st in enumerate(SIGIL_TYPES):
            var = tk.BooleanVar(value=(st in allowed))
            self._sigil_vars[st] = var
            cb = tk.Checkbutton(
                sig_f, text=st, variable=var,
                bg="#1a1a1a", fg="#ccc",
                selectcolor="#2a2a3a",
                activebackground="#1a1a1a",
                font=("Arial", 8),
                command=lambda it=item: self._save_sigils(it),
            )
            cb.grid(row=i // 3, column=i % 3, sticky="w", padx=4, pady=1)

        # ── Content Text preview ──────────────────────────────────────────────
        self._sep_label(f, "Sigil / Content Text")
        preview_text = item.get("content_text") or item.get("sigil") or "(leer)"
        preview_lbl = tk.Label(f, text=preview_text[:120],
                               bg="#1e1e2e", fg="#aaddff",
                               font=("Consolas", 9), wraplength=480,
                               justify="left", anchor="w", pady=4, padx=6)
        preview_lbl.pack(fill="x", padx=12, pady=2)

        # ── Effekte & Häufigkeiten ────────────────────────────────────────────
        self._sep_label(f, "Effekte & Häufigkeiten")
        tk.Label(f, text="Welche Effekte können in diesem Item landen:",
                 bg="#1a1a1a", fg="#888", font=("Arial", 8, "italic")).pack(
            anchor="w", padx=12)

        self._eff_frame = tk.Frame(f, bg="#1a1a1a")
        self._eff_frame.pack(fill="x", padx=12, pady=4)
        self._rebuild_effects_panel(item)

        eff_btn_row = tk.Frame(f, bg="#1a1a1a")
        eff_btn_row.pack(fill="x", padx=12, pady=(0, 4))
        tk.Button(eff_btn_row, text="+ Effekt hinzufügen",
                  command=lambda: self._add_effect(item),
                  bg="#2a2a3a", fg="#88aaff",
                  font=("Arial", 8), relief="flat", cursor="hand2").pack(side="left")

        # ── ContentEditor button ──────────────────────────────────────────────
        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=8)
        tk.Button(f, text="✏  Im ContentEditor öffnen",
                  command=lambda: self._open_editor(item),
                  bg="#333344", fg="#aaaaff",
                  font=("Arial", 10), relief="flat", cursor="hand2",
                  pady=6).pack(fill="x", padx=12, pady=(0, 12))

    def _sep_label(self, parent, text: str):
        row = tk.Frame(parent, bg="#1a1a1a")
        row.pack(fill="x", padx=8, pady=(10, 0))
        tk.Label(row, text=text, bg="#1a1a1a", fg=self._accent,
                 font=("Arial", 9, "bold")).pack(side="left")
        ttk.Separator(row, orient="horizontal").pack(side="left", fill="x",
                                                      expand=True, padx=6)

    def _rebuild_effects_panel(self, item: dict):
        for w in self._eff_frame.winfo_children():
            w.destroy()
        effects = item.setdefault("item_effects", [])
        # header
        if effects:
            hdr = tk.Frame(self._eff_frame, bg="#1a1a1a")
            hdr.pack(fill="x")
            tk.Label(hdr, text="Effekt-ID", bg="#1a1a1a", fg="#666",
                     width=22, anchor="w", font=("Arial", 7, "bold")).pack(side="left")
            tk.Label(hdr, text="Chance", bg="#1a1a1a", fg="#666",
                     width=8, font=("Arial", 7, "bold")).pack(side="left")

        for i, eff in enumerate(effects):
            row = tk.Frame(self._eff_frame, bg="#1a1a1a")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=eff.get("effect_id", "?"),
                     bg="#1a1a1a", fg="#88ff88",
                     width=22, anchor="w", font=("Consolas", 8)).pack(side="left")
            prob_var = tk.StringVar(value=str(eff.get("probability", 1.0)))
            tk.Entry(row, textvariable=prob_var, width=7,
                     bg="#2a2a2a", fg="white",
                     font=("Arial", 8)).pack(side="left", padx=4)

            def _on_prob(_, i=i, v=prob_var, it=item):
                try:
                    it["item_effects"][i]["probability"] = float(v.get())
                    self._save_items()
                except Exception:
                    pass

            prob_var.trace_add("write", _on_prob)
            tk.Button(row, text="✕", width=2,
                      command=lambda i=i, it=item: self._remove_effect(it, i),
                      bg="#2a2a2a", fg="#ff8888",
                      font=("Arial", 7), relief="flat").pack(side="left")

    def _save_sigils(self, item: dict):
        selected = [st for st, var in self._sigil_vars.items() if var.get()]
        item.setdefault("conditions", {})["allowed_box_types"] = selected
        self._save_items()

    def _add_effect(self, item: dict):
        # Build picker with all known effect IDs
        all_effects = [
            e["id"] for e in self._all_data.get("Effect", []) if "id" in e
        ]
        if not all_effects:
            messagebox.showinfo("Keine Effekte",
                                "Erst Effekte im Content Editor anlegen.",
                                parent=self)
            return
        top = tk.Toplevel(self)
        top.title("Effekt auswählen")
        top.configure(bg="#1a1a1a")
        top.grab_set()
        result = [None]
        lb = tk.Listbox(top, bg="#2a2a2a", fg="white",
                        font=("Consolas", 9), height=20, width=36)
        lb.pack(padx=8, pady=8)
        for eid in sorted(all_effects):
            lb.insert("end", eid)

        def _ok():
            sel = lb.curselection()
            if sel:
                result[0] = lb.get(sel[0])
            top.destroy()

        tk.Button(top, text="OK", command=_ok,
                  bg="#1a6e3c", fg="white", font=("Arial", 9)).pack(pady=(0, 8))
        top.wait_window()
        if result[0]:
            item.setdefault("item_effects", []).append(
                {"effect_id": result[0], "probability": 1.0})
            self._save_items()
            self._rebuild_effects_panel(item)

    def _remove_effect(self, item: dict, idx: int):
        effects = item.get("item_effects", [])
        if 0 <= idx < len(effects):
            effects.pop(idx)
            self._save_items()
            self._rebuild_effects_panel(item)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _new_item(self):
        new_id = simpledialog.askstring(
            f"Neues {self.type_name}-Item",
            "ID (z.B. heal_self, poison_enemy):",
            parent=self,
        )
        if not new_id:
            return
        new_id = new_id.strip()
        if any(i.get("id") == new_id for i in self._items):
            messagebox.showerror("Duplikat", f"ID '{new_id}' existiert bereits.", parent=self)
            return
        item = {
            "id":          new_id,
            "sigil":       "",
            "content_text": "",
            "probability": 1.0,
            "conditions":  {"allowed_box_types": []},
            "item_effects": [],
            "cv1": 0.0, "cv2": 0.0, "cv3": 0.0,
            "complexity": 0.0,
        }
        self._items.append(item)
        self._save_items()
        idx = len(self._items) - 1
        self._refresh_list(keep_selection=idx)
        # Open ContentEditor immediately
        self._open_editor(item)

    def _delete_item(self):
        if self._selected_idx is None:
            return
        item = self._item_by_idx(self._selected_idx)
        if not item:
            return
        if not messagebox.askyesno(
            "Löschen?",
            f"'{item.get('id', '?')}' wirklich löschen?",
            parent=self,
        ):
            return
        self._items.pop(self._selected_idx)
        self._selected_idx = None
        self._save_items()
        self._refresh_list()
        self._show_empty_detail()

    # ── ContentEditor integration ─────────────────────────────────────────────

    def _open_editor(self, item: dict):
        from CardContent.content_editor import ContentEditor

        def _on_save():
            self._save_items()
            # Refresh detail view with updated item
            idx = self._selected_idx
            self._refresh_list(keep_selection=idx)

        ContentEditor(self, item, self._all_data, on_save=_on_save)
