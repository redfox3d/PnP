"""
renderer.py – CardRenderer: draws a complete card onto a tk.Canvas.
"""

import re
import tkinter as tk

from .constants import (
    CARD_W, CARD_H, ARTWORK_W,
    BLOCK_COLORS, BLOCK_SYMBOLS,
    ELEMENT_COLORS, ELEMENT_ICONS,
    TYPE_SYMBOLS, COND_SYMBOL, EFFECT_SYMBOL, COST_SYMBOL,
)
from .data import get_content_data, fill_placeholders

class CardRenderer:
    FONT_FAMILY = "Palatino Linotype"
    FONT_SIZE   = 13   # war 7

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self.W  = CARD_W
        self.H  = CARD_H
        self.AW = ARTWORK_W

    def render(self, card: dict) -> None:
        c = self.canvas
        c.delete("all")
        elem = card.get("element", "Fire")
        self._draw_background(elem)
        c.create_rectangle(2, 2, self.W - 2, self.H - 2, outline="black", width=3)
        c.create_text(14, 14, text=card.get("name", ""),
                      anchor="nw",
                      font=(self.FONT_FAMILY, 16, "bold"),
                      fill="white")
        self._draw_element_icon(elem)
        self._draw_artwork(card)
        self._draw_blocks(card)

    def _draw_background(self, element: str) -> None:
        c = self.canvas
        color = ELEMENT_COLORS.get(element, "#555555")
        c.create_rectangle(0, 0, self.W, self.H, fill="#1a1a1a", outline="")
        c.create_rectangle(0, 0, self.W, self.H, fill=color, outline="", stipple="gray25")

    def _draw_element_icon(self, element: str) -> None:
        c  = self.canvas
        cx = self.W - self.AW // 2 - 4
        cy = 26
        color = ELEMENT_COLORS.get(element, "#555555")
        icon  = ELEMENT_ICONS.get(element, "?")
        c.create_oval(cx - 22, cy - 22, cx + 22, cy + 22,
                      fill=color, outline="gold", width=2)
        c.create_text(cx, cy, text=icon, font=("Arial", 16))

    def _draw_artwork(self, card: dict) -> None:
        c  = self.canvas
        x0 = self.W - self.AW - 4
        y0 = 54
        y1 = self.H - 6

        c.create_rectangle(x0, y0, self.W - 6, y1, fill="#111111", outline="#444")

        symbols = []
        for blk in card.get("blocks", []):
            symbols.append(BLOCK_SYMBOLS.get(blk["type"], "?"))
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
            c.create_text(x0 + self.AW // 2, y, text=sym,
                          font=("Arial", 14), fill="#cccccc", anchor="center")
            y -= step

    def _draw_blocks(self, card: dict) -> None:
        c      = self.canvas
        blocks = card.get("blocks", [])

        if not blocks:
            c.create_text((self.W - self.AW) // 2, self.H // 2,
                          text="No blocks", fill="#555",
                          font=(self.FONT_FAMILY, 14))
            return

        TOP     = 52
        BOTTOM  = self.H - 6
        total_h = BOTTOM - TOP
        block_h = total_h // len(blocks)

        for i, blk in enumerate(blocks):
            y0    = TOP + i * block_h
            y1    = y0 + block_h
            btype = blk["type"]
            col   = BLOCK_COLORS.get(btype, "#333333")

            c.create_rectangle(6, y0, self.W - self.AW - 10, y1,
                               fill=col, outline="#888", width=1, stipple="gray50")
            c.create_text(10, y0 + 4,
                          text=f"[{btype}]",
                          anchor="nw",
                          font=(self.FONT_FAMILY, 10, "bold"),
                          fill="white")

            inner_y = y0 + 24
            for ab in blk.get("abilities", []):
                inner_y = self._draw_ability(ab, inner_y, y1 - 4)
                if inner_y >= y1:
                    break

    def _draw_ability(self, ab: dict, y_start: int, y_max: int) -> int:
        c      = self.canvas
        x      = 10
        max_w  = self.W - self.AW - 28
        FN     = (self.FONT_FAMILY, self.FONT_SIZE)
        FB     = (self.FONT_FAMILY, self.FONT_SIZE, "bold")
        line_h = self.FONT_SIZE + 6
        y      = y_start
        CD     = get_content_data()

        if ab.get("condition_id"):
            cond = CD.get("condition", ab["condition_id"])
            if cond:
                txt = fill_placeholders(cond.get("effect_text", ""), ab.get("condition_vals", {}))
                txt = re.sub(r"\\(\w+)", r"\1", txt)
                y = self._wrap(txt, x, y, max_w, FN, "#ffdd88", y_max)

        atype      = ab.get("ability_type", "Play")
        cost_parts = []
        for ci in ab.get("costs", []):
            co = CD.get("cost", ci["cost_id"])
            if co:
                ct = fill_placeholders(co.get("effect_text", ""), ci.get("vals", {}))
                ct = re.sub(r"\\(\w+)", r"\1", ct)
                cost_parts.append(ct)
        type_line = f"{atype}: {', '.join(cost_parts)}" if cost_parts else atype
        if y + line_h <= y_max:
            c.create_text(x, y, text=type_line, anchor="nw", font=FB, fill="#aaddff")
            y += line_h

        if ab.get("choose_n"):
            rep = " You can choose the same multiple times." if ab.get("choose_repeat") else ""
            y = self._wrap(f"Choose {ab['choose_n']}.{rep}",
                           x + 6, y, max_w - 6, FN, "#ffaaff", y_max)

        for ei in ab.get("effects", []):
            eff = CD.get("effect", ei["effect_id"])
            if eff:
                etxt = fill_placeholders(eff.get("effect_text", ""), ei.get("vals", {}))
                etxt = re.sub(r"\\(\w+)", r"\1", etxt)
                y = self._wrap(f"• {etxt}", x + 6, y, max_w - 6, FN, "white", y_max)

        return y + 4

    def _wrap(self, text: str, x: int, y: int,
              max_w: int, font: tuple, color: str, y_max: int) -> int:
        c      = self.canvas
        line_h = font[1] + 6
        words  = text.split()
        line   = ""

        for word in words:
            test = (line + " " + word).strip()
            if len(test) * font[1] * 0.55 > max_w and line:
                if y + line_h > y_max:
                    return y
                c.create_text(x, y, text=line, anchor="nw", font=font, fill=color)
                y   += line_h
                line = word
            else:
                line = test

        if line and y + line_h <= y_max:
            c.create_text(x, y, text=line, anchor="nw", font=font, fill=color)
            y += line_h

        return y