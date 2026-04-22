"""
random_builder/ui/sigil_rules_editor.py – Standalone editor for Sigil Rules.

Sigil Rules = "For block type X, always include Y effects from container/list
               with probability P and count min..max."

Layout:
  Left  : list of block types (Play, Hand, Lost, …)
  Right : rules for the selected block type
  Bottom: Incompatible Pairs + Save/Close
"""

import tkinter as tk
from tkinter import ttk

BG      = "#15151f"
BG2     = "#1e1e2e"
BG3     = "#252535"
FG      = "#e0e0f0"
FG_DIM  = "#666680"
FG_HEAD = "#aaaadd"
ACCENT  = "#3a6ea5"
GREEN   = "#2a5a2a"
RED     = "#5a1a1a"


def _pick_effects_dialog(parent, all_effect_ids: list, current: list) -> list | None:
    """Simple modal multi-select dialog. Returns new list or None if cancelled."""
    dlg = tk.Toplevel(parent)
    dlg.title("Effekte wählen")
    dlg.configure(bg=BG)
    dlg.resizable(False, True)
    dlg.geometry("320x420")
    dlg.grab_set()

    tk.Label(dlg, text="Effekte wählen (Strg+Klick für Mehrfach):",
             bg=BG, fg=FG_HEAD, font=("Arial", 9)).pack(anchor="w", padx=10, pady=(10, 4))

    lb = tk.Listbox(dlg, selectmode="extended", bg=BG3, fg=FG,
                    selectbackground=ACCENT, font=("Consolas", 9),
                    activestyle="none", height=18)
    lb.pack(fill="both", expand=True, padx=10, pady=4)

    for eid in sorted(all_effect_ids):
        lb.insert("end", eid)
        if eid in current:
            lb.selection_set(lb.size() - 1)

    result = [None]

    def _ok():
        result[0] = [lb.get(i) for i in lb.curselection()]
        dlg.destroy()

    def _cancel():
        dlg.destroy()

    btn_row = tk.Frame(dlg, bg=BG)
    btn_row.pack(fill="x", padx=10, pady=8)
    tk.Button(btn_row, text="✔ OK", bg=GREEN, fg="white",
              command=_ok, width=10).pack(side="left")
    tk.Button(btn_row, text="Abbrechen", bg=BG3, fg=FG_DIM,
              command=_cancel, width=10).pack(side="right")

    dlg.wait_window()
    return result[0]


class SigilRulesEditor(tk.Toplevel):
    """Standalone window for editing sigil rules and incompatible pairs."""

    def __init__(self, parent,
                 sigil_rules: dict,          # {block_type: [rule_dict, ...]}
                 incompatible_pairs: list,    # [[eid1, eid2], ...]
                 block_types: list,           # ordered list of sigil types
                 containers: dict,            # {container_id: {...}}
                 effect_ids: list,            # all available effect IDs
                 on_save=None):              # callback(sigil_rules, incompat_pairs)
        super().__init__(parent)
        self.title("Sigil Regeln")
        self.configure(bg=BG)
        self.geometry("780x540")
        self.minsize(640, 400)
        self.grab_set()

        # Deep-copy so we don't mutate the caller's data until Save
        import copy
        self._rules      = {bt: [dict(r) for r in rules]
                            for bt, rules in sigil_rules.items()}
        self._incompat   = [list(p) for p in incompatible_pairs]
        self._block_types = block_types
        self._containers  = containers
        self._effect_ids  = effect_ids
        self._on_save     = on_save

        self._selected_bt = tk.StringVar(value=block_types[0] if block_types else "")

        self._build()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg="#0e0e1a")
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚡  Sigil Regeln",
                 bg="#0e0e1a", fg="#ffdd88",
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=14, pady=8)
        tk.Label(hdr,
                 text="Legt fest welche Effekte in einem Sigil-Typ garantiert (mit Wahrscheinlichkeit) vorkommen.",
                 bg="#0e0e1a", fg=FG_DIM, font=("Segoe UI", 8)).pack(
            side="left", padx=4)

        # ── Main area: left panel + right panel ───────────────────────────
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=8, pady=4)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # Left: block type selector
        left = tk.Frame(main, bg=BG2, width=130, relief="sunken", bd=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.pack_propagate(False)

        tk.Label(left, text="Sigil-Typ", bg=BG2, fg=FG_HEAD,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=8, pady=(8, 4))

        self._bt_buttons = {}
        for bt in self._block_types:
            btn = tk.Button(left, text=bt,
                            bg=BG3 if bt != self._selected_bt.get() else ACCENT,
                            fg=FG, font=("Segoe UI", 9),
                            relief="flat", anchor="w",
                            cursor="hand2",
                            command=lambda b=bt: self._select_bt(b))
            btn.pack(fill="x", padx=4, pady=1)
            self._bt_buttons[bt] = btn

        # Right: rules panel
        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self._rules_canvas = tk.Canvas(right, bg=BG, highlightthickness=0)
        vsb = tk.Scrollbar(right, orient="vertical",
                           command=self._rules_canvas.yview)
        self._rules_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._rules_canvas.pack(fill="both", expand=True)

        self._rules_frame = tk.Frame(self._rules_canvas, bg=BG)
        self._rules_win = self._rules_canvas.create_window(
            (0, 0), window=self._rules_frame, anchor="nw")
        self._rules_frame.bind(
            "<Configure>",
            lambda e: self._rules_canvas.configure(
                scrollregion=self._rules_canvas.bbox("all")))
        self._rules_canvas.bind(
            "<Configure>",
            lambda e: self._rules_canvas.itemconfig(self._rules_win, width=e.width))
        self._rules_canvas.bind(
            "<MouseWheel>",
            lambda e: self._rules_canvas.yview_scroll(int(-e.delta / 120), "units"))

        # ── Bottom: incompat pairs + buttons ─────────────────────────────
        bot = tk.Frame(self, bg=BG2, relief="groove", bd=1)
        bot.pack(fill="x", padx=8, pady=(0, 6))

        tk.Label(bot, text="Unverträgliche Paare  (zwei Effekte die nie gemeinsam erscheinen):",
                 bg=BG2, fg="#ffcc44", font=("Segoe UI", 8, "bold")).pack(
            anchor="w", padx=8, pady=(6, 2))

        ic_row = tk.Frame(bot, bg=BG2)
        ic_row.pack(fill="x", padx=8, pady=(0, 6))

        self._incompat_lb = tk.Listbox(ic_row, height=3, bg=BG3, fg="#ffcc44",
                                        selectbackground="#4a4a20",
                                        font=("Consolas", 8), activestyle="none")
        self._incompat_lb.pack(side="left", fill="x", expand=True)
        for pair in self._incompat:
            self._incompat_lb.insert("end", f"  {pair[0]}  ↔  {pair[1]}")

        ic_btns = tk.Frame(ic_row, bg=BG2)
        ic_btns.pack(side="left", padx=6)
        tk.Button(ic_btns, text="+ Paar", bg=GREEN, fg="white",
                  font=("Segoe UI", 8), command=self._add_incompat).pack(pady=1)
        tk.Button(ic_btns, text="✕ Entfernen", bg=RED, fg="#ff8888",
                  font=("Segoe UI", 8), command=self._remove_incompat).pack(pady=1)

        # Save / Cancel
        save_row = tk.Frame(self, bg=BG)
        save_row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(save_row, text="💾  Speichern & Schließen",
                  bg="#1a6e3c", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  command=self._save).pack(side="right", padx=4)
        tk.Button(save_row, text="Abbrechen",
                  bg=BG3, fg=FG_DIM,
                  font=("Segoe UI", 9),
                  command=self.destroy).pack(side="right", padx=4)

        self._rebuild_rules()

    # ── Block type selection ──────────────────────────────────────────────

    def _select_bt(self, bt: str):
        old = self._selected_bt.get()
        if old in self._bt_buttons:
            self._bt_buttons[old].config(bg=BG3)
        self._selected_bt.set(bt)
        self._bt_buttons[bt].config(bg=ACCENT)
        self._rebuild_rules()

    # ── Rules panel ───────────────────────────────────────────────────────

    def _rebuild_rules(self):
        for w in self._rules_frame.winfo_children():
            w.destroy()

        bt    = self._selected_bt.get()
        rules = self._rules.get(bt, [])

        # Header row
        hdr = tk.Frame(self._rules_frame, bg=BG)
        hdr.pack(fill="x", padx=4, pady=(6, 2))
        tk.Label(hdr, text=f"Regeln für:  {bt}",
                 bg=BG, fg="#ffdd88",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(hdr, text="+ Neue Regel",
                  bg=GREEN, fg="white",
                  font=("Segoe UI", 8),
                  command=lambda: self._add_rule(bt)).pack(side="right", padx=4)

        if not rules:
            tk.Label(self._rules_frame,
                     text="Keine Regeln für diesen Sigil-Typ.\nKlicke '+ Neue Regel' um eine hinzuzufügen.",
                     bg=BG, fg=FG_DIM,
                     font=("Segoe UI", 9), justify="left").pack(
                anchor="w", padx=16, pady=12)
            return

        for idx, rule in enumerate(rules):
            self._build_rule_card(bt, idx, rule)

    def _build_rule_card(self, bt: str, idx: int, rule: dict):
        card = tk.Frame(self._rules_frame, bg=BG2, relief="groove", bd=1)
        card.pack(fill="x", padx=4, pady=4)

        # ── Title bar ─────────────────────────────────────────────────
        title_row = tk.Frame(card, bg="#0e0e1a")
        title_row.pack(fill="x")
        tk.Label(title_row, text=f"  Regel {idx + 1}",
                 bg="#0e0e1a", fg=FG_HEAD,
                 font=("Segoe UI", 9, "bold")).pack(side="left", pady=3)
        tk.Button(title_row, text="✕ Löschen",
                  bg=RED, fg="#ff8888",
                  font=("Segoe UI", 7),
                  command=lambda i=idx, b=bt: self._remove_rule(b, i)
                  ).pack(side="right", padx=4, pady=2)

        body = tk.Frame(card, bg=BG2)
        body.pack(fill="x", padx=10, pady=6)

        # ── Row 1: Source ──────────────────────────────────────────────
        src_row = tk.Frame(body, bg=BG2)
        src_row.pack(fill="x", pady=2)
        tk.Label(src_row, text="Quelle:", width=9, anchor="w",
                 bg=BG2, fg=FG_HEAD, font=("Segoe UI", 8, "bold")).pack(side="left")

        mode = "effects" if rule.get("effects") else "container"
        mode_var = tk.StringVar(value=mode)
        src_holder = tk.Frame(src_row, bg=BG2)
        src_holder.pack(side="left", fill="x", expand=True)

        def _build_src(holder=src_holder, r=rule, mv=mode_var):
            for w in holder.winfo_children():
                w.destroy()
            m = mv.get()
            if m == "container":
                choices = list(self._containers.keys())
                c_var = tk.StringVar(value=r.get("container", choices[0] if choices else ""))
                cb = ttk.Combobox(holder, textvariable=c_var,
                                  values=choices, width=20, state="readonly")
                cb.pack(side="left")
                def _sc(*_, rv=r, cv=c_var):
                    rv["container"] = cv.get(); rv.pop("effects", None)
                c_var.trace_add("write", _sc)
            else:
                effs = r.get("effects", [])
                preview = ", ".join(effs) if effs else "(keine gewählt — klicken)"
                lbl = tk.Label(holder, text=preview,
                               bg=BG3, fg="#88ff88",
                               font=("Consolas", 8), cursor="hand2",
                               anchor="w", relief="groove",
                               wraplength=340, justify="left")
                lbl.pack(side="left", fill="x", expand=True, ipadx=4, ipady=2)
                def _pick(e, rv=r, lbl=lbl):
                    new_effs = _pick_effects_dialog(
                        self, self._effect_ids, rv.get("effects", []))
                    if new_effs is not None:
                        rv["effects"] = new_effs
                        rv.pop("container", None)
                        lbl.config(text=", ".join(new_effs) if new_effs
                                   else "(keine gewählt — klicken)")
                lbl.bind("<Button-1>", _pick)

        toggle_btn = tk.Button(
            src_row,
            text="→ Effekte" if mode == "container" else "→ Container",
            bg=BG3, fg="#aaaacc", font=("Segoe UI", 7),
            relief="flat", cursor="hand2",
        )

        def _toggle(r=rule, mv=mode_var, holder=src_holder, btn=toggle_btn):
            new = "effects" if mv.get() == "container" else "container"
            mv.set(new)
            if new == "effects":
                r.setdefault("effects", []); r.pop("container", None)
            else:
                choices = list(self._containers.keys())
                r.setdefault("container", choices[0] if choices else "")
                r.pop("effects", None)
            _build_src(holder, r, mv)
            btn.config(text="→ Effekte" if new == "container" else "→ Container")

        toggle_btn.config(command=_toggle)
        toggle_btn.pack(side="right", padx=(6, 0))
        _build_src()

        # ── Row 2: Chance + Anzahl ─────────────────────────────────────
        nums_row = tk.Frame(body, bg=BG2)
        nums_row.pack(fill="x", pady=(4, 2))

        def _make_num_field(parent, label, key, default, width=6, is_float=True):
            tk.Label(parent, text=label, bg=BG2, fg=FG_DIM,
                     font=("Segoe UI", 8)).pack(side="left")
            var = tk.StringVar(value=str(rule.get(key, default)))
            tk.Entry(parent, textvariable=var, width=width,
                     bg=BG3, fg=FG, insertbackground=FG,
                     font=("Consolas", 9),
                     relief="groove").pack(side="left", padx=(2, 10))
            def _sync(*_, r=rule, v=var, k=key, fl=is_float):
                try:
                    r[k] = float(v.get()) if fl else int(v.get())
                except Exception:
                    pass
            var.trace_add("write", _sync)
            return var

        _make_num_field(nums_row, "Chance (0–1):", "probability", 1.0, width=6)
        _make_num_field(nums_row, "Anzahl min:", "min", 1, width=4, is_float=False)
        _make_num_field(nums_row, "max:", "max", 1, width=4, is_float=False)

        # ── Hint ──────────────────────────────────────────────────────
        tk.Label(body,
                 text="→ Mit dieser Wahrscheinlichkeit werden min–max Effekte aus der Quelle in das Sigil gezwungen.",
                 bg=BG2, fg=FG_DIM, font=("Segoe UI", 7),
                 wraplength=440, justify="left").pack(anchor="w", pady=(0, 2))

    # ── Rule management ───────────────────────────────────────────────────

    def _add_rule(self, bt: str):
        choices = list(self._containers.keys())
        self._rules.setdefault(bt, []).append({
            "container": choices[0] if choices else "",
            "probability": 1.0, "min": 1, "max": 1,
        })
        self._rebuild_rules()

    def _remove_rule(self, bt: str, idx: int):
        rules = self._rules.get(bt, [])
        if 0 <= idx < len(rules):
            rules.pop(idx)
        self._rebuild_rules()

    # ── Incompatible pairs ────────────────────────────────────────────────

    def _add_incompat(self):
        dlg = tk.Toplevel(self)
        dlg.title("Unverträgliches Paar hinzufügen")
        dlg.configure(bg=BG)
        dlg.geometry("340x460")
        dlg.grab_set()

        tk.Label(dlg, text="Effekt 1:", bg=BG, fg=FG_HEAD,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(10, 2))
        lb1 = tk.Listbox(dlg, bg=BG3, fg=FG, selectbackground=ACCENT,
                          font=("Consolas", 8), height=7, activestyle="none")
        lb1.pack(fill="x", padx=10)

        tk.Label(dlg, text="Effekt 2:", bg=BG, fg=FG_HEAD,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(8, 2))
        lb2 = tk.Listbox(dlg, bg=BG3, fg=FG, selectbackground=ACCENT,
                          font=("Consolas", 8), height=7, activestyle="none")
        lb2.pack(fill="x", padx=10)

        for eid in sorted(self._effect_ids):
            lb1.insert("end", eid)
            lb2.insert("end", eid)

        def _add():
            s1 = lb1.curselection()
            s2 = lb2.curselection()
            if not s1 or not s2:
                return
            e1, e2 = lb1.get(s1[0]), lb2.get(s2[0])
            if e1 == e2:
                return
            pair = sorted([e1, e2])
            if pair not in [sorted(p) for p in self._incompat]:
                self._incompat.append(pair)
                self._incompat_lb.insert("end", f"  {pair[0]}  ↔  {pair[1]}")
            dlg.destroy()

        tk.Button(dlg, text="+ Hinzufügen", bg=GREEN, fg="white",
                  command=_add).pack(pady=8)

    def _remove_incompat(self):
        sel = self._incompat_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        self._incompat_lb.delete(idx)
        if 0 <= idx < len(self._incompat):
            self._incompat.pop(idx)

    # ── Save ──────────────────────────────────────────────────────────────

    def _save(self):
        if self._on_save:
            self._on_save(self._rules, self._incompat)
        self.destroy()
