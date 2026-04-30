"""
spell_card.py – Editor and renderer for Spells and Prowess cards.

Spells:  element, artwork, mana cost symbols left of content, boxes
Prowess: no element, no artwork, boxes full width
"""

import tkinter as tk
from tkinter import ttk

from card_builder.CardTypes.base_card import BaseCardEditor, _render_content
from card_builder.constants import (
    CARD_W, CARD_H, ARTWORK_W,
    BOX_TYPES, BOX_COLORS, BOX_SYMBOLS,
    ELEMENT_COLORS, ELEMENT_ICONS,
    TYPE_SYMBOLS, COND_SYMBOL, EFFECT_SYMBOL, COST_SYMBOL,
    MANA_COST_ID, GENERIC_MANA_ICON, GENERIC_MANA_COLOR,
    card_type_label, sigil_label,
)
from card_builder.models import empty_box, migrate_ability
from card_builder.widgets import BoxEditor

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False

# Width reserved for mana symbols on the left of the content area
MANA_STRIP_W   = 28
# Width reserved for the action (Manual trigger) symbol, placed right of mana
ACTION_STRIP_W = 26

MANUAL_TRIGGER_ID       = "Manual_Trigger"
MANUAL_TRIGGER_HALF_ID  = "Manual_Trigger_Half"
MANUAL_TRIGGER_THIRD_ID = "Manual_Trigger_Third"
MANUAL_TRIGGER_IDS = (MANUAL_TRIGGER_ID, MANUAL_TRIGGER_HALF_ID,
                      MANUAL_TRIGGER_THIRD_ID)


# ── Editor ────────────────────────────────────────────────────────────────────

class SpellCardEditor(BaseCardEditor):

    def _build_type_fields(self):
        ef   = self._f
        card = self.card
        ct   = card.get("card_type", "Spells")

        # Block controls – default = Play
        ctrl = tk.Frame(ef, bg=self.BG)
        ctrl.pack(fill="x", padx=8, pady=4)
        tk.Label(ctrl, text="Add Block:", bg=self.BG, fg="#ccc",
                 font=("Arial", 9, "bold")).pack(side="left")
        self._new_block_var = tk.StringVar(value="Play")
        # Use the live sigil registry so removed sigils disappear here too
        from CardContent.sigil_registry import get_sigil_names as _gsn
        ttk.Combobox(ctrl, textvariable=self._new_block_var,
                     values=_gsn(), width=16, state="readonly").pack(
            side="left", padx=4)
        tk.Button(ctrl, text="+ Add Block", command=self._add_block,
                  bg="#1a6e3c", fg="white", font=("Arial", 8)).pack(
            side="left", padx=4)
        count = len(card.get("blocks", []))
        tk.Label(ctrl, text=f"({count}/4 blocks)",
                 bg=self.BG, fg="#888", font=("Arial", 8)).pack(side="left")

        self._blocks_frame = tk.Frame(ef, bg=self.BG)
        self._blocks_frame.pack(fill="x", padx=8, pady=4)
        self._rebuild_blocks()

    def _rebuild_blocks(self):
        for w in self._blocks_frame.winfo_children():
            w.destroy()
        for idx, blk in enumerate(self.card.get("blocks", [])):
            wrapper = tk.Frame(self._blocks_frame, bg="#212121",
                               relief="groove", bd=1)
            wrapper.pack(fill="x", pady=4)

            type_row = tk.Frame(wrapper, bg="#212121")
            type_row.pack(fill="x", padx=4, pady=2)
            tk.Label(type_row, text="Typ:", bg="#212121", fg="#888",
                     font=("Arial", 8)).pack(side="left", padx=4)
            tv = tk.StringVar(value=blk.get("type", "Play"))
            from CardContent.sigil_registry import get_sigil_names as _gsn
            tc = ttk.Combobox(type_row, textvariable=tv,
                              values=_gsn(), state="readonly",
                              width=16, font=("Arial", 8))
            tc.pack(side="left", padx=4)

            def _change_type(_, b=blk, v=tv):
                b["type"] = v.get()
                self._rebuild_blocks()
                if self.on_change: self.on_change()

            tc.bind("<<ComboboxSelected>>", _change_type)

            BoxEditor(wrapper, blk,
                        on_change=self.on_change,
                        on_delete=lambda i=idx: self._del_block(i),
                        card_type=self.card.get("card_type", ""),
                        bg="#212121").pack(fill="x")

    def _add_block(self):
        blocks = self.card.setdefault("blocks", [])
        if len(blocks) >= 4:
            from tkinter import messagebox
            messagebox.showwarning("Limit", "Max 4 blocks.")
            return
        blocks.append(empty_box(self._new_block_var.get()))
        self._rebuild_blocks()
        if self.on_change: self.on_change()

    def _del_block(self, idx: int):
        self.card["blocks"].pop(idx)
        self._rebuild_blocks()
        if self.on_change: self.on_change()


# ── Renderer ──────────────────────────────────────────────────────────────────

class SpellCardRenderer:
    FF   = "Palatino Linotype"
    FS   = 13
    FS_S = 10

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.W  = CARD_W
        self.H  = CARD_H
        self.AW = ARTWORK_W
        self._img = None

    def render(self, card: dict):
        import math
        c  = self.canvas
        c.delete("all")
        ct = card.get("card_type", "Spells")

        # Normalise element list (backward compat: old "element" string)
        if ct == "Spells":
            elements = card.get("elements")
            if elements is None:
                old = card.get("element", "Fire")
                elements = [old] if old else ["Fire"]
        else:
            elements = []

        primary_elem  = elements[0] if elements else None
        primary_color = ELEMENT_COLORS.get(primary_elem, "#2a1a3a") if primary_elem else "#2a1a3a"

        c.create_rectangle(0, 0, self.W, self.H, fill="#1a1a1a", outline="")
        c.create_rectangle(0, 0, self.W, self.H, fill=primary_color,
                           outline="", stipple="gray25")
        if len(elements) > 1:
            c.create_rectangle(0, 0, self.W, self.H, fill="#aa8800",
                               outline="", stipple="gray12")
        c.create_rectangle(2, 2, self.W-2, self.H-2, outline="black", width=3)

        # Name
        c.create_text(12, 12, text=card.get("name", ""), anchor="nw",
                      font=(self.FF, 16, "bold"), fill="white")

        # Card-type badge (A1/A2): "Chant" or "Act" with related icons
        self._draw_card_type_badge(ct, x=12, y=32)

        # Layout: mana strip (with action symbol on top) | blocks
        content_left  = 6 + MANA_STRIP_W
        content_top   = 52

        if ct == "Spells":
            # Symbol strip on the right for Spells
            self._draw_artwork_strip(card)
            content_right = self.W - self.AW - 6
        else:
            # Prowess: full width, no symbol strip
            content_right = self.W - 6

        self._draw_blocks(card, top=content_top,
                          left=content_left, right=content_right)

        # Draw element badges last so they appear on top of the artwork strip
        if ct == "Spells":
            self._draw_element_badges(elements, primary_color)

    def _draw_element_badges(self, elements: list, primary_color: str):
        """Draw element circles in the top-right corner, polygon for 3+."""
        import math
        c  = self.canvas
        n  = len(elements)
        if n == 0:
            return

        # Centre anchor for the badge cluster
        cx, cy = self.W - 52, 52

        if n == 1:
            r = 22
            positions = [(cx, cy)]
        elif n == 2:
            r = 16
            positions = [(cx - 18, cy), (cx + 18, cy)]
        else:
            # n = 3..6  →  regular polygon, start from top
            poly_r = {3: 24, 4: 22, 5: 22, 6: 22}.get(n, 22)
            r = {3: 14, 4: 13, 5: 12, 6: 11}.get(n, 11)
            positions = []
            for i in range(n):
                angle = 2 * math.pi * i / n - math.pi / 2
                px = cx + poly_r * math.cos(angle)
                py = cy + poly_r * math.sin(angle)
                positions.append((int(px), int(py)))

        icon_font = ("Arial", max(8, 16 - n * 2))
        for (px, py), elem in zip(positions, elements):
            col  = ELEMENT_COLORS.get(elem, "#888")
            icon = ELEMENT_ICONS.get(elem, "?")
            c.create_oval(px - r, py - r, px + r, py + r,
                          fill=col, outline="gold", width=2)
            c.create_text(px, py, text=icon, font=icon_font)

    def _draw_artwork_box(self, card, x0, y0, x1, y1):
        c    = self.canvas
        path = card.get("artwork", "")
        c.create_rectangle(x0, y0, x1, y1, fill="#111", outline="#444")
        if path and _PIL:
            import os
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    w, h = x1-x0, y1-y0
                    iw, ih = img.size
                    scale = max(w/iw, h/ih)
                    nw, nh = int(iw*scale), int(ih*scale)
                    img = img.resize((nw, nh), Image.LANCZOS)
                    left = (nw-w)//2; top = (nh-h)//2
                    img = img.crop((left, top, left+w, top+h))
                    self._img = ImageTk.PhotoImage(img)
                    c.create_image(x0, y0, image=self._img, anchor="nw")
                    return
                except Exception:
                    pass
        c.create_text((x0+x1)//2, (y0+y1)//2,
                      text="Artwork", fill="#444", font=(self.FF, self.FS_S))

    def _draw_card_type_badge(self, card_type: str, x: int, y: int):
        """Draw a small icon + label for Chant (Spells) / Act (Prowess).

        The two icons share a common hexagonal frame so they read as
        related; the inner glyph differs: Chant = musical note (sound),
        Act = star-burst (action).
        """
        c = self.canvas
        label = card_type_label(card_type)
        if card_type == "Spells":
            accent = "#ffd580"   # warm gold
            self._draw_chant_icon(x + 10, y + 10, r=9, color=accent)
        elif card_type == "Prowess":
            accent = "#ffb347"   # slightly oranger gold
            self._draw_act_icon(x + 10, y + 10, r=9, color=accent)
        else:
            return
        c.create_text(x + 24, y + 2, text=label, anchor="nw",
                      font=(self.FF, 11, "bold"), fill=accent)

    def _draw_hex_frame(self, cx: int, cy: int, r: int, color: str):
        """Shared hexagonal frame around Chant/Act icons (A2 visual kinship)."""
        import math
        c = self.canvas
        pts = []
        for i in range(6):
            a = math.pi / 6 + i * math.pi / 3  # flat-top hex
            pts.extend([cx + r * math.cos(a), cy + r * math.sin(a)])
        c.create_polygon(*pts, fill="#1a1a1a", outline=color, width=1)

    def _draw_chant_icon(self, cx: int, cy: int, r: int, color: str):
        """Chant (Spells): hex frame + stylised eighth-note glyph."""
        c = self.canvas
        self._draw_hex_frame(cx, cy, r, color)
        # Note stem
        c.create_line(cx + 1, cy - r + 3, cx + 1, cy + r - 4,
                      fill=color, width=2)
        # Note head (filled oval)
        c.create_oval(cx - 4, cy + r - 7, cx + 2, cy + r - 3,
                      fill=color, outline=color)
        # Flag
        c.create_line(cx + 1, cy - r + 3, cx + r - 3, cy - r + 6,
                      fill=color, width=2)

    def _draw_act_icon(self, cx: int, cy: int, r: int, color: str):
        """Act (Prowess): same hex frame + four-point star-burst glyph."""
        c = self.canvas
        self._draw_hex_frame(cx, cy, r, color)
        # 4-point star
        s = r - 3
        pts = [cx, cy - s,
               cx + 2, cy - 1,
               cx + s, cy,
               cx + 2, cy + 2,
               cx, cy + s,
               cx - 2, cy + 2,
               cx - s, cy,
               cx - 2, cy - 1]
        c.create_polygon(*pts, fill=color, outline=color)
        # tiny centre pip
        c.create_oval(cx - 1, cy - 1, cx + 1, cy + 1,
                      fill="#1a1a1a", outline="")

    def _draw_artwork_strip(self, card):
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
                for _ in ab.get("costs", []): symbols.append(COST_SYMBOL)
                groups = ab.get("effect_groups", [])
                if groups:
                    for g in groups:
                        symbols.append(EFFECT_SYMBOL)
                        for _ in g.get("modifiers", []):
                            symbols.append("·")
                else:
                    for _ in ab.get("effects", []): symbols.append(EFFECT_SYMBOL)
        step = 22; y = y1 - 14
        for sym in reversed(symbols):
            if y < y0 + 10: break
            c.create_text(x0 + self.AW//2, y, text=sym,
                          font=("Arial", 14), fill="#cccccc", anchor="center")
            y -= step

    def _draw_blocks(self, card, top, left, right):
        c      = self.canvas
        blocks = card.get("blocks", [])
        if not blocks:
            c.create_text((left+right)//2, (top+self.H)//2,
                          text="No blocks", fill="#555", font=(self.FF, 14))
            return

        BOTTOM  = self.H - 6
        block_h = (BOTTOM - top) // len(blocks)
        from card_builder.data import get_content_data
        CD = get_content_data()
        FN = (self.FF, self.FS)
        FB = (self.FF, self.FS, "bold")

        for i, blk in enumerate(blocks):
            y0    = top + i * block_h
            y1    = y0 + block_h
            btype = blk["type"]
            col   = BOX_COLORS.get(btype, "#333")

            c.create_rectangle(left - MANA_STRIP_W, y0, right, y1,
                               fill=col, outline="#888", width=1, stipple="gray50")
            # Sigil label (A3 + per-card-type renames, e.g. Play→Chant on
            # Spells, Play→Act on Prowess). Internal key stays stable.
            ct = card.get("card_type", "")
            c.create_text(left, y0+4, text=f"[{sigil_label(btype, ct)}]",
                          anchor="nw",
                          font=(self.FF, 10, "bold"), fill="white")

            # Mana strip boundary
            sx = left - MANA_STRIP_W
            c.create_line(left, y0, left, y1, fill="#555", width=1)

            # Draw mana symbols (with manual-trigger icons on top) for this block
            self._draw_mana_strip(blk, left - MANA_STRIP_W + 2, y0+20, y1-4, CD)

            ab_list = blk.get("abilities", [])
            if not ab_list:
                continue

            def ab_height(ab):
                lh = self.FS + 6
                n  = 1
                if ab.get("condition_id"): n += 1
                non_mana = [ci for ci in ab.get("costs", [])
                            if ci.get("cost_id") != MANA_COST_ID]
                groups = ab.get("effect_groups", [])
                if groups:
                    n += len(non_mana)

                    # Account for merged buckets: each targeting bucket uses
                    # 1 header line + 1 line per primary; each non-targeting
                    # bucket uses 1 line per primary.
                    buckets = self._merge_display_buckets(groups)
                    for b in buckets:
                        n_primaries = max(1, len(b["primaries"]))
                        if b["target_type"] in ("Target Enemy", "Target Ally",
                                                "Target Neutral"):
                            n += 1 + n_primaries
                        else:
                            n += n_primaries

                    cn = ab.get("choose_n")
                    if cn and cn < len(groups):
                        n += 1  # "Choose X of Y" line

                    # Sub-sigils per bucket
                    for b in buckets:
                        gs = b.get("sub_sigil")
                        if gs:
                            n += 1  # sub-sigil header
                            sub_buckets = self._merge_display_buckets(
                                gs.get("effect_groups", []))
                            for sb in sub_buckets:
                                np = max(1, len(sb["primaries"]))
                                if sb["target_type"] in ("Target Enemy",
                                                         "Target Ally",
                                                         "Target Neutral"):
                                    n += 1 + np
                                else:
                                    n += np

                    # Global sub-sigil (Option B/C)
                    global_sub = ab.get("sub_sigil_global")
                    if global_sub:
                        n += 2  # separator + header
                        n += len(global_sub.get("effect_groups", []))

                    # Backward compat global sub-sigil
                    old_sub = ab.get("sub_sigil")
                    if old_sub and not global_sub:
                        n += 2
                        n += len(old_sub.get("effect_groups", []))
                else:
                    n += len(non_mana) + len(ab.get("effects", []))
                return n * lh

            total      = sum(ab_height(ab) for ab in ab_list) + 4*(len(ab_list)-1)
            block_inner = block_h - 26
            start_y    = y0 + 24 + max(0, (block_inner - total) // 2)

            iy = start_y
            for ab in ab_list:
                iy = self._draw_ability(ab, iy, y1-4, CD, FN, FB, left, right)
                if iy >= y1: break

    def _draw_mana_strip(self, blk, x, y_start, y_max, CD):
        """Draw manual-trigger icons (top) then sorted mana costs underneath.

        Mana order: Quinta (Meta) first, then other specific elements, then Generic.
        Manual triggers (Manual / Half / Third) are drawn first above the mana stack.
        """
        c  = self.canvas
        cx = x + MANA_STRIP_W//2 - 2
        y  = y_start
        r  = 9   # circle radius

        # 1) Manual trigger markers on top
        for ab in blk.get("abilities", []):
            tid = ab.get("trigger_id")
            if tid in MANUAL_TRIGGER_IDS:
                if y + r*2 + 2 > y_max:
                    break
                variant = {
                    MANUAL_TRIGGER_ID:       "full",
                    MANUAL_TRIGGER_HALF_ID:  "half",
                    MANUAL_TRIGGER_THIRD_ID: "third",
                }.get(tid, "full")
                self._draw_action_symbol(cx, y + r, r, variant=variant)
                y += r*2 + 3

        # 2) Collect mana costs for this block (from all abilities) and sort
        META = "Quinta"  # "Meta" mana
        buckets = {"meta": [], "other": [], "generic": []}
        for ab in blk.get("abilities", []):
            for ci in ab.get("costs", []):
                if ci.get("cost_id") != MANA_COST_ID:
                    continue
                vals    = ci.get("vals", {})
                element = vals.get("element", vals.get("Element", ""))
                if element == META:
                    buckets["meta"].append(element)
                elif element and element in ELEMENT_COLORS:
                    buckets["other"].append(element)
                else:
                    buckets["generic"].append(element or "")
        ordered = buckets["meta"] + sorted(buckets["other"]) + buckets["generic"]

        # 3) Draw mana circles in sorted order
        for element in ordered:
            if y + r*2 + 2 > y_max:
                break
            if element and element in ELEMENT_COLORS:
                col  = ELEMENT_COLORS[element]
                icon = ELEMENT_ICONS[element]
            else:
                col  = GENERIC_MANA_COLOR
                icon = GENERIC_MANA_ICON
            c.create_oval(cx-r, y, cx+r, y+r*2,
                          fill=col, outline="gold", width=1)
            c.create_text(cx, y+r, text=icon,
                          font=("Arial", 9), anchor="center")
            y += r*2 + 3

    def _draw_action_symbol(self, cx: int, cy: int, r: int,
                            variant: str = "full"):
        """Action-cost marker. Three variants:
        - 'full' (Manual_Trigger): circle + regular downward triangle, yellow
        - 'half' (Manual_Trigger_Half): grey circle + INVERTED yellow triangle
        - 'third' (Manual_Trigger_Third): bronze circle + bronze triangle +
          inverted triangle below it (shifted up), all bronze/brown
        """
        c  = self.canvas
        tr = int(r * 0.58)

        if variant == "half":
            # Grey disc, inverted yellow triangle (pointing up)
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          fill="#3a3a3a", outline="#888888", width=2)
            pts = [cx - tr, cy + int(tr * 0.65),
                   cx + tr, cy + int(tr * 0.65),
                   cx,      cy - int(tr * 0.80)]
            c.create_polygon(pts, fill="#ffaa00")
            return

        if variant == "third":
            # Bronze disc with TWO stacked triangles (upper = downward,
            # lower = upward/inverted), both bronze. The lower one is shifted
            # upward so they nearly touch at the center.
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          fill="#2a1808", outline="#b87333", width=2)
            tr2 = int(r * 0.44)
            # Upper triangle (points down)
            cy_u = cy - int(r * 0.28)
            pts_up = [cx - tr2, cy_u - int(tr2 * 0.55),
                      cx + tr2, cy_u - int(tr2 * 0.55),
                      cx,       cy_u + int(tr2 * 0.75)]
            c.create_polygon(pts_up, fill="#b87333")
            # Lower triangle (points up), shifted up so its tip almost touches
            # the upper triangle's tip.
            cy_l = cy + int(r * 0.18)
            pts_dn = [cx - tr2, cy_l + int(tr2 * 0.55),
                      cx + tr2, cy_l + int(tr2 * 0.55),
                      cx,       cy_l - int(tr2 * 0.75)]
            c.create_polygon(pts_dn, fill="#8b5a2b")
            return

        # Default / "full": standard Manual_Trigger look
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill="#1a1200", outline="#ffaa00", width=2)
        pts = [cx - tr, cy - int(tr * 0.65),
               cx + tr, cy - int(tr * 0.65),
               cx,      cy + int(tr * 0.80)]
        c.create_polygon(pts, fill="#ffaa00")

    def _draw_ability(self, ab, y, y_max, CD, FN, FB, left, right):
        c     = self.canvas
        x     = left
        max_w = right - left - 8
        lh    = self.FS + 6

        # Manual-trigger markers are drawn above the mana strip,
        # see _draw_mana_strip().

        # ── Header ───────────────────────────────────────────────────────────
        # Manual triggers are symbol-only — skip them in text
        trigger_text = ""
        if ab.get("trigger_id") and ab["trigger_id"] not in MANUAL_TRIGGER_IDS:
            trig = CD.get("trigger", ab["trigger_id"])
            if trig:
                trigger_text = _render_content(trig, {
                    "var_values": ab.get("trigger_vals", {}),
                    "opt_values": ab.get("trigger_opt_vals", {})})
            if not trigger_text.strip():
                # fallback: render the sigil template directly
                try:
                    from CardContent.template_parser import render_content_text
                    sigil_tmpl = trig.get("sigil", "") if trig else ""
                    if sigil_tmpl:
                        trigger_text = render_content_text(sigil_tmpl, ab.get("trigger_vals", {}), ab.get("trigger_opt_vals", {}))
                except Exception:
                    pass

        cond_text = ""
        if ab.get("condition_id"):
            cond = CD.get("condition", ab["condition_id"])
            if cond:
                cond_text = _render_content(cond, {
                    "var_values": ab.get("condition_vals", {}),
                    "opt_values": ab.get("condition_opt_vals", {})})

        # Trigger template already contains the full "If you …" phrase.
        # G: Triggers can contain literal newlines from their content_text
        #    template (used for line breaking in editors). Collapse them
        #    into single spaces and tidy the trailing period before use.
        if trigger_text:
            import re as _re
            trigger_text = _re.sub(r"\s+", " ", trigger_text).strip()
        trig_clean = trigger_text.rstrip(".").strip() if trigger_text else ""
        if trig_clean and cond_text:
            # G: Use "while you have …" — reads more naturally than
            # "and you have" when the trigger already starts with "If you".
            prefix = f"{trig_clean}, while you have {cond_text}"
        elif trig_clean:
            prefix = trig_clean
        elif cond_text:
            prefix = f"If you have {cond_text}"
        else:
            prefix = ""

        non_mana_costs = []
        for ci in ab.get("costs", []):
            if ci.get("cost_id") == MANA_COST_ID:
                continue
            co = CD.get("cost", ci["cost_id"])
            if co:
                non_mana_costs.append(_render_content(co, {
                    "var_values": ci.get("vals", {}),
                    "opt_values": ci.get("opt_vals", {})}))
        cost_str = ", ".join(non_mana_costs)

        groups     = ab.get("effect_groups", [])
        GROUP_ORDER = {"Non Targeting": 0, "Target Ally": 1, "Target Enemy": 2, "Target Neutral": 3}
        groups = sorted(groups, key=lambda g: GROUP_ORDER.get(g.get("target_type", "Non Targeting"), 99))
        choose_n   = ab.get("choose_n")
        choose_rep = ab.get("choose_repeat", False)
        n_items    = len(groups) if groups else (
            len(ab.get("effects", [])) + len(ab.get("continuouses", [])))

        TARGET_COLORS = {
            "Target Enemy":   "#ff8888",
            "Target Ally":    "#88ff88",
            "Non Targeting":  "white",
            "Target Neutral": "#ffdd88",
        }
        TARGET_PREFIX = {
            "Target Enemy":   "→",
            "Target Ally":    "→",
            "Non Targeting":  "•",
            "Target Neutral": "→",
        }
        # Target-type specific indent. Headers ("• Target Enemy:") sit at the
        # same indent as Non-Targeting bullets; primaries below them get the
        # extra step inwards from the +12 in their _wrap call.
        TARGET_INDENT = {
            "Non Targeting":  0,
            "Target Ally":    0,
            "Target Enemy":   0,
            "Target Neutral": 0,
        }

        use_or      = False
        choose_part = ""
        if choose_n and choose_n < n_items:
            if n_items == 2 and choose_n == 1:
                use_or = True
            else:
                if choose_rep:
                    choose_part = f"Choose {choose_n} (you can repeat your choice)"
                else:
                    choose_part = f"Choose {choose_n}"

        if prefix:
            header = f"{prefix}; {cost_str}:" if cost_str else f"{prefix}:"
        else:
            header = f"{cost_str}:" if cost_str else ""

        if header and y + lh <= y_max:
            y = self._wrap(header, x, y, max_w, FB, "#aaddff", y_max)

        if choose_part and y + lh <= y_max:
            y = self._wrap(choose_part, x + 6, y, max_w - 6,
                           (self.FF, self.FS_S, "italic"), "#aaddff", y_max)

        # ── Effect groups (new format) ────────────────────────────────────────
        if groups:
            # Merge consecutive groups sharing the same (target_type, modifier-sig)
            # and no sub_sigil into one display bucket. Each bucket renders as
            # a single header ("Target Enemy, ranged:") with its primaries as
            # bullet lines beneath.
            buckets = self._merge_display_buckets(groups)

            for bi, bucket in enumerate(buckets):
                if y + lh > y_max:
                    break
                if use_or and bi > 0:
                    y = self._wrap("or", x + 6, y, max_w - 6,
                                   (self.FF, self.FS_S, "italic"), "#aaddff", y_max)

                ttype     = bucket["target_type"]
                grp_color = TARGET_COLORS.get(ttype, "white")
                t_indent  = TARGET_INDENT.get(ttype, 0)
                modifiers = bucket["modifiers"]
                primaries = bucket["primaries"]
                group_sub = bucket["sub_sigil"]

                is_targeting = ttype in ("Target Enemy", "Target Ally",
                                         "Target Neutral")

                # Build modifier text "ranged 5, precise"
                mod_parts = []
                for mod in modifiers:
                    eid = mod.get("effect_id", "")
                    # D: Range Reform — skip Ranged modifier when X∈{0,1}
                    if eid == "Ranged" and \
                       int(mod.get("vals", {}).get("X", 0) or 0) <= 1:
                        continue
                    # AoE modifier — synthesized, not an effect entry
                    if eid == "AoE":
                        pattern = mod.get("aoe_pattern", "")
                        if pattern:
                            mod_parts.append(f"AoE {pattern}")
                        continue
                    meff = CD.get("effect", eid)
                    if meff:
                        mt = meff.get("content_text") or ""
                        for k, v in mod.get("vals", {}).items():
                            mt = mt.replace(f"{{{k}}}", str(v))
                        if mt:
                            mod_parts.append(mt)

                if is_targeting:
                    # Header: "• Target Enemy, ranged 5:" — bullet for the
                    # bucket label so it visually leads the indented primaries.
                    header_parts = [ttype] + mod_parts
                    header = "• " + ", ".join(header_parts) + ":"
                    if y + lh <= y_max:
                        y = self._wrap(header, x + 6 + t_indent, y,
                                       max_w - 6 - t_indent, FN,
                                       grp_color, y_max)
                    # Primaries as bullets underneath
                    for primary in primaries:
                        if y + lh > y_max:
                            break
                        eff = CD.get("effect", primary.get("effect_id", ""))
                        if not eff:
                            continue
                        # F1: route through _render_content so [if OPT…] tags
                        # in the effect's content_text resolve correctly.
                        pt = _render_content(eff, {
                            "var_values": primary.get("vals", {}),
                            "opt_values": primary.get("opt_vals", {})})
                        if not pt:
                            pt = eff.get("content_text") or ""
                            for k, v in primary.get("vals", {}).items():
                                pt = pt.replace(f"{{{k}}}", str(v))
                        pt = self._decorate_damage(pt, primary)
                        if pt:
                            y = self._wrap(f"  • {pt}", x + 12 + t_indent, y,
                                           max_w - 14 - t_indent, FN,
                                           grp_color, y_max)
                else:
                    # Non Targeting: no header. Each primary on its own bullet
                    # line; if there are modifiers, fold them into each line.
                    mod_suffix = (", " + ", ".join(mod_parts)) if mod_parts else ""
                    for primary in primaries:
                        if y + lh > y_max:
                            break
                        eff = CD.get("effect", primary.get("effect_id", ""))
                        if not eff:
                            continue
                        pt = _render_content(eff, {
                            "var_values": primary.get("vals", {}),
                            "opt_values": primary.get("opt_vals", {})})
                        if not pt:
                            pt = eff.get("content_text") or ""
                            for k, v in primary.get("vals", {}).items():
                                pt = pt.replace(f"{{{k}}}", str(v))
                        pt = self._decorate_damage(pt, primary)
                        if pt:
                            y = self._wrap(f"• {pt}{mod_suffix}", x + 6, y,
                                           max_w - 6, FN, grp_color, y_max)

                # ── Sub-Sigil attached to this bucket ─────────────────────────
                if group_sub and y + lh <= y_max:
                    y = self._render_sub_sigil(group_sub, CD, c, x, y, max_w,
                                               y_max,
                                               indent_x=6 + t_indent,
                                               color=grp_color)

            # ── Global Sub-Sigil (Option B/C - rendered at bottom) ─────────────
            global_sub = ab.get("sub_sigil_global")
            if global_sub and y + lh * 2 <= y_max:
                # Separator line
                c.create_line(x + 6, y + 2, right - 6, y + 2,
                              fill="#666", width=1, dash=(3, 3))
                y += 6

                # Render global sub-sigil
                y = self._render_sub_sigil(global_sub, CD, c, x, y, max_w, y_max,
                                         indent_x=0, color="#ffcc66")

            # ── Backward compat: Old global sub-sigil ──────────────────────
            # (if card was saved with old format, render it too)
            old_sub = ab.get("sub_sigil")
            if old_sub and not global_sub and y + lh * 2 <= y_max:
                c.create_line(x + 6, y + 2, right - 6, y + 2,
                              fill="#666", width=1, dash=(3, 3))
                y += 6
                y = self._render_sub_sigil(old_sub, CD, c, x, y, max_w, y_max,
                                         indent_x=0, color="#ffcc66")

        # ── Legacy flat effects ───────────────────────────────────────────────
        else:
            eff_data = []
            for ei in ab.get("effects", []):
                eff = CD.get("effect", ei.get("effect_id", ""))
                if not eff:
                    continue
                ct = eff.get("content_text") or eff.get("content_box", "")
                for k, v in ei.get("vals", {}).items():
                    ct = ct.replace(f"{{{k}}}", str(v))
                eff_data.append([eff, ei, ct])

            for cont in ab.get("continuouses", []):
                itm = CD.get("continuous", cont.get("effect_id", ""))
                if not itm:
                    continue
                ct = itm.get("content_text") or itm.get("content_box", "")
                for k, v in cont.get("vals", {}).items():
                    ct = ct.replace(f"{{{k}}}", str(v))
                eff_data.append([itm, cont, ct])

            chars_per_line = max(1, int(max_w / max(1, FN[1] * 0.6)))

            def _est_lines(text: str) -> int:
                if not text: return 1
                import math
                return max(1, math.ceil(
                    sum(len(w)+1 for w in text.split()) / chars_per_line))

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

            for gi, (_, _, etxt) in enumerate(eff_data):
                if not etxt or y + lh > y_max:
                    break
                if use_or and gi > 0:
                    y = self._wrap("or", x + 6, y, max_w - 6,
                                   (self.FF, self.FS_S, "italic"), "#aaddff", y_max)
                y = self._wrap(f"• {etxt}", x + 6, y, max_w - 6, FN, "white", y_max)

        return y + 4

    @staticmethod
    def _decorate_damage(text: str, primary: dict) -> str:
        """Append the damage type after a damage-tagged effect's text.

        Turns ``"Damage 4D6"`` into ``"Damage 4D6 (Ice)"`` so users can see
        the rolled damage flavour. Leaves non-damage effects untouched.
        """
        dtype = primary.get("damage_type")
        if not dtype:
            return text
        if not text:
            return text
        # Avoid double-decoration if the type name is already in the text
        if dtype.lower() in text.lower():
            return text
        return f"{text} ({dtype})"

    def _merge_display_buckets(self, groups: list) -> list:
        """Merge consecutive effect groups that share the same target_type and
        modifier signature (same modifier effect_ids with same vals) into
        display buckets. Groups that own a sub_sigil always get their own bucket.

        Each bucket: {
            "target_type": str,
            "modifiers":   list[mod dict],   # from first group in bucket
            "primaries":   list[primary dict] (flattened across merged groups),
            "sub_sigil":   dict | None,
        }
        """
        def mod_sig(group):
            sig = []
            for m in group.get("modifiers", []):
                mid  = m.get("effect_id", "")
                vals = tuple(sorted(m.get("vals", {}).items()))
                sig.append((mid, vals))
            return tuple(sorted(sig))

        buckets = []
        for g in groups:
            ttype = g.get("target_type", "Non Targeting")
            # Extract primaries (support multiple field names)
            primaries = g.get("primaries") or g.get("effects") or []
            if not primaries and "primary" in g:
                primaries = [g["primary"]]
            sub_sigil = g.get("sub_sigil")
            sig = mod_sig(g)

            # Can we merge into the previous bucket?
            if (buckets
                    and buckets[-1]["target_type"] == ttype
                    and buckets[-1]["_modsig"] == sig
                    and buckets[-1]["sub_sigil"] is None
                    and sub_sigil is None):
                buckets[-1]["primaries"].extend(primaries)
                continue

            buckets.append({
                "target_type": ttype,
                "modifiers":   list(g.get("modifiers", [])),
                "primaries":   list(primaries),
                "sub_sigil":   sub_sigil,
                "_modsig":     sig,
            })
        return buckets

    def _render_group_text(self, group: dict, CD) -> tuple:
        """
        Render one effect group as 'Target Type: Primary1 and Primary2, Modifier1, Modifier2'.
        Returns (main_text: str, reminder_text: str).
        """
        # Support both 'primaries' list and old 'primary' singular (and legacy 'effects')
        primaries = group.get("primaries")
        if primaries is None:
            primaries = group.get("effects")
        if primaries is None:
            p = group.get("primary", {})
            primaries = [p] if p.get("effect_id") else []

        primary_parts = []
        reminder_parts = []
        for primary in primaries:
            eff = CD.get("effect", primary.get("effect_id", ""))
            if eff:
                ct = eff.get("content_text") or ""
                for k, v in primary.get("vals", {}).items():
                    ct = ct.replace(f"{{{k}}}", str(v))
                if ct:
                    primary_parts.append(ct)
                rt = eff.get("reminder_text", "")
                if rt:
                    for k, v in primary.get("vals", {}).items():
                        rt = rt.replace(f"{{{k}}}", str(v))
                    reminder_parts.append(rt)

        mod_parts = []
        for mod in group.get("modifiers", []):
            # D: Range Reform — skip Ranged with X==0
            if mod.get("effect_id") == "Ranged" and \
               int(mod.get("vals", {}).get("X", 0) or 0) == 0:
                continue
            meff = CD.get("effect", mod.get("effect_id", ""))
            if meff:
                mt = meff.get("content_text") or ""
                for k, v in mod.get("vals", {}).items():
                    mt = mt.replace(f"{{{k}}}", str(v))
                if mt:
                    mod_parts.append(mt)

        # Build: "Target Type, Modifier1: Primary1 and Primary2"
        # Modifiers fold into the header (before the colon), effects follow
        tt = group.get("target_type", "")
        TARGETING_TYPES = {"Target Enemy", "Target Ally", "Target Neutral"}
        if tt in TARGETING_TYPES:
            header = tt
        else:
            header = ""
        if mod_parts:
            header = (header + ", " + ", ".join(mod_parts)) if header else ", ".join(mod_parts)
        eff_text = " and ".join(primary_parts)

        if header and eff_text:
            main_text = f"{header}: {eff_text}"
        elif eff_text:
            main_text = eff_text
        else:
            main_text = header

        reminder_text = "; ".join(reminder_parts)
        return (main_text, reminder_text)

    def _render_sub_sigil(self, sub_sigil: dict, CD: dict, c, x, y, max_w, y_max,
                          indent_x: int = 0, color: str = "#ffcc66") -> int:
        """Render a sub-sigil: costs + effect groups.

        Args:
            sub_sigil: Sub-sigil dict with costs and effect_groups
            CD: Content data lookup
            c: Canvas object
            x, y, max_w, y_max: Layout parameters
            indent_x: Additional indent from left edge
            color: Color for sub-sigil text

        Returns: New y position after rendering
        """
        lh = self.FS + 6
        FN = (self.FF, self.FS, "normal")

        if not sub_sigil:
            return y

        sub_type = sub_sigil.get("sub_sigil_type", "enhance")

        # Skip silent sub-sigils: enhance / target_enemy / target_ally / choose
        # all need at least one effect_group to be worth rendering.
        _NEEDS_GROUPS = ("enhance", "target_enemy", "target_ally", "choose")
        if sub_type in _NEEDS_GROUPS and not sub_sigil.get("effect_groups"):
            return y

        # Render costs. Mana costs are rendered as element glyphs inline
        # (e.g. "Enhance ❄ ⚙:") — no "Pay Mana" wording. Multiple mana costs
        # become multiple symbols. Other costs render as plain text.
        mana_glyphs: list[str] = []
        sub_other_costs: list[str] = []
        for ci in sub_sigil.get("costs", []):
            cid = ci.get("cost_id", "")
            if cid == MANA_COST_ID:
                vals    = ci.get("vals", {})
                element = vals.get("element", vals.get("Element", ""))
                glyph   = ELEMENT_ICONS.get(element, GENERIC_MANA_ICON)
                mana_glyphs.append(glyph)
                continue
            co = CD.get("cost", cid)
            if not co:
                continue
            txt = _render_content(co, {
                "var_values": ci.get("vals", {}),
                "opt_values": ci.get("opt_vals", {})})
            if txt:
                sub_other_costs.append(txt)

        # Header verb depends on sub-sigil type
        verb = {
            "enhance":      "Enhance",
            "doublecast":   "Doublecast",
            "multicast":    "Multicast",
            "target_enemy": "Vs. Enemy",
            "target_ally":  "Aid Ally",
            "choose":       "Choose 1",
        }.get(sub_type, "Enhance")
        # Compose: "Enhance ❄ ⚙ — Discard a card:" / "Enhance ❄:" / "Enhance:"
        head_parts = [verb]
        if mana_glyphs:
            head_parts.append(" ".join(mana_glyphs))
        if sub_other_costs:
            head_parts.append("— " + ", ".join(sub_other_costs))
        sub_header = " ".join(head_parts) + ":"

        if y + lh <= y_max:
            y = self._wrap(sub_header, x + indent_x + 4, y, max_w - indent_x - 4,
                          (self.FF, self.FS_S, "bold"), color, y_max)

        # Render effect groups in sub-sigil using the same merge-and-header
        # layout as the main ability, so "Target Enemy, ranged:" only appears
        # once per bucket and its primaries become indented bullets.
        TARGETING = ("Target Enemy", "Target Ally", "Target Neutral")
        for bucket in self._merge_display_buckets(
                sub_sigil.get("effect_groups", [])):
            if y + lh > y_max:
                break
            ttype     = bucket["target_type"]
            modifiers = bucket["modifiers"]
            primaries = bucket["primaries"]

            mod_parts = []
            for mod in modifiers:
                # D: Range Reform — skip Ranged with X∈{0,1}
                if mod.get("effect_id") == "Ranged" and \
                   int(mod.get("vals", {}).get("X", 0) or 0) <= 1:
                    continue
                meff = CD.get("effect", mod.get("effect_id", ""))
                if meff:
                    mt = meff.get("content_text") or ""
                    for k, v in mod.get("vals", {}).items():
                        mt = mt.replace(f"{{{k}}}", str(v))
                    if mt:
                        mod_parts.append(mt)

            if ttype in TARGETING:
                header = "• " + ", ".join([ttype] + mod_parts) + ":"
                if y + lh <= y_max:
                    y = self._wrap(header, x + indent_x + 10, y,
                                   max_w - indent_x - 14, FN, color, y_max)
                for primary in primaries:
                    if y + lh > y_max:
                        break
                    eff = CD.get("effect", primary.get("effect_id", ""))
                    if not eff:
                        continue
                    pt = eff.get("content_text") or ""
                    for k, v in primary.get("vals", {}).items():
                        pt = pt.replace(f"{{{k}}}", str(v))
                    pt = self._decorate_damage(pt, primary)
                    if pt:
                        y = self._wrap(f"  • {pt}", x + indent_x + 16, y,
                                       max_w - indent_x - 20, FN, color, y_max)
            else:
                mod_suffix = (", " + ", ".join(mod_parts)) if mod_parts else ""
                for primary in primaries:
                    if y + lh > y_max:
                        break
                    eff = CD.get("effect", primary.get("effect_id", ""))
                    if not eff:
                        continue
                    pt = eff.get("content_text") or ""
                    for k, v in primary.get("vals", {}).items():
                        pt = pt.replace(f"{{{k}}}", str(v))
                    pt = self._decorate_damage(pt, primary)
                    if pt:
                        y = self._wrap(f"• {pt}{mod_suffix}",
                                       x + indent_x + 10, y,
                                       max_w - indent_x - 14, FN, color, y_max)

        return y

    def _wrap(self, text, x, y, max_w, font, color, y_max):
        c      = self.canvas
        line_h = font[1] + 5
        words  = text.split()
        line   = ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) * font[1] * 0.55 > max_w and line:
                if y + line_h > y_max: return y
                c.create_text(x, y, text=line, anchor="nw", font=font, fill=color)
                y += line_h; line = word
            else:
                line = test
        if line and y + line_h <= y_max:
            c.create_text(x, y, text=line, anchor="nw", font=font, fill=color)
            y += line_h
        return y
