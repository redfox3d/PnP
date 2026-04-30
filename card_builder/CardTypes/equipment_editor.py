"""
equipment_editor.py – Editors for Equipment and Supplies cards.

Items now use a block-based model (mirrors Spells / Prowess), filtered by
``sigils_for_card_type``. The Materials sigil is implicit (drawn from
``card.materials``) and never needs to be added as a block.
"""

import tkinter as tk
from tkinter import ttk

from card_builder.CardTypes.base_card import BaseCardEditor, TagSelector
from card_builder.constants import ELEMENTS, sigils_for_card_type, sigil_label
from card_builder.materials import merged_materials, save_central_materials, load_central_materials
from card_builder.models import migrate_item_card


class _ItemBlockMixin:
    """Shared behaviour for item-card editors with a block list.

    Subclasses must call ``self._build_common_fields()`` and
    ``self._build_blocks_section()``. They also implement ``_changed``
    which collects the non-block fields.
    """

    # Sigils that get the right-side rendering treatment in the canvas
    _RIGHT_SIDE_SIGILS = ("Equipped",)

    # ── shared fields: element-sources / object-type / materials / weight / value
    def _build_common_fields(self):
        ef   = self._f
        card = self.card

        r = self._row()
        self._lbl("Element-Quellen (max 3):", r).pack(side="left")
        self._el_src = TagSelector(
            self._f, values=ELEMENTS,
            selected=card.get("element_sources", []),
            on_change=self._changed, max_items=3, bg=self.BG)
        self._el_src.pack(fill="x", padx=8, pady=2)

        r = self._row()
        self._lbl("Objekt-Typ:", r).pack(side="left")
        known = ["Schwert", "Dolch", "Bogen", "Schild", "Ruestung",
                 "Muenze", "Ring", "Stab", "Trank", "Buch", "Werkzeug"]
        self._obj_type = TagSelector(
            self._f, values=known,
            selected=card.get("object_type", []),
            on_change=self._changed, bg=self.BG)
        self._obj_type.pack(fill="x", padx=8, pady=2)

        r = self._row()
        self._lbl("Materialien:", r).pack(side="left")
        all_mats = merged_materials()
        self._materials = TagSelector(
            self._f, values=all_mats,
            selected=card.get("materials", []),
            on_change=self._changed, bg=self.BG)
        self._materials.pack(fill="x", padx=8, pady=2)

        self._sep()

        r = self._row()
        self._lbl("Weight:", r).pack(side="left")
        self._weight_var = tk.StringVar(value=str(card.get("weight", 0)))
        self._weight_var.trace_add("write", self._changed)
        tk.Spinbox(r, from_=0, to=9999, textvariable=self._weight_var,
                   width=6, bg="#2a2a2a", fg="white",
                   insertbackground="white",
                   buttonbackground="#2a2a2a").pack(side="left", padx=4)

        r = self._row()
        self._lbl("Wert (0-999):", r).pack(side="left")
        self._value_var = tk.StringVar(value=str(card.get("value", 0)))
        self._value_var.trace_add("write", self._changed)
        tk.Spinbox(r, from_=0, to=999, textvariable=self._value_var,
                   width=6, bg="#2a2a2a", fg="white",
                   insertbackground="white",
                   buttonbackground="#2a2a2a").pack(side="left", padx=4)

    def _build_blocks_section(self):
        """Renders the block list with an Add-Block dropdown (filtered by
        ``sigils_for_card_type``). The Materials sigil is implicit and not
        listed here — it's drawn from ``card.materials`` directly."""
        # Migrate legacy text fields BEFORE we render the editor.
        migrate_item_card(self.card)

        self._sep()
        ct = self.card.get("card_type", "")
        allowed = [s for s in sigils_for_card_type(ct)
                   if s != "Materials"]   # Materials is implicit

        ctrl = tk.Frame(self._f, bg=self.BG)
        ctrl.pack(fill="x", padx=8, pady=4)
        tk.Label(ctrl, text="Add Sigil:", bg=self.BG, fg="#ccc",
                 font=("Arial", 9, "bold")).pack(side="left")
        self._new_block_var = tk.StringVar(value=allowed[0] if allowed else "")
        ttk.Combobox(ctrl, textvariable=self._new_block_var,
                     values=allowed, width=14, state="readonly"
                     ).pack(side="left", padx=4)
        tk.Button(ctrl, text="+ Add Sigil", command=self._add_block,
                  bg="#1a6e3c", fg="white", font=("Arial", 8)
                  ).pack(side="left", padx=4)
        tk.Label(ctrl,
                 text="(Materials ist immer da — aus 'Materialien' oben.)",
                 bg=self.BG, fg="#888",
                 font=("Arial", 8, "italic")).pack(side="left", padx=12)

        self._blocks_frame = tk.Frame(self._f, bg=self.BG)
        self._blocks_frame.pack(fill="x", padx=8, pady=4)
        self._rebuild_blocks()

    def _rebuild_blocks(self):
        for w in self._blocks_frame.winfo_children():
            w.destroy()
        ct = self.card.get("card_type", "")
        for idx, blk in enumerate(self.card.get("blocks", [])):
            self._build_one_block(idx, blk, ct)

    def _build_one_block(self, idx: int, blk: dict, card_type: str):
        wrap = tk.LabelFrame(self._blocks_frame,
                              text=f"  ◆ {sigil_label(blk.get('type','?'), card_type)}  ",
                              bg=self.BG, fg="#ffd9a3",
                              font=("Arial", 9, "bold"),
                              relief="groove", bd=1)
        wrap.pack(fill="x", pady=4)

        # Header: del button (right)
        hdr = tk.Frame(wrap, bg=self.BG); hdr.pack(fill="x", padx=4, pady=2)
        tk.Label(hdr, text=f"Sigil-Typ: {blk.get('type','?')}",
                 bg=self.BG, fg="#ccc",
                 font=("Arial", 8)).pack(side="left")
        tk.Button(hdr, text="✕ entfernen",
                  command=lambda i=idx: self._del_block(i),
                  bg="#6e1a1a", fg="white",
                  font=("Arial", 8)).pack(side="right")

        # Single-ability raw-text editor for now (Items don't yet use the
        # full effect_groups model — they store text on each block).
        ab = blk.get("abilities", [{}])[0] if blk.get("abilities") else {}
        if not blk.get("abilities"):
            blk["abilities"] = [{}]

        tk.Label(wrap, text="Effekt-Text:",
                 bg=self.BG, fg="#aaa",
                 font=("Arial", 8, "bold")).pack(anchor="w", padx=4)
        txt = tk.Text(wrap, height=3, bg="#2a2a2a", fg="white",
                      insertbackground="white",
                      font=("Arial", 9), wrap="word")
        txt.insert("1.0", ab.get("raw_text", ""))
        txt.pack(fill="x", padx=4, pady=2)

        def _on_text(_=None, t=txt, a=ab):
            a["raw_text"] = t.get("1.0", "end-1c")
            self._changed()
        txt.bind("<KeyRelease>", _on_text)

        # Equipped sigils get an extra Cost-Text field
        if blk.get("type") == "Equipped":
            tk.Label(wrap, text="Equip-Kosten:",
                     bg=self.BG, fg="#aaa",
                     font=("Arial", 8, "bold")).pack(anchor="w", padx=4)
            ctxt = tk.Text(wrap, height=2, bg="#2a2a2a", fg="white",
                            insertbackground="white",
                            font=("Arial", 9), wrap="word")
            ctxt.insert("1.0", ab.get("raw_cost_text", ""))
            ctxt.pack(fill="x", padx=4, pady=2)

            def _on_cost(_=None, t=ctxt, a=ab):
                a["raw_cost_text"] = t.get("1.0", "end-1c")
                self._changed()
            ctxt.bind("<KeyRelease>", _on_cost)

    def _add_block(self):
        bt = self._new_block_var.get().strip()
        if not bt:
            return
        # Disallow duplicate sigil types per card
        if any(b.get("type") == bt for b in self.card.get("blocks", [])):
            return
        self.card.setdefault("blocks", []).append({
            "type": bt,
            "abilities": [{"raw_text": "", "effect_groups": [], "costs": []}],
        })
        self._rebuild_blocks()
        self._changed()

    def _del_block(self, idx: int):
        try:
            self.card.get("blocks", []).pop(idx)
        except (IndexError, AttributeError):
            return
        self._rebuild_blocks()
        self._changed()


class EquipmentCardEditor(BaseCardEditor, _ItemBlockMixin):

    def _build_type_fields(self):
        self._build_common_fields()
        self._build_blocks_section()

    def _changed(self, *_):
        card = self.card
        if hasattr(self, "_el_src"):
            card["element_sources"] = self._el_src.get()
        if hasattr(self, "_obj_type"):
            card["object_type"] = self._obj_type.get()
        if hasattr(self, "_materials"):
            card["materials"] = self._materials.get()
            save_central_materials(load_central_materials() + card["materials"])
        try:
            card["weight"] = max(0, min(9999, int(self._weight_var.get())))
        except (ValueError, AttributeError):
            pass
        try:
            card["value"] = max(0, min(999, int(self._value_var.get())))
        except (ValueError, AttributeError):
            pass
        if self.on_change:
            self.on_change()


class SuppliesCardEditor(BaseCardEditor, _ItemBlockMixin):
    """Editor for Supplies cards – sigils whitelist excludes Equipped."""

    def _build_type_fields(self):
        self._build_common_fields()
        self._build_blocks_section()

    def _changed(self, *_):
        card = self.card
        if hasattr(self, "_el_src"):
            card["element_sources"] = self._el_src.get()
        if hasattr(self, "_obj_type"):
            card["object_type"] = self._obj_type.get()
        if hasattr(self, "_materials"):
            card["materials"] = self._materials.get()
            save_central_materials(load_central_materials() + card["materials"])
        try:
            card["weight"] = max(0, min(9999, int(self._weight_var.get())))
        except (ValueError, AttributeError):
            pass
        try:
            card["value"] = max(0, min(999, int(self._value_var.get())))
        except (ValueError, AttributeError):
            pass
        if self.on_change:
            self.on_change()


# ── Tokens / Creatures / StatusEffects editors ───────────────────────────────
# All three share the same block-based skeleton as SuppliesCardEditor but
# expose different stat fields (HP/Move, Duration) and skip Materials.

class _WorldCardMixin:
    """Common element-sources + tags row used by Tokens / Creatures /
    StatusEffects (no Materials, no weight/value)."""

    def _build_world_common_fields(self):
        card = self.card
        r = self._row()
        self._lbl("Element-Quellen (max 3):", r).pack(side="left")
        self._el_src = TagSelector(
            self._f, values=ELEMENTS,
            selected=card.get("element_sources", []),
            on_change=self._changed, max_items=3, bg=self.BG)
        self._el_src.pack(fill="x", padx=8, pady=2)

        r = self._row()
        self._lbl("Tags:", r).pack(side="left")
        self._tags = TagSelector(
            self._f, values=[], selected=card.get("tags", []),
            on_change=self._changed, bg=self.BG)
        self._tags.pack(fill="x", padx=8, pady=2)

    def _flush_world_common(self):
        c = self.card
        if hasattr(self, "_el_src"):
            c["element_sources"] = self._el_src.get()
        if hasattr(self, "_tags"):
            c["tags"] = self._tags.get()


class TokensCardEditor(BaseCardEditor, _WorldCardMixin, _ItemBlockMixin):

    def _build_type_fields(self):
        self._build_world_common_fields()
        self._sep()
        self._build_blocks_section()

    def _changed(self, *_):
        self._flush_world_common()
        if self.on_change: self.on_change()


class CreaturesCardEditor(BaseCardEditor, _WorldCardMixin, _ItemBlockMixin):

    MAX_ATTACKS = 4   # hard cap per creature

    def _build_type_fields(self):
        self._build_world_common_fields()
        self._sep()

        r = self._row()
        self._lbl("HP:", r).pack(side="left")
        self._hp_var = tk.StringVar(value=str(self.card.get("hp", 1)))
        self._hp_var.trace_add("write", self._changed)
        tk.Spinbox(r, from_=0, to=999, textvariable=self._hp_var,
                   width=5, bg="#2a2a2a", fg="white",
                   insertbackground="white",
                   buttonbackground="#2a2a2a").pack(side="left", padx=4)

        self._lbl("  Move:", r).pack(side="left")
        self._move_var = tk.StringVar(value=str(self.card.get("move", 1)))
        self._move_var.trace_add("write", self._changed)
        tk.Spinbox(r, from_=0, to=99, textvariable=self._move_var,
                   width=4, bg="#2a2a2a", fg="white",
                   insertbackground="white",
                   buttonbackground="#2a2a2a").pack(side="left", padx=4)

        # Strong / weak against — multi-element selectors
        r = self._row()
        self._lbl("Stark gegen:", r).pack(side="left")
        self._strong = TagSelector(
            self._f, values=ELEMENTS,
            selected=self.card.get("strong_against", []),
            on_change=self._changed, bg=self.BG)
        self._strong.pack(fill="x", padx=8, pady=2)

        r = self._row()
        self._lbl("Schwach gegen:", r).pack(side="left")
        self._weak = TagSelector(
            self._f, values=ELEMENTS,
            selected=self.card.get("weak_against", []),
            on_change=self._changed, bg=self.BG)
        self._weak.pack(fill="x", padx=8, pady=2)

        self._sep()
        self._build_blocks_section()

    def _changed(self, *_):
        c = self.card
        self._flush_world_common()
        try: c["hp"]   = max(0, min(999, int(self._hp_var.get())))
        except (ValueError, AttributeError): pass
        try: c["move"] = max(0, min(99,  int(self._move_var.get())))
        except (ValueError, AttributeError): pass
        if hasattr(self, "_strong"):
            c["strong_against"] = self._strong.get()
        if hasattr(self, "_weak"):
            c["weak_against"]   = self._weak.get()
        if self.on_change: self.on_change()

    # ── Override block render: Attack sigils get specialised UI ──────────────

    def _build_one_block(self, idx: int, blk: dict, card_type: str):
        if blk.get("type") == "Attack":
            return self._build_attack_block(idx, blk)
        return super()._build_one_block(idx, blk, card_type)

    def _build_attack_block(self, idx: int, blk: dict):
        """Attack sigil: list of (lower, upper, text) attacks, max 4."""
        wrap = tk.LabelFrame(self._blocks_frame,
                              text="  ⚔ Attack  ",
                              bg=self.BG, fg="#ff8888",
                              font=("Arial", 9, "bold"),
                              relief="groove", bd=1)
        wrap.pack(fill="x", pady=4)

        hdr = tk.Frame(wrap, bg=self.BG); hdr.pack(fill="x", padx=4, pady=2)
        atks = blk.get("abilities", [])
        tk.Label(hdr,
                 text=f"Sigil-Typ: Attack  ({len(atks)}/{self.MAX_ATTACKS})",
                 bg=self.BG, fg="#ccc", font=("Arial", 8)).pack(side="left")
        tk.Button(hdr, text="✕ entfernen",
                  command=lambda i=idx: self._del_block(i),
                  bg="#6e1a1a", fg="white",
                  font=("Arial", 8)).pack(side="right")

        # Existing attacks
        for ai, ab in enumerate(list(atks)):
            self._draw_one_attack(wrap, blk, ab, ai)

        # Add-attack button
        if len(atks) < self.MAX_ATTACKS:
            tk.Button(wrap, text="+ Angriff hinzufügen",
                      bg="#553300", fg="white", font=("Arial", 8),
                      command=lambda b=blk: self._add_attack(b)
                      ).pack(anchor="w", padx=6, pady=4)

    def _draw_one_attack(self, wrap, blk, ab, ai):
        row = tk.Frame(wrap, bg="#1a0a0a")
        row.pack(fill="x", padx=6, pady=2)

        tk.Label(row, text=f"#{ai+1}", bg="#1a0a0a", fg="#ff8888",
                 font=("Arial", 9, "bold"), width=3).pack(side="left")

        # Lower number
        tk.Label(row, text="von:", bg="#1a0a0a", fg="#aaa",
                 font=("Arial", 8)).pack(side="left", padx=(4, 0))
        lo_var = tk.StringVar(value=str(ab.get("lower", 1)))
        lo_e = tk.Entry(row, textvariable=lo_var, width=4,
                         bg="#2a1a1a", fg="white", insertbackground="white")
        lo_e.pack(side="left", padx=2)

        tk.Label(row, text="bis:", bg="#1a0a0a", fg="#aaa",
                 font=("Arial", 8)).pack(side="left", padx=(4, 0))
        hi_var = tk.StringVar(value=str(ab.get("upper", 6)))
        hi_e = tk.Entry(row, textvariable=hi_var, width=4,
                         bg="#2a1a1a", fg="white", insertbackground="white")
        hi_e.pack(side="left", padx=2)

        # Text
        text_var = tk.StringVar(value=ab.get("raw_text", ""))
        te = tk.Entry(row, textvariable=text_var, width=40,
                       bg="#2a1a1a", fg="white", insertbackground="white")
        te.pack(side="left", padx=4, fill="x", expand=True)

        # Delete button
        tk.Button(row, text="✕", fg="white", bg="#6e1a1a",
                  font=("Arial", 8, "bold"),
                  command=lambda b=blk, i=ai:
                      self._del_attack(b, i)
                  ).pack(side="left", padx=2)

        def _on_change(*_, a=ab, l=lo_var, h=hi_var, t=text_var):
            try: a["lower"] = int(l.get())
            except (ValueError, TypeError): pass
            try: a["upper"] = int(h.get())
            except (ValueError, TypeError): pass
            a["raw_text"] = t.get()
            self._changed()

        for v in (lo_var, hi_var, text_var):
            v.trace_add("write", _on_change)

    def _add_attack(self, blk):
        atks = blk.setdefault("abilities", [])
        if len(atks) >= self.MAX_ATTACKS:
            return
        atks.append({"lower": 1, "upper": 6, "raw_text": ""})
        self._rebuild_blocks()
        self._changed()

    def _del_attack(self, blk, idx):
        atks = blk.get("abilities", [])
        if 0 <= idx < len(atks):
            atks.pop(idx)
            self._rebuild_blocks()
            self._changed()

    def _add_block(self):
        bt = self._new_block_var.get().strip()
        # Attacks initialise with one empty entry
        if bt == "Attack":
            if any(b.get("type") == "Attack"
                   for b in self.card.get("blocks", [])):
                return
            self.card.setdefault("blocks", []).append({
                "type": "Attack",
                "abilities": [{"lower": 1, "upper": 6, "raw_text": ""}],
            })
            self._rebuild_blocks()
            self._changed()
            return
        super()._add_block()


class StatusEffectsCardEditor(BaseCardEditor, _WorldCardMixin, _ItemBlockMixin):

    SUBTYPES = ("Condition", "Curse", "Blessing")

    def _build_type_fields(self):
        self._build_world_common_fields()
        self._sep()

        r = self._row()
        self._lbl("Subtyp:", r).pack(side="left")
        self._subtype_var = tk.StringVar(
            value=self.card.get("subtype", "Condition"))
        self._subtype_var.trace_add("write", self._changed)
        ttk.Combobox(r, textvariable=self._subtype_var,
                     values=self.SUBTYPES, state="readonly",
                     width=12).pack(side="left", padx=6)

        r = self._row()
        self._lbl("Dauer (Runden):", r).pack(side="left")
        self._dur_var = tk.StringVar(value=str(self.card.get("duration", 1)))
        self._dur_var.trace_add("write", self._changed)
        tk.Spinbox(r, from_=1, to=99, textvariable=self._dur_var,
                   width=4, bg="#2a2a2a", fg="white",
                   insertbackground="white",
                   buttonbackground="#2a2a2a").pack(side="left", padx=4)
        tk.Label(r, text="(0 = permanent)", bg=self.BG, fg="#888",
                 font=("Arial", 8, "italic")).pack(side="left", padx=4)

        self._sep()
        self._build_blocks_section()

    def _changed(self, *_):
        c = self.card
        self._flush_world_common()
        try: c["duration"] = max(0, min(99, int(self._dur_var.get())))
        except (ValueError, AttributeError): pass
        st = (self._subtype_var.get() if hasattr(self, "_subtype_var")
              else "").strip()
        if st in self.SUBTYPES:
            c["subtype"] = st
        if self.on_change: self.on_change()
