"""
alchemy_card.py – Editor and renderer for Alchemy cards.

Layout: name, artwork, ingredients list, result content (with var/opt inputs), on-field effect
"""

import tkinter as tk
from tkinter import ttk

from card_builder.CardTypes.base_card import (
    BaseCardEditor, TagSelector, ContentSelector, _render_content
)
from card_builder.constants import CARD_W, CARD_H
from card_builder.materials import merged_materials

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False


# ── Editor ────────────────────────────────────────────────────────────────────

class AlchemyCardEditor(BaseCardEditor):

    def _build_type_fields(self):
        ef   = self._f
        card = self.card

        # Ingredients
        self._lbl("Zutaten (Materialien):").pack(anchor="w", padx=8)
        all_mats = merged_materials()
        self._ingredients = TagSelector(
            ef, values=all_mats,
            selected=card.get("ingredients", []),
            on_change=self._changed, bg=self.BG)
        self._ingredients.pack(fill="x", padx=8, pady=2)

        self._sep()

        # Result content selector
        from card_builder.data import get_content_data
        CD = get_content_data()

        result_val = card.setdefault("result", {
            "content_id": card.get("result_content_id", ""),
            "var_values": {},
            "opt_values": {},
        })

        self._result_selector = ContentSelector(
            ef,
            content_ids=CD.effect_ids(),
            data_getter=lambda id_: CD.get("effect", id_),
            value=result_val,
            on_change=self._changed,
            on_text_change=self._result_text_changed,
            label="Ergebnis",
            bg=self.BG,
        )
        self._result_selector.pack(fill="x", padx=8, pady=4)

        # Result text preview (readonly)
        prev_row = tk.Frame(ef, bg=self.BG)
        prev_row.pack(fill="x", padx=8, pady=2)
        tk.Label(prev_row, text="→", bg=self.BG, fg="#888",
                 font=("Arial", 9)).pack(side="left")
        self._result_preview = tk.Label(prev_row, text=card.get("result_text", ""),
                                         bg="#1a2a1a", fg="#aaffaa",
                                         font=("Arial", 9), wraplength=400,
                                         anchor="w", justify="left")
        self._result_preview.pack(side="left", fill="x", expand=True, padx=4)

        self._sep()

        # On-field effect
        self._lbl("On-Field Effekt:").pack(anchor="w", padx=8)
        self._alchemy_effect = tk.Text(ef, height=4, bg="#2a2a2a", fg="white",
                                       insertbackground="white", font=("Arial", 9),
                                       wrap="word")
        self._alchemy_effect.insert("1.0", card.get("on_field_effect", ""))
        self._alchemy_effect.bind("<KeyRelease>", self._changed)
        self._alchemy_effect.pack(fill="x", padx=8, pady=2)

    def _result_text_changed(self, text: str):
        self.card["result_text"] = text
        if hasattr(self, "_result_preview"):
            self._result_preview.config(text=text)

    def _changed(self, *_):
        card = self.card
        if hasattr(self, "_ingredients"):
            card["ingredients"] = self._ingredients.get()
        if hasattr(self, "_alchemy_effect"):
            card["on_field_effect"] = self._alchemy_effect.get("1.0", "end-1c")
        if self.on_change: self.on_change()


# ── Renderer ──────────────────────────────────────────────────────────────────

class AlchemyCardRenderer:
    FF   = "Palatino Linotype"
    FS_S = 11
    PAD  = 8

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.W   = CARD_W
        self.H   = CARD_H
        self._img = None

    def render(self, card: dict):
        c = self.canvas
        c.delete("all")
        P = self.PAD

        c.create_rectangle(0, 0, self.W, self.H, fill="#1a2a1a", outline="")
        c.create_rectangle(2, 2, self.W-2, self.H-2,
                           outline="#55aa55", width=2)

        # Name
        c.create_text(P, P, text=card.get("name", ""), anchor="nw",
                      font=(self.FF, 16, "bold"), fill="#aaffaa")

        # Artwork
        AY0, AY1 = 36, 190
        self._draw_art(card.get("artwork", ""), P, AY0, self.W-P, AY1)

        y = AY1 + 6

        # Ingredients
        c.create_text(P, y, text="Zutaten:", anchor="nw",
                      fill="#888", font=(self.FF, 10, "bold"))
        y += 18
        ings = card.get("ingredients", [])
        tx   = P
        for ing in ings:
            tw = len(ing) * 7 + 10
            if tx + tw > self.W - P:
                tx = P; y += 22
            c.create_rectangle(tx, y, tx+tw, y+18,
                               fill="#1a3a1a", outline="#55aa55")
            c.create_text(tx+tw//2, y+9, text=ing,
                          fill="#aaffaa", font=("Arial", 9))
            tx += tw + 4
        y += 26

        # Result box
        res_text = card.get("result_text", "")
        if not res_text:
            rid = card.get("result", {}).get("content_id", "")
            res_text = rid or ""
        if res_text:
            RH = 70
            c.create_rectangle(P, y, self.W-P, y+RH,
                               fill="#2a1a00", outline="#cc8800")
            c.create_text(P+4, y+3, text="⚗ Ergebnis", anchor="nw",
                          fill="#cc8800", font=(self.FF, 9, "bold"))
            font   = (self.FF, self.FS_S)
            lines  = self._wrap_lines(res_text, self.W-P*2-8, font)
            line_h = self.FS_S + 5
            total  = len(lines) * line_h
            sy     = y + 18 + max(0, (RH-18-total)//2)
            for line in lines:
                if sy + line_h > y + RH - 2: break
                c.create_text(P+4, sy, text=line, anchor="nw",
                              font=font, fill="#ffdd88")
                sy += line_h
            y += RH + 6

        # On-field effect
        eff = card.get("on_field_effect", "")
        if eff:
            BOT = self.H - P
            c.create_rectangle(P, y, self.W-P, BOT,
                               fill="#111", outline="#555")
            c.create_text(P+4, y+3, text="On-Field:", anchor="nw",
                          fill="#888", font=(self.FF, 9, "bold"))
            font   = (self.FF, self.FS_S)
            lines  = self._wrap_lines(eff, self.W-P*2-8, font)
            line_h = self.FS_S + 5
            avail  = BOT - y - 18 - P
            total  = len(lines) * line_h
            sy     = y + 18 + max(0, (avail - total) // 2)
            for line in lines:
                if sy + line_h > BOT - P: break
                c.create_text(P+4, sy, text=line, anchor="nw",
                              font=font, fill="white")
                sy += line_h

    def _draw_art(self, path, x0, y0, x1, y1):
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill="#111", outline="#444")
        if path and _PIL:
            import os
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    w, h = x1-x0, y1-y0
                    iw, ih = img.size
                    s = max(w/iw, h/ih)
                    nw, nh = int(iw*s), int(ih*s)
                    img = img.resize((nw, nh), Image.LANCZOS)
                    l, t = (nw-w)//2, (nh-h)//2
                    img = img.crop((l, t, l+w, t+h))
                    self._img = ImageTk.PhotoImage(img)
                    c.create_image(x0, y0, image=self._img, anchor="nw")
                    return
                except Exception:
                    pass
        c.create_text((x0+x1)//2, (y0+y1)//2,
                      text="Artwork", fill="#444", font=(self.FF, 11))

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
