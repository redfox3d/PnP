"""
constants.py – all static configuration.
"""

BOX_TYPES = [
    "Play", "Excavate", "Hand", "Concentration",
    "Enchantment", "Equipped", "Exhausted", "Fleeting", "Forgotten", "Lost",
]

ABILITY_TYPES = ["Trigger", "Play", "Continues", "Activate"]

ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Meta", "Generic"]

# Generic mana symbol (used when no element is specified)
GENERIC_MANA_ICON  = "◎"
GENERIC_MANA_COLOR = "#888888"

# The special Cost ID that renders as mana symbols instead of text
MANA_COST_ID = "Mana"

NO_ELEMENT_TYPES  = ["Supplies", "Equipment", "Alchemy", "Prowess"]
BOX_CARD_TYPES    = ["Spells", "Prowess"]

BOX_COLORS = {
    "Play":          "#1a3e8e",
    "Excavate":      "#8B6914",
    "Hand":          "#1a6e3c",
    "Concentration": "#2a4a6e",
    "Enchantment":   "#6a1a8e",
    "Equipped":      "#3a5a3a",
    "Exhausted":     "#5a3a2a",
    "Fleeting":      "#1a5a5a",
    "Lost":          "#3a3a3a",
}

ELEMENT_COLORS = {
    "Fire":   "#c0392b",
    "Metal":  "#7f8c8d",
    "Ice":    "#2980b9",
    "Nature": "#27ae60",
    "Blood":  "#8e0000",
    "Meta":   "#8e44ad",
}

ELEMENT_ICONS = {
    "Fire":   "🔥",
    "Metal":  "⚙️",
    "Ice":    "❄️",
    "Nature": "🌿",
    "Blood":  "🩸",
    "Meta":   "✨",
}

BOX_SYMBOLS = {
    "Play":          "▶",
    "Excavate":      "⛏",
    "Hand":          "✋",
    "Concentration": "◉",
    "Enchantment":   "✦",
    "Equipped":      "⚔",
    "Exhausted":     "💤",
    "Fleeting":      "💨",
    "Lost":          "☠",
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

CARD_W    = 476
CARD_H    = 666
ARTWORK_W = 88
