"""
constants.py – all static configuration: block types, elements, colours, symbols.
"""

BLOCK_TYPES = [
    "Excavate", "Hand", "Play", "Enchantment",
    "Graveyard", "Exile", "Banished Facedown",
]

ABILITY_TYPES = ["Trigger", "Play", "Continues", "Activate"]

ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Meta", "Potion", "Skills"]

# ── Block colours (hex, used as semi-transparent overlays on the canvas) ──────
BLOCK_COLORS = {
    "Excavate":         "#8B6914",
    "Hand":             "#1a6e3c",
    "Play":             "#1a3e8e",
    "Enchantment":      "#6a1a8e",
    "Graveyard":        "#3a3a3a",
    "Exile":            "#8e1a1a",
    "Banished Facedown":"#1a6e8e",
}

ELEMENT_COLORS = {
    "Fire":   "#c0392b",
    "Metal":  "#7f8c8d",
    "Ice":    "#2980b9",
    "Nature": "#27ae60",
    "Blood":  "#8e0000",
    "Meta":   "#8e44ad",
    "Potion": "#16a085",
    "Skills": "#d35400",
}

ELEMENT_ICONS = {
    "Fire":   "🔥",
    "Metal":  "⚙️",
    "Ice":    "❄️",
    "Nature": "🌿",
    "Blood":  "🩸",
    "Meta":   "✨",
    "Potion": "⚗️",
    "Skills": "⚔️",
}

# ── Symbols for the artwork strip ─────────────────────────────────────────────
BLOCK_SYMBOLS = {
    "Excavate":         "⛏",
    "Hand":             "✋",
    "Play":             "▶",
    "Enchantment":      "✦",
    "Graveyard":        "☠",
    "Exile":            "⊗",
    "Banished Facedown":"◼",
}

TYPE_SYMBOLS = {
    "Trigger":   "⚡",
    "Play":      "▶",
    "Continues": "∞",
    "Activate":  "⚙",
}

COND_SYMBOL   = "◈"
EFFECT_SYMBOL = "◆"
COST_SYMBOL   = "◉"

# ── Card canvas dimensions ────
CARD_W    = 476   # war 238
CARD_H    = 666   # war 333
ARTWORK_W = 88    # war 44