"""
dialogs.py -- Reusable dialog widgets for the card builder.
"""

import tkinter as tk


class EffectPickerDialog(tk.Toplevel):
    """Reusable effect picker dialog.

    Parameters:
        parent: parent widget
        title: dialog title string
        current_data: dict with optional keys 'effect_id', 'vals', 'opt_vals'
        on_ok: callback(effect_data_dict) called when OK pressed
    """

    _BG = "#1a1a1a"
    _BG_ROW = "#1e1e1e"
    _BG_SEL = "#1a4a1a"

    def __init__(self, parent, title: str, current_data: dict, on_ok):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=self._BG)
        self.grab_set()
        self.resizable(True, True)

        self._on_ok = on_ok
        self._cd = None
        self._effs = []
        self._var_vals: dict = dict((current_data or {}).get("vals", {}))
        self._var_widgets: dict = {}  # var_name -> StringVar
        self._effect_rows: dict = {}  # eid -> frame

        # Load effects
        try:
            from card_builder.data import get_content_data
            self._cd = get_content_data()
            self._effs = self._cd.effects
        except Exception:
            self._effs = []

        if not self._effs:
            self.destroy()
            return

        cur_id = (current_data or {}).get("effect_id", "")
        self._sel_var = tk.StringVar(value=cur_id)

        self._build_search_bar()
        self._build_effect_list()
        self._build_var_panel()
        self._build_buttons()

        # Initial population
        self._populate_list()
        self._rebuild_var_inputs()

        self.bind("<Return>", lambda _: self._do_ok())
        self.bind("<Escape>", lambda _: self.destroy())

    # ── Search bar ────────────────────────────────────────────────────────────

    def _build_search_bar(self):
        self._search_var = tk.StringVar()
        sf = tk.Frame(self, bg=self._BG)
        sf.pack(fill="x", padx=8, pady=(8, 2))
        tk.Label(sf, text="\U0001f50d", bg=self._BG, fg="#aaa").pack(side="left")
        tk.Entry(sf, textvariable=self._search_var, bg="#2a2a2a", fg="white",
                 insertbackground="white", font=("Arial", 9), width=28).pack(
            side="left", padx=4, fill="x", expand=True)
        self._search_var.trace_add(
            "write", lambda *_: self._populate_list(self._search_var.get()))

    # ── Effect list (scrollable) ──────────────────────────────────────────────

    def _build_effect_list(self):
        list_outer = tk.Frame(self, bg=self._BG)
        list_outer.pack(fill="both", expand=True, padx=8, pady=4)

        vsb = tk.Scrollbar(list_outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._canvas = tk.Canvas(list_outer, bg=self._BG,
                                 yscrollcommand=vsb.set, highlightthickness=0,
                                 width=420, height=320)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._canvas.yview)

        self._inner = tk.Frame(self._canvas, bg=self._BG)
        self._inner_win = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._inner_win, width=e.width))
        self._canvas.bind(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-e.delta / 120), "units"))

    # ── Variable inputs panel ─────────────────────────────────────────────────

    def _build_var_panel(self):
        self._var_frame = tk.LabelFrame(self, text="Variablen", bg=self._BG,
                                        fg="#88aaff", font=("Arial", 8))
        self._var_frame.pack(fill="x", padx=8, pady=4)

    # ── Buttons ───────────────────────────────────────────────────────────────

    def _build_buttons(self):
        btn_row = tk.Frame(self, bg=self._BG)
        btn_row.pack(fill="x", padx=8, pady=(2, 8))

        tk.Button(btn_row, text="\u2713 OK", command=self._do_ok,
                  bg="#1a4a1a", fg="#88ff88",
                  font=("Arial", 9, "bold"), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        tk.Button(btn_row, text="\u2715 L\u00f6schen", command=self._do_clear,
                  bg="#3a1a1a", fg="#ff8888",
                  font=("Arial", 9), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        tk.Button(btn_row, text="Abbrechen", command=self.destroy,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 9), cursor="hand2",
                  width=10).pack(side="left", padx=4)

    # ── Internal logic ────────────────────────────────────────────────────────

    def _on_select(self, eid: str):
        self._sel_var.set(eid)
        self._rebuild_row_highlights()
        self._rebuild_var_inputs()

    def _rebuild_row_highlights(self):
        cur = self._sel_var.get()
        for eid, fr in self._effect_rows.items():
            fr.config(bg=self._BG_SEL if eid == cur else self._BG_ROW)

    def _populate_list(self, filter_text=""):
        for w in self._inner.winfo_children():
            w.destroy()
        self._effect_rows.clear()
        ft = filter_text.lower()
        for item in self._effs:
            eid = item.get("id", "")
            if ft and ft not in eid.lower():
                continue
            ct = item.get("content_text") or item.get("effect_text", "")
            is_sel = (eid == self._sel_var.get())
            bg = self._BG_SEL if is_sel else self._BG_ROW

            fr = tk.Frame(self._inner, bg=bg, cursor="hand2")
            fr.pack(fill="x", pady=1, padx=2)
            self._effect_rows[eid] = fr

            chk_var = tk.BooleanVar(value=is_sel)
            tk.Checkbutton(fr, variable=chk_var,
                           bg=bg, activebackground=bg,
                           selectcolor=self._BG_SEL,
                           command=lambda e=eid, cv=chk_var: (
                               self._on_select(e) if cv.get() else self._on_select("")
                           )).pack(side="left", padx=4)

            tk.Label(fr, text=eid, bg=bg, fg="#88ff88",
                     font=("Consolas", 9, "bold"), width=22,
                     anchor="w").pack(side="left")
            tk.Label(fr, text=ct[:40] if ct else "\u2014",
                     bg=bg, fg="#aaa",
                     font=("Arial", 8), anchor="w").pack(side="left", padx=4)

            fr.bind("<Button-1>", lambda _, e=eid: self._on_select(e))

    def _rebuild_var_inputs(self):
        for w in self._var_frame.winfo_children():
            w.destroy()
        self._var_widgets.clear()
        eid = self._sel_var.get()
        if not eid:
            return
        try:
            item = self._cd.get("effect", eid)
        except Exception:
            item = None
        if not item:
            return
        variables = item.get("variables", {})
        if not variables:
            tk.Label(self._var_frame, text="(keine Variablen)",
                     bg=self._BG, fg="#555", font=("Arial", 8)).pack(
                anchor="w", padx=6)
            return
        for vname in variables:
            r = tk.Frame(self._var_frame, bg=self._BG)
            r.pack(fill="x", padx=6, pady=1)
            tk.Label(r, text=f"{{{vname}}}:",
                     bg=self._BG, fg="#88aaff",
                     font=("Arial", 8, "bold"), width=10).pack(side="left")
            vv = tk.StringVar(value=str(self._var_vals.get(vname, "")))
            self._var_widgets[vname] = vv
            tk.Entry(r, textvariable=vv, width=8,
                     bg="#2a2a2a", fg="white",
                     insertbackground="white",
                     font=("Arial", 8)).pack(side="left", padx=4)

    def _do_ok(self):
        eid = self._sel_var.get()
        if eid:
            vals = {k: v.get() for k, v in self._var_widgets.items()}
            result = {"effect_id": eid, "vals": vals, "opt_vals": {}}
        else:
            result = {}
        self._on_ok(result)
        self.destroy()

    def _do_clear(self):
        self._sel_var.set("")
        self._rebuild_row_highlights()
        self._rebuild_var_inputs()
