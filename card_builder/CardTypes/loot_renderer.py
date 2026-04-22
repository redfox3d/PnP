"""
loot_renderer.py – Renderer for Supplies and Equipment cards.
"""

import tkinter as tk

from card_builder.constants import (
    CARD_W, CARD_H, ELEMENT_COLORS, ELEMENT_ICONS,
    GENERIC_MANA_ICON, GENERIC_MANA_COLOR,
)

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False


class LootCardRenderer:
    FF     = "Palatino Linotype"
    FF_ALT = "Arial"
    PAD    = 10

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.W      = CARD_W
        self.H      = CARD_H
        self._img   = [None]

    def render(self, card: dict):
        c  = self.canvas
        ct = card.get("card_type", "Supplies")
        c.delete("all")

        if ct == "Equipment":
            self._render_equipment(card)
        else:
            self._render_loot(card)

    # ── Supplies renderer ─────────────────────────────────────────────────────

    def _render_loot(self, card: dict):
        c  = self.canvas
        P  = self.PAD
        W, H = self.W, self.H

        c.create_rectangle(0, 0, W, H, fill="#12121e", outline="")
        c.create_rectangle(2, 2, W-2, H-2, outline="#666", width=2)

        # Name
        c.create_text(P + 4, P + 4, text=card.get("name", ""),
                      anchor="nw", font=(self.FF, 14, "bold"), fill="white")

        # Element source circles (left stripe, vertical)
        srcs = card.get("element_sources", [])
        r    = 10
        ix   = P + r + 3
        iy   = 36 + r + 4
        for el in srcs[:3]:
            col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
            icon = ELEMENT_ICONS.get(el, "?")
            c.create_oval(ix-r, iy-r, ix+r, iy+r,
                          fill=col, outline="gold", width=1)
            c.create_text(ix, iy, text=icon,
                          font=("Arial", 10), anchor="center")
            iy += r * 2 + 4

        # Artwork
        art_x0 = P + (r * 2 + 6) if srcs else P
        art_y0 = 36
        art_y1 = H - 160
        self._draw_artwork(card, art_x0, art_y0, W - P, art_y1)

        # Tags (object_type + materials)
        y    = art_y1 + 6
        tags = card.get("object_type", []) + card.get("materials", [])
        tx   = P
        for tag in tags:
            tw = len(tag) * 7 + 10
            if tx + tw > W - P:
                tx = P; y += 22
            c.create_rectangle(tx, y, tx + tw, y + 18,
                               fill="#1a1a2a", outline="#6688aa")
            c.create_text(tx + tw // 2, y + 9, text=tag,
                          fill="#aaccff", font=("Arial", 8))
            tx += tw + 4
        if tags:
            y += 24
        else:
            y += 4

        BOX_BOTTOM = H - 44

        # Effect text box (skip if empty)
        effect_text = card.get("effect_text", "").strip()
        if effect_text:
            self._text_box(P, y, W - P, BOX_BOTTOM,
                           effect_text,
                           fill="#111", outline="#555",
                           color="white", header="Effekt")

        # Bottom stat bar: weight (left) | value (right)
        by = H - 36
        bh = 28
        # Weight
        wt = card.get("weight", 0)
        c.create_rectangle(P, by, P + 80, by + bh,
                           fill="#1a1a2a", outline="#446688", width=1)
        c.create_text(P + 4, by + bh // 2, anchor="w",
                      text=f"Weight: {wt}",
                      fill="#88aacc", font=(self.FF, 10))
        # Value
        val = card.get("value", 0)
        c.create_rectangle(W - P - 80, by, W - P, by + bh,
                           fill="#1a1500", outline="gold", width=1)
        c.create_text(W - P - 4, by + bh // 2, anchor="e",
                      text=f"Value: {val}",
                      fill="gold", font=(self.FF, 10))

    # ── Equipment renderer ────────────────────────────────────────────────────

    def _render_equipment(self, card: dict):
        c  = self.canvas
        P  = self.PAD
        W, H = self.W, self.H

        c.create_rectangle(0, 0, W, H, fill="#1a1a2a", outline="")
        c.create_rectangle(2, 2, W-2, H-2, outline="#888", width=2)

        # Name
        c.create_text(P, P, text=card.get("name", ""), anchor="nw",
                      font=(self.FF, 16, "bold"), fill="white")

        # Artwork
        AY0, AY1 = 36, 230
        self._draw_artwork(card, P, AY0, W - P, AY1)

        # Element source circles (left stripe over artwork)
        srcs = card.get("element_sources", [])
        r    = 10
        ix   = P + r + 3
        iy   = AY0 + r + 4
        for el in srcs[:3]:
            col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
            icon = ELEMENT_ICONS.get(el, GENERIC_MANA_ICON)
            c.create_oval(ix-r, iy-r, ix+r, iy+r,
                          fill=col, outline="gold", width=1)
            c.create_text(ix, iy, text=icon, font=("Arial", 10))
            iy += r * 2 + 4

        # Tags (object_type + materials)
        y    = AY1 + 6
        tags = card.get("object_type", []) + card.get("materials", [])
        tx   = P
        for tag in tags:
            tw = len(tag) * 7 + 10
            if tx + tw > W - P:
                tx = P; y += 22
            c.create_rectangle(tx, y, tx + tw, y + 18,
                               fill="#2a3a2a", outline="#aaffaa")
            c.create_text(tx + tw // 2, y + 9, text=tag,
                          fill="#aaffaa", font=("Arial", 9))
            tx += tw + 4
        y += 26

        BOX_BOTTOM = H - 44

        effect_text = card.get("effect_text", "").strip()
        equip_text  = card.get("equip_text", "").strip()
        equip_cost  = card.get("equip_cost_text", "").strip()

        has_effect = bool(effect_text)
        has_equip  = bool(equip_text)
        has_cost   = bool(equip_cost)

        equip_cost_h  = 36 if has_cost else 0
        equip_top     = y
        equip_box_bot = BOX_BOTTOM - equip_cost_h - (2 if has_cost else 0)

        if has_effect and (has_equip or has_cost):
            # Split: effect left | equip right
            MID = W // 2
            self._text_box(P, equip_top, MID - 2, BOX_BOTTOM,
                           effect_text,
                           fill="#111", outline="#555",
                           color="white", header="Effekt")
            if has_equip:
                self._text_box(MID + 2, equip_top, W - P, equip_box_bot,
                               equip_text,
                               fill="#1a1100", outline="#997700",
                               color="#ffdd88", header="Equip")
            if has_cost:
                c.create_rectangle(MID + 2, equip_box_bot + 2, W - P, BOX_BOTTOM,
                                   fill="#0d0a00", outline="#997700")
                c.create_text(MID + 6, equip_box_bot + 4, text="Cost:", anchor="nw",
                              fill="#997700", font=(self.FF, 8, "bold"))
                c.create_text(MID + 46,
                              (equip_box_bot + 2 + BOX_BOTTOM) // 2,
                              text=equip_cost,
                              anchor="w", fill="#ffdd88", font=(self.FF, 11))

        elif has_effect:
            # Full-width effect box
            self._text_box(P, equip_top, W - P, BOX_BOTTOM,
                           effect_text,
                           fill="#111", outline="#555",
                           color="white", header="Effekt")

        elif has_equip or has_cost:
            # Full-width equip (no effect)
            if has_equip:
                self._text_box(P, equip_top, W - P, equip_box_bot,
                               equip_text,
                               fill="#1a1100", outline="#997700",
                               color="#ffdd88", header="Equip")
            if has_cost:
                c.create_rectangle(P, equip_box_bot + 2, W - P, BOX_BOTTOM,
                                   fill="#0d0a00", outline="#997700")
                c.create_text(P + 4, equip_box_bot + 4, text="Cost:", anchor="nw",
                              fill="#997700", font=(self.FF, 8, "bold"))
                c.create_text(P + 44,
                              (equip_box_bot + 2 + BOX_BOTTOM) // 2,
                              text=equip_cost,
                              anchor="w", fill="#ffdd88", font=(self.FF, 11))

        # Bottom stat bar: weight (left) | value (right)
        by = H - 36
        bh = 28
        wt = card.get("weight", 0)
        c.create_rectangle(P, by, P + 80, by + bh,
                           fill="#1a1a2a", outline="#446688", width=1)
        c.create_text(P + 4, by + bh // 2, anchor="w",
                      text=f"Weight: {wt}",
                      fill="#88aacc", font=(self.FF, 10))
        val = card.get("value", 0)
        c.create_rectangle(W - P - 80, by, W - P, by + bh,
                           fill="#1a1500", outline="gold", width=1)
        c.create_text(W - P - 4, by + bh // 2, anchor="e",
                      text=f"Value: {val}",
                      fill="gold", font=(self.FF, 10))

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _draw_artwork(self, card, x0, y0, x1, y1):
        import os
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill="#0d0d18", outline="#333")

        path = card.get("artwork", "")
        if path and _PIL and os.path.exists(path):
            try:
                img    = Image.open(path)
                w, h   = x1 - x0, y1 - y0
                iw, ih = img.size
                s      = max(w / iw, h / ih)
                nw, nh = int(iw * s), int(ih * s)
                img    = img.resize((nw, nh), Image.LANCZOS)
                lf, tp = (nw - w) // 2, (nh - h) // 2
                img    = img.crop((lf, tp, lf + w, tp + h))
                self._img[0] = ImageTk.PhotoImage(img)
                c.create_image(x0, y0, image=self._img[0], anchor="nw")
            except Exception:
                c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text="Artwork",
                              fill="#444", font=(self.FF, 11))
        else:
            c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text="Artwork",
                          fill="#333", font=(self.FF, 11))

    def _text_box(self, x0, y0, x1, y1, text, fill, outline,
                  color="white", header=None):
        c = self.canvas
        P = 4
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline)
        ty = y0 + P
        if header:
            c.create_text(x0 + P, ty, text=header, anchor="nw",
                          fill="#888", font=(self.FF, 9, "bold"))
            ty += 16
        if not text:
            return
        font   = (self.FF, 11)
        line_h = 16
        max_w  = x1 - x0 - P * 2
        lines  = self._wrap(text, max_w)
        total  = len(lines) * line_h
        avail  = y1 - ty - P
        sy     = ty + max(0, (avail - total) // 2)
        for line in lines:
            if sy + line_h > y1 - P:
                break
            c.create_text(x0 + P, sy, text=line, anchor="nw",
                          font=font, fill=color)
            sy += line_h

    def _wrap(self, text: str, max_w: int) -> list:
        words, lines, line = text.split(), [], ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) * 11 * 0.55 > max_w and line:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        return lines
