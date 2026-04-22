"""
random_builder/ui/sigil_constraints.py – Standalone Sigil Constraints Manager.

Opens as a Toplevel window.  Edits sigil_constraints inside a gen_config dict
in-place and calls on_change() after every edit so the caller can autosave.

Data shape (in gen_config["sigil_constraints"]):
  {
    "Hand": {
      "forbidden":       ["EffectA"],
      "required_groups": [["EffectB", "EffectC"], ["EffectD"]]
    },
    ...
  }

required_groups: list of playlists.  From each playlist ONE effect is picked
at generation time.  A playlist with a single entry = that effect is always added.
"""

import tkinter as tk
from tkinter import ttk


class SigilConstraintsWindow(tk.Toplevel):
    """Popup window for editing per-sigil forbidden / required-group constraints."""

    BG      = "#111822"
    BG2     = "#1a2030"
    BG3     = "#1e2a3a"
    FG      = "#c8d4e8"
    FG_DIM  = "#556070"
    C_FORB  = "#ff6666"
    C_GRP   = "#ffcc44"

    def __init__(self, parent, gen_config: dict, content_data: dict,
                 on_change=None, **kw):
        super().__init__(parent, **kw)
        self.title("⚙  Sigil Constraints Manager")
        self.geometry("720x540")
        self.configure(bg=self.BG)
        self.resizable(True, True)

        self._gen_config    = gen_config
        self._content_data  = content_data
        self._on_change     = on_change or (lambda: None)

        # Build internal model (copied from config; written back on every change)
        self._all_effect_ids = [
            item["id"] for item in content_data.get("Effect", [])
        ]
        self._bt_names = self._collect_bt_names()
        self._data     = self._load_data()

        self._build()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _collect_bt_names(self):
        from card_builder.constants import BOX_TYPES
        box_cfg = self._gen_config.get("box_config", {})
        if box_cfg:
            return sorted(box_cfg.keys())
        from_rules = [r["block_type"]
                      for r in self._gen_config.get("block_rules", [])
                      if r.get("block_type")]
        return from_rules or list(BOX_TYPES)

    def _load_data(self) -> dict:
        """Build internal {bt: {forbidden, required_groups}} from gen_config."""
        raw = self._gen_config.get("sigil_constraints", {})
        result = {}
        for bt in self._bt_names:
            c = raw.get(bt, {})
            groups = [list(g) for g in c.get("required_groups", [])]
            # backward-compat: migrate old required_one_of
            rone = list(c.get("required_one_of", []))
            if rone and not groups:
                groups = [rone]
            result[bt] = {
                "forbidden":       list(c.get("forbidden", [])),
                "required_groups": groups,
            }
        return result

    def _commit(self):
        """Write _data back to gen_config and call on_change."""
        sc = {}
        for bt, c in self._data.items():
            entry = {}
            if c.get("forbidden"):        entry["forbidden"]        = c["forbidden"]
            if c.get("required_groups"):  entry["required_groups"]  = c["required_groups"]
            if entry:
                sc[bt] = entry
        self._gen_config["sigil_constraints"] = sc
        self._on_change()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg="#0d1117", pady=6)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙  Sigil Constraints Manager",
                 bg="#0d1117", fg="#5b9bd5",
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=12)
        tk.Label(hdr,
                 text="Verboten = kommt in diesem Sigil-Typ nie vor.  "
                      "Pflicht-Gruppen = aus jeder Gruppe wird beim Generieren\n"
                      "genau 1 Effekt zufällig gezogen.  "
                      "Einzelne Gruppe mit 1 Eintrag = immer dieser Effekt.",
                 bg="#0d1117", fg=self.FG_DIM,
                 font=("Segoe UI", 8), justify="left").pack(
            side="left", padx=8)

        # ── Block-type selector ───────────────────────────────────────────────
        sel_bar = tk.Frame(self, bg=self.BG, pady=4)
        sel_bar.pack(fill="x", padx=8)
        tk.Label(sel_bar, text="Sigil-Typ:", bg=self.BG, fg=self.FG,
                 font=("Segoe UI", 9)).pack(side="left")
        self._bt_var = tk.StringVar(value=self._bt_names[0] if self._bt_names else "")
        bt_cb = ttk.Combobox(sel_bar, textvariable=self._bt_var,
                             values=self._bt_names, state="readonly", width=14,
                             font=("Segoe UI", 9))
        bt_cb.pack(side="left", padx=6)
        bt_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_panel())

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # ── Scrollable inner area ─────────────────────────────────────────────
        outer = tk.Frame(self, bg=self.BG)
        outer.pack(fill="both", expand=True)
        vsb = tk.Scrollbar(outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._canvas = tk.Canvas(outer, yscrollcommand=vsb.set,
                                 bg=self.BG, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        vsb.config(command=self._canvas.yview)
        self._canvas.bind(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._inner = tk.Frame(self._canvas, bg=self.BG)
        self._win_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width))

        self._refresh_panel()

    def _refresh_panel(self):
        for w in self._inner.winfo_children():
            w.destroy()
        bt = self._bt_var.get()
        c  = self._data.setdefault(bt, {"forbidden": [], "required_groups": []})
        self._draw_forbidden(bt, c)
        ttk.Separator(self._inner, orient="horizontal").pack(
            fill="x", pady=6, padx=4)
        self._draw_required_groups(bt, c)

    # ── Verboten ──────────────────────────────────────────────────────────────

    def _draw_forbidden(self, bt: str, c: dict):
        sec = tk.Frame(self._inner, bg=self.BG)
        sec.pack(fill="x", padx=8, pady=(6, 2))

        hrow = tk.Frame(sec, bg=self.BG)
        hrow.pack(fill="x")
        tk.Label(hrow, text="Verboten", bg=self.BG, fg=self.C_FORB,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(hrow,
                 text="  Diese Effekte erscheinen in diesem Sigil-Typ nie.",
                 bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 8)).pack(
            side="left")

        body = tk.Frame(sec, bg=self.BG2, relief="groove", bd=1)
        body.pack(fill="x", pady=4)

        lb = tk.Listbox(body, height=4, bg="#221a1a", fg=self.C_FORB,
                        selectbackground="#442222", activestyle="none",
                        font=("Consolas", 8), relief="flat", bd=0)
        for eid in c.get("forbidden", []):
            lb.insert("end", eid)
        lb.pack(side="left", fill="x", expand=True, padx=4, pady=4)

        ctrl = tk.Frame(body, bg=self.BG2)
        ctrl.pack(side="left", padx=4, pady=4, anchor="n")

        add_var = tk.StringVar()
        ttk.Combobox(ctrl, textvariable=add_var,
                     values=self._all_effect_ids,
                     width=20, font=("Segoe UI", 8)).pack(pady=1)

        def _add(_bt=bt, _lb=lb, _av=add_var):
            eid = _av.get().strip()
            if eid and eid not in self._data[_bt]["forbidden"]:
                self._data[_bt]["forbidden"].append(eid)
                _lb.insert("end", eid)
                _av.set("")
                self._commit()

        def _del(_bt=bt, _lb=lb):
            sel = _lb.curselection()
            if not sel: return
            idx = sel[0]
            _lb.delete(idx)
            lst = self._data[_bt]["forbidden"]
            if 0 <= idx < len(lst): lst.pop(idx)
            self._commit()

        tk.Button(ctrl, text="+ Hinzufügen", command=_add,
                  bg=self.BG3, fg=self.C_FORB,
                  font=("Segoe UI", 8), cursor="hand2",
                  relief="flat").pack(fill="x", pady=1)
        tk.Button(ctrl, text="✕ Entfernen", command=_del,
                  bg=self.BG3, fg=self.C_FORB,
                  font=("Segoe UI", 8), cursor="hand2",
                  relief="flat").pack(fill="x")

    # ── Pflicht-Gruppen ───────────────────────────────────────────────────────

    def _draw_required_groups(self, bt: str, c: dict):
        sec = tk.Frame(self._inner, bg=self.BG)
        sec.pack(fill="x", padx=8, pady=2)

        hrow = tk.Frame(sec, bg=self.BG)
        hrow.pack(fill="x")
        tk.Label(hrow, text="Pflicht-Gruppen", bg=self.BG, fg=self.C_GRP,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(hrow,
                 text="  Aus jeder Gruppe wird genau 1 Effekt zufällig gezogen.",
                 bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 8)).pack(
            side="left")
        tk.Button(hrow, text="+ Neue Gruppe",
                  command=lambda _bt=bt: self._add_group(_bt),
                  bg=self.BG3, fg=self.C_GRP,
                  font=("Segoe UI", 8), cursor="hand2",
                  relief="flat").pack(side="right")

        self._groups_container = tk.Frame(sec, bg=self.BG)
        self._groups_container.pack(fill="x", pady=4)
        self._redraw_groups(bt)

    def _redraw_groups(self, bt: str):
        for w in self._groups_container.winfo_children():
            w.destroy()
        groups = self._data.get(bt, {}).get("required_groups", [])
        if not groups:
            tk.Label(self._groups_container,
                     text="Keine Gruppen — '+ Neue Gruppe' klicken.",
                     bg=self.BG, fg=self.FG_DIM,
                     font=("Segoe UI", 8, "italic")).pack(
                anchor="w", padx=4, pady=4)
            return
        for gi, group in enumerate(groups):
            self._draw_group(bt, gi, group)

    def _draw_group(self, bt: str, gi: int, group: list):
        box = tk.Frame(self._groups_container, bg=self.BG2,
                       relief="groove", bd=1)
        box.pack(fill="x", pady=3)

        ghdr = tk.Frame(box, bg=self.BG2)
        ghdr.pack(fill="x", padx=6, pady=(4, 2))
        tk.Label(ghdr, text=f"Gruppe {gi + 1}",
                 bg=self.BG2, fg=self.C_GRP,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(ghdr,
                 text=f"({len(group)} Effekt{'e' if len(group) != 1 else ''}"
                      f" — 1 wird gezogen)",
                 bg=self.BG2, fg=self.FG_DIM,
                 font=("Segoe UI", 7)).pack(side="left", padx=6)
        tk.Button(ghdr, text="✕ Gruppe löschen",
                  command=lambda i=gi, _bt=bt: self._del_group(_bt, i),
                  bg="#2a1a1a", fg="#ff8888",
                  font=("Segoe UI", 7), cursor="hand2",
                  relief="flat").pack(side="right")

        body = tk.Frame(box, bg=self.BG2)
        body.pack(fill="x", padx=6, pady=(0, 4))

        lb = tk.Listbox(body, height=max(2, len(group)),
                        bg="#221e00", fg=self.C_GRP,
                        selectbackground="#554400", activestyle="none",
                        font=("Consolas", 8), relief="flat", bd=0)
        for eid in group:
            lb.insert("end", eid)
        lb.pack(side="left", fill="x", expand=True, padx=0)

        ctrl = tk.Frame(body, bg=self.BG2)
        ctrl.pack(side="left", padx=6, anchor="n")

        add_var = tk.StringVar()
        ttk.Combobox(ctrl, textvariable=add_var,
                     values=self._all_effect_ids,
                     width=20, font=("Segoe UI", 8)).pack(pady=1)

        def _add(i=gi, _lb=lb, _av=add_var, _bt=bt):
            eid = _av.get().strip()
            grp = self._data[_bt]["required_groups"][i]
            if eid and eid not in grp:
                grp.append(eid)
                _lb.insert("end", eid)
                _lb.config(height=max(2, len(grp)))
                _av.set("")
                self._commit()
                self._redraw_groups(_bt)

        def _del(i=gi, _lb=lb, _bt=bt):
            sel = _lb.curselection()
            if not sel: return
            idx = sel[0]
            _lb.delete(idx)
            grp = self._data[_bt]["required_groups"][i]
            if 0 <= idx < len(grp): grp.pop(idx)
            _lb.config(height=max(2, len(grp)))
            self._commit()
            self._redraw_groups(_bt)

        tk.Button(ctrl, text="+ Effekt hinzufügen", command=_add,
                  bg=self.BG3, fg=self.C_GRP,
                  font=("Segoe UI", 8), cursor="hand2",
                  relief="flat").pack(fill="x", pady=1)
        tk.Button(ctrl, text="✕ Effekt entfernen", command=_del,
                  bg=self.BG3, fg=self.C_GRP,
                  font=("Segoe UI", 8), cursor="hand2",
                  relief="flat").pack(fill="x")

    def _add_group(self, bt: str):
        self._data.setdefault(bt, {
            "forbidden": [], "required_groups": []})
        self._data[bt].setdefault("required_groups", []).append([])
        self._commit()
        self._redraw_groups(bt)

    def _del_group(self, bt: str, idx: int):
        groups = self._data.get(bt, {}).get("required_groups", [])
        if 0 <= idx < len(groups):
            groups.pop(idx)
        self._commit()
        self._redraw_groups(bt)
