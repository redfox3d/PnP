"""
recipe_card.py – Editor and renderer for Recipe cards (Potions, Phials, Tinctures).

Recipes have two sigils:
  - Ingredient sigil: lists materials (each is a cost with its own CV)
  - Effect/Recipe sigil: shows effects derived from ingredients
No artwork, no triggers, no mana costs.
"""

import tkinter as tk
from tkinter import ttk

from card_builder.CardTypes.base_card import BaseCardEditor, _render_content
from card_builder.constants import (
    CARD_W, CARD_H,
    RECIPE_TYPES, RECIPE_TYPE_COLORS, RECIPE_TYPE_ICONS,
    INGREDIENT_CV,
)
from card_builder.materials import merged_materials, save_central_materials, load_central_materials

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False


# ═══════════════════════════════════════════════════════════════════════════════
#  RECIPE CARD EDITOR
# ═══════════════════════════════════════════════════════════════════════════════

class RecipeCardEditor(BaseCardEditor):

    def _build_type_fields(self):
        ef   = self._f
        card = self.card

        # ── Ingredients section ───────────────────────────────────────────────
        self._lbl("Zutaten (Kosten):").pack(anchor="w", padx=8)

        ctrl = tk.Frame(ef, bg=self.BG)
        ctrl.pack(fill="x", padx=8, pady=2)

        all_mats = merged_materials()
        self._new_ing_var = tk.StringVar()
        ttk.Combobox(ctrl, textvariable=self._new_ing_var,
                     values=all_mats, width=20).pack(side="left", padx=2)
        tk.Button(ctrl, text="+ Zutat", command=self._add_ingredient,
                  bg="#1a6e3c", fg="white", font=("Arial", 8)).pack(
            side="left", padx=4)

        self._ing_frame = tk.Frame(ef, bg=self.BG)
        self._ing_frame.pack(fill="x", padx=8, pady=4)
        self._rebuild_ingredients()

        self._sep()

        # ── Effects section ───────────────────────────────────────────────────
        self._lbl("Effekte:").pack(anchor="w", padx=8)
        self._use_text = tk.Text(ef, height=5, bg="#2a2a2a", fg="white",
                                 insertbackground="white", font=("Arial", 9),
                                 wrap="word")
        self._use_text.insert("1.0", card.get("use_text", ""))
        self._use_text.bind("<KeyRelease>", self._on_use_change)
        self._use_text.pack(fill="x", padx=8, pady=2)

    # ── Ingredients ───────────────────────────────────────────────────────────

    def _rebuild_ingredients(self):
        for w in self._ing_frame.winfo_children():
            w.destroy()
        for idx, ing in enumerate(self.card.get("ingredients", [])):
            self._build_ingredient_row(idx, ing)

    def _build_ingredient_row(self, idx: int, ing: dict):
        bg = "#1e2a2a"
        row = tk.Frame(self._ing_frame, bg=bg, relief="groove", bd=1)
        row.pack(fill="x", pady=1)

        tk.Button(row, text="✕", font=("Arial", 8), cursor="hand2",
                  bg="#3a1a1a", fg="#ff8888", width=2,
                  command=lambda i=idx: self._remove_ingredient(i)
                  ).pack(side="left", padx=2, pady=2)

        tk.Label(row, text=ing.get("material", "?"), bg=bg, fg="#aaffaa",
                 font=("Arial", 9, "bold"), width=16, anchor="w"
                 ).pack(side="left", padx=4)

        tk.Label(row, text="CV:", bg=bg, fg="#888",
                 font=("Arial", 8)).pack(side="left", padx=2)
        cv_var = tk.StringVar(value=str(ing.get("cv", INGREDIENT_CV)))
        tk.Entry(row, textvariable=cv_var, width=4,
                 bg="#2a2a2a", fg="white", insertbackground="white",
                 font=("Arial", 8)).pack(side="left", padx=2)

        def _cv_change(*_, v=cv_var, i=idx):
            try:
                self.card["ingredients"][i]["cv"] = max(0, int(float(v.get())))
            except (ValueError, IndexError):
                pass
            self._changed()

        cv_var.trace_add("write", _cv_change)

    def _add_ingredient(self):
        mat = self._new_ing_var.get().strip()
        if not mat:
            return
        ingredients = self.card.setdefault("ingredients", [])
        ingredients.append({"material": mat, "cv": INGREDIENT_CV})
        existing = load_central_materials()
        save_central_materials(existing + [mat])
        self._rebuild_ingredients()
        self._new_ing_var.set("")
        self._changed()

    def _remove_ingredient(self, idx: int):
        ingredients = self.card.get("ingredients", [])
        if 0 <= idx < len(ingredients):
            ingredients.pop(idx)
        self._rebuild_ingredients()
        self._changed()

    def _on_use_change(self, *_):
        self.card["use_text"] = self._use_text.get("1.0", "end-1c")
        self._changed()

    def _changed(self, *_):
        if self.on_change:
            self.on_change()


# ═══════════════════════════════════════════════════════════════════════════════
#  RECIPE CARD RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

class RecipeCardRenderer:
    FF   = "Palatino Linotype"
    FS   = 13
    FS_S = 10

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.W  = CARD_W
        self.H  = CARD_H
        self._img = None

    def render(self, card: dict):
        c  = self.canvas
        c.delete("all")
        ct    = card.get("card_type", "Potions")
        rtype = card.get("recipe_type", ct)

        color = RECIPE_TYPE_COLORS.get(rtype, "#333")
        icon  = RECIPE_TYPE_ICONS.get(rtype, "?")

        # Background + colored border
        c.create_rectangle(0, 0, self.W, self.H, fill="#1a1a1a", outline="")
        c.create_rectangle(0, 0, self.W, self.H, fill=color, outline="",
                           stipple="gray25")
        c.create_rectangle(2, 2, self.W-2, self.H-2, outline=color, width=3)

        PAD = 8

        # Name (top-left)
        c.create_text(PAD, PAD, text=card.get("name", ""),
                      anchor="nw", font=(self.FF, 16, "bold"), fill="white")

        # Recipe type icon (top-right)
        cx = self.W - 30
        cy = 26
        c.create_oval(cx-22, cy-22, cx+22, cy+22,
                      fill=color, outline="gold", width=2)
        c.create_text(cx, cy, text=icon, font=("Arial", 16))

        # Artwork
        ART_Y0 = 36
        ART_Y1 = ART_Y0 + 160
        self._artwork_box(card.get("artwork", ""), PAD, ART_Y0,
                          self.W - 60, ART_Y1)

        ingredients = card.get("ingredients", [])

        # ── Sigil layout: split remaining space into two blocks ───────────────
        SIGIL_TOP = ART_Y1 + 6
        SIGIL_BOT = self.H - 40
        SIGIL_MID = SIGIL_TOP + (SIGIL_BOT - SIGIL_TOP) // 2

        # ── Ingredient Sigil (top half) ───────────────────────────────────────
        ing_color = "#8B6914"  # amber/golden
        c.create_rectangle(PAD, SIGIL_TOP, self.W - PAD, SIGIL_MID - 2,
                           fill=ing_color, outline="#888", width=1,
                           stipple="gray50")
        c.create_text(PAD + 4, SIGIL_TOP + 4, text="[Ingredients]",
                      anchor="nw", font=(self.FF, 10, "bold"), fill="white")

        y = SIGIL_TOP + 26
        for ing in ingredients:
            mat = ing.get("material", "?")
            cv  = ing.get("cv", INGREDIENT_CV)
            if y + 18 > SIGIL_MID - 4:
                break
            c.create_text(PAD + 12, y, text=f"• {mat}",
                          anchor="nw", fill="#ffdd88",
                          font=(self.FF, self.FS_S))
            c.create_text(self.W - PAD - 8, y, text=f"CV {cv}",
                          anchor="ne", fill="#aa8833",
                          font=(self.FF, 9))
            y += 18

        # ── Effect Sigil (bottom half) ────────────────────────────────────────
        eff_color = "#1a3e8e"  # blue
        c.create_rectangle(PAD, SIGIL_MID + 2, self.W - PAD, SIGIL_BOT,
                           fill=eff_color, outline="#888", width=1,
                           stipple="gray50")
        c.create_text(PAD + 4, SIGIL_MID + 6, text="[Recipe Effect]",
                      anchor="nw", font=(self.FF, 10, "bold"), fill="white")

        use = card.get("use_text", "")
        if use:
            self._wrap(use, PAD + 12, SIGIL_MID + 28,
                       self.W - PAD*2 - 16, (self.FF, self.FS_S),
                       "white", SIGIL_BOT - 4)

        # ── CV badge (bottom) ─────────────────────────────────────────────────
        total_cv = sum(ing.get("cv", INGREDIENT_CV) for ing in ingredients)
        c.create_rectangle(self.W - 70, self.H - 34, self.W - PAD, self.H - PAD,
                           fill="#2a2200", outline="gold", width=2)
        c.create_text(self.W - 38, self.H - 18, text=f"CV {total_cv}",
                      fill="gold", font=(self.FF, 11, "bold"))

        # Recipe type label bottom-left
        c.create_text(PAD, self.H - 18, text=rtype,
                      anchor="w", font=(self.FF, 9, "italic"), fill="#aaa")

    def _artwork_box(self, path, x0, y0, x1, y1):
        c = self.canvas
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
                    left = (nw-w)//2; top_ = (nh-h)//2
                    img = img.crop((left, top_, left+w, top_+h))
                    self._img = ImageTk.PhotoImage(img)
                    c.create_image(x0, y0, image=self._img, anchor="nw")
                    return
                except Exception:
                    pass
        c.create_text((x0+x1)//2, (y0+y1)//2,
                      text="Artwork", fill="#444",
                      font=(self.FF, self.FS_S))

    def _wrap(self, text, x, y, max_w, font, color, y_max):
        c      = self.canvas
        line_h = font[1] + 5
        words  = text.split()
        line   = ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) * font[1] * 0.55 > max_w and line:
                if y + line_h > y_max:
                    return y
                c.create_text(x, y, text=line, anchor="nw", font=font, fill=color)
                y += line_h
                line = word
            else:
                line = test
        if line and y + line_h <= y_max:
            c.create_text(x, y, text=line, anchor="nw", font=font, fill=color)
            y += line_h
        return y
