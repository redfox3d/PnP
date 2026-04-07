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
)
from card_builder.models import empty_box, empty_ability
from card_builder.widgets import BoxEditor

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False

# Width reserved for mana symbols on the left of the content area
MANA_STRIP_W = 28


# ── Editor ────────────────────────────────────────────────────────────────────

class SpellCardEditor(BaseCardEditor):

    def _build_type_fields(self):
        ef   = self._f
        card = self.card
        ct   = card.get("card_type", "Spells")

        # Block controls – default = Play
        ctrl = tk.Frame(ef, bg=self.BG)
        ctrl.pack(fill="x", padx=8, pady=4)
        tk.Label(ctrl, text="Sigil hinzufügen:", bg=self.BG, fg="#ccc",
                 font=("Arial", 9, "bold")).pack(side="left")
        self._new_block_var = tk.StringVar(value="Play")
        ttk.Combobox(ctrl, textvariable=self._new_block_var,
                     values=BOX_TYPES, width=16, state="readonly").pack(
            side="left", padx=4)
        tk.Button(ctrl, text="+ Sigil", command=self._add_block,
                  bg="#1a6e3c", fg="white", font=("Arial", 8)).pack(
            side="left", padx=4)
        count = len(card.get("blocks", []))
        tk.Label(ctrl, text=f"({count}/4 Sigils)",
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
            tc = ttk.Combobox(type_row, textvariable=tv,
                              values=BOX_TYPES, state="readonly",
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
        print(f"[renderer] render() card={card.get('name')} "
              f"blocks={[b.get('type') for b in card.get('blocks',[])]} ...")
        c  = self.canvas
        c.delete("all")
        ct = card.get("card_type", "Spells")

        elem  = card.get("element", "Fire") if ct == "Spells" else None
        color = ELEMENT_COLORS.get(elem, "#2a1a3a") if elem else "#2a1a3a"

        c.create_rectangle(0, 0, self.W, self.H, fill="#1a1a1a", outline="")
        c.create_rectangle(0, 0, self.W, self.H, fill=color,
                           outline="", stipple="gray25")
        c.create_rectangle(2, 2, self.W-2, self.H-2, outline="black", width=3)

        # Name
        c.create_text(12, 12, text=card.get("name", ""), anchor="nw",
                      font=(self.FF, 16, "bold"), fill="white")

        if ct == "Spells":
            # Element icon top-right
            cx = self.W - self.AW//2 - 4
            cy = 26
            c.create_oval(cx-22, cy-22, cx+22, cy+22,
                          fill=color, outline="gold", width=2)
            c.create_text(cx, cy, text=ELEMENT_ICONS.get(elem, "?"),
                          font=("Arial", 16))
            # Element strip on the right — no artwork box for Spells
            self._draw_artwork_strip(card)
            content_left = 6 + MANA_STRIP_W
            content_top  = 40
        else:
            # Prowess: no artwork, no strip
            content_left = 6
            content_top  = 40

        content_right = self.W - (self.AW + 8 if ct == "Spells" else 6)
        self._draw_blocks(card, top=content_top,
                          left=content_left, right=content_right)

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
                for _ in ab.get("costs",   []): symbols.append(COST_SYMBOL)
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
        print(f"[renderer] _draw_blocks: {len(blocks)} Blöcke, lade CD ...")
        CD = get_content_data()
        print(f"[renderer] CD geladen")
        FN = (self.FF, self.FS)
        FB = (self.FF, self.FS, "bold")

        for i, blk in enumerate(blocks):
            y0    = top + i * block_h
            y1    = y0 + block_h
            btype = blk["type"]
            col   = BOX_COLORS.get(btype, "#333")

            c.create_rectangle(left-MANA_STRIP_W, y0, right, y1,
                               fill=col, outline="#888", width=1, stipple="gray50")
            c.create_text(left, y0+4, text=f"[{btype}]", anchor="nw",
                          font=(self.FF, 10, "bold"), fill="white")

            # Draw mana symbols for this block's costs in the left strip
            self._draw_mana_strip(blk, left-MANA_STRIP_W+2, y0+20, y1-4, CD)

            ab_list = blk.get("abilities", [])
            if not ab_list:
                continue

            def ab_height(ab):
                lh = self.FS + 6
                n  = 1
                if ab.get("condition_id"): n += 1
                if ab.get("choose_n"):     n += 1
                # skip mana costs from text count
                non_mana = [ci for ci in ab.get("costs", [])
                            if ci.get("cost_id") != MANA_COST_ID]
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
        """Draw mana cost symbols stacked vertically in the left strip."""
        c  = self.canvas
        cx = x + MANA_STRIP_W//2 - 2
        y  = y_start
        r  = 9   # circle radius

        for ab in blk.get("abilities", []):
            for ci in ab.get("costs", []):
                if ci.get("cost_id") != MANA_COST_ID:
                    continue
                if y + r*2 + 2 > y_max:
                    break
                # Determine element from vals
                vals    = ci.get("vals", {})
                element = vals.get("element", vals.get("Element", ""))
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

    def _draw_ability(self, ab, y, y_max, CD, FN, FB, left, right):
        c     = self.canvas
        x     = left
        max_w = right - left - 8
        lh    = self.FS + 6

        # ── Build header: "If [trigger] and you have [cond]; cost - Choose Y:" ─
        trigger_text = ""
        if ab.get("trigger_id"):
            trig = CD.get("trigger", ab["trigger_id"])
            if trig:
                trigger_text = _render_content(trig, {
                    "var_values": ab.get("trigger_vals", {}),
                    "opt_values": ab.get("trigger_opt_vals", {})})

        cond_text = ""
        if ab.get("condition_id"):
            cond = CD.get("condition", ab["condition_id"])
            if cond:
                cond_text = _render_content(cond, {
                    "var_values": ab.get("condition_vals", {}),
                    "opt_values": ab.get("condition_opt_vals", {})})

        if trigger_text and cond_text:
            prefix = f"If {trigger_text} and you have {cond_text}"
        elif trigger_text:
            prefix = f"If {trigger_text}"
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

        # ── Draw effects as bullets, prefer content_text; swap complex → reminder ─
        eff_data = []
        for ei in effects:
            eff = CD.get("effect", ei.get("effect_id", ""))
            if not eff:
                continue
            # ei["content_text"] is pre-rendered by _to_render_card → use directly
            # Otherwise render on the fly with proper template functions
            if ei.get("content_text"):
                ct = ei["content_text"]
            else:
                from CardContent.template_parser import render_content_text, render_display_text
                raw_ct    = eff.get("content_text", "")
                raw_sigil = eff.get("sigil", "")
                vals_ei   = ei.get("vals", {})
                opts_ei   = ei.get("opt_vals", {})
                if raw_ct:
                    ct = render_display_text(raw_ct, vals_ei, opts_ei)
                elif raw_sigil:
                    ct = render_content_text(raw_sigil, vals_ei, opts_ei)
                else:
                    ct = eff.get("id", "")
            eff_data.append([eff, ei, ct])

        for cont in ab.get("continuouses", []):
            itm = CD.get("continuous", cont.get("effect_id", "")) if hasattr(CD, 'get') else None
            if not itm:
                continue
            from CardContent.template_parser import render_content_text, render_display_text
            raw_ct    = itm.get("content_text", "")
            raw_sigil = itm.get("sigil", "")
            vals_c    = cont.get("vals", {})
            opts_c    = cont.get("opt_vals", {})
            if raw_ct:
                ct = render_display_text(raw_ct, vals_c, opts_c)
            elif raw_sigil:
                ct = render_content_text(raw_sigil, vals_c, opts_c)
            else:
                ct = itm.get("id", "")
            eff_data.append([itm, cont, ct])

        # Estimate fit; if tight, swap most complex items to reminder_text
        chars_per_line = max(1, int(max_w / max(1, FN[1] * 0.6)))

        def _est_lines(text: str) -> int:
            if not text:
                return 1
            words = text.split()
            total_chars = sum(len(w) + 1 for w in words)
            import math
            return max(1, math.ceil(total_chars / chars_per_line))

        avail_lines = max(1, (y_max - 4 - y) // lh)
        total_lines = sum(_est_lines(f"• {row[2]}") for row in eff_data)

        if total_lines > avail_lines:
            # Sort by complexity descending (use complexity_base as proxy)
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
