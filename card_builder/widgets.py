"""
widgets.py – reusable editor widgets:
    PlaceholderFrame  – inline {X}/{Y} variable entry fields
    EffectGroupEditor – one group (target_type + primary + modifiers)
    AbilityEditor     – one ability (condition + type + costs + groups + choose + sub_sigil)
    BoxEditor         – one labelled box frame containing multiple AbilityEditors
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .constants import ABILITY_TYPES, BOX_COLORS, BOX_SYMBOLS
from .data import get_content_data, parse_placeholders
from .models import empty_ability, empty_effect_group, empty_sub_sigil, _migrate_group

TARGET_TYPES = ["Non Targeting", "Target Enemy", "Target Ally", "Target Neutral"]


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

    def update_text(self, text: str) -> None:
        self._build(text)

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


# ── EffectGroupEditor ─────────────────────────────────────────────────────────

class EffectGroupEditor(tk.Frame):
    """
    Edits one effect group in-place.
    Layout:
        Row 0  – [Type: TargetType ▾]  [+ Effect]  [✕ delete group]
        Rows   – effect pills (one per effect in group["effects"])
        Row N  – Mods: [+ Mod]  <modifier pills…>
    """

    def __init__(self, parent: tk.Widget, group: dict,
                 on_change: Callable, on_delete: Callable, **kw) -> None:
        super().__init__(parent, relief="ridge", bd=1, **kw)
        self.group     = group
        self.on_change = on_change
        self.on_delete = on_delete
        # Migrate old 'primary'/'primaries' → 'effects' list
        _migrate_group(self.group)
        self._build()

    def _build(self) -> None:
        bg = self.cget("bg")

        # ── Row 0: target type + add-effect button + delete ───────────────────
        r0 = tk.Frame(self, bg=bg)
        r0.pack(fill="x", padx=2, pady=1)

        tk.Label(r0, text="Type:", font=("Arial", 8), bg=bg).pack(side="left")
        self._tt_var = tk.StringVar(
            value=self.group.get("target_type", "Non Targeting"))
        ttk.Combobox(r0, textvariable=self._tt_var, values=TARGET_TYPES,
                     width=14, font=("Arial", 8), state="readonly").pack(
            side="left", padx=2)
        self._tt_var.trace_add("write", lambda *_: self._set_tt(self._tt_var.get()))

        tk.Button(r0, text="✕", command=self.on_delete,
                  fg="red", font=("Arial", 8), relief="flat").pack(side="right")
        tk.Button(r0, text="+ Effect", command=self._add_effect,
                  font=("Arial", 8)).pack(side="right", padx=2)

        # ── Effects section ───────────────────────────────────────────────────
        self._eff_frame = tk.Frame(self, bg=bg)
        self._eff_frame.pack(fill="x", padx=4, pady=1)
        self._rebuild_effects()

        # ── Modifiers row ─────────────────────────────────────────────────────
        r1 = tk.Frame(self, bg=bg)
        r1.pack(fill="x", padx=4, pady=1)
        tk.Label(r1, text="Mods:", font=("Arial", 8), bg=bg).pack(side="left")
        tk.Button(r1, text="+ Mod", command=self._add_modifier,
                  font=("Arial", 8)).pack(side="left", padx=2)
        self._mod_frame = tk.Frame(r1, bg=bg)
        self._mod_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_modifiers()

        # ── Per-group Sub-Sigil toggle ────────────────────────────────────────
        r2 = tk.Frame(self, bg=bg)
        r2.pack(fill="x", padx=4, pady=1)
        self._group_sub_var = tk.BooleanVar(
            value=self.group.get("sub_sigil") is not None)
        tk.Checkbutton(r2, text="Group Sub-Sigil", variable=self._group_sub_var,
                       font=("Arial", 8), bg=bg,
                       command=self._group_sub_toggled).pack(side="left")

        self._group_sub_frame = tk.Frame(self, bg=bg, relief="groove", bd=1)
        if self.group.get("sub_sigil") is not None:
            self._group_sub_frame.pack(fill="x", padx=8, pady=2)
            self._rebuild_group_sub()

    # ── effects helpers ───────────────────────────────────────────────────────

    def _rebuild_effects(self) -> None:
        for w in self._eff_frame.winfo_children():
            w.destroy()
        effects = self.group.setdefault(
            "effects", [{"effect_id": "", "vals": {}, "opt_vals": {}}])
        for idx, eff in enumerate(effects):
            self._effect_pill(self._eff_frame, eff, idx)

    def _effect_pill(self, parent: tk.Widget, eff: dict, idx: int) -> None:
        CD = get_content_data()
        bg = parent.cget("bg")
        f  = tk.Frame(parent, relief="solid", bd=1, bg=bg)
        f.pack(fill="x", pady=1)

        primary_ids = self._primary_ids(CD)
        var = tk.StringVar(value=eff.get("effect_id", ""))
        cb  = ttk.Combobox(f, textvariable=var, values=primary_ids,
                           width=14, font=("Arial", 8))
        cb.pack(side="left", padx=2)

        ph = PlaceholderFrame(f, self._effect_text(eff.get("effect_id", "")),
                              eff.setdefault("vals", {}), self.on_change, bg=bg)
        ph.pack(side="left")

        def on_sel(_=None, v=var, e=eff, ph_=ph):
            eid = v.get()
            e["effect_id"] = eid
            e["vals"]      = {}
            ph_.update_text(self._effect_text(eid))
            self._rebuild_modifiers()
            self.on_change()

        cb.bind("<<ComboboxSelected>>", on_sel)

        # Delete only shown if more than one effect
        if len(self.group.get("effects", [])) > 1:
            tk.Button(f, text="✕",
                      command=lambda i=idx: self._del_effect(i),
                      font=("Arial", 7), relief="flat", fg="red"
                      ).pack(side="right")

    def _add_effect(self) -> None:
        self.group.setdefault("effects", []).append(
            {"effect_id": "", "vals": {}, "opt_vals": {}})
        self._rebuild_effects()
        self.on_change()

    def _del_effect(self, idx: int) -> None:
        effects = self.group.get("effects", [])
        if len(effects) > 1:
            effects.pop(idx)
            self._rebuild_effects()
            self.on_change()

    # ── modifier helpers ──────────────────────────────────────────────────────

    def _rebuild_modifiers(self) -> None:
        for w in self._mod_frame.winfo_children():
            w.destroy()
        for idx, mod in enumerate(self.group.get("modifiers", [])):
            self._modifier_pill(self._mod_frame, mod, idx)

    def _get_violations(self, mod_eid: str) -> list:
        """Return list of human-readable violation strings for a modifier effect."""
        if not mod_eid:
            return []
        CD = get_content_data()
        item = CD.get("effect", mod_eid)
        if not item:
            return []
        violations = []
        target_type = self.group.get("target_type", "Non Targeting")

        attaches = item.get("attaches_to", [])
        if attaches and target_type not in attaches:
            violations.append(
                f"needs target in {attaches}, got '{target_type}'"
            )

        req_tags = item.get("requires_primary_tags", [])
        if req_tags:
            # Collect tags from all effects in the group
            primary_tags: set = set()
            for eff in self.group.get("effects", []):
                eid = eff.get("effect_id", "")
                ei  = CD.get("effect", eid) if eid else None
                if ei:
                    primary_tags.update(ei.get("tags", []))
            if not primary_tags.intersection(req_tags):
                eff_names = [e.get("effect_id", "?") for e in self.group.get("effects", [])]
                have = list(primary_tags) if primary_tags else ["none"]
                violations.append(
                    f"effects must have tags {req_tags}, {eff_names} has {have}"
                )

        return violations

    def _modifier_pill(self, parent: tk.Widget, mod: dict, idx: int) -> None:
        CD = get_content_data()
        bg = parent.cget("bg")
        f  = tk.Frame(parent, relief="solid", bd=1, bg=bg)
        f.pack(side="left", padx=1, pady=1)

        mod_ids = self._modifier_ids(CD)
        var = tk.StringVar(value=mod.get("effect_id", ""))
        cb  = ttk.Combobox(f, textvariable=var, values=mod_ids,
                            width=12, font=("Arial", 8))
        cb.pack(side="left")

        ph = PlaceholderFrame(f, self._effect_text(mod.get("effect_id", "")),
                              mod.setdefault("vals", {}), self.on_change, bg=bg)
        ph.pack(side="left")

        warn_lbl = tk.Label(f, text="", font=("Arial", 7),
                            fg="white", bg="#cc0000", wraplength=200)

        def _apply_validation(eid: str) -> None:
            violations = self._get_violations(eid)
            if violations:
                f.config(bg="#660000")
                warn_lbl.config(text=" ! " + ";  ".join(violations))
                warn_lbl.pack(side="left", padx=2)
            else:
                f.config(bg=bg)
                warn_lbl.pack_forget()

        def on_sel(_=None, v=var, m=mod, p=ph):
            m["effect_id"] = v.get()
            m["vals"]      = {}
            p.update_text(self._effect_text(v.get()))
            _apply_validation(v.get())
            self.on_change()

        cb.bind("<<ComboboxSelected>>", on_sel)
        tk.Button(f, text="✕", command=lambda i=idx: self._del_modifier(i),
                  font=("Arial", 7), relief="flat", fg="red").pack(side="left")

        _apply_validation(mod.get("effect_id", ""))

    def _add_modifier(self) -> None:
        self.group.setdefault("modifiers", []).append(
            {"effect_id": "", "vals": {}, "opt_vals": {}})
        self._rebuild_modifiers()
        self.on_change()

    def _del_modifier(self, idx: int) -> None:
        self.group["modifiers"].pop(idx)
        self._rebuild_modifiers()
        self.on_change()

    # ── per-group sub-sigil helpers ───────────────────────────────────────────

    def _group_sub_toggled(self) -> None:
        if self._group_sub_var.get():
            self.group["sub_sigil"] = empty_sub_sigil()
            self._group_sub_frame.pack(fill="x", padx=8, pady=2)
            self._rebuild_group_sub()
        else:
            self.group["sub_sigil"] = None
            for w in self._group_sub_frame.winfo_children():
                w.destroy()
            self._group_sub_frame.pack_forget()
        self.on_change()

    def _rebuild_group_sub(self) -> None:
        for w in self._group_sub_frame.winfo_children():
            w.destroy()
        sub = self.group.get("sub_sigil")
        if sub is None:
            return
        bg = self.cget("bg")

        # Sub costs
        sc_row = tk.Frame(self._group_sub_frame, bg=bg)
        sc_row.pack(fill="x", padx=2, pady=1)
        tk.Label(sc_row, text="Costs:", font=("Arial", 8, "bold"),
                 bg=bg).pack(side="left")
        tk.Button(sc_row, text="+", font=("Arial", 8),
                  command=self._add_group_sub_cost).pack(side="left", padx=2)
        self._group_sub_cost_frame = tk.Frame(sc_row, bg=bg)
        self._group_sub_cost_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_group_sub_costs()

        # Sub effect groups
        sg_row = tk.Frame(self._group_sub_frame, bg=bg)
        sg_row.pack(fill="x", padx=2, pady=1)
        tk.Label(sg_row, text="Effects:", font=("Arial", 8, "bold"),
                 bg=bg).pack(side="left")
        tk.Button(sg_row, text="+ Group", font=("Arial", 8),
                  command=self._add_group_sub_group).pack(side="left", padx=2)
        self._group_sub_group_frame = tk.Frame(self._group_sub_frame, bg=bg)
        self._group_sub_group_frame.pack(fill="x", padx=4)
        self._rebuild_group_sub_groups()

    def _rebuild_group_sub_costs(self) -> None:
        if not hasattr(self, "_group_sub_cost_frame"):
            return
        for w in self._group_sub_cost_frame.winfo_children():
            w.destroy()
        sub = self.group.get("sub_sigil") or {}
        for idx, ci in enumerate(sub.get("costs", [])):
            self._cost_pill_mini(self._group_sub_cost_frame, ci, idx, sub["costs"])

    def _rebuild_group_sub_groups(self) -> None:
        if not hasattr(self, "_group_sub_group_frame"):
            return
        for w in self._group_sub_group_frame.winfo_children():
            w.destroy()
        sub = self.group.get("sub_sigil") or {}
        bg  = self.cget("bg")
        for idx, grp in enumerate(sub.get("effect_groups", [])):
            EffectGroupEditor(
                self._group_sub_group_frame, grp,
                on_change=self.on_change,
                on_delete=lambda i=idx: self._del_group_sub_group(i),
                bg=bg,
            ).pack(fill="x", pady=1)

    def _cost_pill_mini(self, parent: tk.Widget, ci: dict,
                        idx: int, cost_list: list) -> None:
        bg = parent.cget("bg")
        f  = tk.Frame(parent, relief="solid", bd=1, bg=bg)
        f.pack(side="left", padx=1, pady=1)
        var = tk.StringVar(value=ci.get("cost_id", ""))
        cb  = ttk.Combobox(f, textvariable=var,
                            values=get_content_data().cost_ids(),
                            width=12, font=("Arial", 8))
        cb.pack(side="left")
        ph = PlaceholderFrame(f, self._item_text("cost", ci.get("cost_id", "")),
                              ci.setdefault("vals", {}), self.on_change, bg=bg)
        ph.pack(side="left")

        def on_sel(_=None, v=var, ci=ci, ph=ph):
            ci["cost_id"] = v.get()
            ci["vals"]    = {}
            ph.update_text(self._item_text("cost", v.get()))
            self.on_change()

        cb.bind("<<ComboboxSelected>>", on_sel)
        tk.Button(f, text="✕",
                  command=lambda i=idx, cl=cost_list: self._del_from_list(cl, i),
                  font=("Arial", 7), relief="flat", fg="red").pack(side="left")

    def _add_group_sub_cost(self) -> None:
        sub = self.group.get("sub_sigil")
        if sub is None: return
        sub.setdefault("costs", []).append(
            {"cost_id": "", "vals": {}, "opt_vals": {}})
        self._rebuild_group_sub_costs()
        self.on_change()

    def _add_group_sub_group(self) -> None:
        sub = self.group.get("sub_sigil")
        if sub is None: return
        sub.setdefault("effect_groups", []).append(empty_effect_group())
        self._rebuild_group_sub_groups()
        self.on_change()

    def _del_group_sub_group(self, idx: int) -> None:
        sub = self.group.get("sub_sigil")
        if sub: sub["effect_groups"].pop(idx)
        self._rebuild_group_sub_groups()
        self.on_change()

    def _del_from_list(self, lst: list, idx: int) -> None:
        lst.pop(idx)
        self._rebuild_group_sub_costs()
        self.on_change()

    # ── misc helpers ──────────────────────────────────────────────────────────

    def _set_tt(self, val: str) -> None:
        self.group["target_type"] = val
        self._rebuild_modifiers()   # re-validate when target type changes
        self.on_change()

    def _effect_text(self, eid: str) -> str:
        item = get_content_data().get("effect", eid)
        return item.get("content_text", "") if item else ""

    def _item_text(self, kind: str, id_: str) -> str:
        item = get_content_data().get(kind, id_)
        return item.get("content_text", item.get("effect_text", "")) if item else ""

    @staticmethod
    def _primary_ids(CD) -> list:
        return [e["id"] for e in CD.effects if e.get("role", "primary") == "primary"]

    @staticmethod
    def _modifier_ids(CD) -> list:
        return [e["id"] for e in CD.effects if e.get("role", "primary") == "modifier"]


# ── AbilityEditor ─────────────────────────────────────────────────────────────

class AbilityEditor(tk.Frame):
    """
    Edits a single ability dict in-place.
    Layout:
        Row 0  – [If: <condition>] [vars…]  [Type: <type>]  [✕]
        Row 1  – Costs: [+] <cost pills…>
        Row 2  – Effect Groups: [+] <group editors…>
        Row 3  – Choose N: [___] of [Total: ___]  [✓ same multiple times]
        Row 4  – Sub-Sigil: [✓ Add] <sub-sigil frame when checked>
    """

    def __init__(self, parent: tk.Widget, ability: dict,
                 on_change: Callable, on_delete: Callable, **kw) -> None:
        super().__init__(parent, relief="groove", bd=1, **kw)
        self.ability   = ability
        self.on_change = on_change
        self.on_delete = on_delete
        # Ensure new fields exist
        self.ability.setdefault("effect_groups", [])
        self.ability.setdefault("choose_total",  None)
        self.ability.setdefault("sub_sigil",     None)
        self.ability.setdefault("sub_sigil_global", None)
        self._build()

    def _build(self) -> None:
        bg = self.cget("bg")

        # ── Row 0: condition + trigger + type + delete ────────────────────────
        r0 = tk.Frame(self, bg=bg)
        r0.pack(fill="x", padx=2, pady=1)
        tk.Label(r0, text="If:", font=("Arial", 8), bg=bg).pack(side="left")
        CD = get_content_data()

        self._cond_var = tk.StringVar(
            value=self.ability.get("condition_id") or "")
        cond_cb = ttk.Combobox(r0, textvariable=self._cond_var,
                               values=[""] + CD.condition_ids(),
                               width=14, font=("Arial", 8))
        cond_cb.pack(side="left", padx=2)
        cond_cb.bind("<<ComboboxSelected>>", self._cond_changed)

        self._cond_ph = PlaceholderFrame(
            r0, self._cond_text(),
            self.ability.setdefault("condition_vals", {}),
            self.on_change, bg=bg)
        self._cond_ph.pack(side="left")

        tk.Label(r0, text="Type:", font=("Arial", 8), bg=bg).pack(
            side="left", padx=(6, 0))
        self._type_var = tk.StringVar(
            value=self.ability.get("ability_type", "Play"))
        ttk.Combobox(r0, textvariable=self._type_var, values=ABILITY_TYPES,
                     width=10, font=("Arial", 8),
                     state="readonly").pack(side="left", padx=2)
        self._type_var.trace_add(
            "write",
            lambda *_: self._set("ability_type", self._type_var.get()))

        tk.Button(r0, text="✕", command=self.on_delete,
                  fg="red", font=("Arial", 8), relief="flat").pack(side="right")

        # ── Row 0b: trigger ───────────────────────────────────────────────────
        r0b = tk.Frame(self, bg=bg)
        r0b.pack(fill="x", padx=2, pady=1)
        tk.Label(r0b, text="When:", font=("Arial", 8), bg=bg).pack(side="left")
        self._trig_var = tk.StringVar(
            value=self.ability.get("trigger_id") or "")
        trig_cb = ttk.Combobox(r0b, textvariable=self._trig_var,
                               values=[""] + CD.trigger_ids(),
                               width=16, font=("Arial", 8))
        trig_cb.pack(side="left", padx=2)
        trig_cb.bind("<<ComboboxSelected>>", self._trig_changed)
        self._trig_ph = PlaceholderFrame(
            r0b, self._trig_text(),
            self.ability.setdefault("trigger_vals", {}),
            self.on_change, bg=bg)
        self._trig_ph.pack(side="left")

        # ── Row 1: costs ──────────────────────────────────────────────────────
        r1 = tk.Frame(self, bg=bg)
        r1.pack(fill="x", padx=2)
        tk.Label(r1, text="Costs:", font=("Arial", 8, "bold"), bg=bg).pack(
            side="left")
        tk.Button(r1, text="+", command=self._add_cost,
                  font=("Arial", 8)).pack(side="left", padx=2)
        self._cost_frame = tk.Frame(r1, bg=bg)
        self._cost_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_costs()

        # ── Row 2: effect groups ──────────────────────────────────────────────
        r2 = tk.Frame(self, bg=bg)
        r2.pack(fill="x", padx=2)
        tk.Label(r2, text="Groups:", font=("Arial", 8, "bold"), bg=bg).pack(
            side="left")
        tk.Button(r2, text="+ Group", command=self._add_group,
                  font=("Arial", 8)).pack(side="left", padx=2)

        self._group_frame = tk.Frame(self, bg=bg)
        self._group_frame.pack(fill="x", padx=4)
        self._rebuild_groups()

        # ── Row 3: choose N ───────────────────────────────────────────────────
        r3 = tk.Frame(self, bg=bg)
        r3.pack(fill="x", padx=2, pady=1)
        tk.Label(r3, text="Choose:", font=("Arial", 8), bg=bg).pack(side="left")
        self._choose_var = tk.StringVar(
            value=str(self.ability.get("choose_n") or ""))
        tk.Entry(r3, textvariable=self._choose_var, width=3,
                 font=("Arial", 8)).pack(side="left", padx=1)
        tk.Label(r3, text="of", font=("Arial", 8), bg=bg).pack(side="left")
        self._choose_total_var = tk.StringVar(
            value=str(self.ability.get("choose_total") or ""))
        tk.Entry(r3, textvariable=self._choose_total_var, width=3,
                 font=("Arial", 8)).pack(side="left", padx=1)
        self._choose_var.trace_add("write", self._choose_changed)
        self._choose_total_var.trace_add("write", self._choose_total_changed)

        self._repeat_var = tk.BooleanVar(
            value=self.ability.get("choose_repeat", False))
        tk.Checkbutton(r3, text="same multiple times",
                       variable=self._repeat_var, font=("Arial", 8), bg=bg,
                       command=self._repeat_changed).pack(side="left")

        # ── Row 4: sub-sigil (legacy format, backward compat) ──────────────────
        r4 = tk.Frame(self, bg=bg)
        r4.pack(fill="x", padx=2, pady=1)
        self._sub_var = tk.BooleanVar(
            value=self.ability.get("sub_sigil") is not None)
        tk.Checkbutton(r4, text="Sub-Sigil (Legacy)", variable=self._sub_var,
                       font=("Arial", 8, "bold"), bg=bg,
                       command=self._sub_toggled).pack(side="left")

        self._sub_frame = tk.Frame(self, bg=bg, relief="groove", bd=1)
        if self.ability.get("sub_sigil") is not None:
            self._sub_frame.pack(fill="x", padx=8, pady=2)
            self._rebuild_sub()

        # ── Row 5: global sub-sigil (new format with target type) ──────────────
        r5 = tk.Frame(self, bg=bg)
        r5.pack(fill="x", padx=2, pady=1)
        self._sub_global_var = tk.BooleanVar(
            value=self.ability.get("sub_sigil_global") is not None)
        tk.Checkbutton(r5, text="Global Sub-Sigil (Overload)", variable=self._sub_global_var,
                       font=("Arial", 8, "bold"), bg=bg,
                       command=self._sub_global_toggled).pack(side="left")

        self._sub_global_frame = tk.Frame(self, bg=bg, relief="groove", bd=1)
        if self.ability.get("sub_sigil_global") is not None:
            self._sub_global_frame.pack(fill="x", padx=8, pady=2)
            self._rebuild_sub_global()

    # ── condition helpers ─────────────────────────────────────────────────────

    def _cond_text(self) -> str:
        cid  = self.ability.get("condition_id")
        if not cid: return ""
        item = get_content_data().get("condition", cid)
        return item.get("content_text", item.get("effect_text", "")) if item else ""

    def _cond_changed(self, _=None) -> None:
        val = self._cond_var.get() or None
        self.ability["condition_id"]   = val
        self.ability["condition_vals"] = {}
        self._cond_ph.values = self.ability["condition_vals"]
        self._cond_ph.update_text(self._cond_text())
        self.on_change()

    def _trig_text(self) -> str:
        tid  = self.ability.get("trigger_id")
        if not tid: return ""
        item = get_content_data().get("trigger", tid)
        return item.get("content_text", item.get("effect_text", "")) if item else ""

    def _trig_changed(self, _=None) -> None:
        val = self._trig_var.get() or None
        self.ability["trigger_id"]   = val
        self.ability["trigger_vals"] = {}
        self._trig_ph.values = self.ability["trigger_vals"]
        self._trig_ph.update_text(self._trig_text())
        self.on_change()

    # ── cost helpers ──────────────────────────────────────────────────────────

    def _rebuild_costs(self) -> None:
        for w in self._cost_frame.winfo_children():
            w.destroy()
        for idx, ci in enumerate(self.ability.get("costs", [])):
            self._cost_pill(self._cost_frame, ci, idx)

    def _cost_pill(self, parent: tk.Widget, ci: dict, idx: int) -> None:
        bg = parent.cget("bg")
        f  = tk.Frame(parent, relief="solid", bd=1, bg=bg)
        f.pack(side="left", padx=1, pady=1)
        var = tk.StringVar(value=ci.get("cost_id", ""))
        cb  = ttk.Combobox(f, textvariable=var,
                            values=get_content_data().cost_ids(),
                            width=12, font=("Arial", 8))
        cb.pack(side="left")
        ph = PlaceholderFrame(f, self._item_text("cost", ci.get("cost_id", "")),
                              ci.setdefault("vals", {}), self.on_change, bg=bg)
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
        self.ability.setdefault("costs", []).append(
            {"cost_id": "", "vals": {}, "opt_vals": {}})
        self._rebuild_costs()
        self.on_change()

    def _del_cost(self, idx: int) -> None:
        self.ability["costs"].pop(idx)
        self._rebuild_costs()
        self.on_change()

    # ── effect group helpers ──────────────────────────────────────────────────

    def _rebuild_groups(self) -> None:
        for w in self._group_frame.winfo_children():
            w.destroy()
        for idx, grp in enumerate(self.ability.get("effect_groups", [])):
            EffectGroupEditor(
                self._group_frame, grp,
                on_change=self.on_change,
                on_delete=lambda i=idx: self._del_group(i),
                bg=self.cget("bg"),
            ).pack(fill="x", pady=1)

    def _add_group(self) -> None:
        self.ability.setdefault("effect_groups", []).append(empty_effect_group())
        self._rebuild_groups()
        self.on_change()

    def _del_group(self, idx: int) -> None:
        self.ability["effect_groups"].pop(idx)
        self._rebuild_groups()
        self.on_change()

    # ── sub-sigil helpers ─────────────────────────────────────────────────────

    def _sub_toggled(self) -> None:
        if self._sub_var.get():
            self.ability["sub_sigil"] = empty_sub_sigil()
            self._sub_frame.pack(fill="x", padx=8, pady=2)
            self._rebuild_sub()
        else:
            self.ability["sub_sigil"] = None
            for w in self._sub_frame.winfo_children():
                w.destroy()
            self._sub_frame.pack_forget()
        self.on_change()

    def _rebuild_sub(self) -> None:
        for w in self._sub_frame.winfo_children():
            w.destroy()
        sub = self.ability.get("sub_sigil")
        # Accept any dict (even one with only None/empty values) as a valid sub_sigil
        if sub is None:
            return
        bg = self.cget("bg")

        # Sub costs
        sc_row = tk.Frame(self._sub_frame, bg=bg)
        sc_row.pack(fill="x", padx=2, pady=1)
        tk.Label(sc_row, text="Sub Costs:", font=("Arial", 8, "bold"),
                 bg=bg).pack(side="left")
        tk.Button(sc_row, text="+", font=("Arial", 8),
                  command=self._add_sub_cost).pack(side="left", padx=2)
        self._sub_cost_frame = tk.Frame(sc_row, bg=bg)
        self._sub_cost_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_sub_costs()

        # Sub effect groups
        sg_row = tk.Frame(self._sub_frame, bg=bg)
        sg_row.pack(fill="x", padx=2, pady=1)
        tk.Label(sg_row, text="Sub Groups:", font=("Arial", 8, "bold"),
                 bg=bg).pack(side="left")
        tk.Button(sg_row, text="+ Group", font=("Arial", 8),
                  command=self._add_sub_group).pack(side="left", padx=2)
        self._sub_group_frame = tk.Frame(self._sub_frame, bg=bg)
        self._sub_group_frame.pack(fill="x", padx=4)
        self._rebuild_sub_groups()

        # Force layout refresh so newly added widgets are visible
        self._sub_frame.update_idletasks()

    def _rebuild_sub_costs(self) -> None:
        if not hasattr(self, "_sub_cost_frame"):
            return
        for w in self._sub_cost_frame.winfo_children():
            w.destroy()
        sub = self.ability.get("sub_sigil") or {}
        for idx, ci in enumerate(sub.get("costs", [])):
            self._cost_pill_in(self._sub_cost_frame, ci, idx, sub["costs"])

    def _rebuild_sub_groups(self) -> None:
        if not hasattr(self, "_sub_group_frame"):
            return
        for w in self._sub_group_frame.winfo_children():
            w.destroy()
        sub = self.ability.get("sub_sigil") or {}
        bg  = self.cget("bg")
        for idx, grp in enumerate(sub.get("effect_groups", [])):
            EffectGroupEditor(
                self._sub_group_frame, grp,
                on_change=self.on_change,
                on_delete=lambda i=idx: self._del_sub_group(i),
                bg=bg,
            ).pack(fill="x", pady=1)

    def _cost_pill_in(self, parent: tk.Widget, ci: dict,
                      idx: int, cost_list: list) -> None:
        bg = parent.cget("bg")
        f  = tk.Frame(parent, relief="solid", bd=1, bg=bg)
        f.pack(side="left", padx=1, pady=1)
        var = tk.StringVar(value=ci.get("cost_id", ""))
        cb  = ttk.Combobox(f, textvariable=var,
                            values=get_content_data().cost_ids(),
                            width=12, font=("Arial", 8))
        cb.pack(side="left")
        ph = PlaceholderFrame(f, self._item_text("cost", ci.get("cost_id", "")),
                              ci.setdefault("vals", {}), self.on_change, bg=bg)
        ph.pack(side="left")

        def on_sel(_=None, v=var, ci=ci, ph=ph):
            ci["cost_id"] = v.get()
            ci["vals"]    = {}
            ph.update_text(self._item_text("cost", v.get()))
            self.on_change()

        cb.bind("<<ComboboxSelected>>", on_sel)
        tk.Button(f, text="✕",
                  command=lambda i=idx, cl=cost_list: self._del_from_list(cl, i),
                  font=("Arial", 7), relief="flat", fg="red").pack(side="left")

    def _add_sub_cost(self) -> None:
        sub = self.ability.get("sub_sigil")
        if sub is None: return
        sub.setdefault("costs", []).append(
            {"cost_id": "", "vals": {}, "opt_vals": {}})
        self._rebuild_sub_costs()
        self.on_change()

    def _add_sub_group(self) -> None:
        sub = self.ability.get("sub_sigil")
        if sub is None: return
        sub.setdefault("effect_groups", []).append(empty_effect_group())
        self._rebuild_sub_groups()
        self.on_change()

    def _del_sub_group(self, idx: int) -> None:
        sub = self.ability.get("sub_sigil")
        if sub: sub["effect_groups"].pop(idx)
        self._rebuild_sub_groups()
        self.on_change()

    def _del_from_list(self, lst: list, idx: int) -> None:
        lst.pop(idx)
        self._rebuild_sub_costs()
        self.on_change()

    # ── misc helpers ──────────────────────────────────────────────────────────

    def _item_text(self, kind: str, id_: str) -> str:
        item = get_content_data().get(kind, id_)
        return item.get("content_text", item.get("effect_text", "")) if item else ""

    def _set(self, key: str, value) -> None:
        self.ability[key] = value
        self.on_change()

    def _choose_changed(self, *_) -> None:
        v = self._choose_var.get().strip()
        self.ability["choose_n"] = int(v) if v.isdigit() else None
        self.on_change()

    def _choose_total_changed(self, *_) -> None:
        v = self._choose_total_var.get().strip()
        self.ability["choose_total"] = int(v) if v.isdigit() else None
        self.on_change()

    def _repeat_changed(self) -> None:
        self.ability["choose_repeat"] = self._repeat_var.get()
        self.on_change()

    # ── global sub-sigil helpers ──────────────────────────────────────────────

    def _sub_global_toggled(self) -> None:
        if self._sub_global_var.get():
            self.ability["sub_sigil_global"] = empty_sub_sigil()
            self._sub_global_frame.pack(fill="x", padx=8, pady=2)
            self._rebuild_sub_global()
        else:
            self.ability["sub_sigil_global"] = None
            for w in self._sub_global_frame.winfo_children():
                w.destroy()
            self._sub_global_frame.pack_forget()
        self.on_change()

    def _rebuild_sub_global(self) -> None:
        for w in self._sub_global_frame.winfo_children():
            w.destroy()
        sub = self.ability.get("sub_sigil_global")
        if sub is None:
            return
        bg = self.cget("bg")

        # Target type selector for global sub-sigil
        tt_row = tk.Frame(self._sub_global_frame, bg=bg)
        tt_row.pack(fill="x", padx=2, pady=1)
        tk.Label(tt_row, text="Target Type:", font=("Arial", 8, "bold"),
                 bg=bg).pack(side="left")
        self._global_sub_tt_var = tk.StringVar(
            value=sub.get("target_type") or "Non Targeting")
        ttk.Combobox(tt_row, textvariable=self._global_sub_tt_var,
                     values=TARGET_TYPES,
                     width=14, font=("Arial", 8), state="readonly").pack(
            side="left", padx=2)
        self._global_sub_tt_var.trace_add("write", self._global_sub_tt_changed)

        # Condition for global sub-sigil
        cond_row = tk.Frame(self._sub_global_frame, bg=bg)
        cond_row.pack(fill="x", padx=2, pady=1)
        tk.Label(cond_row, text="Condition:", font=("Arial", 8, "bold"),
                 bg=bg).pack(side="left")
        self._global_sub_cond_var = tk.StringVar(
            value=sub.get("condition_id") or "")
        cond_cb = ttk.Combobox(cond_row, textvariable=self._global_sub_cond_var,
                               values=[""] + get_content_data().condition_ids(),
                               width=14, font=("Arial", 8))
        cond_cb.pack(side="left", padx=2)
        cond_cb.bind("<<ComboboxSelected>>", self._global_sub_cond_changed)

        # Sub costs
        sc_row = tk.Frame(self._sub_global_frame, bg=bg)
        sc_row.pack(fill="x", padx=2, pady=1)
        tk.Label(sc_row, text="Costs:", font=("Arial", 8, "bold"),
                 bg=bg).pack(side="left")
        tk.Button(sc_row, text="+", font=("Arial", 8),
                  command=self._add_global_sub_cost).pack(side="left", padx=2)
        self._global_sub_cost_frame = tk.Frame(sc_row, bg=bg)
        self._global_sub_cost_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_global_sub_costs()

        # Sub effect groups
        sg_row = tk.Frame(self._sub_global_frame, bg=bg)
        sg_row.pack(fill="x", padx=2, pady=1)
        tk.Label(sg_row, text="Effects:", font=("Arial", 8, "bold"),
                 bg=bg).pack(side="left")
        tk.Button(sg_row, text="+ Group", font=("Arial", 8),
                  command=self._add_global_sub_group).pack(side="left", padx=2)
        self._global_sub_group_frame = tk.Frame(self._sub_global_frame, bg=bg)
        self._global_sub_group_frame.pack(fill="x", padx=4)
        self._rebuild_global_sub_groups()

    def _global_sub_tt_changed(self, *_) -> None:
        sub = self.ability.get("sub_sigil_global")
        if sub:
            val = self._global_sub_tt_var.get() or None
            sub["target_type"] = val
            self.on_change()

    def _global_sub_cond_changed(self, *_) -> None:
        sub = self.ability.get("sub_sigil_global")
        if sub:
            val = self._global_sub_cond_var.get() or None
            sub["condition_id"] = val
            sub["condition_vals"] = {}
            self.on_change()

    def _rebuild_global_sub_costs(self) -> None:
        if not hasattr(self, "_global_sub_cost_frame"):
            return
        for w in self._global_sub_cost_frame.winfo_children():
            w.destroy()
        sub = self.ability.get("sub_sigil_global") or {}
        for idx, ci in enumerate(sub.get("costs", [])):
            self._cost_pill_in(self._global_sub_cost_frame, ci, idx, sub["costs"])

    def _rebuild_global_sub_groups(self) -> None:
        if not hasattr(self, "_global_sub_group_frame"):
            return
        for w in self._global_sub_group_frame.winfo_children():
            w.destroy()
        sub = self.ability.get("sub_sigil_global") or {}
        bg  = self.cget("bg")
        for idx, grp in enumerate(sub.get("effect_groups", [])):
            EffectGroupEditor(
                self._global_sub_group_frame, grp,
                on_change=self.on_change,
                on_delete=lambda i=idx: self._del_global_sub_group(i),
                bg=bg,
            ).pack(fill="x", pady=1)

    def _add_global_sub_cost(self) -> None:
        sub = self.ability.get("sub_sigil_global")
        if sub is None: return
        sub.setdefault("costs", []).append(
            {"cost_id": "", "vals": {}, "opt_vals": {}})
        self._rebuild_global_sub_costs()
        self.on_change()

    def _add_global_sub_group(self) -> None:
        sub = self.ability.get("sub_sigil_global")
        if sub is None: return
        sub.setdefault("effect_groups", []).append(empty_effect_group())
        self._rebuild_global_sub_groups()
        self.on_change()

    def _del_global_sub_group(self, idx: int) -> None:
        sub = self.ability.get("sub_sigil_global")
        if sub: sub["effect_groups"].pop(idx)
        self._rebuild_global_sub_groups()
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
