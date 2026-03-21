"""
widgets.py – reusable editor widgets:
    PlaceholderFrame  – inline {X}/{Y} variable entry fields
    AbilityEditor     – one ability row (condition + type + costs + effects + choose)
    BoxEditor         – one labelled box frame containing multiple AbilityEditors
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .constants import ABILITY_TYPES, BOX_COLORS, BOX_SYMBOLS
from .data import get_content_data, parse_placeholders, fill_placeholders
from .models import empty_ability


# ── PlaceholderFrame ──────────────────────────────────────────────────────────

class PlaceholderFrame(tk.Frame):
    """
    Shows a small inline entry for every {X} placeholder found in *text*.
    Writes results directly into *values* dict and calls *on_change()*.
    """

    def __init__(self, parent: tk.Widget, text: str,
                 values: dict, on_change: Callable, **kw) -> None:
        super().__init__(parent, **kw)
        self.values    = values
        self.on_change = on_change
        self._vars: dict[str, tk.StringVar] = {}
        self._build(text)

    # ── public ────────────────────────────────────────────────────────────────

    def update_text(self, text: str) -> None:
        self._build(text)

    # ── private ───────────────────────────────────────────────────────────────

    def _build(self, text: str) -> None:
        for w in self.winfo_children():
            w.destroy()
        self._vars.clear()

        placeholders = parse_placeholders(text)
        if not placeholders:
            return

        tk.Label(self, text="Vars:", font=("Arial", 8)).pack(side="left")
        for ph in placeholders:
            tk.Label(self, text=f"{ph}=", font=("Arial", 8)).pack(side="left")
            var = tk.StringVar(value=str(self.values.get(ph, "")))
            self._vars[ph] = var
            var.trace_add("write",
                          lambda *_, p=ph, v=var: self._changed(p, v))
            tk.Entry(self, textvariable=var, width=4,
                     font=("Arial", 8)).pack(side="left", padx=1)

    def _changed(self, ph: str, var: tk.StringVar) -> None:
        self.values[ph] = var.get()
        self.on_change()


# ── AbilityEditor ─────────────────────────────────────────────────────────────

class AbilityEditor(tk.Frame):
    """
    Edits a single ability dict in-place.
    Layout:
        Row 0  – [If: <condition>] [vars…]  [Type: <type>]  [✕]
        Row 1  – Costs: [+] <cost pills…>
        Row 2  – Effects: [+] <effect pills…>
        Row 3  – Choose N: [___]  [✓ same multiple times]
    """

    def __init__(self, parent: tk.Widget, ability: dict,
                 on_change: Callable, on_delete: Callable, **kw) -> None:
        super().__init__(parent, relief="groove", bd=1, **kw)
        self.ability   = ability
        self.on_change = on_change
        self.on_delete = on_delete
        self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        bg = self.cget("bg")

        # ── Row 0: condition + type + delete ──────────────────────────────────
        r0 = tk.Frame(self, bg=bg)
        r0.pack(fill="x", padx=2, pady=1)

        tk.Label(r0, text="If:", font=("Arial", 8), bg=bg).pack(side="left")
        CD = get_content_data()

        self._cond_var = tk.StringVar(value=self.ability.get("condition_id") or "")
        cond_cb = ttk.Combobox(r0, textvariable=self._cond_var,
                               values=[""] + CD.condition_ids(),
                               width=16, font=("Arial", 8))
        cond_cb.pack(side="left", padx=2)
        cond_cb.bind("<<ComboboxSelected>>", self._cond_changed)

        self._cond_ph = PlaceholderFrame(
            r0, self._cond_text(),
            self.ability.setdefault("condition_vals", {}),
            self.on_change, bg=bg)
        self._cond_ph.pack(side="left")

        tk.Label(r0, text="Type:", font=("Arial", 8), bg=bg).pack(
            side="left", padx=(6, 0))
        self._type_var = tk.StringVar(value=self.ability.get("ability_type", "Play"))
        ttk.Combobox(r0, textvariable=self._type_var,
                     values=ABILITY_TYPES, width=10,
                     font=("Arial", 8), state="readonly").pack(side="left", padx=2)
        self._type_var.trace_add(
            "write", lambda *_: self._set("ability_type", self._type_var.get()))

        tk.Button(r0, text="✕", command=self.on_delete,
                  fg="red", font=("Arial", 8), relief="flat").pack(side="right")

        # ── Row 1: costs ──────────────────────────────────────────────────────
        r1 = tk.Frame(self, bg=bg)
        r1.pack(fill="x", padx=2)
        tk.Label(r1, text="Costs:", font=("Arial", 8, "bold"), bg=bg).pack(side="left")
        tk.Button(r1, text="+", command=self._add_cost,
                  font=("Arial", 8)).pack(side="left", padx=2)
        self._cost_frame = tk.Frame(r1, bg=bg)
        self._cost_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_costs()

        # ── Row 2: effects ────────────────────────────────────────────────────
        r2 = tk.Frame(self, bg=bg)
        r2.pack(fill="x", padx=2)
        tk.Label(r2, text="Effects:", font=("Arial", 8, "bold"), bg=bg).pack(side="left")
        tk.Button(r2, text="+", command=self._add_effect,
                  font=("Arial", 8)).pack(side="left", padx=2)
        self._eff_frame = tk.Frame(r2, bg=bg)
        self._eff_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_effects()

        # ── Row 3: choose N ───────────────────────────────────────────────────
        r3 = tk.Frame(self, bg=bg)
        r3.pack(fill="x", padx=2, pady=1)
        tk.Label(r3, text="Choose N:", font=("Arial", 8), bg=bg).pack(side="left")
        self._choose_var = tk.StringVar(
            value=str(self.ability.get("choose_n") or ""))
        tk.Entry(r3, textvariable=self._choose_var,
                 width=4, font=("Arial", 8)).pack(side="left", padx=2)
        self._choose_var.trace_add("write", self._choose_changed)

        self._repeat_var = tk.BooleanVar(value=self.ability.get("choose_repeat", False))
        tk.Checkbutton(r3, text="same multiple times",
                       variable=self._repeat_var,
                       font=("Arial", 8), bg=bg,
                       command=self._repeat_changed).pack(side="left")

    # ── condition helpers ─────────────────────────────────────────────────────

    def _cond_text(self) -> str:
        cid = self.ability.get("condition_id")
        if not cid:
            return ""
        item = get_content_data().get("condition", cid)
        return item.get("effect_text", "") if item else ""

    def _cond_changed(self, _=None) -> None:
        val = self._cond_var.get() or None
        self.ability["condition_id"]   = val
        self.ability["condition_vals"] = {}
        self._cond_ph.values = self.ability["condition_vals"]
        self._cond_ph.update_text(self._cond_text())
        self.on_change()

    # ── cost helpers ──────────────────────────────────────────────────────────

    def _rebuild_costs(self) -> None:
        for w in self._cost_frame.winfo_children():
            w.destroy()
        for idx, ci in enumerate(self.ability.get("costs", [])):
            self._cost_pill(self._cost_frame, ci, idx)

    def _cost_pill(self, parent: tk.Widget, ci: dict, idx: int) -> None:
        f = tk.Frame(parent, relief="solid", bd=1)
        f.pack(side="left", padx=1, pady=1)

        var = tk.StringVar(value=ci.get("cost_id", ""))
        cb  = ttk.Combobox(f, textvariable=var,
                            values=get_content_data().cost_ids(),
                            width=12, font=("Arial", 8))
        cb.pack(side="left")

        ph = PlaceholderFrame(f, self._item_text("cost", ci.get("cost_id", "")),
                              ci.setdefault("vals", {}), self.on_change)
        ph.pack(side="left")

        def on_sel(_=None, v=var, ci=ci, ph=ph):
            ci["cost_id"] = v.get()
            ci["vals"]    = {}
            ph.update_text(self._item_text("cost", v.get()))
            self.on_change()

        cb.bind("<<ComboboxSelected>>", on_sel)
        tk.Button(f, text="✕", command=lambda i=idx: self._del_cost(i),
                  font=("Arial", 7), relief="flat", fg="red").pack(side="left")

    def _add_cost(self) -> None:
        self.ability.setdefault("costs", []).append({"cost_id": "", "vals": {}})
        self._rebuild_costs()
        self.on_change()

    def _del_cost(self, idx: int) -> None:
        self.ability["costs"].pop(idx)
        self._rebuild_costs()
        self.on_change()

    # ── effect helpers ────────────────────────────────────────────────────────

    def _rebuild_effects(self) -> None:
        for w in self._eff_frame.winfo_children():
            w.destroy()
        for idx, ei in enumerate(self.ability.get("effects", [])):
            self._effect_pill(self._eff_frame, ei, idx)

    def _effect_pill(self, parent: tk.Widget, ei: dict, idx: int) -> None:
        f = tk.Frame(parent, relief="solid", bd=1)
        f.pack(fill="x", padx=1, pady=1)

        var = tk.StringVar(value=ei.get("effect_id", ""))
        cb  = ttk.Combobox(f, textvariable=var,
                            values=get_content_data().effect_ids(),
                            width=14, font=("Arial", 8))
        cb.pack(side="left")

        ph = PlaceholderFrame(f, self._item_text("effect", ei.get("effect_id", "")),
                              ei.setdefault("vals", {}), self.on_change)
        ph.pack(side="left")

        def on_sel(_=None, v=var, ei=ei, ph=ph):
            ei["effect_id"] = v.get()
            ei["vals"]      = {}
            ph.update_text(self._item_text("effect", v.get()))
            self.on_change()

        cb.bind("<<ComboboxSelected>>", on_sel)
        tk.Button(f, text="✕", command=lambda i=idx: self._del_effect(i),
                  font=("Arial", 7), relief="flat", fg="red").pack(side="left")

    def _add_effect(self) -> None:
        self.ability.setdefault("effects", []).append({"effect_id": "", "vals": {}})
        self._rebuild_effects()
        self.on_change()

    def _del_effect(self, idx: int) -> None:
        self.ability["effects"].pop(idx)
        self._rebuild_effects()
        self.on_change()

    # ── misc ──────────────────────────────────────────────────────────────────

    def _item_text(self, kind: str, id_: str) -> str:
        item = get_content_data().get(kind, id_)
        return item.get("effect_text", "") if item else ""

    def _set(self, key: str, value) -> None:
        self.ability[key] = value
        self.on_change()

    def _choose_changed(self, *_) -> None:
        v = self._choose_var.get().strip()
        self.ability["choose_n"] = int(v) if v.isdigit() else None
        self.on_change()

    def _repeat_changed(self) -> None:
        self.ability["choose_repeat"] = self._repeat_var.get()
        self.on_change()


# ── BoxEditor ─────────────────────────────────────────────────────────────────

class BoxEditor(tk.LabelFrame):
    """
    Labelled frame for one card box.
    Contains a header (Add Ability / Remove Box) and
    one AbilityEditor per ability.
    """

    def __init__(self, parent: tk.Widget, block: dict,
                 on_change: Callable, on_delete: Callable, **kw) -> None:
        btype = block.get("type", "?")
        color = BOX_COLORS.get(btype, "#333")
        super().__init__(
            parent,
            text=f" {BOX_SYMBOLS.get(btype, '?')} {btype} ",
            fg=color, font=("Arial", 9, "bold"),
            relief="groove", bd=2, **kw,
        )
        self.block     = block
        self.on_change = on_change
        self.on_delete = on_delete
        self._build()

    def _build(self) -> None:
        hdr = tk.Frame(self, bg=self.cget("bg"))
        hdr.pack(fill="x")
        tk.Button(hdr, text="+ Ability", command=self._add_ability,
                  font=("Arial", 8)).pack(side="left", padx=4)
        tk.Button(hdr, text="Remove Block", command=self.on_delete,
                  fg="red", font=("Arial", 8)).pack(side="right", padx=4)

        self._ab_frame = tk.Frame(self, bg=self.cget("bg"))
        self._ab_frame.pack(fill="x", padx=4, pady=2)
        self._rebuild()

    def _rebuild(self) -> None:
        for w in self._ab_frame.winfo_children():
            w.destroy()
        for idx, ab in enumerate(self.block.get("abilities", [])):
            AbilityEditor(
                self._ab_frame, ab,
                on_change=self.on_change,
                on_delete=lambda i=idx: self._del_ability(i),
                bg="#2a2a2a",
            ).pack(fill="x", pady=2)

    def _add_ability(self) -> None:
        self.block.setdefault("abilities", []).append(empty_ability())
        self._rebuild()
        self.on_change()

    def _del_ability(self, idx: int) -> None:
        self.block["abilities"].pop(idx)
        self._rebuild()
        self.on_change()
