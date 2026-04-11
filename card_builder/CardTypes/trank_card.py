"""
trank_card.py – Editor and renderer for Trank (potion) cards.

Layout:
  - Name + type badge (header, via BaseCardEditor)
  - Artwork (top portion)
  - Charges strip (row of circles)
  - Ingredients section (middle) — TagSelector with material pills
  - Effects section (lower) — per-ingredient effect lookup from material_effects
  - Charges badge (bottom center)

Effects shown are NOT stored in the card dict — they are looked up dynamically
from materials.json via load_material_effects() at both edit-time and render-time.
"""

import random
import tkinter as tk
from tkinter import ttk

from card_builder.CardTypes.base_card import BaseCardEditor, TagSelector
from card_builder.materials import merged_materials, load_material_effects
from card_builder.constants import CARD_W, CARD_H

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False


# ── Helper constants ──────────────────────────────────────────────────────────

TRANK_NAMES = [
    "Heiltrank", "Frostelixier", "Bluttrank", "Naturessenz",
    "Schattentropfen", "Glutessenz", "Eiswasser", "Lebenstrank",
    "Giftkur", "Stahlsud", "Quintafluid", "Mondtau", "Erdextrakt",
    "Feuerbalsam", "Silbertropfen", "Dunkelbrühe", "Himmelsessenz",
    "Wutgebräu", "Stärketrank", "Geistertau",
]


# ── Editor ────────────────────────────────────────────────────────────────────

class TrankCardEditor(BaseCardEditor):
    """
    Editor for Trank cards.

    Card dict structure:
        {
            "name":        str,
            "card_type":   "Trank",
            "artwork":     str,
            "ingredients": [str, ...],
            "charges":     int,
        }

    Effects are NOT stored in the card — they are derived at display time from
    material_effects in materials.json.
    """

    def _build_type_fields(self):
        ef   = self._f
        card = self.card

        # ── Ingredients ───────────────────────────────────────────────────────
        self._lbl("Zutaten (Materialien):").pack(anchor="w", padx=8, pady=(6, 0))
        all_mats = merged_materials()
        self._ingredients = TagSelector(
            ef,
            values=all_mats,
            selected=card.get("ingredients", []),
            on_change=self._changed,
            bg=self.BG,
        )
        self._ingredients.pack(fill="x", padx=8, pady=2)

        # ── Charges ───────────────────────────────────────────────────────────
        charges_row = self._row()
        self._lbl("Ladungen:", parent=charges_row).pack(side="left")
        self._charges_var = tk.StringVar(value=str(card.get("charges", 1)))
        self._charges_var.trace_add("write", self._changed)
        tk.Spinbox(
            charges_row,
            from_=1, to=10,
            textvariable=self._charges_var,
            width=4,
            bg="#2a2a2a", fg="white",
            buttonbackground="#333",
            insertbackground="white",
            font=("Arial", 9),
        ).pack(side="left", padx=4)

        # ── Effects preview ───────────────────────────────────────────────────
        prev_frame = tk.Frame(ef, bg=self.BG)
        prev_frame.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(
            prev_frame, text="Effekte aus Zutaten:",
            bg=self.BG, fg="#aaaaaa",
            font=("Arial", 9, "bold"),
        ).pack(anchor="w")
        self._effects_label = tk.Label(
            prev_frame, text="",
            bg="#1a1a2a", fg="#aaaaff",
            font=("Arial", 9), wraplength=400,
            anchor="w", justify="left",
        )
        self._effects_label.pack(fill="x", padx=4, pady=2)
        self._update_effects_preview()

        self._sep()

        # ── Random generator button ───────────────────────────────────────────
        btn_row = self._row()
        tk.Button(
            btn_row, text="🎲 Zufälliger Trank",
            command=self._generate_random,
            bg="#2a1a4a", fg="#ccaaff",
            font=("Arial", 9, "bold"),
            cursor="hand2",
        ).pack(side="left", padx=2)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _changed(self, *_):
        """Sync widget state back into card dict and notify."""
        card = self.card
        if hasattr(self, "_ingredients"):
            card["ingredients"] = self._ingredients.get()
        if hasattr(self, "_charges_var"):
            try:
                card["charges"] = int(self._charges_var.get())
            except ValueError:
                pass
        self._update_effects_preview()
        if self.on_change:
            self.on_change()

    def _update_effects_preview(self):
        """Rebuild the effects preview label from current ingredients."""
        if not hasattr(self, "_effects_label"):
            return

        mat_effects = load_material_effects()
        ingredients = self.card.get("ingredients", [])

        lines = []
        for ing in ingredients:
            entry = mat_effects.get(ing)
            if entry and entry.get("effect_id"):
                eid  = entry["effect_id"]
                vals = entry.get("vals", {})
                vals_str = ", ".join(f"{k}={v}" for k, v in vals.items())
                if vals_str:
                    lines.append(f"• {ing}: {eid} ({vals_str})")
                else:
                    lines.append(f"• {ing}: {eid}")

        if lines:
            self._effects_label.config(text="\n".join(lines))
        else:
            self._effects_label.config(
                text="(keine Zutaten mit bekannten Effekten)"
            )

    def _generate_random(self):
        """Fill card with a randomised set of ingredients, name and charges."""
        from card_builder.data import get_content_data

        mat_effects = load_material_effects()
        CD          = get_content_data()

        # Collect materials that have a valid effect
        valid = []
        for mat, entry in mat_effects.items():
            eid = entry.get("effect_id", "")
            if not eid:
                continue
            # Check allowed_in: if the effect has an "allowed_in" list it must
            # include "Tränke" (or be empty / absent → always allowed).
            effect_item = CD.get("effect", eid)
            if effect_item is not None:
                allowed = effect_item.get("allowed_in", [])
                if allowed and "Tränke" not in allowed:
                    continue
            valid.append(mat)

        # If nothing passed the filter fall back to all materials with effects
        if not valid:
            valid = [m for m, e in mat_effects.items() if e.get("effect_id")]

        # Fallback: pick from all known materials
        if not valid:
            valid = merged_materials()

        count       = random.randint(1, min(3, len(valid)))
        ingredients = random.sample(valid, count)

        self.card["ingredients"] = ingredients
        self.card["charges"]     = random.randint(1, 5)
        self.card["name"]        = random.choice(TRANK_NAMES)

        # Refresh widgets to reflect new values
        if hasattr(self, "_ingredients"):
            # TagSelector has no full "set" API; rebuild by manipulating its
            # internal list and re-rendering the pills.
            self._ingredients._sel = list(ingredients)
            self._ingredients._rebuild()

        if hasattr(self, "_charges_var"):
            self._charges_var.set(str(self.card["charges"]))

        if hasattr(self, "_name_var"):
            self._name_var.set(self.card["name"])

        self._update_effects_preview()
        if self.on_change:
            self.on_change()


# ── Renderer ──────────────────────────────────────────────────────────────────

class TrankCardRenderer:
    """Canvas renderer for Trank cards."""

    FF   = "Palatino Linotype"
    FS   = 11        # body font size
    FS_S = 9         # small font size
    PAD  = 8

    # Layout y-anchors (approximate)
    NAME_Y0    = 0
    NAME_Y1    = 36
    ART_Y0     = 36
    ART_Y1     = 260
    ING_Y0     = 260
    ING_Y1     = 302
    EFF_Y0     = 302
    BADGE_H    = 30   # height of bottom badge strip

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.W      = CARD_W
        self.H      = CARD_H
        self._img   = None

    # ── Public entry point ────────────────────────────────────────────────────

    def render(self, card: dict):
        c = self.canvas
        c.delete("all")
        P = self.PAD

        # Background + border
        c.create_rectangle(0, 0, self.W, self.H, fill="#121218", outline="")
        c.create_rectangle(2, 2, self.W - 2, self.H - 2,
                           outline="#666666", width=2)

        # Name strip
        c.create_rectangle(0, self.NAME_Y0, self.W, self.NAME_Y1,
                           fill="#1a1a2e", outline="")
        c.create_text(P, self.NAME_Y0 + P,
                      text=card.get("name", "Trank"),
                      anchor="nw",
                      font=(self.FF, 16, "bold"),
                      fill="white")

        # Charges display (top-right, inside name strip)
        charges = int(card.get("charges", 1))
        self._draw_charges_strip(charges,
                                 x_right=self.W - P,
                                 y_center=self.NAME_Y0 + self.NAME_Y1 // 2)

        # Artwork
        self._draw_art(card.get("artwork", ""),
                       P, self.ART_Y0,
                       self.W - P, self.ART_Y1)

        # Ingredients section
        self._draw_ingredients(card, P)

        # Effects section
        eff_bottom = self.H - self.BADGE_H - 4
        self._draw_effects(card, P, self.EFF_Y0, eff_bottom)

        # Bottom badge: charge count centered
        self._draw_charges_badge(charges, eff_bottom)

    # ── Sub-renderers ─────────────────────────────────────────────────────────

    def _draw_charges_strip(self, charges: int, x_right: int, y_center: int):
        """Row of small circles for charges, right-aligned in name strip."""
        c      = self.canvas
        r      = 6
        gap    = 4
        total  = charges * (r * 2 + gap) - gap
        x      = x_right - total
        y0     = y_center - r

        for _ in range(charges):
            c.create_oval(x, y0, x + r * 2, y0 + r * 2,
                          fill="#2a2a5a", outline="#aaaaff", width=1)
            x += r * 2 + gap

    def _draw_art(self, path, x0, y0, x1, y1):
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill="#111122", outline="#444455")
        if path and _PIL:
            import os
            if os.path.exists(path):
                try:
                    img  = Image.open(path)
                    w, h = x1 - x0, y1 - y0
                    iw, ih = img.size
                    s    = max(w / iw, h / ih)
                    nw, nh = int(iw * s), int(ih * s)
                    img  = img.resize((nw, nh), Image.LANCZOS)
                    l, t = (nw - w) // 2, (nh - h) // 2
                    img  = img.crop((l, t, l + w, t + h))
                    self._img = ImageTk.PhotoImage(img)
                    c.create_image(x0, y0, image=self._img, anchor="nw")
                    return
                except Exception:
                    pass
        c.create_text((x0 + x1) // 2, (y0 + y1) // 2,
                      text="Artwork", fill="#444455",
                      font=(self.FF, self.FS))

    def _draw_ingredients(self, card: dict, pad: int):
        """Ingredient pills row (ING_Y0 → ING_Y1)."""
        c    = self.canvas
        y0   = self.ING_Y0
        y1   = self.ING_Y1
        P    = pad

        c.create_rectangle(0, y0, self.W, y1, fill="#18181e", outline="")
        c.create_text(P, y0 + 4, text="Zutaten:",
                      anchor="nw", fill="#888899",
                      font=(self.FF, self.FS_S, "bold"))

        ings = card.get("ingredients", [])
        tx   = P + 56   # leave room for "Zutaten:" label
        py   = y0 + 4

        for ing in ings:
            tw = len(ing) * 6 + 10
            if tx + tw > self.W - P:
                tx = P
                py += 20
                if py + 16 > y1:
                    break
            c.create_rectangle(tx, py, tx + tw, py + 16,
                               fill="#2a1a4a", outline="#8855aa")
            c.create_text(tx + tw // 2, py + 8,
                          text=ing, fill="#ddaaff",
                          font=("Arial", self.FS_S),
                          anchor="center")
            tx += tw + 4

    def _draw_effects(self, card: dict, pad: int, y_top: int, y_bottom: int):
        """Effect lines for each ingredient that has a material_effect."""
        c    = self.canvas
        P    = pad

        # Section background
        c.create_rectangle(0, y_top, self.W, y_bottom,
                           fill="#0e0e18", outline="")

        from card_builder.data import get_content_data
        mat_effects = load_material_effects()
        CD          = get_content_data()

        ings  = card.get("ingredients", [])
        lines = []   # list of (label, text) pairs

        for ing in ings:
            entry = mat_effects.get(ing)
            if not entry:
                continue
            eid = entry.get("effect_id", "")
            if not eid:
                continue

            # Try to get human-readable content_text from ContentData
            effect_item = CD.get("effect", eid) if CD else None
            if effect_item:
                raw_ct = (effect_item.get("content_text")
                          or effect_item.get("effect_text", ""))
                if raw_ct:
                    vals = entry.get("vals", {})
                    try:
                        from CardContent.template_parser import render_display_text
                        display = render_display_text(raw_ct, vals, entry.get("opt_vals", {}))
                    except Exception:
                        # Fallback: simple substitution
                        display = raw_ct
                        for k, v in vals.items():
                            display = display.replace(f"{{{k}}}", str(v))
                else:
                    display = self._format_effect_vals(eid, entry)
            else:
                display = self._format_effect_vals(eid, entry)

            lines.append((ing, display))

        # Draw the lines
        lh = self.FS + 6
        y  = y_top + 6

        if not lines:
            c.create_text(P, y, text="(keine Effekte)",
                          anchor="nw", fill="#444455",
                          font=(self.FF, self.FS_S, "italic"))
            return

        # Sort by complexity descending so most complex effects appear first
        def _complexity(pair):
            ing_name, _ = pair
            entry = mat_effects.get(ing_name, {})
            eid   = entry.get("effect_id", "")
            item  = CD.get("effect", eid) if CD and eid else None
            return float(item.get("complexity_base", 1.0)) if item else 1.0
        lines.sort(key=_complexity, reverse=True)

        for (label, text) in lines:
            if y + lh > y_bottom - 2:
                break

            # Ingredient name in accent colour
            label_text = f"{label}: "
            c.create_text(P, y, text=label_text,
                          anchor="nw", fill="#ddaaff",
                          font=(self.FF, self.FS, "bold"))
            label_w = len(label_text) * self.FS * 0.55

            # Effect text in lighter colour, word-wrapped
            max_w = self.W - P * 2 - int(label_w)
            wrapped = self._wrap_lines(text, max_w, (self.FF, self.FS))
            for idx, line in enumerate(wrapped):
                if y + lh > y_bottom - 2:
                    break
                tx = P + int(label_w) if idx == 0 else P + 8
                c.create_text(tx, y, text=line,
                              anchor="nw", fill="#ccccff",
                              font=(self.FF, self.FS))
                y += lh
                label_w = 0   # subsequent lines start at left margin + indent

            # Reminder text — show in italic/grey if there is room
            entry = mat_effects.get(label, {})
            eid   = entry.get("effect_id", "")
            item  = CD.get("effect", eid) if CD and eid else None
            if item:
                rt = item.get("reminder_text", "")
                if rt and y + lh <= y_bottom - 2:
                    vals = entry.get("vals", {})
                    for k, v in vals.items():
                        rt = rt.replace(f"{{{k}}}", str(v))
                    rt_wrapped = self._wrap_lines(f"({rt})", max_w, (self.FF, self.FS_S))
                    for rt_line in rt_wrapped:
                        if y + lh > y_bottom - 2:
                            break
                        c.create_text(P + 10, y, text=rt_line,
                                      anchor="nw", fill="#888899",
                                      font=(self.FF, self.FS_S, "italic"))
                        y += self.FS_S + 5

    def _draw_charges_badge(self, charges: int, y_top: int):
        """Centered numeric charges badge at the bottom."""
        c = self.canvas
        P = self.PAD

        badge_w = 60
        badge_h = self.BADGE_H - 6
        bx      = (self.W - badge_w) // 2
        by      = y_top + 3

        c.create_rectangle(bx, by, bx + badge_w, by + badge_h,
                           fill="#2a2a5a", outline="#aaaaff", width=2)
        c.create_text(bx + badge_w // 2, by + badge_h // 2,
                      text=f"×{charges}",
                      fill="#aaaaff",
                      font=(self.FF, 12, "bold"),
                      anchor="center")

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _format_effect_vals(eid: str, entry: dict) -> str:
        """Compact fallback: 'Heal (X=2)'."""
        vals = entry.get("vals", {})
        if vals:
            vals_str = ", ".join(f"{k}={v}" for k, v in vals.items())
            return f"{eid} ({vals_str})"
        return eid

    @staticmethod
    def _wrap_lines(text: str, max_w: int, font) -> list:
        """Naive word-wrap using character-width estimate."""
        fs    = font[1]
        words = text.split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) * fs * 0.55 > max_w and line:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        return lines or [""]
