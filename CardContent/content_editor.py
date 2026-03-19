"""
content_editor.py – ContentEditor window and sub-dialogs.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from CardContent.template_parser import (
    parse_template, render_content_text,
    make_default_stat, sync_item_template,
    collect_all_ids, find_references,
    rename_id_everywhere, rename_content_id,
)
from CardContent.window_memory import wm
from CardContent.template_syntax_help import SyntaxHelpWindow

ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Meta"]

# Card types for the weight section grouping
CARD_TYPES = ["Spells", "Prowess", "Loot", "Equipment", "Alchemy"]

DEFAULT_ELEMENT_WEIGHT = 10   # used by auto-generator when field is empty


def get_element_weight(weights: dict, el: str) -> float:
    """Return element weight, falling back to DEFAULT_ELEMENT_WEIGHT if missing/empty."""
    v = weights.get(el, "")
    if v == "" or v is None:
        return DEFAULT_ELEMENT_WEIGHT
    try:
        return float(v)
    except (ValueError, TypeError):
        return DEFAULT_ELEMENT_WEIGHT


class ContentEditor(tk.Toplevel):

    def __init__(self, parent, item: dict, data: dict, on_save=None):
        super().__init__(parent)
        self.item         = item
        self.data         = data
        self.on_save      = on_save
        self._original_id = item.get("id", "")
        self.title(f"Edit – {item.get('id', '?')}")
        wm.restore(self, "content_editor", "860x700")
        self._build()

    # ── Scrollable layout ──────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self)
        outer.pack(fill="both", expand=True)
        vsb   = tk.Scrollbar(outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(outer, yscrollcommand=vsb.set, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        vsb.config(command=canvas.yview)

        self._f  = tk.Frame(canvas)
        win_id   = canvas.create_window((0, 0), window=self._f, anchor="nw")
        self._f.bind("<Configure>",
                     lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._f.columnconfigure(1, weight=1)
        self._row = 0
        self._build_basic_fields()
        self._sep()
        self._build_var_section()
        self._sep()
        self._build_opt_section()
        self._sep()
        tk.Button(self._f, text="💾 Save", command=self._save,
                  bg="#1a6e3c", fg="white", font=("Arial", 10, "bold"),
                  width=20).grid(row=self._row, column=0, columnspan=6, pady=14)

    def _sep(self):
        ttk.Separator(self._f, orient="horizontal").grid(
            row=self._row, column=0, columnspan=6, sticky="ew", pady=6)
        self._row += 1

    # ── Basic fields ───────────────────────────────────────────────────────────

    def _build_basic_fields(self):
        def lbl(text):
            tk.Label(self._f, text=text, font=("Arial", 9, "bold")).grid(
                row=self._row, column=0, sticky="w", padx=8, pady=3)

        lbl("ID")
        self._id_var = tk.StringVar(value=self.item.get("id", ""))
        tk.Entry(self._f, textvariable=self._id_var, width=36).grid(
            row=self._row, column=1, columnspan=3, sticky="we", padx=8, pady=3)
        tk.Label(self._f, text="(Umbenennen propagiert alle Child-IDs)",
                 fg="#888", font=("Arial", 8)).grid(
            row=self._row, column=4, sticky="w", padx=4)
        self._row += 1

        lbl("Content Box")
        self._cb_var = tk.StringVar(value=self.item.get("content_box", ""))
        tk.Entry(self._f, textvariable=self._cb_var, width=52).grid(
            row=self._row, column=1, columnspan=4, sticky="we", padx=8, pady=3)
        tk.Button(self._f, text="?", command=lambda: SyntaxHelpWindow(self),
                  font=("Arial", 9, "bold"), width=2,
                  bg="#334", fg="#88ccff").grid(row=self._row, column=5, padx=2)
        self._cb_var.trace_add("write", self._on_cb_change)
        self._row += 1

        lbl("Content Text")
        self._ct_var = tk.StringVar(value=self.item.get("content_text", ""))
        ct_f = tk.Frame(self._f)
        ct_f.grid(row=self._row, column=1, columnspan=5, sticky="we", padx=8, pady=3)
        tk.Entry(ct_f, textvariable=self._ct_var, width=52).pack(
            side="left", fill="x", expand=True)
        tk.Button(ct_f, text="↺", command=self._sync_preview,
                  font=("Arial", 8), width=2).pack(side="left", padx=2)
        tk.Button(ct_f, text="?", command=lambda: SyntaxHelpWindow(self),
                  font=("Arial", 9, "bold"), width=2,
                  bg="#334", fg="#88ccff").pack(side="left", padx=2)
        self._row += 1

        lbl("Reminder Text")
        self._rt_var = tk.StringVar(value=self.item.get("reminder_text", ""))
        rt_f = tk.Frame(self._f)
        rt_f.grid(row=self._row, column=1, columnspan=5, sticky="we", padx=8, pady=3)
        tk.Entry(rt_f, textvariable=self._rt_var, width=52).pack(
            side="left", fill="x", expand=True)
        tk.Button(rt_f, text="?", command=lambda: SyntaxHelpWindow(self),
                  font=("Arial", 9, "bold"), width=2,
                  bg="#334", fg="#88ccff").pack(side="left", padx=2)
        self._row += 1

        lbl("Rarity")
        self._rar_var = tk.StringVar(value=str(self.item.get("rarity", 10)))
        tk.Entry(self._f, textvariable=self._rar_var, width=10).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=3)
        self._row += 1

        lbl("Complexity Base")
        self._cpx_var = tk.StringVar(value=str(self.item.get("complexity_base", 1.0)))
        tk.Entry(self._f, textvariable=self._cpx_var, width=10).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=3)
        self._row += 1

        # cv1 / cv2 / cv3 – content value fields for the whole item
        lbl("cv1")
        self._cv1_var = tk.StringVar(value=str(self.item.get("cv1", "")))
        tk.Entry(self._f, textvariable=self._cv1_var, width=10).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=3)
        tk.Label(self._f, text="cv2", font=("Arial", 9, "bold")).grid(
            row=self._row, column=2, sticky="w", padx=4)
        self._cv2_var = tk.StringVar(value=str(self.item.get("cv2", "")))
        tk.Entry(self._f, textvariable=self._cv2_var, width=10).grid(
            row=self._row, column=3, sticky="w", padx=4, pady=3)
        tk.Label(self._f, text="cv3", font=("Arial", 9, "bold")).grid(
            row=self._row, column=4, sticky="w", padx=4)
        self._cv3_var = tk.StringVar(value=str(self.item.get("cv3", "")))
        tk.Entry(self._f, textvariable=self._cv3_var, width=10).grid(
            row=self._row, column=5, sticky="w", padx=4, pady=3)
        self._row += 1

        bf = tk.Frame(self._f)
        bf.grid(row=self._row, column=1, columnspan=5, sticky="w", padx=8, pady=4)
        tk.Button(bf, text="◈ Effect Conditions",
                  command=self._edit_effect_conditions,
                  bg="#553300", fg="white").pack(side="left", padx=4)
        self._row += 1

        # ── Collapsible weights section ────────────────────────────────────────
        self._build_weights_section()

    def _build_weights_section(self):
        """Collapsible card-type weights + element weights section."""
        # Load saved open/closed state
        _state_key = "weights_open"
        is_open = self.item.get(_state_key, False)

        container = tk.Frame(self._f, relief="groove", bd=1)
        container.grid(row=self._row, column=0, columnspan=6,
                       sticky="ew", padx=8, pady=4)
        self._row += 1

        # Toggle header
        header = tk.Frame(container, bg="#1a1a2a")
        header.pack(fill="x")

        self._weights_open = tk.BooleanVar(value=is_open)
        self._weights_body  = tk.Frame(container)

        def _toggle():
            if self._weights_open.get():
                self._weights_body.pack(fill="x", padx=8, pady=4)
                toggle_btn.config(text="▼  Kartentyp & Element Gewichtungen")
            else:
                self._weights_body.pack_forget()
                toggle_btn.config(text="▶  Kartentyp & Element Gewichtungen")
            self.item[_state_key] = self._weights_open.get()

        toggle_btn = tk.Button(
            header,
            text=("▼" if is_open else "▶") + "  Kartentyp & Element Gewichtungen",
            command=lambda: (
                self._weights_open.set(not self._weights_open.get()),
                _toggle()
            ),
            bg="#1a1a2a", fg="#aaaacc",
            font=("Arial", 9, "bold"), relief="flat", anchor="w",
        )
        toggle_btn.pack(fill="x", padx=4, pady=4)

        # ── Body (card type weights) ───────────────────────────────────────────
        body = self._weights_body

        tk.Label(body, text="Kartentyp Gewichtungen",
                 font=("Arial", 9, "bold"), fg="#cc8833").pack(anchor="w", pady=(4,2))
        tk.Label(body, text="Leer = Standard (10)   0 = nie",
                 fg="#888", font=("Arial", 8)).pack(anchor="w")

        ct_weights = self.item.setdefault("card_type_weights", {})
        self._ct_weight_vars = {}
        ct_grid = tk.Frame(body)
        ct_grid.pack(fill="x", pady=4)

        for i, ct in enumerate(CARD_TYPES):
            col = i * 2
            tk.Label(ct_grid, text=ct, font=("Arial", 8, "bold"),
                     width=10, anchor="w").grid(row=0, column=col, padx=4)
            raw = ct_weights.get(ct, "")
            v   = tk.StringVar(value="" if raw == "" or raw is None else str(raw))
            self._ct_weight_vars[ct] = v
            tk.Entry(ct_grid, textvariable=v, width=6).grid(
                row=0, column=col+1, padx=2)

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=6)

        # ── Element weights (only for Spells) ──────────────────────────────────
        tk.Label(body, text="Element Gewichtungen  (nur für Spells)",
                 font=("Arial", 9, "bold"), fg="#5588cc").pack(anchor="w", pady=(2,2))
        tk.Label(body, text="☑ = erlaubt   Leer = Standard (10)   0 = nie",
                 fg="#888", font=("Arial", 8)).pack(anchor="w")

        el_weights  = self.item.setdefault("element_weights", {})
        allowed_els = self.item.get("allowed_elements", [])
        self._el_vars    = {}
        self._el_weights = {}

        hdr = tk.Frame(body)
        hdr.pack(fill="x", pady=2)
        for txt, w in [("Element", 10), ("Erlaubt", 7), ("Gewicht", 8), ("", 10)]:
            tk.Label(hdr, text=txt, font=("Arial", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2)

        for el in ELEMENTS:
            row_f = tk.Frame(body)
            row_f.pack(fill="x", pady=1)

            enabled = (el in allowed_els) if allowed_els else True
            ev = tk.BooleanVar(value=enabled)
            self._el_vars[el] = ev
            tk.Checkbutton(row_f, text=el, variable=ev, width=10,
                           anchor="w").pack(side="left")

            raw_w = el_weights.get(el, "")
            wv = tk.StringVar(value="" if raw_w == "" or raw_w is None
                              else str(raw_w))
            self._el_weights[el] = wv
            tk.Entry(row_f, textvariable=wv, width=6).pack(side="left", padx=4)

            bar = tk.Label(row_f, text="", bg="#1a6e3c", height=1, width=1)
            bar.pack(side="left", padx=2)

            def _upd(ev=None, b=bar, wvar=wv):
                raw = wvar.get().strip()
                try:    val = max(0, min(20, int(float(raw)))) if raw else DEFAULT_ELEMENT_WEIGHT
                except: val = 0
                b.config(width=max(1, val))

            wv.trace_add("write", lambda *_, fn=_upd: fn())
            _upd()

        # Show/hide body based on initial state
        if is_open:
            self._weights_body.pack(fill="x", padx=8, pady=4)

    def _sync_preview(self):
        parsed  = parse_template(self._cb_var.get())
        preview = render_content_text(
            self._cb_var.get(), {},
            {str(i): c[0] for i, c in enumerate(parsed["options"]) if c}
        )
        self._ct_var.set(preview)

    # ── Sections ───────────────────────────────────────────────────────────────

    def _build_var_section(self):
        tk.Label(self._f, text="Variables  {X}",
                 font=("Arial", 10, "bold"), fg="#5588cc").grid(
            row=self._row, column=0, sticky="w", padx=8)
        self._row += 1
        self._var_frame = tk.Frame(self._f)
        self._var_frame.grid(row=self._row, column=0, columnspan=6,
                             sticky="ew", padx=8)
        self._row += 1
        self._rebuild_vars()

    def _build_opt_section(self):
        tk.Label(self._f, text="Options  [a, b, c]",
                 font=("Arial", 10, "bold"), fg="#cc8833").grid(
            row=self._row, column=0, sticky="w", padx=8)
        self._row += 1
        self._opt_frame = tk.Frame(self._f)
        self._opt_frame.grid(row=self._row, column=0, columnspan=6,
                             sticky="ew", padx=8)
        self._row += 1
        self._rebuild_opts()

    def _on_cb_change(self, *_):
        self.item["content_box"] = self._cb_var.get()
        sync_item_template(self.item)
        self._rebuild_vars()
        self._rebuild_opts()

    # ── Stat header & row ──────────────────────────────────────────────────────

    def _stat_header(self, parent):
        hdr = tk.Frame(parent)
        hdr.pack(fill="x")
        for txt, w in [("Name", 10), ("ID", 16), ("Rarity", 7), ("Cmplx", 7),
                       ("cv1", 5), ("cv2", 5), ("cv3", 5), ("", 8), ("🎲?", 4), ("🎲!", 4), ("", 3)]:
            tk.Label(hdr, text=txt, font=("Arial", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=1)

    def _stat_row(self, parent, label: str, label_color: str,
                  stat: dict,
                  stat_type: str = "variable",
                  choices: list  = None,
                  can_delete: bool = False,
                  on_delete = None):

        row = tk.Frame(parent, relief="groove", bd=1)
        row.pack(fill="x", pady=1)

        tk.Label(row, text=label, width=10,
                 fg=label_color, font=("Arial", 9, "bold")).pack(side="left", padx=4)

        id_var   = tk.StringVar(value=stat.get("id", ""))
        id_entry = tk.Entry(row, textvariable=id_var, width=16,
                            font=("Arial", 8), fg="#aaaaff", bg="#1a1a2e")
        id_entry.pack(side="left", padx=2)
        old_ref = [stat.get("id", "")]

        def _on_id(_e, s=stat, iv=id_var, ref=old_ref):
            new = iv.get().strip()
            old = ref[0]
            if new and new != old:
                n = rename_id_everywhere(old, new, self.data)
                s["id"] = new
                ref[0]  = new
                if n:
                    self._flash(f"'{old}' → '{new}'  ({n} Refs aktualisiert)")

        id_entry.bind("<FocusOut>", _on_id)
        id_entry.bind("<Return>",   _on_id)

        fields = [
            ("rarity",     tk.StringVar(value=str(stat.get("rarity",     10))),  7),
            ("complexity", tk.StringVar(value=str(stat.get("complexity", 1.0))), 7),
            ("cv1",        tk.StringVar(value=str(stat.get("cv1", 0))),           5),
            ("cv2",        tk.StringVar(value=str(stat.get("cv2", 0))),           5),
            ("cv3",        tk.StringVar(value=str(stat.get("cv3", 0))),           5),
        ]
        casts = {"rarity": int, "complexity": float,
                 "cv1": float, "cv2": float, "cv3": float}

        def _trace(*_, s=stat, fl=fields, ca=casts):
            for key, var, _ in fl:
                try:    s[key] = ca[key](var.get())
                except: pass

        for key, var, w in fields:
            var.trace_add("write", _trace)
            tk.Entry(row, textvariable=var, width=w).pack(side="left", padx=1)

        tk.Button(
            row, text="Cond.",
            command=lambda s=stat, st=stat_type, ch=choices: ConditionsEditor(
                self, s, self.data, stat_type=st, choices=ch or []),
            font=("Arial", 8)
        ).pack(side="left", padx=3)

        # Dice checkboxes – only for variable rows
        if stat_type == "variable":
            for dk, dl, tt in [
                ("dice_allowed", "🎲?", "Würfel erlaubt"),
                ("dice_only",    "🎲!", "Nur Würfel"),
            ]:
                bv = tk.BooleanVar(value=bool(stat.get(dk, False)))
                bv.trace_add("write",
                             lambda *_, k=dk, v=bv, s=stat: s.__setitem__(k, v.get()))
                tk.Checkbutton(row, text=dl, variable=bv,
                               font=("Arial", 7),
                               activebackground="#2a2a3a").pack(side="left", padx=1)

        if can_delete and on_delete:
            tk.Button(row, text="✕", fg="red",
                      command=lambda s=stat: on_delete(s),
                      font=("Arial", 8, "bold"), width=2).pack(side="left", padx=2)

    # ── Rebuild vars ───────────────────────────────────────────────────────────

    def _rebuild_vars(self):
        for w in self._var_frame.winfo_children():
            w.destroy()
        variables = self.item.get("variables", {})
        if not variables:
            tk.Label(self._var_frame, text="(none – use {X} in Content Box)",
                     fg="#888").pack(anchor="w", padx=4)
            return

        self._stat_header(self._var_frame)
        for vname, stat in variables.items():
            if not stat.get("id"):
                stat["id"] = f"{self.item.get('id', 'item')}.{vname}"

            def _del(s, n=vname):
                refs = find_references(s.get("id", ""), self.data)
                if refs:
                    messagebox.showerror("Löschen nicht möglich",
                        "Noch referenziert in:\n" +
                        "\n".join(r["location"] for r in refs))
                    return
                del self.item["variables"][n]
                self._cb_var.set(self._cb_var.get().replace(f"{{{n}}}", ""))
                self._rebuild_vars()

            self._stat_row(self._var_frame, label=f"{{{vname}}}",
                           label_color="#5588cc", stat=stat,
                           stat_type="variable", can_delete=True, on_delete=_del)

    # ── Rebuild opts ───────────────────────────────────────────────────────────

    def _rebuild_opts(self):
        for w in self._opt_frame.winfo_children():
            w.destroy()
        options = self.item.get("options", {})
        if not options:
            tk.Label(self._opt_frame, text="(none – use [a, b, c] in Content Box)",
                     fg="#888").pack(anchor="w", padx=4)
            return

        for opt_key, opt in options.items():
            choices    = opt.get("choices", [])
            per_choice = opt.setdefault("per_choice", {})

            grp = tk.LabelFrame(self._opt_frame,
                                text=f"Option {opt_key}:  [{', '.join(choices)}]",
                                font=("Arial", 9, "bold"), fg="#cc8833")
            grp.pack(fill="x", pady=3)
            self._stat_header(grp)

            for choice in choices:
                stat = per_choice.setdefault(choice, make_default_stat())
                if not stat.get("id"):
                    stat["id"] = f"{self.item.get('id', 'item')}.{opt_key}.{choice}"

                def _del(s, c=choice, ok=opt_key):
                    refs = find_references(s.get("id", ""), self.data)
                    if refs:
                        messagebox.showerror("Löschen nicht möglich",
                            "Noch referenziert in:\n" +
                            "\n".join(r["location"] for r in refs))
                        return
                    self.item["options"][ok]["choices"].remove(c)
                    self.item["options"][ok]["per_choice"].pop(c, None)
                    if not self.item["options"][ok]["choices"]:
                        self.item["options"].pop(ok, None)
                    self._rebuild_opts()

                self._stat_row(grp, label=choice, label_color="#cc8833",
                               stat=stat, stat_type="choice", choices=choices,
                               can_delete=True, on_delete=_del)

    # ── Sub-editors ────────────────────────────────────────────────────────────

    def _edit_effect_conditions(self):
        ConditionsEditor(self, self.item, self.data, stat_type="effect")

    def _flash(self, msg: str):
        bar = tk.Label(self, text=msg, bg="#1a3e8e", fg="white", font=("Arial", 9))
        bar.pack(side="bottom", fill="x")
        self.after(3000, bar.destroy)

    # ── Save ───────────────────────────────────────────────────────────────────

    def _save(self):
        new_id = self._id_var.get().strip()
        old_id = self._original_id
        if new_id and new_id != old_id:
            n = rename_content_id(old_id, new_id, self.data)
            if n:
                self._flash(f"Content ID '{old_id}' → '{new_id}'  ({n} Änderungen)")

        self.item["id"]              = new_id
        self.item["content_box"]     = self._cb_var.get()
        self.item["content_text"]    = self._ct_var.get()
        self.item["reminder_text"]   = self._rt_var.get()
        try:    self.item["rarity"]          = int(self._rar_var.get())
        except: pass
        try:    self.item["complexity_base"] = float(self._cpx_var.get())
        except: pass

        # cv1 / cv2 / cv3 item-level values
        for key, var in [("cv1", self._cv1_var),
                         ("cv2", self._cv2_var),
                         ("cv3", self._cv3_var)]:
            raw = var.get().strip()
            if raw:
                try:    self.item[key] = float(raw)
                except: pass
            else:
                self.item.pop(key, None)

        # Card type weights
        if hasattr(self, "_ct_weight_vars"):
            ct_w = {}
            for ct, v in self._ct_weight_vars.items():
                raw = v.get().strip()
                if raw:
                    try:    ct_w[ct] = float(raw)
                    except: pass
            if ct_w:
                self.item["card_type_weights"] = ct_w
            else:
                self.item.pop("card_type_weights", None)

        # Element weights + allowed (from collapsible section)
        if hasattr(self, "_el_vars"):
            sel = [el for el, v in self._el_vars.items() if v.get()]
            if len(sel) < len(ELEMENTS):
                self.item["allowed_elements"] = sel
            else:
                self.item.pop("allowed_elements", None)
            ew = {}
            for el in ELEMENTS:
                raw = self._el_weights[el].get().strip()
                if raw:
                    try:    ew[el] = float(raw)
                    except: pass
            if ew:
                self.item["element_weights"] = ew
            else:
                self.item.pop("element_weights", None)

        if self.on_save:
            self.on_save()
        self.destroy()


# ── Conditions Editor ──────────────────────────────────────────────────────────

class ConditionsEditor(tk.Toplevel):
    """
    stat_type:
        "effect"    – item-level (no var_min/max, no excluded_choices)
        "variable"  – has var_min / var_max
        "choice"    – has excluded_choices checklist
    """

    def __init__(self, parent, stat_or_item: dict, data: dict,
                 stat_type: str = "variable", choices: list = None):
        super().__init__(parent)
        self.data      = data
        self.stat_type = stat_type
        self.choices   = choices or []
        self.title({
            "effect":   "Effect Conditions",
            "variable": "Variable Conditions",
            "choice":   "Choice Conditions",
        }.get(stat_type, "Conditions"))
        wm.restore(self, "conditions_editor", "540x660")
        self.cond = stat_or_item.setdefault("conditions", {})
        self._build()

    def _build(self):
        outer = tk.Frame(self)
        outer.pack(fill="both", expand=True)
        vsb   = tk.Scrollbar(outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(outer, yscrollcommand=vsb.set, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        vsb.config(command=canvas.yview)
        f = tk.Frame(canvas)
        wid = canvas.create_window((0, 0), window=f, anchor="nw")
        f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        f.columnconfigure(1, weight=1)
        row = 0

        # ── Mana range ────────────────────────────────────────────────────────
        tk.Label(f, text="Mana Kosten", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(8,2)); row += 1
        for label, key in [("Min", "min_mana"), ("Max", "max_mana")]:
            tk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=16)
            var = tk.StringVar(value=str(self.cond.get(key, "")))
            tk.Entry(f, textvariable=var, width=8).grid(
                row=row, column=1, sticky="w", padx=8)
            setattr(self, f"_{key}_var", var)
            row += 1

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Variable min/max ──────────────────────────────────────────────────
        if self.stat_type == "variable":
            tk.Label(f, text="Variablen Wertebereich",
                     font=("Arial", 9, "bold")).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            tk.Label(f, text="Leer = kein Limit",
                     fg="#888", font=("Arial", 8)).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            for label, key in [("Min Wert", "var_min"), ("Max Wert", "var_max")]:
                tk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=16)
                var = tk.StringVar(value=str(self.cond.get(key, "")))
                tk.Entry(f, textvariable=var, width=8).grid(
                    row=row, column=1, sticky="w", padx=8)
                setattr(self, f"_{key}_var", var)
                row += 1
            ttk.Separator(f, orient="horizontal").grid(
                row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Excluded choices ──────────────────────────────────────────────────
        elif self.stat_type == "choice":
            tk.Label(f, text="Erlaubte Choices",
                     font=("Arial", 9, "bold")).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            tk.Label(f, text="Deaktiviert = wird nie vom Auto-Generator gewählt",
                     fg="#888", font=("Arial", 8)).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            excluded = self.cond.get("excluded_choices", [])
            self._choice_vars: dict = {}
            for c in self.choices:
                v = tk.BooleanVar(value=(c not in excluded))
                self._choice_vars[c] = v
                tk.Checkbutton(f, text=c, variable=v).grid(
                    row=row, column=0, columnspan=3, sticky="w", padx=16)
                row += 1
            ttk.Separator(f, orient="horizontal").grid(
                row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Element weights & allowed ─────────────────────────────────────────
        tk.Label(f, text="Elemente – Erlaubt & Häufigkeit",
                 font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
        tk.Label(f,
                 text="☑ = erlaubt   Gewicht leer = Standard (10)   0 = nie",
                 fg="#888", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

        # header
        hdr = tk.Frame(f)
        hdr.grid(row=row, column=0, columnspan=3, sticky="w", padx=16); row += 1
        for txt, w in [("Element", 10), ("Erlaubt", 6), ("Gewicht", 8), ("", 12)]:
            tk.Label(hdr, text=txt, font=("Arial", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2)

        allowed         = self.cond.get("allowed_elements", [])
        stored_weights  = self.cond.get("element_weights", {})
        self._el_vars    = {}
        self._el_weights = {}

        el_f = tk.Frame(f)
        el_f.grid(row=row, column=0, columnspan=3, sticky="w", padx=16); row += 1

        for el in ELEMENTS:  # ELEMENTS now = ["Fire","Metal","Ice","Nature","Blood","Meta"]
            ef = tk.Frame(el_f)
            ef.pack(fill="x", pady=1)

            # Checkbox – default True when allowed_elements is empty (= all allowed)
            enabled = (el in allowed) if allowed else True
            v = tk.BooleanVar(value=enabled)
            self._el_vars[el] = v
            tk.Checkbutton(ef, text=el, variable=v, width=10,
                           anchor="w").pack(side="left")

            # Weight – stored value or empty string (empty = default 10)
            raw_w = stored_weights.get(el, "")
            wv = tk.StringVar(value="" if raw_w == "" or raw_w is None
                              else str(raw_w))
            self._el_weights[el] = wv

            entry = tk.Entry(ef, textvariable=wv, width=6)
            entry.pack(side="left", padx=4)

            # Visual bar – uses DEFAULT_ELEMENT_WEIGHT when empty
            bar = tk.Label(ef, text="", bg="#1a6e3c", height=1, width=1)
            bar.pack(side="left", padx=2)

            def _upd(ev=None, b=bar, wvar=wv):
                raw = wvar.get().strip()
                val = DEFAULT_ELEMENT_WEIGHT if raw == "" else 0
                try:    val = max(0, min(20, int(float(raw)))) if raw else DEFAULT_ELEMENT_WEIGHT
                except: val = 0
                b.config(width=max(1, val))

            wv.trace_add("write", lambda *_, fn=_upd: fn())
            _upd()

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── ID Conditions ─────────────────────────────────────────────────────
        tk.Label(f, text="ID Bedingungen", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
        tk.Label(f, text="✓ Muss aktiv = grün   ✗ Ausschluss = rot",
                 fg="#888", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

        self._ids_frame = tk.Frame(f)
        self._ids_frame.grid(row=row, column=0, columnspan=3,
                             sticky="ew", padx=8); row += 1

        raw = self.cond.get("id_conditions", [])
        if raw and isinstance(raw[0], str):
            raw = [{"id": r, "mode": "required"} for r in raw]
        self._id_conditions = [dict(r) for r in raw]
        self._rebuild_id_ui()

        add_f = tk.Frame(f)
        add_f.grid(row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

        all_ids    = collect_all_ids(self.data)
        var_ids    = [k for k, v in all_ids.items() if v["type"] == "variable"]
        choice_ids = [k for k, v in all_ids.items() if v["type"] == "choice"]

        self._new_id_var   = tk.StringVar()
        self._new_mode_var = tk.StringVar(value="required")

        ttk.Combobox(add_f, textvariable=self._new_id_var,
                     values=var_ids + choice_ids, width=24).pack(side="left", padx=4)
        ttk.Combobox(add_f, textvariable=self._new_mode_var,
                     values=["required", "exclude"],
                     state="readonly", width=10).pack(side="left", padx=4)
        tk.Button(add_f, text="＋ Add", command=self._add_id).pack(side="left")

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Notes ─────────────────────────────────────────────────────────────
        tk.Label(f, text="Notizen", font=("Arial", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8); row += 1
        self._notes_var = tk.StringVar(value=self.cond.get("notes", ""))
        tk.Entry(f, textvariable=self._notes_var, width=46).grid(
            row=row, column=0, columnspan=3, sticky="we", padx=8); row += 1

        tk.Button(self, text="Save", command=self._save,
                  bg="#1a6e3c", fg="white", width=14).pack(pady=10)

    # ── ID condition UI ────────────────────────────────────────────────────────

    def _rebuild_id_ui(self):
        for w in self._ids_frame.winfo_children():
            w.destroy()
        all_ids    = collect_all_ids(self.data)
        var_ids    = [k for k, v in all_ids.items() if v["type"] == "variable"]
        choice_ids = [k for k, v in all_ids.items() if v["type"] == "choice"]

        for entry in self._id_conditions:
            sid  = entry["id"]
            mode = entry["mode"]
            rf   = tk.Frame(self._ids_frame)
            rf.pack(fill="x", pady=1)

            exists = sid in all_ids
            color  = "#88ff88" if (exists and mode == "required") else \
                     "#ff8888" if (exists and mode == "exclude")  else "#ffaaaa"

            tk.Label(rf, text=sid, fg=color, font=("Arial", 9, "bold"),
                     width=24, anchor="w").pack(side="left", padx=4)

            def _toggle(e=entry):
                e["mode"] = "exclude" if e["mode"] == "required" else "required"
                self._rebuild_id_ui()

            tk.Button(rf,
                      text="✓ Muss" if mode == "required" else "✗ Ausschluss",
                      bg="#1a6e3c" if mode == "required" else "#8e1a1a",
                      fg="white", font=("Arial", 8), width=12,
                      command=_toggle).pack(side="left", padx=4)

            if not exists:
                rv = tk.StringVar()
                ttk.Combobox(rf, textvariable=rv,
                             values=var_ids + choice_ids, width=20).pack(
                    side="left", padx=2)
                def _reassign(old=sid, rv=rv, e=entry):
                    new = rv.get().strip()
                    if new and new != old:
                        e["id"] = new
                        self._rebuild_id_ui()
                tk.Button(rf, text="Reassign", command=_reassign,
                          font=("Arial", 8)).pack(side="left", padx=2)
            else:
                info = all_ids[sid]
                tk.Label(rf, text=f"({info['type']}  {info['item_id']})",
                         fg="#888", font=("Arial", 8)).pack(side="left", padx=4)

            tk.Button(rf, text="✕", fg="red",
                      command=lambda e=entry: self._remove_id(e),
                      font=("Arial", 8, "bold"), width=2).pack(side="left", padx=2)

    def _add_id(self):
        sid  = self._new_id_var.get().strip()
        mode = self._new_mode_var.get()
        if sid and not any(e["id"] == sid for e in self._id_conditions):
            self._id_conditions.append({"id": sid, "mode": mode})
            self._new_id_var.set("")
            self._rebuild_id_ui()

    def _remove_id(self, entry: dict):
        self._id_conditions = [e for e in self._id_conditions if e is not entry]
        self._rebuild_id_ui()

    # ── Save ───────────────────────────────────────────────────────────────────

    def _save(self):
        # Mana
        for key in ("min_mana", "max_mana"):
            var = getattr(self, f"_{key}_var")
            try:    self.cond[key] = int(var.get())
            except: self.cond.pop(key, None)

        # Variable min/max
        if self.stat_type == "variable":
            for key in ("var_min", "var_max"):
                var = getattr(self, f"_{key}_var", None)
                if var:
                    try:    self.cond[key] = float(var.get())
                    except: self.cond.pop(key, None)

        # Excluded choices
        if self.stat_type == "choice":
            excl = [c for c, v in self._choice_vars.items() if not v.get()]
            if excl: self.cond["excluded_choices"] = excl
            else:    self.cond.pop("excluded_choices", None)

        # Allowed elements – only save if not all checked
        sel = [el for el, v in self._el_vars.items() if v.get()]
        if len(sel) < len(ELEMENTS):
            self.cond["allowed_elements"] = sel
        else:
            self.cond.pop("allowed_elements", None)

        # Element weights – only save non-empty entries
        weights = {}
        for el in ELEMENTS:
            raw = self._el_weights[el].get().strip()
            if raw != "":
                try:    weights[el] = float(raw)
                except: pass
        if weights:
            self.cond["element_weights"] = weights
        else:
            self.cond.pop("element_weights", None)

        # ID conditions
        if self._id_conditions:
            self.cond["id_conditions"] = list(self._id_conditions)
        else:
            self.cond.pop("id_conditions", None)

        # Notes
        notes = self._notes_var.get()
        if notes: self.cond["notes"] = notes
        else:     self.cond.pop("notes", None)

        self.destroy()