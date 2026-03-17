"""
loot_card.py – Editor and renderer for Equipment and Supplies cards.
(formerly Loot = Supplies, Equipment unchanged name)

Supplies:  name, element sources, artwork (mana icons stacked left), type/material tags, effect, value
Equipment: same as Supplies + left: EquipBox + EquipCost | right: Effect Box
"""

import tkinter as tk
from tkinter import ttk

from card_builder.CardTypes.base_card import BaseCardEditor, TagSelector
from card_builder.constants import (
    CARD_W, CARD_H, ELEMENTS, ELEMENT_COLORS, ELEMENT_ICONS,
    GENERIC_MANA_ICON, GENERIC_MANA_COLOR,
)
from card_builder.materials import merged_materials, save_central_materials, load_central_materials

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False


# ── Editor ────────────────────────────────────────────────────────────────────

class SuppliesCardEditor(BaseCardEditor):

    def _build_type_fields(self):
        self._build_item_fields()

    def _build_item_fields(self):
        ef   = self._f
        card = self.card
        ct   = card.get("card_type", "Supplies")

        # Element sources – Supplies and Equipment both use same widget
        EL_SOURCE_VALUES = ELEMENTS + ["Generic"]
        r = self._row()
        self._lbl("Element-Quellen (max 3):", r).pack(side="left")
        self._el_src = TagSelector(
            self._f,                              # parent = scroll frame, not row
            values=EL_SOURCE_VALUES,
            selected=card.get("element_sources", []),
            on_change=self._changed,
            max_items=3, bg=self.BG)
        self._el_src.pack(fill="x", padx=8, pady=2)

        # Object type
        r = self._row()
        self._lbl("Objekt-Typ:", r).pack(side="left")
        known = ["Schwert", "Dolch", "Bogen", "Schild", "Rüstung",
                 "Münze", "Ring", "Stab", "Trank", "Buch", "Werkzeug"]
        self._obj_type = TagSelector(
            self._f, values=known,
            selected=card.get("object_type", []),
            on_change=self._changed, bg=self.BG)
        self._obj_type.pack(fill="x", padx=8, pady=2)

        # Materials
        r = self._row()
        self._lbl("Materialien:", r).pack(side="left")
        all_mats = merged_materials()
        self._materials = TagSelector(
            self._f, values=all_mats,
            selected=card.get("materials", []),
            on_change=self._changed, bg=self.BG)
        self._materials.pack(fill="x", padx=8, pady=2)

        self._sep()

        # Effect text
        self._lbl("On-Field Effekt:").pack(anchor="w", padx=8)
        self._effect_text = tk.Text(ef, height=4, bg="#2a2a2a", fg="white",
                                    insertbackground="white", font=("Arial", 9),
                                    wrap="word")
        self._effect_text.insert("1.0", card.get("effect_text", ""))
        self._effect_text.bind("<KeyRelease>", self._changed)
        self._effect_text.pack(fill="x", padx=8, pady=2)

        if ct == "Equipment":
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
        self._lbl("Wert (0-999):", r).pack(side="left")
        self._value_var = tk.StringVar(value=str(card.get("value", 0)))
        self._value_var.trace_add("write", self._changed)
        tk.Spinbox(r, from_=0, to=999, textvariable=self._value_var,
                   width=6, bg="#2a2a2a", fg="white",
                   insertbackground="white").pack(side="left", padx=4)

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
            card["value"] = max(0, min(999, int(self._value_var.get())))
        except (ValueError, AttributeError):
            pass
        if self.on_change: self.on_change()


class EquipmentCardEditor(SuppliesCardEditor):
    pass


# ── Renderer helpers ──────────────────────────────────────────────────────────

def _draw_art_with_mana(canvas, card, x0, y0, x1, y1, img_ref_holder):
    """Draw artwork with mana source icons stacked on the left inside the art box."""
    import os
    c = canvas
    c.create_rectangle(x0, y0, x1, y1, fill="#111", outline="#444")

    path = card.get("artwork", "")
    if path and _PIL and os.path.exists(path):
        try:
            img = Image.open(path)
            w, h = x1-x0, y1-y0
            iw, ih = img.size
            s = max(w/iw, h/ih)
            nw, nh = int(iw*s), int(ih*s)
            img = img.resize((nw, nh), Image.LANCZOS)
            lf, tp = (nw-w)//2, (nh-h)//2
            img = img.crop((lf, tp, lf+w, tp+h))
            img_ref_holder[0] = ImageTk.PhotoImage(img)
            c.create_image(x0, y0, image=img_ref_holder[0], anchor="nw")
        except Exception:
            c.create_text((x0+x1)//2, (y0+y1)//2,
                          text="Artwork", fill="#444", font=("Palatino Linotype", 11))
    else:
        c.create_text((x0+x1)//2, (y0+y1)//2,
                      text="Artwork", fill="#444", font=("Palatino Linotype", 11))

    # Mana icons stacked left inside artwork
    srcs = card.get("element_sources", [])
    r    = 10
    ix   = x0 + r + 3
    iy   = y0 + r + 4
    for el in srcs[:3]:
        col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
        icon = ELEMENT_ICONS.get(el, GENERIC_MANA_ICON)
        c.create_oval(ix-r, iy-r, ix+r, iy+r,
                      fill=col, outline="gold", width=1)
        c.create_text(ix, iy, text=icon, font=("Arial", 10), anchor="center")
        iy += r*2 + 4

# ── Supplies Renderer ─────────────────────────────────────────────────────────

class LootCardRenderer:
    FF   = "Palatino Linotype"
    FS_S = 11
    PAD  = 8

    def __init__(self, canvas: tk.Canvas):
        self.canvas  = canvas
        self.W       = CARD_W
        self.H       = CARD_H
        self._img    = [None]

    def render(self, card: dict):
        c  = self.canvas
        c.delete("all")
        ct = card.get("card_type", "Supplies")
        P  = self.PAD

        c.create_rectangle(0, 0, self.W, self.H, fill="#1a1a2a", outline="")
        c.create_rectangle(2, 2, self.W-2, self.H-2, outline="#888", width=2)

        # Name
        c.create_text(P, P, text=card.get("name", ""), anchor="nw",
                      font=(self.FF, 16, "bold"), fill="white")

        # Artwork with mana icons inside left
        AY0, AY1 = 36, 240
        _draw_art_with_mana(c, card, P, AY0, self.W-P, AY1, self._img)

        # Tags
        y = AY1 + 6
        tags = card.get("object_type", []) + card.get("materials", [])
        tx   = P
        for tag in tags:
            tw = len(tag) * 7 + 10
            if tx + tw > self.W - P:
                tx = P; y += 22
            c.create_rectangle(tx, y, tx+tw, y+18,
                               fill="#2a3a2a", outline="#aaffaa")
            c.create_text(tx+tw//2, y+9, text=tag,
                          fill="#aaffaa", font=("Arial", 9))
            tx += tw + 4
        y += 26

        BOX_BOTTOM = self.H - 40

        if ct == "Supplies":
            self._text_box(P, y, self.W-P, BOX_BOTTOM,
                           card.get("effect_text", ""),
                           fill="#111", outline="#555", color="white")
        elif ct == "Equipment":
            self._render_equipment_boxes(card, P, y, BOX_BOTTOM)

        # Value badge
        val = card.get("value", 0)
        c.create_rectangle(self.W-64, self.H-36, self.W-P, self.H-P,
                           fill="#2a2200", outline="gold", width=2)
        c.create_text(self.W-34, self.H-18, text=f"⚙ {val}",
                      fill="gold", font=(self.FF, 12, "bold"))

    def _render_equipment_boxes(self, card, P, y, bot):
        c   = self.canvas
        MID = self.W // 2

        equip_cost_h  = 36
        equip_box_bot = bot - equip_cost_h - 2

        # ── Left: Effect box ──────────────────────────────────────────────────
        self._text_box(P, y, MID-2, bot,
                       card.get("effect_text", ""),
                       fill="#111", outline="#555",
                       color="white", header="Effekt")

        # ── Right top: Equip box ──────────────────────────────────────────────
        self._text_box(MID+2, y, self.W-P, equip_box_bot,
                       card.get("equip_text", ""),
                       fill="#1a1100", outline="#997700",
                       color="#ffdd88", header="Equip")

        # ── Right bottom: EquipCost strip ─────────────────────────────────────
        c.create_rectangle(MID+2, equip_box_bot+2, self.W-P, bot,
                           fill="#0d0a00", outline="#997700")
        c.create_text(MID+6, equip_box_bot+4, text="Cost:", anchor="nw",
                      fill="#997700", font=(self.FF, 8, "bold"))
        ec = card.get("equip_cost_text", "")
        if ec:
            c.create_text(MID+46, (equip_box_bot+2+bot)//2, text=ec,
                          anchor="w", fill="#ffdd88",
                          font=(self.FF, self.FS_S))

    def _text_box(self, x0, y0, x1, y1, text, fill, outline,
                  color="white", header=None):
        c  = self.canvas
        P  = 4
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline)
        ty = y0 + P
        if header:
            c.create_text(x0+P, ty, text=header, anchor="nw",
                          fill="#888", font=(self.FF, 9, "bold"))
            ty += 16
        if not text:
            return
        font   = (self.FF, self.FS_S)
        line_h = self.FS_S + 5
        max_w  = x1 - x0 - P*2
        lines  = self._wrap_lines(text, max_w, font)
        total  = len(lines) * line_h
        avail  = y1 - ty - P
        sy     = ty + max(0, (avail - total) // 2)
        for line in lines:
            if sy + line_h > y1 - P: break
            c.create_text(x0+P, sy, text=line, anchor="nw",
                          font=font, fill=color)
            sy += line_h

    def _wrap_lines(self, text, max_w, font):
        words, lines, line = text.split(), [], ""
        fs = font[1]
        for word in words:
            test = (line + " " + word).strip()
            if len(test) * fs * 0.55 > max_w and line:
                lines.append(line); line = word
            else:
                line = test
        if line: lines.append(line)
        return lines