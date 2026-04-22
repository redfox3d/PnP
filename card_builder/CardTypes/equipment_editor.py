"""
equipment_editor.py – Editors for Equipment and Supplies cards.
"""

import tkinter as tk

from card_builder.CardTypes.base_card import BaseCardEditor, TagSelector
from card_builder.constants import ELEMENTS
from card_builder.materials import merged_materials, save_central_materials, load_central_materials


class EquipmentCardEditor(BaseCardEditor):

    def _build_type_fields(self):
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

        self._lbl("Effekt-Text:").pack(anchor="w", padx=8)
        self._effect_text = tk.Text(ef, height=4, bg="#2a2a2a", fg="white",
                                    insertbackground="white", font=("Arial", 9),
                                    wrap="word")
        self._effect_text.insert("1.0", card.get("effect_text", ""))
        self._effect_text.bind("<KeyRelease>", self._changed)
        self._effect_text.pack(fill="x", padx=8, pady=2)

        self._sep()
        self._lbl("Equip Box:").pack(anchor="w", padx=8)
        self._equip_text = tk.Text(ef, height=3, bg="#2a2a2a", fg="white",
                                   insertbackground="white", font=("Arial", 9),
                                   wrap="word")
        self._equip_text.insert("1.0", card.get("equip_text", ""))
        self._equip_text.bind("<KeyRelease>", self._changed)
        self._equip_text.pack(fill="x", padx=8, pady=2)

        self._lbl("Equip Cost:").pack(anchor="w", padx=8)
        self._equip_cost = tk.Text(ef, height=2, bg="#2a2a2a", fg="white",
                                   insertbackground="white", font=("Arial", 9),
                                   wrap="word")
        self._equip_cost.insert("1.0", card.get("equip_cost_text", ""))
        self._equip_cost.bind("<KeyRelease>", self._changed)
        self._equip_cost.pack(fill="x", padx=8, pady=2)

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

    def _changed(self, *_):
        card = self.card
        if hasattr(self, "_el_src"):
            card["element_sources"] = self._el_src.get()
        if hasattr(self, "_obj_type"):
            card["object_type"] = self._obj_type.get()
        if hasattr(self, "_materials"):
            card["materials"] = self._materials.get()
            save_central_materials(load_central_materials() + card["materials"])
        if hasattr(self, "_effect_text"):
            card["effect_text"] = self._effect_text.get("1.0", "end-1c")
        if hasattr(self, "_equip_text"):
            card["equip_text"] = self._equip_text.get("1.0", "end-1c")
        if hasattr(self, "_equip_cost"):
            card["equip_cost_text"] = self._equip_cost.get("1.0", "end-1c")
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


class SuppliesCardEditor(BaseCardEditor):
    """Editor for Supplies cards – no equip fields."""

    def _build_type_fields(self):
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

        self._lbl("Effekt-Text:").pack(anchor="w", padx=8)
        self._effect_text = tk.Text(ef, height=4, bg="#2a2a2a", fg="white",
                                    insertbackground="white", font=("Arial", 9),
                                    wrap="word")
        self._effect_text.insert("1.0", card.get("effect_text", ""))
        self._effect_text.bind("<KeyRelease>", self._changed)
        self._effect_text.pack(fill="x", padx=8, pady=2)

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

    def _changed(self, *_):
        card = self.card
        if hasattr(self, "_el_src"):
            card["element_sources"] = self._el_src.get()
        if hasattr(self, "_obj_type"):
            card["object_type"] = self._obj_type.get()
        if hasattr(self, "_materials"):
            card["materials"] = self._materials.get()
            save_central_materials(load_central_materials() + card["materials"])
        if hasattr(self, "_effect_text"):
            card["effect_text"] = self._effect_text.get("1.0", "end-1c")
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
