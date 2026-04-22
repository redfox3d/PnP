"""
loot_editor.py – Editor for Loot cards.

Loot cards have:
  - Up to 3 elements (colored circles)
  - Per element: optional sacrifice effect
  - Neutral effects (no element)
  - Artwork, Name, Materials, Value
"""

import tkinter as tk
from tkinter import ttk

from card_builder.CardTypes.base_card import BaseCardEditor, TagSelector, ArtworkPicker
from card_builder.constants import (
    ELEMENTS, ELEMENT_COLORS, ELEMENT_ICONS, GENERIC_MANA_COLOR,
)
from card_builder.materials import merged_materials, save_central_materials, load_central_materials

_ELEMENT_OPTIONS = [e for e in ELEMENTS if e != "Generic"]


class LootCardEditor(BaseCardEditor):
    """
    Editor for Loot cards.
    Card dict structure:
        {
            "name":             str,
            "card_type":        "Loot",
            "artwork":          str,
            "elements":         [str, ...],           # up to 3
            "sacrifice_effects": {                     # keyed by element name
                "Fire": {"effect_id": str, "vals": {}, "opt_vals": {}},
                ...
            },
            "neutral_effects":  [{"effect_id": str, "vals": {}, "opt_vals": {}}, ...],
            "neutral_text":     str,
            "materials":        [str, ...],
            "value":            int,
        }
    """

    def _build_type_fields(self):
        card = self.card
        f    = self._f

        # ── Elements ──────────────────────────────────────────────────────────
        self._lbl("Elemente (max 3):").pack(anchor="w", padx=8, pady=(6, 0))
        self._el_frame = tk.Frame(f, bg=self.BG)
        self._el_frame.pack(fill="x", padx=8, pady=2)
        self._rebuild_element_rows()

        add_btn = tk.Button(
            f, text="+ Element hinzufügen",
            command=self._add_element,
            bg="#1a2a1a", fg="#88ff88",
            font=("Arial", 8), cursor="hand2",
        )
        add_btn.pack(anchor="w", padx=8, pady=2)
        self._add_el_btn = add_btn

        self._sep()

        # ── Neutral effects ──────────────────────────────────────────────────
        self._lbl("Neutrale Effekte:").pack(anchor="w", padx=8)
        tk.Label(f, text="Effekte ohne Element (werden in neutraler Box angezeigt)",
                 bg=self.BG, fg="#555", font=("Arial", 7, "italic")).pack(
            anchor="w", padx=16)

        card.setdefault("neutral_effects", [])
        self._neutral_frame = tk.Frame(f, bg=self.BG)
        self._neutral_frame.pack(fill="x", padx=8, pady=2)
        self._rebuild_neutral_rows()

        tk.Button(f, text="+ Neutraler Effekt",
                  command=self._add_neutral_effect,
                  bg="#1a2a2a", fg="#88aaff",
                  font=("Arial", 8), cursor="hand2").pack(
            anchor="w", padx=8, pady=2)

        # Neutral manual text
        self._lbl("Neutraler Freitext:").pack(anchor="w", padx=8, pady=(4, 0))
        self._neutral_text = tk.Text(f, height=3, bg="#2a2a2a", fg="white",
                                     insertbackground="white", font=("Arial", 9),
                                     wrap="word")
        self._neutral_text.insert("1.0", card.get("neutral_text", ""))
        self._neutral_text.bind("<KeyRelease>", self._on_neutral_text_change)
        self._neutral_text.pack(fill="x", padx=8, pady=2)

        self._sep()

        # ── Materials ─────────────────────────────────────────────────────────
        self._lbl("Materialien:").pack(anchor="w", padx=8)
        all_mats = merged_materials()
        self._materials = TagSelector(
            f, values=all_mats,
            selected=list(card.get("materials", [])),
            on_change=self._on_materials_change,
            bg=self.BG,
        )
        self._materials.pack(fill="x", padx=8, pady=2)

        self._sep()

        # ── Value ─────────────────────────────────────────────────────────────
        r = self._row()
        self._lbl("Wert (0-999):", r).pack(side="left")
        self._value_var = tk.StringVar(value=str(card.get("value", 0)))
        self._value_var.trace_add("write", self._on_value_change)
        tk.Spinbox(r, from_=0, to=999, textvariable=self._value_var,
                   width=6, bg="#2a2a2a", fg="white",
                   insertbackground="white",
                   buttonbackground="#2a2a2a").pack(side="left", padx=4)

    # ── Element rows ──────────────────────────────────────────────────────────

    def _rebuild_element_rows(self):
        for w in self._el_frame.winfo_children():
            w.destroy()
        elements = self.card.get("elements", [])
        sac      = self.card.get("sacrifice_effects", {})
        for idx, el in enumerate(elements):
            self._build_element_row(idx, el, sac.get(el))
        if hasattr(self, "_add_el_btn"):
            self._add_el_btn.config(
                state="normal" if len(elements) < 3 else "disabled")

    def _build_element_row(self, idx: int, element: str, eff_data: dict):
        bg = "#1e1e2a"
        outer = tk.Frame(self._el_frame, bg=bg, relief="groove", bd=1)
        outer.pack(fill="x", pady=2)

        row = tk.Frame(outer, bg=bg)
        row.pack(fill="x")

        tk.Button(row, text="x", font=("Arial", 8), cursor="hand2",
                  bg="#3a1a1a", fg="#ff8888", width=2,
                  command=lambda i=idx: self._remove_element(i)
                  ).pack(side="left", padx=(2, 0), pady=2)

        col  = ELEMENT_COLORS.get(element, GENERIC_MANA_COLOR)
        icon = ELEMENT_ICONS.get(element, "?")
        tk.Label(row, text=icon, bg=col, fg="white",
                 font=("Arial", 11), width=3).pack(side="left", padx=2, pady=2)

        el_var = tk.StringVar(value=element)
        cb = ttk.Combobox(row, textvariable=el_var,
                          values=_ELEMENT_OPTIONS,
                          state="readonly", width=9)
        cb.pack(side="left", padx=4, pady=2)

        def _on_el_change(*_, iv=idx, v=el_var):
            elems = self.card.get("elements", [])
            old_el = elems[iv] if iv < len(elems) else ""
            new_el = v.get()
            sac = self.card.setdefault("sacrifice_effects", {})
            if old_el in sac:
                sac[new_el] = sac.pop(old_el)
            elems[iv] = new_el
            self._rebuild_element_rows()
            self._changed()

        cb.bind("<<ComboboxSelected>>", _on_el_change)

        eff_text = self._render_effect_short(eff_data)
        eff_lbl  = tk.Label(row, text=eff_text or "---",
                            bg=bg, fg="#88ff88" if eff_text else "#555",
                            font=("Arial", 8), anchor="w")
        eff_lbl.pack(side="left", padx=4, fill="x", expand=True)

        tk.Button(row, text="Edit", font=("Arial", 8), cursor="hand2",
                  bg="#2a3a2a", fg="#88ff88",
                  command=lambda el=element, lbl=eff_lbl: self._open_effect_picker(el, lbl)
                  ).pack(side="right", padx=2, pady=2)

        # Manual text entry
        manual_text = (eff_data or {}).get("manual_text", "")
        mt_row = tk.Frame(outer, bg=bg)
        mt_row.pack(fill="x", padx=4, pady=(0, 2))
        tk.Label(mt_row, text="Freitext:", bg=bg, fg="#666",
                 font=("Arial", 7)).pack(side="left", padx=2)
        mt_entry = tk.Entry(mt_row, bg="#2a2a2a", fg="#ffcc88",
                            insertbackground="white", font=("Arial", 8))
        mt_entry.insert(0, manual_text)
        mt_entry.pack(side="left", fill="x", expand=True, padx=2)

        def _on_manual_change(*_, el=element, entry=mt_entry):
            sac = self.card.setdefault("sacrifice_effects", {})
            data = sac.setdefault(el, {})
            txt = entry.get().strip()
            if txt:
                data["manual_text"] = txt
            else:
                data.pop("manual_text", None)
            self._changed()

        mt_entry.bind("<KeyRelease>", _on_manual_change)

    def _render_effect_short(self, eff_data: dict) -> str:
        if not eff_data or not eff_data.get("effect_id"):
            return ""
        eid = eff_data["effect_id"]
        try:
            from card_builder.data import get_content_data
            cd = get_content_data()
            item = cd.get("effect", eid)
            if item:
                from card_builder.CardTypes.base_card import _render_content
                text = _render_content(item, {
                    "var_values": eff_data.get("vals", {}),
                    "opt_values": eff_data.get("opt_vals", {}),
                })
                return text[:32] + ("..." if len(text) > 32 else "")
        except Exception:
            pass
        return eid

    # ── Effect picker dialog ──────────────────────────────────────────────────

    def _open_effect_picker(self, element: str, lbl_widget: tk.Label):
        from card_builder.dialogs import EffectPickerDialog
        try:
            from card_builder.data import get_content_data
            cd   = get_content_data()
            effs = cd.effects
        except Exception:
            effs = []
        if not effs:
            return

        sac      = self.card.get("sacrifice_effects", {})
        cur_data = dict(sac.get(element) or {})

        def _on_done(result):
            sac = self.card.setdefault("sacrifice_effects", {})
            if result:
                sac[element] = result
            else:
                sac.pop(element, None)
            lbl_widget.config(
                text=self._render_effect_short(sac.get(element)) or "--- kein Opfer-Effekt",
                fg="#88ff88" if sac.get(element) else "#555",
            )
            self._changed()

        EffectPickerDialog(
            self.winfo_toplevel(),
            title=f"Opfer-Effekt: {element}",
            current_data=cur_data,
            on_ok=_on_done,
        )

    # ── Neutral effects ──────────────────────────────────────────────────────

    def _rebuild_neutral_rows(self):
        for w in self._neutral_frame.winfo_children():
            w.destroy()
        for idx, neff in enumerate(self.card.get("neutral_effects", [])):
            self._build_neutral_row(idx, neff)

    def _build_neutral_row(self, idx: int, neff: dict):
        bg = "#1e2a2a"
        row = tk.Frame(self._neutral_frame, bg=bg, relief="groove", bd=1)
        row.pack(fill="x", pady=1)

        tk.Button(row, text="x", font=("Arial", 8), cursor="hand2",
                  bg="#3a1a1a", fg="#ff8888", width=2,
                  command=lambda i=idx: self._remove_neutral_effect(i)
                  ).pack(side="left", padx=2, pady=2)

        eid = neff.get("effect_id", "")
        label_text = self._render_effect_short(neff) if eid else "---"
        lbl = tk.Label(row, text=label_text, bg=bg,
                       fg="#88aaff" if eid else "#555",
                       font=("Arial", 8), anchor="w")
        lbl.pack(side="left", padx=4, fill="x", expand=True)

        tk.Button(row, text="Edit", font=("Arial", 8), cursor="hand2",
                  bg="#2a2a3a", fg="#88aaff",
                  command=lambda i=idx, l=lbl: self._open_neutral_picker(i, l)
                  ).pack(side="right", padx=2, pady=2)

    def _add_neutral_effect(self):
        neutrals = self.card.setdefault("neutral_effects", [])
        neutrals.append({})
        self._rebuild_neutral_rows()
        self._changed()

    def _remove_neutral_effect(self, idx: int):
        neutrals = self.card.get("neutral_effects", [])
        if 0 <= idx < len(neutrals):
            neutrals.pop(idx)
        self._rebuild_neutral_rows()
        self._changed()

    def _open_neutral_picker(self, idx: int, lbl_widget: tk.Label):
        from card_builder.dialogs import EffectPickerDialog
        try:
            from card_builder.data import get_content_data
            cd   = get_content_data()
            effs = cd.effects
        except Exception:
            effs = []
        if not effs:
            return

        neutrals = self.card.setdefault("neutral_effects", [])
        cur_data = dict(neutrals[idx]) if idx < len(neutrals) else {}

        def _on_done(result):
            if result:
                neutrals[idx] = result
            else:
                neutrals[idx] = {}
            lbl_widget.config(
                text=self._render_effect_short(neutrals[idx]) or "---",
                fg="#88aaff" if neutrals[idx].get("effect_id") else "#555",
            )
            self._changed()

        EffectPickerDialog(
            self.winfo_toplevel(),
            title=f"Neutraler Effekt #{idx+1}",
            current_data=cur_data,
            on_ok=_on_done,
        )

    def _on_neutral_text_change(self, *_):
        self.card["neutral_text"] = self._neutral_text.get("1.0", "end-1c")
        self._changed()

    # ── CRUD helpers ──────────────────────────────────────────────────────────

    def _add_element(self):
        elems = self.card.setdefault("elements", [])
        if len(elems) >= 3:
            return
        used = set(elems)
        for el in _ELEMENT_OPTIONS:
            if el not in used:
                elems.append(el)
                break
        else:
            elems.append(_ELEMENT_OPTIONS[0])
        self._rebuild_element_rows()
        self._changed()

    def _remove_element(self, idx: int):
        elems = self.card.get("elements", [])
        if 0 <= idx < len(elems):
            el = elems.pop(idx)
            self.card.get("sacrifice_effects", {}).pop(el, None)
        self._rebuild_element_rows()
        self._changed()

    def _on_materials_change(self):
        mats = self._materials.get()
        self.card["materials"] = mats
        existing = load_central_materials()
        save_central_materials(existing + mats)
        self._changed()

    def _on_value_change(self, *_):
        try:
            self.card["value"] = max(0, min(999, int(self._value_var.get())))
        except (ValueError, AttributeError):
            pass
        self._changed()

    def _changed(self, *_):
        if self.on_change:
            self.on_change()
