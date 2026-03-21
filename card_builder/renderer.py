"""
renderer.py – CardRenderer: draws cards per type onto a tk.Canvas.

Layout per type:
    Spells    – name + element icon + artwork strip (right) + blocks
    Prowess   – like Spells but no artwork strip, no element
    Loot      – name + element source icons (top-left) + artwork + type/material + effect + value
    Equipment – like Loot but effect left half, equip box right half
    Alchemy   – name + artwork + ingredients list + on-field effect
"""

import os
import re
import tkinter as tk

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False

from .constants import (
    CARD_W, CARD_H, ARTWORK_W,
    BOX_COLORS, BOX_SYMBOLS,
    ELEMENT_COLORS, ELEMENT_ICONS,
    TYPE_SYMBOLS, COND_SYMBOL, EFFECT_SYMBOL, COST_SYMBOL,
)
from .data import get_content_data, fill_placeholders


class CardRenderer:
    FF     = "Palatino Linotype"
    FS     = 13
    FS_SM  = 10

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas  = canvas
        self.W       = CARD_W
        self.H       = CARD_H
        self.AW      = ARTWORK_W
        self._img    = None   # keep PIL ref alive

    # ── Public ────────────────────────────────────────────────────────────────

    def render(self, card: dict) -> None:
        c  = self.canvas
        c.delete("all")
        ct = card.get("card_type", "Spells")

        if ct == "Spells":
            self._render_spell(card)
        elif ct == "Prowess":
            self._render_prowess(card)
        elif ct == "Loot":
            self._render_loot(card)
        elif ct == "Equipment":
            self._render_equipment(card)
        elif ct == "Alchemy":
            self._render_alchemy(card)
        else:
            self._render_spell(card)

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _bg(self, color: str, stipple: str = "gray25") -> None:
        c = self.canvas
        c.create_rectangle(0, 0, self.W, self.H, fill="#1a1a1a", outline="")
        if color:
            c.create_rectangle(0, 0, self.W, self.H,
                               fill=color, outline="", stipple=stipple)

    def _border(self) -> None:
        self.canvas.create_rectangle(2, 2, self.W-2, self.H-2,
                                     outline="black", width=3)

    def _name(self, name: str, x: int = 10, y: int = 10,
              color: str = "white") -> None:
        self.canvas.create_text(x, y, text=name, anchor="nw",
                                font=(self.FF, 16, "bold"), fill=color)

    def _artwork_box(self, path: str, x0: int, y0: int,
                     x1: int, y1: int) -> None:
        """Draw artwork image or placeholder."""
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill="#111", outline="#444")
        if path and _PIL and os.path.exists(path):
            try:
                img = Image.open(path)
                img = img.resize((x1-x0, y1-y0), Image.LANCZOS)
                self._img = ImageTk.PhotoImage(img)
                c.create_image(x0, y0, image=self._img, anchor="nw")
                return
            except Exception:
                pass
        c.create_text((x0+x1)//2, (y0+y1)//2,
                      text="Artwork", fill="#444",
                      font=(self.FF, self.FS_SM))

    def _wrap(self, text: str, x: int, y: int, max_w: int,
              font: tuple, color: str, y_max: int) -> int:
        c      = self.canvas
        line_h = font[1] + 5
        words  = text.split()
        line   = ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) * font[1] * 0.55 > max_w and line:
                if y + line_h > y_max:
                    return y
                c.create_text(x, y, text=line, anchor="nw",
                              font=font, fill=color)
                y   += line_h
                line = word
            else:
                line = test
        if line and y + line_h <= y_max:
            c.create_text(x, y, text=line, anchor="nw",
                          font=font, fill=color)
            y += line_h
        return y

    # ── Spell renderer ────────────────────────────────────────────────────────

    def _render_spell(self, card: dict) -> None:
        elem  = card.get("element", "Fire")
        color = ELEMENT_COLORS.get(elem, "#555")
        self._bg(color)
        self._border()
        self._name(card.get("name", ""))
        self._draw_element_icon(elem)
        self._draw_artwork_strip(card)
        self._draw_blocks(card)

    def _draw_element_icon(self, element: str) -> None:
        c  = self.canvas
        cx = self.W - self.AW // 2 - 4
        cy = 26
        color = ELEMENT_COLORS.get(element, "#555")
        icon  = ELEMENT_ICONS.get(element, "?")
        c.create_oval(cx-22, cy-22, cx+22, cy+22,
                      fill=color, outline="gold", width=2)
        c.create_text(cx, cy, text=icon, font=("Arial", 16))

    def _draw_artwork_strip(self, card: dict) -> None:
        c  = self.canvas
        x0 = self.W - self.AW - 4
        y0 = 54
        y1 = self.H - 6
        c.create_rectangle(x0, y0, self.W-6, y1, fill="#111", outline="#444")
        symbols = []
        for blk in card.get("blocks", []):
            symbols.append(BOX_SYMBOLS.get(blk["type"], "?"))
            for ab in blk.get("abilities", []):
                if ab.get("condition_id"):
                    symbols.append(COND_SYMBOL)
                symbols.append(TYPE_SYMBOLS.get(ab.get("ability_type", ""), "·"))
                for _ in ab.get("costs",   []): symbols.append(COST_SYMBOL)
                for _ in ab.get("effects", []): symbols.append(EFFECT_SYMBOL)
        step = 22
        y    = y1 - 14
        for sym in reversed(symbols):
            if y < y0 + 10:
                break
            c.create_text(x0 + self.AW//2, y, text=sym,
                          font=("Arial", 14), fill="#cccccc", anchor="center")
            y -= step

    def _draw_blocks(self, card: dict) -> None:
        c      = self.canvas
        blocks = card.get("blocks", [])
        if not blocks:
            c.create_text((self.W-self.AW)//2, self.H//2,
                          text="No blocks", fill="#555",
                          font=(self.FF, 14))
            return
        TOP     = 52
        BOTTOM  = self.H - 6
        block_h = (BOTTOM - TOP) // len(blocks)
        CD      = get_content_data()
        FN      = (self.FF, self.FS)
        FB      = (self.FF, self.FS, "bold")

        for i, blk in enumerate(blocks):
            y0    = TOP + i * block_h
            y1    = y0 + block_h
            btype = blk["type"]
            col   = BOX_COLORS.get(btype, "#333")
            c.create_rectangle(6, y0, self.W-self.AW-10, y1,
                               fill=col, outline="#888", width=1, stipple="gray50")
            c.create_text(10, y0+4, text=f"[{btype}]", anchor="nw",
                          font=(self.FF, 10, "bold"), fill="white")
            iy = y0 + 24
            for ab in blk.get("abilities", []):
                iy = self._draw_ability(ab, iy, y1-4, CD, FN, FB)
                if iy >= y1:
                    break

    def _draw_ability(self, ab, y, y_max, CD, FN, FB) -> int:
        c     = self.canvas
        x     = 10
        max_w = self.W - self.AW - 28
        lh    = self.FS + 6

        # ── Build header ──────────────────────────────────────────────────────
        trigger_text = ""
        if ab.get("trigger_id"):
            trig = CD.get("trigger", ab["trigger_id"])
            if trig:
                t = trig.get("content_text") or trig.get("effect_text", "")
                for k, v in ab.get("trigger_vals", {}).items():
                    t = t.replace(f"{{{k}}}", str(v))
                trigger_text = t

        cond_text = ""
        if ab.get("condition_id"):
            cond = CD.get("condition", ab["condition_id"])
            if cond:
                t = cond.get("content_text") or cond.get("effect_text", "")
                for k, v in ab.get("condition_vals", {}).items():
                    t = t.replace(f"{{{k}}}", str(v))
                cond_text = t

        if trigger_text and cond_text:
            prefix = f"If {trigger_text} and you have {cond_text}"
        elif trigger_text:
            prefix = f"If {trigger_text}"
        elif cond_text:
            prefix = f"If you have {cond_text}"
        else:
            prefix = ""

        costs_text = []
        for ci in ab.get("costs", []):
            co = CD.get("cost", ci["cost_id"])
            if co:
                t = co.get("content_text") or co.get("effect_text", "")
                for k, v in ci.get("vals", {}).items():
                    t = t.replace(f"{{{k}}}", str(v))
                costs_text.append(t)
        cost_str = ", ".join(costs_text)

        effects    = ab.get("effects", [])
        choose_n   = ab.get("choose_n")
        choose_rep = ab.get("choose_repeat", False)
        n_eff      = len(effects) + len(ab.get("continuouses", []))
        choose_part = ""
        if choose_n and choose_n < n_eff:
            choose_part = f" - Choose {choose_n}"
            if choose_rep:
                choose_part += ", same multiple times"

        if prefix:
            header = f"{prefix}; {cost_str}{choose_part}:" if cost_str else f"{prefix}{choose_part}:"
        else:
            header = f"{cost_str}{choose_part}:" if cost_str else ""

        if header and y + lh <= y_max:
            y = self._wrap(header, x, y, max_w, FB, "#aaddff", y_max)

        # ── Effects as bullets ────────────────────────────────────────────────
        eff_data = []
        for ei in effects:
            eff = CD.get("effect", ei.get("effect_id", ""))
            if not eff:
                continue
            ct = eff.get("content_text") or eff.get("effect_text", "")
            for k, v in ei.get("vals", {}).items():
                ct = ct.replace(f"{{{k}}}", str(v))
            eff_data.append([eff, ei, ct])

        chars_per_line = max(1, int(max_w / max(1, FN[1] * 0.6)))

        def _est_lines(text: str) -> int:
            if not text:
                return 1
            import math
            return max(1, math.ceil(sum(len(w)+1 for w in text.split()) / chars_per_line))

        avail_lines = max(1, (y_max - 4 - y) // lh)
        total_lines = sum(_est_lines(f"• {row[2]}") for row in eff_data)

        if total_lines > avail_lines:
            sortable = sorted(range(len(eff_data)),
                              key=lambda i: float(eff_data[i][0].get("complexity_base", 1.0)),
                              reverse=True)
            for i in sortable:
                eff, ei, _ = eff_data[i]
                rt = eff.get("reminder_text", "")
                if rt:
                    for k, v in ei.get("vals", {}).items():
                        rt = rt.replace(f"{{{k}}}", str(v))
                    eff_data[i][2] = rt
                total_lines = sum(_est_lines(f"• {row[2]}") for row in eff_data)
                if total_lines <= avail_lines:
                    break

        for _, _, etxt in eff_data:
            if etxt and y + lh <= y_max:
                y = self._wrap(f"• {etxt}", x + 6, y, max_w - 6, FN, "white", y_max)

        return y + 4

    # ── Prowess renderer ──────────────────────────────────────────────────────

    def _render_prowess(self, card: dict) -> None:
        self._bg("#2a1a3a")
        self._border()
        self._name(card.get("name", ""))
        # No artwork strip, blocks fill full width
        self._draw_blocks_fullwidth(card)

    def _draw_blocks_fullwidth(self, card: dict) -> None:
        c      = self.canvas
        blocks = card.get("blocks", [])
        if not blocks:
            c.create_text(self.W//2, self.H//2, text="No blocks",
                          fill="#555", font=(self.FF, 14))
            return
        TOP     = 52
        BOTTOM  = self.H - 6
        block_h = (BOTTOM - TOP) // len(blocks)
        CD      = get_content_data()
        FN      = (self.FF, self.FS)
        FB      = (self.FF, self.FS, "bold")
        for i, blk in enumerate(blocks):
            y0    = TOP + i * block_h
            y1    = y0 + block_h
            btype = blk["type"]
            col   = BOX_COLORS.get(btype, "#333")
            c.create_rectangle(6, y0, self.W-8, y1,
                               fill=col, outline="#888", width=1, stipple="gray50")
            c.create_text(10, y0+4, text=f"[{btype}]", anchor="nw",
                          font=(self.FF, 10, "bold"), fill="white")
            iy = y0 + 24
            for ab in blk.get("abilities", []):
                iy = self._draw_ability(ab, iy, y1-4, CD, FN, FB)
                if iy >= y1:
                    break

    # ── Loot renderer ─────────────────────────────────────────────────────────

    def _render_loot(self, card: dict) -> None:
        self._bg("#1a1a2a")
        self._border()

        c   = self.canvas
        PAD = 8
        W   = self.W

        # Name (top)
        self._name(card.get("name", ""), x=PAD, y=PAD)

        # Element source icons (top-left, row)
        srcs = card.get("element_sources", [])
        ix   = PAD
        for el in srcs[:3]:
            col  = ELEMENT_COLORS.get(el, "#555")
            icon = ELEMENT_ICONS.get(el, "?")
            c.create_oval(ix, 32, ix+20, 52, fill=col, outline="gold", width=1)
            c.create_text(ix+10, 42, text=icon, font=("Arial", 10))
            ix += 26

        # Artwork
        ART_Y0 = 58
        ART_Y1 = ART_Y0 + 200
        self._artwork_box(card.get("artwork", ""), PAD, ART_Y0, W-PAD, ART_Y1)

        # Object type + Material tags
        y = ART_Y1 + 6
        tags = card.get("object_type", []) + card.get("materials", [])
        tag_x = PAD
        for tag in tags:
            tw = len(tag) * 7 + 10
            c.create_rectangle(tag_x, y, tag_x+tw, y+18,
                               fill="#2a3a2a", outline="#aaffaa")
            c.create_text(tag_x+tw//2, y+9, text=tag,
                          fill="#aaffaa", font=("Arial", 9))
            tag_x += tw + 4
            if tag_x > W - 40:
                tag_x = PAD
                y += 22
        y += 26

        # Effect text
        eff = card.get("effect_text", "")
        if eff:
            c.create_rectangle(PAD, y, W-PAD, y+90,
                               fill="#111", outline="#555")
            self._wrap(eff, PAD+4, y+4, W-PAD*2-8,
                       (self.FF, self.FS_SM), "white", y+88)
            y += 96

        # Value badge (bottom right)
        val = card.get("value", 0)
        c.create_rectangle(W-60, self.H-34, W-PAD, self.H-PAD,
                           fill="#2a2200", outline="gold", width=2)
        c.create_text(W-32, self.H-18, text=f"⚙ {val}",
                      fill="gold", font=(self.FF, 12, "bold"))

    # ── Equipment renderer ────────────────────────────────────────────────────

    def _render_equipment(self, card: dict) -> None:
        self._bg("#1a1a2a")
        self._border()

        c   = self.canvas
        PAD = 8
        W   = self.W
        MID = W // 2

        self._name(card.get("name", ""), x=PAD, y=PAD)

        # Element sources
        srcs = card.get("element_sources", [])
        ix   = PAD
        for el in srcs[:3]:
            col  = ELEMENT_COLORS.get(el, "#555")
            icon = ELEMENT_ICONS.get(el, "?")
            c.create_oval(ix, 32, ix+20, 52, fill=col, outline="gold", width=1)
            c.create_text(ix+10, 42, text=icon, font=("Arial", 10))
            ix += 26

        ART_Y0 = 58
        ART_Y1 = ART_Y0 + 180
        self._artwork_box(card.get("artwork", ""), PAD, ART_Y0, W-PAD, ART_Y1)

        # Tags
        y = ART_Y1 + 6
        tags = card.get("object_type", []) + card.get("materials", [])
        tag_x = PAD
        for tag in tags:
            tw = len(tag) * 7 + 10
            c.create_rectangle(tag_x, y, tag_x+tw, y+18,
                               fill="#2a3a2a", outline="#aaffaa")
            c.create_text(tag_x+tw//2, y+9, text=tag,
                          fill="#aaffaa", font=("Arial", 9))
            tag_x += tw + 4
        y += 26

        BOX_Y0 = y
        BOX_Y1 = self.H - 34

        # Left half – effect
        c.create_rectangle(PAD, BOX_Y0, MID-2, BOX_Y1,
                           fill="#111", outline="#555")
        c.create_text(PAD+4, BOX_Y0+4, text="Effekt", anchor="nw",
                      fill="#888", font=(self.FF, 9, "bold"))
        eff = card.get("effect_text", "")
        if eff:
            self._wrap(eff, PAD+4, BOX_Y0+18,
                       MID-PAD*2, (self.FF, self.FS_SM), "white", BOX_Y1-4)

        # Right half – equip box
        c.create_rectangle(MID+2, BOX_Y0, W-PAD, BOX_Y1,
                           fill="#1a1100", outline="#997700")
        c.create_text(MID+6, BOX_Y0+4, text="Equip", anchor="nw",
                      fill="#cc9900", font=(self.FF, 9, "bold"))
        eq = card.get("equip_text", "")
        if eq:
            self._wrap(eq, MID+6, BOX_Y0+18,
                       W-MID-PAD*2, (self.FF, self.FS_SM), "#ffdd88", BOX_Y1-4)

        # Value
        val = card.get("value", 0)
        c.create_rectangle(W-60, self.H-34, W-PAD, self.H-PAD,
                           fill="#2a2200", outline="gold", width=2)
        c.create_text(W-32, self.H-18, text=f"⚙ {val}",
                      fill="gold", font=(self.FF, 12, "bold"))

    # ── Alchemy renderer ──────────────────────────────────────────────────────

    def _render_alchemy(self, card: dict) -> None:
        self._bg("#1a2a1a")
        self._border()

        c   = self.canvas
        PAD = 8
        W   = self.W

        self._name(card.get("name", ""), x=PAD, y=PAD, color="#aaffaa")

        # Artwork
        ART_Y0 = 36
        ART_Y1 = ART_Y0 + 160
        self._artwork_box(card.get("artwork", ""), PAD, ART_Y0, W-PAD, ART_Y1)

        # Ingredients list
        y = ART_Y1 + 6
        c.create_text(PAD, y, text="Zutaten:", anchor="nw",
                      fill="#888888", font=(self.FF, 10, "bold"))
        y += 18
        ings = card.get("ingredients", [])
        ing_x = PAD
        for ing in ings:
            tw = len(ing) * 7 + 10
            c.create_rectangle(ing_x, y, ing_x+tw, y+18,
                               fill="#1a3a1a", outline="#55aa55")
            c.create_text(ing_x+tw//2, y+9, text=ing,
                          fill="#aaffaa", font=("Arial", 9))
            ing_x += tw + 4
            if ing_x > W - 40:
                ing_x = PAD
                y += 22
        y += 28

        # Result
        res_id = card.get("result_content_id", "")
        if res_id:
            CD   = get_content_data()
            item = CD.get("effect", res_id)
            res_txt = ""
            if item:
                res_txt = item.get("content_text") or item.get("effect_text", "")
            c.create_rectangle(PAD, y, W-PAD, y+60,
                               fill="#2a1a00", outline="#cc8800")
            c.create_text(PAD+4, y+3, text="⚗ Ergebnis", anchor="nw",
                          fill="#cc8800", font=(self.FF, 9, "bold"))
            self._wrap(res_txt or res_id, PAD+4, y+18,
                       W-PAD*2, (self.FF, self.FS_SM), "#ffdd88", y+58)
            y += 66

        # On-field effect
        eff = card.get("on_field_effect", "")
        if eff:
            c.create_rectangle(PAD, y, W-PAD, self.H-PAD-6,
                               fill="#111", outline="#555")
            c.create_text(PAD+4, y+4, text="On-Field:", anchor="nw",
                          fill="#888", font=(self.FF, 9, "bold"))
            self._wrap(eff, PAD+4, y+20,
                       W-PAD*2, (self.FF, self.FS_SM), "white", self.H-PAD-10)
