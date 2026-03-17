import json
import os
import re
import math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter import font as tkfont
import copy

# ─────────────────────────────────────────────
#  PATHS  (relative to this script)
# ─────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = BASE_DIR                        # jsons live next to this script
CARDS_FILE  = os.path.join(BASE_DIR, "cards.json")

EFFECT_FILE    = os.path.join(DATA_DIR, "effects.json")
TRIGGER_FILE   = os.path.join(DATA_DIR, "triggers.json")
CONDITION_FILE = os.path.join(DATA_DIR, "conditions.json")
COST_FILE      = os.path.join(DATA_DIR, "costs.json")

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────
BLOCK_TYPES = [
    "Excavate", "Hand", "Play", "Enchantment",
    "Graveyard", "Exile", "Banished Facedown"
]

ABILITY_TYPES = ["Trigger", "Play", "Continues", "Activate"]

ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Meta", "Potion", "Skills"]

# Block colours (RGBA-ish — we use semi-transparent overlays on canvas)
BLOCK_COLORS = {
    "Excavate":        "#8B6914",
    "Hand":            "#1a6e3c",
    "Play":            "#1a3e8e",
    "Enchantment":     "#6a1a8e",
    "Graveyard":       "#3a3a3a",
    "Exile":           "#8e1a1a",
    "Banished Facedown":"#1a6e8e",
}

ELEMENT_ICONS = {
    "Fire":   "🔥", "Metal": "⚙️", "Ice":   "❄️", "Nature":"🌿",
    "Blood":  "🩸", "Meta":  "✨", "Potion":"⚗️", "Skills":"⚔️",
}

# Symbol sets for the "artwork" strip
BLOCK_SYMBOLS = {
    "Excavate":        "⛏", "Hand":            "✋",
    "Play":            "▶", "Enchantment":     "✦",
    "Graveyard":       "☠", "Exile":           "⊗",
    "Banished Facedown":"◼",
}
TYPE_SYMBOLS  = {"Trigger":"⚡","Play":"▶","Continues":"∞","Activate":"⚙"}
COND_SYMBOL   = "◈"
EFFECT_SYMBOL = "◆"
COST_SYMBOL   = "◉"

# Magic card dimensions at 96 dpi: 63mm × 88mm ≈ 238 × 333 px
CARD_W = 238
CARD_H = 333
ARTWORK_W = 44   # right-side artwork strip width

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def load_json_list(path, key):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get(key, [])
    return []

def save_cards(cards):
    with open(CARDS_FILE, "w") as f:
        json.dump({"cards": cards}, f, indent=4)

def load_cards():
    if os.path.exists(CARDS_FILE):
        with open(CARDS_FILE) as f:
            return json.load(f).get("cards", [])
    return []

def parse_placeholders(text):
    """Return list of unique placeholder names like X, Y, N from {X}, {Y}, {N}."""
    return list(dict.fromkeys(re.findall(r"\{([A-Za-z0-9_]+)\}", text)))

def fill_placeholders(text, values: dict):
    """Replace {X} with values[X] if present."""
    def repl(m):
        k = m.group(1)
        return str(values.get(k, m.group(0)))
    return re.sub(r"\{([A-Za-z0-9_]+)\}", repl, text)

# ─────────────────────────────────────────────
#  DATA LOADER
# ─────────────────────────────────────────────
class ContentData:
    def __init__(self):
        self.effects    = load_json_list(EFFECT_FILE,    "Effect")
        self.triggers   = load_json_list(TRIGGER_FILE,   "Trigger")
        self.conditions = load_json_list(CONDITION_FILE, "Condition")
        self.costs      = load_json_list(COST_FILE,      "Cost")

    def ids(self, kind):
        return [i["id"] for i in getattr(self, kind+"s", [])]

    def get(self, kind, id_):
        lst = getattr(self, kind+"s", [])
        return next((i for i in lst if i["id"] == id_), None)

    def effect_ids(self):  return [i["id"] for i in self.effects]
    def trigger_ids(self): return [i["id"] for i in self.triggers]
    def condition_ids(self): return [i["id"] for i in self.conditions]
    def cost_ids(self):    return [i["id"] for i in self.costs]

CD = ContentData()

# ─────────────────────────────────────────────
#  CARD DATA MODEL
# ─────────────────────────────────────────────
def empty_card():
    return {
        "name": "New Card",
        "element": "Fire",
        "blocks": [],   # list of block dicts
    }

def empty_block(btype="Play"):
    return {
        "type": btype,
        "abilities": [],   # list of ability dicts
    }

def empty_ability():
    return {
        "condition_id": None,
        "condition_vals": {},
        "ability_type": "Play",
        "costs": [],         # list of {"cost_id": ..., "vals": {...}}
        "effects": [],       # list of {"effect_id": ..., "vals": {...}}
        "choose_n": None,    # None or int
        "choose_repeat": False,
    }

# ─────────────────────────────────────────────
#  CARD RENDERER  (Canvas-based preview)
# ─────────────────────────────────────────────
class CardRenderer:
    FONT_FAMILY = "Palatino Linotype"   # close to Magic's font
    FONT_SIZE   = 7                     # pt – Magic uses ~7–8pt

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.W = CARD_W
        self.H = CARD_H
        self.AW = ARTWORK_W
        self.TEXT_W = self.W - self.AW - 8

    # ── public ──────────────────────────────

    def render(self, card: dict):
        c = self.canvas
        c.delete("all")

        # background gradient (dark parchment)
        self._bg(card.get("element","Fire"))

        # black border
        c.create_rectangle(2, 2, self.W-2, self.H-2,
                           outline="black", width=3)

        # card name top
        c.create_text(8, 8, text=card.get("name",""), anchor="nw",
                      font=(self.FONT_FAMILY, 9, "bold"), fill="white")

        # element icon top-right circle
        elem = card.get("element","Fire")
        icon = ELEMENT_ICONS.get(elem, "?")
        cx, cy = self.W - self.AW//2 - 2, 14
        c.create_oval(cx-12, cy-12, cx+12, cy+12,
                      fill=self._elem_color(elem), outline="gold", width=2)
        c.create_text(cx, cy, text=icon, font=("Arial", 9))

        # artwork strip (right side, bottom to top)
        self._render_artwork(card)

        # content blocks (left side)
        self._render_blocks(card)

    # ── private ─────────────────────────────

    def _bg(self, element):
        c = self.canvas
        color = self._elem_color(element)
        # dark base
        c.create_rectangle(0, 0, self.W, self.H, fill="#1a1a1a", outline="")
        # subtle element tint overlay
        c.create_rectangle(0, 0, self.W, self.H,
                           fill=color, outline="", stipple="gray25")

    def _elem_color(self, elem):
        MAP = {
            "Fire":"#c0392b","Metal":"#7f8c8d","Ice":"#2980b9",
            "Nature":"#27ae60","Blood":"#8e0000","Meta":"#8e44ad",
            "Potion":"#16a085","Skills":"#d35400",
        }
        return MAP.get(elem, "#555555")

    def _render_artwork(self, card):
        c = self.canvas
        x0 = self.W - self.AW - 2
        y0 = 28
        y1 = self.H - 4
        # strip background
        c.create_rectangle(x0, y0, self.W-4, y1,
                           fill="#111111", outline="#444")

        # collect symbols
        symbols = []
        for blk in card.get("blocks", []):
            symbols.append(BLOCK_SYMBOLS.get(blk["type"], "?"))
            for ab in blk.get("abilities", []):
                if ab.get("condition_id"):
                    symbols.append(COND_SYMBOL)
                symbols.append(TYPE_SYMBOLS.get(ab.get("ability_type",""), "·"))
                for _ in ab.get("costs",  []): symbols.append(COST_SYMBOL)
                for _ in ab.get("effects",[]): symbols.append(EFFECT_SYMBOL)

        # draw bottom to top
        step = 12
        y = y1 - 8
        for sym in reversed(symbols):
            if y < y0 + 6:
                break
            c.create_text(x0 + self.AW//2, y, text=sym,
                          font=("Arial", 8), fill="#cccccc", anchor="center")
            y -= step

    def _render_blocks(self, card):
        c = self.canvas
        blocks = card.get("blocks", [])
        if not blocks:
            c.create_text(self.W//2 - self.AW//2, self.H//2,
                          text="No blocks", fill="#555", font=(self.FONT_FAMILY, 9))
            return

        # Measure available height
        TOP = 26
        BOTTOM = self.H - 4
        total_h = BOTTOM - TOP
        block_count = len(blocks)
        block_h = total_h // block_count

        for i, blk in enumerate(blocks):
            y0 = TOP + i * block_h
            y1 = y0 + block_h
            btype = blk["type"]
            col = BLOCK_COLORS.get(btype, "#333333")

            # block bg
            c.create_rectangle(4, y0, self.W - self.AW - 6, y1,
                               fill=col, outline="#888", width=1,
                               stipple="gray50")

            # block label
            c.create_text(6, y0+2, text=f"[{btype}]",
                          anchor="nw", font=(self.FONT_FAMILY, 6, "bold"),
                          fill="white")

            inner_y = y0 + 13
            for ab in blk.get("abilities", []):
                inner_y = self._render_ability(ab, inner_y, y1 - 2)
                if inner_y >= y1:
                    break

    def _render_ability(self, ab, y_start, y_max):
        c = self.canvas
        x = 6
        max_w = self.W - self.AW - 16
        FONT_N = (self.FONT_FAMILY, self.FONT_SIZE)
        FONT_B = (self.FONT_FAMILY, self.FONT_SIZE, "bold")
        FONT_I = (self.FONT_FAMILY, self.FONT_SIZE, "italic")
        line_h = self.FONT_SIZE + 4

        y = y_start

        # condition line
        if ab.get("condition_id"):
            cond = CD.get("condition", ab["condition_id"])
            if cond:
                txt = fill_placeholders(cond.get("effect_text",""), ab.get("condition_vals",{}))
                txt = re.sub(r"\\(\w+)", r"\1", txt)
                y = self._wrap_text(txt, x, y, max_w, FONT_N, "#ffdd88", y_max)

        # type + costs
        atype = ab.get("ability_type","Play")
        cost_parts = []
        for ci in ab.get("costs", []):
            co = CD.get("cost", ci["cost_id"])
            if co:
                ct = fill_placeholders(co.get("effect_text",""), ci.get("vals",{}))
                ct = re.sub(r"\\(\w+)", r"\1", ct)
                cost_parts.append(ct)
        cost_str = ", ".join(cost_parts)
        type_line = f"{atype}: {cost_str}" if cost_str else atype
        if y + line_h <= y_max:
            c.create_text(x, y, text=type_line, anchor="nw",
                          font=FONT_B, fill="#aaddff")
            y += line_h

        # choose N
        if ab.get("choose_n"):
            n = ab["choose_n"]
            rep = " You can choose the same multiple times." if ab.get("choose_repeat") else ""
            choose_txt = f"Choose {n}.{rep}"
            y = self._wrap_text(choose_txt, x+4, y, max_w-4, FONT_N, "#ffaaff", y_max)

        # effects
        for ei in ab.get("effects", []):
            eff = CD.get("effect", ei["effect_id"])
            if eff:
                etxt = fill_placeholders(eff.get("effect_text",""), ei.get("vals",{}))
                etxt = re.sub(r"\\(\w+)", r"\1", etxt)
                bullet = f"• {etxt}"
                y = self._wrap_text(bullet, x+4, y, max_w-4, FONT_N, "white", y_max)

        return y + 2

    def _wrap_text(self, text, x, y, max_w, font, color, y_max):
        """Simple word-wrap text drawing; returns new y."""
        c = self.canvas
        line_h = font[1] + 4
        words = text.split()
        line = ""
        for w in words:
            test = (line + " " + w).strip()
            # estimate width: ~0.55 * font_size * chars
            if len(test) * font[1] * 0.55 > max_w and line:
                if y + line_h > y_max:
                    return y
                c.create_text(x, y, text=line, anchor="nw", font=font, fill=color)
                y += line_h
                line = w
            else:
                line = test
        if line and y + line_h <= y_max:
            c.create_text(x, y, text=line, anchor="nw", font=font, fill=color)
            y += line_h
        return y


# ─────────────────────────────────────────────
#  PLACEHOLDER FRAME  (fills {X} etc.)
# ─────────────────────────────────────────────
class PlaceholderFrame(tk.Frame):
    """Tiny widget showing entry fields for each {X} in a text."""
    def __init__(self, parent, text: str, values: dict, on_change, **kw):
        super().__init__(parent, **kw)
        self.values = values
        self.on_change = on_change
        self._vars = {}
        self._build(text)

    def _build(self, text):
        for w in self.winfo_children():
            w.destroy()
        placeholders = parse_placeholders(text)
        if not placeholders:
            return
        tk.Label(self, text="Vars:", font=("Arial",8)).pack(side="left")
        for ph in placeholders:
            tk.Label(self, text=f"{ph}=", font=("Arial",8)).pack(side="left")
            var = tk.StringVar(value=str(self.values.get(ph, "")))
            self._vars[ph] = var
            var.trace_add("write", lambda *_, ph=ph, var=var: self._changed(ph, var))
            e = tk.Entry(self, textvariable=var, width=4, font=("Arial",8))
            e.pack(side="left", padx=1)

    def _changed(self, ph, var):
        self.values[ph] = var.get()
        self.on_change()

    def update_text(self, text):
        self._build(text)


# ─────────────────────────────────────────────
#  ABILITY EDITOR  (one ability / row)
# ─────────────────────────────────────────────
class AbilityEditor(tk.Frame):
    def __init__(self, parent, ability: dict, on_change, on_delete, **kw):
        super().__init__(parent, relief="groove", bd=1, **kw)
        self.ability   = ability
        self.on_change = on_change
        self.on_delete = on_delete
        self._ph_frames = []  # placeholder frames to refresh
        self._build()

    def _build(self):
        # ── Row 0: condition + type + delete ──
        r0 = tk.Frame(self)
        r0.pack(fill="x", padx=2, pady=1)

        tk.Label(r0, text="If:", font=("Arial",8)).pack(side="left")
        self._cond_var = tk.StringVar(value=self.ability.get("condition_id") or "")
        cond_cb = ttk.Combobox(r0, textvariable=self._cond_var,
                               values=[""] + CD.condition_ids(), width=16,
                               font=("Arial",8))
        cond_cb.pack(side="left", padx=2)
        cond_cb.bind("<<ComboboxSelected>>", self._cond_changed)

        # cond placeholder frame
        self._cond_ph = PlaceholderFrame(r0,
            self._cond_text(), self.ability.setdefault("condition_vals",{}),
            self.on_change, bg=self["bg"])
        self._cond_ph.pack(side="left")

        tk.Label(r0, text="Type:", font=("Arial",8)).pack(side="left", padx=(6,0))
        self._type_var = tk.StringVar(value=self.ability.get("ability_type","Play"))
        ttk.Combobox(r0, textvariable=self._type_var,
                     values=ABILITY_TYPES, width=10, font=("Arial",8),
                     state="readonly").pack(side="left", padx=2)
        self._type_var.trace_add("write", lambda *_: self._simple_change("ability_type", self._type_var))

        tk.Button(r0, text="✕", command=self.on_delete,
                  fg="red", font=("Arial",8), relief="flat").pack(side="right")

        # ── Row 1: costs ──
        r1 = tk.Frame(self)
        r1.pack(fill="x", padx=2)
        tk.Label(r1, text="Costs:", font=("Arial",8,"bold")).pack(side="left")
        tk.Button(r1, text="+", command=self._add_cost,
                  font=("Arial",8)).pack(side="left", padx=2)
        self._cost_frame = tk.Frame(r1)
        self._cost_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_costs()

        # ── Row 2: effects ──
        r2 = tk.Frame(self)
        r2.pack(fill="x", padx=2)
        tk.Label(r2, text="Effects:", font=("Arial",8,"bold")).pack(side="left")
        tk.Button(r2, text="+", command=self._add_effect,
                  font=("Arial",8)).pack(side="left", padx=2)
        self._eff_frame = tk.Frame(r2)
        self._eff_frame.pack(side="left", fill="x", expand=True)
        self._rebuild_effects()

        # ── Row 3: Choose N ──
        r3 = tk.Frame(self)
        r3.pack(fill="x", padx=2, pady=1)
        tk.Label(r3, text="Choose N:", font=("Arial",8)).pack(side="left")
        self._choose_var = tk.StringVar(
            value=str(self.ability.get("choose_n") or ""))
        tk.Entry(r3, textvariable=self._choose_var, width=4,
                 font=("Arial",8)).pack(side="left", padx=2)
        self._choose_var.trace_add("write", self._choose_changed)

        self._repeat_var = tk.BooleanVar(value=self.ability.get("choose_repeat", False))
        tk.Checkbutton(r3, text="same multiple times",
                       variable=self._repeat_var, font=("Arial",8),
                       command=self._repeat_changed).pack(side="left")

    # ── condition helpers ───────────────────

    def _cond_text(self):
        cid = self.ability.get("condition_id")
        if not cid: return ""
        c = CD.get("condition", cid)
        return c.get("effect_text","") if c else ""

    def _cond_changed(self, _=None):
        val = self._cond_var.get() or None
        self.ability["condition_id"] = val
        self.ability["condition_vals"] = {}
        txt = self._cond_text()
        self._cond_ph.values = self.ability["condition_vals"]
        self._cond_ph.update_text(txt)
        self.on_change()

    # ── cost helpers ────────────────────────

    def _rebuild_costs(self):
        for w in self._cost_frame.winfo_children():
            w.destroy()
        for idx, ci in enumerate(self.ability.get("costs", [])):
            self._cost_row(self._cost_frame, ci, idx)

    def _cost_row(self, parent, ci, idx):
        f = tk.Frame(parent, relief="solid", bd=1)
        f.pack(side="left", padx=1, pady=1)
        var = tk.StringVar(value=ci.get("cost_id",""))
        cb = ttk.Combobox(f, textvariable=var, values=CD.cost_ids(),
                          width=12, font=("Arial",8))
        cb.pack(side="left")

        def on_sel(_=None, v=var, ci=ci):
            ci["cost_id"] = v.get()
            ci["vals"] = {}
            ph.update_text(self._item_text("cost", v.get()))
            self.on_change()

        cb.bind("<<ComboboxSelected>>", on_sel)
        ph = PlaceholderFrame(f, self._item_text("cost", ci.get("cost_id","")),
                              ci.setdefault("vals",{}), self.on_change)
        ph.pack(side="left")
        tk.Button(f, text="✕",
                  command=lambda i=idx: self._del_cost(i),
                  font=("Arial",7), relief="flat", fg="red").pack(side="left")

    def _add_cost(self):
        self.ability.setdefault("costs",[]).append({"cost_id":"","vals":{}})
        self._rebuild_costs()
        self.on_change()

    def _del_cost(self, idx):
        self.ability["costs"].pop(idx)
        self._rebuild_costs()
        self.on_change()

    # ── effect helpers ──────────────────────

    def _rebuild_effects(self):
        for w in self._eff_frame.winfo_children():
            w.destroy()
        for idx, ei in enumerate(self.ability.get("effects", [])):
            self._effect_row(self._eff_frame, ei, idx)

    def _effect_row(self, parent, ei, idx):
        f = tk.Frame(parent, relief="solid", bd=1)
        f.pack(fill="x", padx=1, pady=1)
        var = tk.StringVar(value=ei.get("effect_id",""))
        cb = ttk.Combobox(f, textvariable=var, values=CD.effect_ids(),
                          width=14, font=("Arial",8))
        cb.pack(side="left")

        def on_sel(_=None, v=var, ei=ei):
            ei["effect_id"] = v.get()
            ei["vals"] = {}
            ph.update_text(self._item_text("effect", v.get()))
            self.on_change()

        cb.bind("<<ComboboxSelected>>", on_sel)
        ph = PlaceholderFrame(f, self._item_text("effect", ei.get("effect_id","")),
                              ei.setdefault("vals",{}), self.on_change)
        ph.pack(side="left")
        tk.Button(f, text="✕",
                  command=lambda i=idx: self._del_effect(i),
                  font=("Arial",7), relief="flat", fg="red").pack(side="left")

    def _add_effect(self):
        self.ability.setdefault("effects",[]).append({"effect_id":"","vals":{}})
        self._rebuild_effects()
        self.on_change()

    def _del_effect(self, idx):
        self.ability["effects"].pop(idx)
        self._rebuild_effects()
        self.on_change()

    # ── misc ────────────────────────────────

    def _item_text(self, kind, id_):
        item = CD.get(kind, id_)
        if item: return item.get("effect_text","")
        return ""

    def _simple_change(self, key, var):
        self.ability[key] = var.get()
        self.on_change()

    def _choose_changed(self, *_):
        v = self._choose_var.get().strip()
        self.ability["choose_n"] = int(v) if v.isdigit() else None
        self.on_change()

    def _repeat_changed(self):
        self.ability["choose_repeat"] = self._repeat_var.get()
        self.on_change()


# ─────────────────────────────────────────────
#  BLOCK EDITOR  (one block + its abilities)
# ─────────────────────────────────────────────
class BlockEditor(tk.LabelFrame):
    def __init__(self, parent, block: dict, on_change, on_delete, **kw):
        btype = block.get("type","?")
        color = BLOCK_COLORS.get(btype, "#333")
        super().__init__(parent, text=f" {BLOCK_SYMBOLS.get(btype,'?')} {btype} ",
                         fg=color, font=("Arial",9,"bold"),
                         relief="groove", bd=2, **kw)
        self.block     = block
        self.on_change = on_change
        self.on_delete = on_delete
        self._build()

    def _build(self):
        hdr = tk.Frame(self)
        hdr.pack(fill="x")
        tk.Button(hdr, text="+ Ability", command=self._add_ability,
                  font=("Arial",8)).pack(side="left", padx=4)
        tk.Button(hdr, text="Remove Block", command=self.on_delete,
                  fg="red", font=("Arial",8)).pack(side="right", padx=4)

        self._ab_frame = tk.Frame(self)
        self._ab_frame.pack(fill="x", padx=4, pady=2)
        self._rebuild_abilities()

    def _rebuild_abilities(self):
        for w in self._ab_frame.winfo_children():
            w.destroy()
        for idx, ab in enumerate(self.block.get("abilities", [])):
            ae = AbilityEditor(
                self._ab_frame, ab,
                on_change=self.on_change,
                on_delete=lambda i=idx: self._del_ability(i),
                bg="#2a2a2a"
            )
            ae.pack(fill="x", pady=2)

    def _add_ability(self):
        self.block.setdefault("abilities", []).append(empty_ability())
        self._rebuild_abilities()
        self.on_change()

    def _del_ability(self, idx):
        self.block["abilities"].pop(idx)
        self._rebuild_abilities()
        self.on_change()


# ─────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────
class CardBuilder:

    def __init__(self, root: tk.Tk):
        self.root  = root
        self.root.title("Card Builder")
        self.root.geometry("1380x820")
        self.root.configure(bg="#1a1a1a")

        self.cards: list  = load_cards()
        self.current_card = empty_card()
        self.current_idx  = None   # index in self.cards if editing existing

        self._build_ui()
        self._refresh_card_list()
        self._refresh_preview()

    # ─────────────────────────────────────
    #  UI LAYOUT
    # ─────────────────────────────────────

    def _build_ui(self):
        root = self.root

        # ── TOP BAR ──────────────────────────
        top = tk.Frame(root, bg="#111", pady=4)
        top.pack(fill="x")
        tk.Label(top, text="✦ CARD BUILDER ✦",
                 bg="#111", fg="gold",
                 font=("Palatino Linotype", 14, "bold")).pack(side="left", padx=12)

        tk.Button(top, text="💾 Save Card",    command=self._save_card,
                  bg="#1a6e3c", fg="white", font=("Arial",9)).pack(side="right", padx=4)
        tk.Button(top, text="📄 New Card",     command=self._new_card,
                  bg="#1a3e8e", fg="white", font=("Arial",9)).pack(side="right", padx=4)
        tk.Button(top, text="🗑 Delete Card",  command=self._delete_card,
                  bg="#8e1a1a", fg="white", font=("Arial",9)).pack(side="right", padx=4)

        # ── MAIN AREA ────────────────────────
        main = tk.Frame(root, bg="#1a1a1a")
        main.pack(fill="both", expand=True)

        # LEFT: card list
        left = tk.Frame(main, bg="#111", width=160)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="Cards", bg="#111", fg="#aaa",
                 font=("Arial",9,"bold")).pack(pady=(6,2))
        self._card_listbox = tk.Listbox(left, bg="#1a1a1a", fg="white",
                                        selectbackground="#1a6e3c",
                                        font=("Arial",8), activestyle="none",
                                        relief="flat", bd=0)
        self._card_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._card_listbox.bind("<<ListboxSelect>>", self._load_card_from_list)

        # CENTER: editor (scrollable)
        center_outer = tk.Frame(main, bg="#1a1a1a")
        center_outer.pack(side="left", fill="both", expand=True)

        cscroll = tk.Scrollbar(center_outer, orient="vertical")
        cscroll.pack(side="right", fill="y")
        self._center_canvas = tk.Canvas(center_outer, bg="#1a1a1a",
                                        yscrollcommand=cscroll.set,
                                        highlightthickness=0)
        self._center_canvas.pack(fill="both", expand=True)
        cscroll.config(command=self._center_canvas.yview)

        self._editor_frame = tk.Frame(self._center_canvas, bg="#1a1a1a")
        self._editor_win = self._center_canvas.create_window(
            (0, 0), window=self._editor_frame, anchor="nw")
        self._editor_frame.bind("<Configure>", self._on_editor_resize)
        self._center_canvas.bind("<Configure>", self._on_canvas_resize)
        # Mouse wheel scrolling
        self._center_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._center_canvas.bind("<Button-4>",   self._on_mousewheel)
        self._center_canvas.bind("<Button-5>",   self._on_mousewheel)

        self._build_editor()

        # RIGHT: preview
        right = tk.Frame(main, bg="#111", width=CARD_W + 20)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="Preview", bg="#111", fg="#aaa",
                 font=("Arial",9,"bold")).pack(pady=(6,2))
        self._preview_canvas = tk.Canvas(right,
            width=CARD_W, height=CARD_H,
            bg="#000", highlightthickness=1,
            highlightbackground="#444")
        self._preview_canvas.pack(pady=8)
        self._renderer = CardRenderer(self._preview_canvas)

    def _on_editor_resize(self, _=None):
        self._center_canvas.configure(
            scrollregion=self._center_canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._center_canvas.itemconfig(self._editor_win, width=event.width)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._center_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._center_canvas.yview_scroll(1, "units")
        else:
            self._center_canvas.yview_scroll(
                int(-1 * (event.delta / 120)), "units")

    # ─────────────────────────────────────
    #  EDITOR (card metadata + blocks)
    # ─────────────────────────────────────

    def _build_editor(self):
        ef = self._editor_frame
        # clear
        for w in ef.winfo_children():
            w.destroy()

        card = self.current_card

        # ── Meta row ──
        meta = tk.Frame(ef, bg="#1a1a1a")
        meta.pack(fill="x", padx=8, pady=6)

        tk.Label(meta, text="Name:", bg="#1a1a1a", fg="#ccc",
                 font=("Arial",9)).pack(side="left")
        self._name_var = tk.StringVar(value=card.get("name",""))
        self._name_var.trace_add("write", self._name_changed)
        tk.Entry(meta, textvariable=self._name_var, width=24,
                 bg="#2a2a2a", fg="white", insertbackground="white",
                 font=("Arial",9)).pack(side="left", padx=(2,12))

        tk.Label(meta, text="Element:", bg="#1a1a1a", fg="#ccc",
                 font=("Arial",9)).pack(side="left")
        self._elem_var = tk.StringVar(value=card.get("element","Fire"))
        self._elem_var.trace_add("write", self._elem_changed)
        ttk.Combobox(meta, textvariable=self._elem_var,
                     values=ELEMENTS, width=10,
                     state="readonly").pack(side="left", padx=2)

        # ── Block controls ──
        blk_ctrl = tk.Frame(ef, bg="#1a1a1a")
        blk_ctrl.pack(fill="x", padx=8, pady=2)

        tk.Label(blk_ctrl, text="Add Block:", bg="#1a1a1a", fg="#ccc",
                 font=("Arial",9,"bold")).pack(side="left")
        self._new_block_var = tk.StringVar(value=BLOCK_TYPES[0])
        ttk.Combobox(blk_ctrl, textvariable=self._new_block_var,
                     values=BLOCK_TYPES, width=18,
                     state="readonly").pack(side="left", padx=4)
        tk.Button(blk_ctrl, text="+ Add Block",
                  command=self._add_block,
                  bg="#1a6e3c", fg="white",
                  font=("Arial",8)).pack(side="left", padx=4)

        # limit info
        count = len(card.get("blocks",[]))
        tk.Label(blk_ctrl, text=f"({count}/4 blocks)",
                 bg="#1a1a1a", fg="#888", font=("Arial",8)).pack(side="left")

        # ── Block editors ──
        for idx, blk in enumerate(card.get("blocks", [])):
            be = BlockEditor(
                ef, blk,
                on_change=self._refresh_preview,
                on_delete=lambda i=idx: self._del_block(i),
                bg="#212121"
            )
            be.pack(fill="x", padx=8, pady=4)

    def _name_changed(self, *_):
        self.current_card["name"] = self._name_var.get()
        self._refresh_preview()

    def _elem_changed(self, *_):
        self.current_card["element"] = self._elem_var.get()
        self._refresh_preview()

    def _add_block(self):
        if len(self.current_card.get("blocks",[])) >= 4:
            messagebox.showwarning("Limit", "A card can have at most 4 blocks.")
            return
        btype = self._new_block_var.get()
        self.current_card.setdefault("blocks",[]).append(empty_block(btype))
        self._build_editor()
        self._refresh_preview()

    def _del_block(self, idx):
        self.current_card["blocks"].pop(idx)
        self._build_editor()
        self._refresh_preview()

    def _refresh_preview(self, *_):
        self._renderer.render(self.current_card)

    # ─────────────────────────────────────
    #  CARD LIST
    # ─────────────────────────────────────

    def _refresh_card_list(self):
        lb = self._card_listbox
        lb.delete(0, "end")
        for c in self.cards:
            lb.insert("end", c.get("name","?"))
        if self.current_idx is not None:
            lb.selection_clear(0, "end")
            lb.selection_set(self.current_idx)

    def _load_card_from_list(self, _=None):
        sel = self._card_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.current_idx  = idx
        self.current_card = copy.deepcopy(self.cards[idx])
        self._build_editor()
        self._refresh_preview()

    # ─────────────────────────────────────
    #  CARD CRUD
    # ─────────────────────────────────────

    def _new_card(self):
        self.current_card = empty_card()
        self.current_idx  = None
        self._card_listbox.selection_clear(0, "end")
        self._build_editor()
        self._refresh_preview()

    def _save_card(self):
        card = self.current_card
        if not card.get("name","").strip():
            messagebox.showerror("Error", "Card needs a name.")
            return

        if self.current_idx is not None:
            self.cards[self.current_idx] = copy.deepcopy(card)
        else:
            self.cards.append(copy.deepcopy(card))
            self.current_idx = len(self.cards) - 1

        save_cards(self.cards)
        self._refresh_card_list()
        self._show_status("Card saved ✓")

    def _delete_card(self):
        if self.current_idx is None:
            return
        if not messagebox.askyesno("Delete", "Delete this card?"):
            return
        self.cards.pop(self.current_idx)
        save_cards(self.cards)
        self.current_idx  = None
        self.current_card = empty_card()
        self._refresh_card_list()
        self._build_editor()
        self._refresh_preview()

    def _show_status(self, msg, ms=2000):
        bar = tk.Label(self.root, text=msg, bg="#1a6e3c", fg="white",
                       font=("Arial",10,"bold"))
        bar.place(relx=0, rely=1.0, anchor="sw", relwidth=1)
        self.root.after(ms, bar.destroy)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    # Dark combobox style
    style.configure("TCombobox",
                    fieldbackground="#2a2a2a",
                    background="#2a2a2a",
                    foreground="white",
                    selectbackground="#1a6e3c")
    root.configure(bg="#1a1a1a")
    app = CardBuilder(root)
    root.mainloop()