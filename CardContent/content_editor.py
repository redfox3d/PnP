"""
content_editor.py – ContentEditor window and its sub-dialogs
(element weights, conditions, variable/option stats).
"""

import tkinter as tk
from tkinter import ttk

from CardContent.template_parser import (
    parse_template, render_content_text,
    make_default_stat, sync_item_template,
)
from CardContent.window_memory import wm

ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Meta", "Potion", "Skills"]


class ContentEditor(tk.Toplevel):
    """
    Full editor for one content item.

    Fields:
        id, content_box (→ live preview in content_text), reminder_text,
        rarity, complexity_base,
        per-variable stats, per-option/choice stats,
        element weights.
    """

    def __init__(self, parent, item: dict, on_save=None):
        super().__init__(parent)
        self.item    = item
        self.on_save = on_save
        self.title(f"Edit – {item.get('id', '?')}")
        wm.restore(self, "content_editor", "700x600")
        self._build()

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        outer  = tk.Frame(self)
        outer.pack(fill="both", expand=True)
        vsb    = tk.Scrollbar(outer, orient="vertical")
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
                  width=20).grid(row=self._row, column=0, columnspan=4, pady=14)

    def _sep(self):
        ttk.Separator(self._f, orient="horizontal").grid(
            row=self._row, column=0, columnspan=4, sticky="ew", pady=6)
        self._row += 1

    def _lbl(self, text):
        tk.Label(self._f, text=text, font=("Arial", 9, "bold")).grid(
            row=self._row, column=0, sticky="w", padx=8, pady=3)

    def _entry_var(self, key, width=52, default="") -> tk.StringVar:
        var = tk.StringVar(value=str(self.item.get(key, default)))
        tk.Entry(self._f, textvariable=var, width=width).grid(
            row=self._row, column=1, columnspan=3, sticky="we", padx=8, pady=3)
        self._row += 1
        return var

    # ── Basic fields ───────────────────────────────────────────────────────────

    def _build_basic_fields(self):
        self._lbl("ID");             self._id_var  = self._entry_var("id")
        self._lbl("Content Box")
        self._cb_var = tk.StringVar(value=self.item.get("content_box", ""))
        tk.Entry(self._f, textvariable=self._cb_var, width=52).grid(
            row=self._row, column=1, columnspan=3, sticky="we", padx=8, pady=3)
        self._cb_var.trace_add("write", self._on_cb_change)
        self._row += 1

        self._lbl("Content Text")
        self._ct_var = tk.StringVar(value=self.item.get("content_text", ""))
        tk.Entry(self._f, textvariable=self._ct_var, width=52).grid(
            row=self._row, column=1, columnspan=3, sticky="we", padx=8, pady=3)
        self._row += 1

        tk.Button(self._f, text="↺ Sync from Box",
                  command=self._sync_preview,
                  font=("Arial", 8)).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=2)
        self._row += 1

        self._lbl("Reminder Text"); self._rt_var  = self._entry_var("reminder_text")
        self._lbl("Rarity")
        self._rar_var = tk.StringVar(value=str(self.item.get("rarity", 10)))
        tk.Entry(self._f, textvariable=self._rar_var, width=10).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=3)
        self._row += 1

        self._lbl("Complexity Base")
        self._cpx_var = tk.StringVar(value=str(self.item.get("complexity_base", 1.0)))
        tk.Entry(self._f, textvariable=self._cpx_var, width=10).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=3)
        self._row += 1

        tk.Button(self._f, text="⚖ Element Weights",
                  command=self._edit_weights).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=4)
        self._row += 1

    # ── Variable section ───────────────────────────────────────────────────────

    def _build_var_section(self):
        tk.Label(self._f, text="Variables  {X}",
                 font=("Arial", 10, "bold"), fg="#5588cc").grid(
            row=self._row, column=0, sticky="w", padx=8)
        self._row += 1
        self._var_frame = tk.Frame(self._f)
        self._var_frame.grid(row=self._row, column=0, columnspan=4,
                             sticky="ew", padx=8)
        self._row += 1
        self._rebuild_vars()

    # ── Option section ─────────────────────────────────────────────────────────

    def _build_opt_section(self):
        tk.Label(self._f, text="Options  [a, b, c]",
                 font=("Arial", 10, "bold"), fg="#cc8833").grid(
            row=self._row, column=0, sticky="w", padx=8)
        self._row += 1
        self._opt_frame = tk.Frame(self._f)
        self._opt_frame.grid(row=self._row, column=0, columnspan=4,
                             sticky="ew", padx=8)
        self._row += 1
        self._rebuild_opts()

    # ── Live template sync ─────────────────────────────────────────────────────

    def _on_cb_change(self, *_):
        self.item["content_box"] = self._cb_var.get()
        sync_item_template(self.item)
        # Nur Variablen/Optionen neu bauen, Content Text NICHT anfassen
        self._rebuild_vars()
        self._rebuild_opts()

    # Neue Methode:
    def _sync_preview(self):
        parsed = parse_template(self._cb_var.get())
        preview = render_content_text(
            self._cb_var.get(), {},
            {str(i): c[0] for i, c in enumerate(parsed["options"]) if c}
        )
        self._ct_var.set(preview)

    # ── Rebuild helpers ────────────────────────────────────────────────────────

    def _rebuild_vars(self):
        for w in self._var_frame.winfo_children():
            w.destroy()
        variables = self.item.get("variables", {})
        if not variables:
            tk.Label(self._var_frame,
                     text="(none – use {X} syntax in Content Box)",
                     fg="#888").pack(anchor="w", padx=4)
            return

        hdr = tk.Frame(self._var_frame)
        hdr.pack(fill="x")
        for txt, w in [("Variable", 14), ("Rarity", 8), ("Complexity", 10), ("", 14)]:
            tk.Label(hdr, text=txt, font=("Arial", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2)

        for vname, stat in variables.items():
            self._stat_row(self._var_frame,
                           label=f"{{{vname}}}", label_color="#5588cc",
                           stat=stat)

    def _rebuild_opts(self):
        for w in self._opt_frame.winfo_children():
            w.destroy()
        options = self.item.get("options", {})
        if not options:
            tk.Label(self._opt_frame,
                     text="(none – use [a, b, c] syntax in Content Box)",
                     fg="#888").pack(anchor="w", padx=4)
            return

        for opt_key, opt in options.items():
            choices   = opt.get("choices", [])
            per_choice = opt.setdefault("per_choice", {})
            grp = tk.LabelFrame(
                self._opt_frame,
                text=f"Option {opt_key}:  [{', '.join(choices)}]",
                font=("Arial", 9, "bold"), fg="#cc8833",
            )
            grp.pack(fill="x", pady=3)

            hdr = tk.Frame(grp)
            hdr.pack(fill="x")
            for txt, w in [("Choice", 14), ("Rarity", 8), ("Complexity", 10), ("", 14)]:
                tk.Label(hdr, text=txt, font=("Arial", 8, "bold"),
                         width=w, anchor="w").pack(side="left", padx=2)

            for choice in choices:
                stat = per_choice.setdefault(choice, make_default_stat())
                self._stat_row(grp, label=choice, label_color="#cc8833", stat=stat)

    def _stat_row(self, parent, label: str, label_color: str, stat: dict):
        """One row: label | rarity entry | complexity entry | conditions button."""
        row = tk.Frame(parent, relief="groove", bd=1)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=label, width=14,
                 fg=label_color, font=("Arial", 9, "bold")).pack(side="left", padx=4)

        rar_v = tk.StringVar(value=str(stat.get("rarity", 10)))
        cpx_v = tk.StringVar(value=str(stat.get("complexity", 1.0)))

        def _trace(*_, s=stat, rv=rar_v, cv=cpx_v):
            try: s["rarity"]     = int(rv.get())
            except: pass
            try: s["complexity"] = float(cv.get())
            except: pass

        rar_v.trace_add("write", _trace)
        cpx_v.trace_add("write", _trace)

        tk.Entry(row, textvariable=rar_v, width=8).pack(side="left", padx=2)
        tk.Entry(row, textvariable=cpx_v, width=10).pack(side="left", padx=2)
        tk.Button(row, text="Conditions",
                  command=lambda s=stat: ConditionsEditor(self, s),
                  font=("Arial", 8)).pack(side="left", padx=4)

    # ── Sub-editors ────────────────────────────────────────────────────────────

    def _edit_weights(self):
        ElementWeightsEditor(self, self.item.setdefault("element_weights", {}))

    # ── Save ───────────────────────────────────────────────────────────────────

    def _save(self):
        self.item["id"]              = self._id_var.get().strip()
        self.item["content_box"]     = self._cb_var.get()
        self.item["content_text"]    = self._ct_var.get()
        self.item["reminder_text"]   = self._rt_var.get()
        try:    self.item["rarity"]          = int(self._rar_var.get())
        except: pass
        try:    self.item["complexity_base"] = float(self._cpx_var.get())
        except: pass
        if self.on_save:
            self.on_save()
        self.destroy()


# ── Element Weights Editor ─────────────────────────────────────────────────────

class ElementWeightsEditor(tk.Toplevel):
    def __init__(self, parent, weights: dict):
        super().__init__(parent)
        self.title("Element Weights")
        wm.restore(self, "weights_editor", "260x320")
        self.weights = weights
        self._build()

    def _build(self):
        entries = {}
        for i, el in enumerate(ELEMENTS):
            tk.Label(self, text=el).grid(row=i, column=0, sticky="w", padx=8, pady=2)
            e = tk.Entry(self, width=10)
            e.insert(0, self.weights.get(el, 0))
            e.grid(row=i, column=1, padx=8, pady=2)
            entries[el] = e

        def _save():
            for el in ELEMENTS:
                try:    self.weights[el] = float(entries[el].get())
                except: self.weights[el] = 0
            self.destroy()

        tk.Button(self, text="Save", command=_save).grid(
            row=len(ELEMENTS), column=0, columnspan=2, pady=8)


# ── Conditions Editor ──────────────────────────────────────────────────────────

class ConditionsEditor(tk.Toplevel):
    """
    Conditions / exceptions for a variable or option-choice.
    Supports: min/max mana, allowed elements, free-text notes.
    Easy to extend later (e.g. block-type restrictions, other content refs).
    """

    def __init__(self, parent, stat: dict):
        super().__init__(parent)
        self.title("Conditions / Exceptions")
        wm.restore(self, "conditions_editor", "400x440")
        self.cond = stat.setdefault("conditions", {})
        self._build()

    def _build(self):
        f = tk.Frame(self)
        f.pack(fill="both", expand=True, padx=10, pady=8)
        f.columnconfigure(1, weight=1)
        row = 0

        # Mana range
        for label, key in [("Min Mana Cost", "min_mana"), ("Max Mana Cost", "max_mana")]:
            tk.Label(f, text=label, font=("Arial", 9, "bold")).grid(
                row=row, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=str(self.cond.get(key, "")))
            tk.Entry(f, textvariable=var, width=8).grid(row=row, column=1, sticky="w")
            setattr(self, f"_{key}_var", var)
            row += 1

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6); row += 1

        # Allowed elements
        tk.Label(f, text="Allowed Elements  (none checked = any)",
                 font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w"); row += 1

        allowed       = self.cond.get("allowed_elements", [])
        self._el_vars = {}
        for el in ELEMENTS:
            v = tk.BooleanVar(value=(el in allowed))
            self._el_vars[el] = v
            tk.Checkbutton(f, text=el, variable=v).grid(
                row=row, column=0, columnspan=2, sticky="w")
            row += 1

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6); row += 1

        # Notes
        tk.Label(f, text="Notes", font=("Arial", 9, "bold")).grid(
            row=row, column=0, sticky="w"); row += 1
        self._notes_var = tk.StringVar(value=self.cond.get("notes", ""))
        tk.Entry(f, textvariable=self._notes_var, width=40).grid(
            row=row, column=0, columnspan=2, sticky="we"); row += 1

        tk.Button(self, text="Save", command=self._save,
                  bg="#1a6e3c", fg="white", width=14).pack(pady=10)

    def _save(self):
        for key in ("min_mana", "max_mana"):
            var = getattr(self, f"_{key}_var")
            try:    self.cond[key] = int(var.get())
            except: self.cond.pop(key, None)

        sel = [el for el, v in self._el_vars.items() if v.get()]
        if sel: self.cond["allowed_elements"] = sel
        else:   self.cond.pop("allowed_elements", None)

        notes = self._notes_var.get()
        if notes: self.cond["notes"] = notes
        else:     self.cond.pop("notes", None)

        self.destroy()
