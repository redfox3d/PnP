"""
loot_renderer.py – Renderer for Supplies and Equipment cards.

Block-based layout:
    Materials sigil (always shown, top of content area).
    Equipped sigil — when present, drawn in a right-side box.
    Every other block — stacked vertically in the left column.
The widths and heights of left/right columns adjust to the text content
("the side with more shrinks the other a bit").
"""

import tkinter as tk

from card_builder.constants import (
    CARD_W, CARD_H, ELEMENT_COLORS, ELEMENT_ICONS,
    GENERIC_MANA_ICON, GENERIC_MANA_COLOR,
    sigil_label,
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
        elif ct in ("Tokens", "Creatures", "StatusEffects"):
            self._render_world(card, ct)
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

        # Object-Type tags (Materials get their own sigil block below)
        y    = art_y1 + 6
        otypes = card.get("object_type", [])
        if otypes:
            tx = P
            for tag in otypes:
                tw = len(tag) * 7 + 10
                if tx + tw > W - P:
                    tx = P; y += 22
                c.create_rectangle(tx, y, tx + tw, y + 18,
                                   fill="#1a1a2a", outline="#6688aa")
                c.create_text(tx + tw // 2, y + 9, text=tag,
                              fill="#aaccff", font=("Arial", 8))
                tx += tw + 4
            y += 24

        # Materials sigil — always shown on Items
        materials = card.get("materials", [])
        mat_h = 24
        c.create_rectangle(P, y, W - P, y + mat_h,
                           fill="#241a14", outline="#a87844", width=1)
        c.create_text(P + 6, y + 4, text="◆ Materials", anchor="nw",
                      fill="#ffd9a3", font=(self.FF, 9, "bold"))
        if materials:
            mtx = P + 96
            for m in materials:
                mw = len(m) * 7 + 10
                if mtx + mw > W - P - 4:
                    break
                c.create_rectangle(mtx, y + 5, mtx + mw, y + mat_h - 5,
                                   fill="#3a2a1a", outline="#a87844")
                c.create_text(mtx + mw // 2, y + mat_h // 2,
                              text=m, fill="#ffd9a3", font=("Arial", 9))
                mtx += mw + 4
        else:
            c.create_text(P + 96, y + mat_h // 2,
                          text="(keine zugewiesen)",
                          anchor="w", fill="#886644",
                          font=("Arial", 9, "italic"))
        y += mat_h + 4

        BOX_BOTTOM = H - 44
        self._draw_item_blocks(card, P, y, W - P, BOX_BOTTOM)

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

        # Object-Type tags
        y    = AY1 + 6
        otypes = card.get("object_type", [])
        if otypes:
            tx = P
            for tag in otypes:
                tw = len(tag) * 7 + 10
                if tx + tw > W - P:
                    tx = P; y += 22
                c.create_rectangle(tx, y, tx + tw, y + 18,
                                   fill="#2a3a2a", outline="#aaffaa")
                c.create_text(tx + tw // 2, y + 9, text=tag,
                              fill="#aaffaa", font=("Arial", 9))
                tx += tw + 4
            y += 26

        # ── Materials sigil — always present on Items ────────────────────────
        # Label header + the list of materials. Mirrors how Spell-card
        # sigil blocks render so the user can read it as "Materials sigil".
        materials = card.get("materials", [])
        mat_h = 28 if materials else 24
        mat_box_top = y
        c.create_rectangle(P, mat_box_top, W - P, mat_box_top + mat_h,
                           fill="#241a14", outline="#a87844", width=1)
        c.create_text(P + 6, mat_box_top + 4,
                      text="◆ Materials", anchor="nw",
                      fill="#ffd9a3", font=(self.FF, 9, "bold"))
        if materials:
            mtx = P + 96
            for m in materials:
                mw = len(m) * 7 + 10
                if mtx + mw > W - P - 4:
                    break  # overflow → trim silently for now
                c.create_rectangle(mtx, mat_box_top + 5,
                                   mtx + mw, mat_box_top + mat_h - 5,
                                   fill="#3a2a1a", outline="#a87844")
                c.create_text(mtx + mw // 2, mat_box_top + mat_h // 2,
                              text=m, fill="#ffd9a3", font=("Arial", 9))
                mtx += mw + 4
        else:
            c.create_text(P + 96, mat_box_top + mat_h // 2,
                          text="(keine zugewiesen)",
                          anchor="w", fill="#886644",
                          font=("Arial", 9, "italic"))
        y = mat_box_top + mat_h + 4

        BOX_BOTTOM = H - 44
        self._draw_item_blocks(card, P, y, W - P, BOX_BOTTOM)

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

    # ── World renderer (Tokens / Creatures / StatusEffects) ─────────────────

    _WORLD_THEME = {
        "Tokens":         {"bg": "#0f1a2a", "border": "#5588cc",
                            "title": "#cce4ff"},
        "Creatures":      {"bg": "#1f0f0f", "border": "#cc5555",
                            "title": "#ffcccc"},
        "StatusEffects":  {"bg": "#1a1a1f", "border": "#cc88cc",
                            "title": "#ffccff"},
    }

    # Per-subtype palette overrides for StatusEffects.
    _STATUS_SUBTHEMES = {
        "Condition":  {"bg": "#1a1a1f", "border": "#aaaaaa",
                        "title": "#dddddd"},
        "Curse":      {"bg": "#1f0a1a", "border": "#cc44aa",
                        "title": "#ffaadd"},
        "Blessing":   {"bg": "#1a1f0f", "border": "#cccc44",
                        "title": "#ffeeaa"},
    }

    def _render_world(self, card: dict, card_type: str):
        c    = self.canvas
        P    = self.PAD
        W, H = self.W, self.H
        theme = self._WORLD_THEME.get(card_type, self._WORLD_THEME["Tokens"])
        # StatusEffect: tint by subtype (Condition / Curse / Blessing)
        if card_type == "StatusEffects":
            sub = card.get("subtype", "Condition")
            theme = self._STATUS_SUBTHEMES.get(sub, theme)

        c.create_rectangle(0, 0, W, H, fill=theme["bg"], outline="")
        c.create_rectangle(2, 2, W - 2, H - 2,
                           outline=theme["border"], width=2)

        # Name + type badge — for StatusEffects show the subtype
        c.create_text(P, P, text=card.get("name", ""), anchor="nw",
                      font=(self.FF, 16, "bold"), fill=theme["title"])
        if card_type == "StatusEffects":
            badge = card.get("subtype", "Status")
        else:
            badge = {"Tokens": "Token",
                     "Creatures": "Creature"}.get(card_type, card_type)
        c.create_text(W - P, P + 2, text=f"[{badge}]", anchor="ne",
                      font=(self.FF, 10, "italic"), fill=theme["title"])

        # Element source circles
        srcs = card.get("element_sources", [])
        r    = 9
        ix   = P + r + 3
        iy   = 36 + r + 4
        for el in srcs[:3]:
            col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
            icon = ELEMENT_ICONS.get(el, "?")
            c.create_oval(ix - r, iy - r, ix + r, iy + r,
                          fill=col, outline="gold", width=1)
            c.create_text(ix, iy, text=icon, font=("Arial", 9),
                          anchor="center")
            iy += r * 2 + 4

        # Artwork (smaller than Items). For Creatures we reserve a strip
        # on the right of the artwork for strong/weak element indicators.
        AY0, AY1 = 36, 200
        AX0 = P + (r * 2 + 6 if srcs else 0)
        AX1 = W - P
        if card_type == "Creatures" and (
                card.get("strong_against") or card.get("weak_against")):
            AX1 = W - P - 36
            self._draw_creature_affinities(card, W - P - 30, AY0,
                                              W - P, AY1, theme)
        self._draw_artwork(card, AX0, AY0, AX1, AY1)

        # Tags row
        y = AY1 + 6
        tags = card.get("tags", [])
        if tags:
            tx = P
            for t in tags:
                tw = len(t) * 7 + 10
                if tx + tw > W - P:
                    tx = P; y += 22
                c.create_rectangle(tx, y, tx + tw, y + 18,
                                   fill="#2a2a3a", outline=theme["border"])
                c.create_text(tx + tw // 2, y + 9, text=t,
                              fill=theme["title"], font=("Arial", 9))
                tx += tw + 4
            y += 24

        # Type-specific stat strip
        STAT_H = 28
        sy = y
        if card_type == "Creatures":
            self._draw_world_stat(P,            sy, P + 70,        sy + STAT_H,
                                    f"HP: {card.get('hp', 0)}",
                                    theme, ratio=0.0)
            self._draw_world_stat(W - P - 70,   sy, W - P,         sy + STAT_H,
                                    f"Move: {card.get('move', 0)}",
                                    theme, ratio=1.0)
            y += STAT_H + 4
        elif card_type == "StatusEffects":
            dur = card.get("duration", 1)
            label = "Permanent" if dur == 0 else f"{dur} Runden"
            self._draw_world_stat(P, sy, W - P, sy + STAT_H,
                                    f"Dauer: {label}",
                                    theme, ratio=0.5)
            y += STAT_H + 4

        # Block area
        self._draw_item_blocks(card, P, y, W - P, H - 12)

    def _draw_creature_affinities(self, card: dict, x0: int, y0: int,
                                     x1: int, y1: int, theme: dict):
        """Right-side strip listing element strengths (▲) and weaknesses (▼)."""
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1,
                           fill="#0a0a0a", outline=theme["border"], width=1)
        ix = (x0 + x1) // 2
        iy = y0 + 12
        r = 9
        # Strong (▲ green badge)
        for el in card.get("strong_against", []):
            if iy + r * 2 + 4 > y1: break
            col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
            icon = ELEMENT_ICONS.get(el, "?")
            c.create_oval(ix - r, iy, ix + r, iy + r * 2,
                          fill=col, outline="#88ff88", width=2)
            c.create_text(ix, iy + r, text=icon,
                          font=("Arial", 9), anchor="center")
            c.create_text(ix + r + 2, iy + r, text="▲",
                          font=("Arial", 8, "bold"), fill="#88ff88",
                          anchor="w")
            iy += r * 2 + 4
        # Weak (▼ red badge)
        for el in card.get("weak_against", []):
            if iy + r * 2 + 4 > y1: break
            col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
            icon = ELEMENT_ICONS.get(el, "?")
            c.create_oval(ix - r, iy, ix + r, iy + r * 2,
                          fill=col, outline="#ff8888", width=2)
            c.create_text(ix, iy + r, text=icon,
                          font=("Arial", 9), anchor="center")
            c.create_text(ix + r + 2, iy + r, text="▼",
                          font=("Arial", 8, "bold"), fill="#ff8888",
                          anchor="w")
            iy += r * 2 + 4

    def _draw_world_stat(self, x0, y0, x1, y1, text, theme,
                          ratio: float = 0.0):
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill="#000",
                           outline=theme["border"], width=1)
        anchor = "w" if ratio < 0.4 else "e" if ratio > 0.6 else "center"
        tx = x0 + 6 if anchor == "w" else (x1 - 6 if anchor == "e"
                                              else (x0 + x1) // 2)
        c.create_text(tx, (y0 + y1) // 2, text=text,
                      anchor=anchor, fill=theme["title"],
                      font=(self.FF, 10, "bold"))

    # ── Shared helpers ────────────────────────────────────────────────────────

    # ── Block layout ──────────────────────────────────────────────────────────

    def _draw_item_blocks(self, card: dict, x0: int, y0: int,
                           x1: int, y1: int) -> None:
        """Draw all blocks in ``card.blocks`` between (x0..x1) × (y0..y1).

        Equipped sigils go on the right; everything else stacks on the left.
        Column widths shrink/grow proportionally to the text content of
        each side. ``Materials`` is the only sigil never drawn here — it
        lives above this section.
        """
        c = self.canvas
        blocks = card.get("blocks", []) or []
        ct = card.get("card_type", "")

        # Filter: ignore Materials (already drawn) and any malformed blocks
        right_blocks = [b for b in blocks if b.get("type") == "Equipped"]
        left_blocks  = [b for b in blocks
                        if b.get("type") not in ("Equipped", "Materials")]

        if not right_blocks and not left_blocks:
            return  # nothing to draw

        total_w = max(40, x1 - x0)

        # Approximate text "weight" per side (chars + small base for header)
        def _block_weight(blk: dict) -> int:
            ab = (blk.get("abilities") or [{}])[0]
            txt = (ab.get("raw_text") or "") + " " + (ab.get("raw_cost_text") or "")
            return 30 + len(txt)

        if right_blocks and left_blocks:
            l_w = sum(_block_weight(b) for b in left_blocks)
            r_w = sum(_block_weight(b) for b in right_blocks)
            tot = max(l_w + r_w, 1)
            # Clamp split to [30%, 70%] so neither side disappears.
            ratio = max(0.3, min(0.7, l_w / tot))
            mid_x = x0 + int(total_w * ratio)
            self._draw_block_column(left_blocks, ct, x0, y0, mid_x - 2, y1,
                                     side="left")
            self._draw_block_column(right_blocks, ct, mid_x + 2, y0, x1, y1,
                                     side="right")
        elif right_blocks:
            self._draw_block_column(right_blocks, ct, x0, y0, x1, y1,
                                     side="right")
        else:
            self._draw_block_column(left_blocks, ct, x0, y0, x1, y1,
                                     side="left")

    # ── helpers used by _draw_item_blocks ─────────────────────────────────────

    _SIDE_STYLE = {
        "left":  {"fill": "#111",    "outline": "#555",    "color": "white"},
        "right": {"fill": "#1a1100", "outline": "#997700", "color": "#ffdd88"},
    }

    def _draw_block_column(self, blocks: list, card_type: str,
                             x0: int, y0: int, x1: int, y1: int,
                             side: str = "left") -> None:
        """Stack ``blocks`` vertically inside the given rectangle.

        Each block's height is proportional to its text content but
        capped to fit inside the rectangle. The header line shows the
        sigil label (per ``card_type``) so e.g. Play renders as "Use".
        """
        if not blocks:
            return
        style = self._SIDE_STYLE[side]
        weights = []
        for b in blocks:
            ab  = (b.get("abilities") or [{}])[0]
            txt = (ab.get("raw_text") or "") + " " + (ab.get("raw_cost_text") or "")
            # Attack blocks are taller because each attack is its own line
            if b.get("type") == "Attack":
                n_atks = len(b.get("abilities") or [])
                weights.append(40 + 28 * max(1, n_atks))
            else:
                weights.append(40 + len(txt))
        total_w = sum(weights)
        avail   = max(20, y1 - y0)
        cur_y   = y0

        for blk, w in zip(blocks, weights):
            h = max(36, int(avail * w / total_w))
            box_bot = min(cur_y + h, y1)

            # Attack: special multi-row rendering
            if blk.get("type") == "Attack":
                self._draw_attack_block(blk, x0, cur_y, x1, box_bot, style)
                cur_y = box_bot + 2
                continue

            ab  = (blk.get("abilities") or [{}])[0]
            txt = (ab.get("raw_text") or "").strip()
            cost = (ab.get("raw_cost_text") or "").strip()

            # Equipped + cost: split off bottom slice for cost line
            cost_strip = 0
            if cost:
                cost_strip = 24
            text_bot = box_bot - cost_strip - (2 if cost else 0)

            self._text_box(x0, cur_y, x1, text_bot,
                            txt or "(leer)",
                            fill=style["fill"], outline=style["outline"],
                            color=style["color"],
                            header=sigil_label(blk.get("type", ""), card_type))
            if cost:
                self.canvas.create_rectangle(x0, text_bot + 2, x1, box_bot,
                                              fill="#0d0a00",
                                              outline=style["outline"])
                self.canvas.create_text(x0 + 4, text_bot + 4,
                                          text="Cost:", anchor="nw",
                                          fill=style["outline"],
                                          font=(self.FF, 8, "bold"))
                self.canvas.create_text(x0 + 44,
                                          (text_bot + 2 + box_bot) // 2,
                                          text=cost, anchor="w",
                                          fill=style["color"],
                                          font=(self.FF, 11))
            cur_y = box_bot + 2

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

    def _draw_attack_block(self, blk: dict, x0: int, y0: int,
                            x1: int, y1: int, style: dict) -> None:
        """Custom render for the Attack sigil — list of (lo–hi) rolls
        with their own text, up to 4 entries."""
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1,
                           fill="#1a0a0a", outline="#cc4444", width=1)
        c.create_text(x0 + 6, y0 + 4, text="⚔ Attack",
                      anchor="nw", fill="#ffaaaa",
                      font=(self.FF, 9, "bold"))

        atks = blk.get("abilities") or []
        cur_y = y0 + 22
        row_h = max(20, (y1 - cur_y) // max(1, len(atks)))
        for ab in atks:
            if cur_y + row_h > y1:
                break
            lo = ab.get("lower", "?")
            hi = ab.get("upper", "?")
            txt = (ab.get("raw_text") or "").strip()

            # Range badge on the left
            badge_w = 60
            c.create_rectangle(x0 + 6, cur_y, x0 + 6 + badge_w,
                                cur_y + row_h - 2,
                                fill="#3a1a1a", outline="#cc4444")
            c.create_text(x0 + 6 + badge_w // 2, cur_y + row_h // 2,
                            text=f"{lo}–{hi}", fill="#ffdddd",
                            font=(self.FF, 11, "bold"))
            # Attack text
            c.create_text(x0 + 6 + badge_w + 8, cur_y + row_h // 2,
                            text=txt or "(leer)", anchor="w",
                            fill="white", font=(self.FF, 9))
            cur_y += row_h

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
