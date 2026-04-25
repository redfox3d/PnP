"""
constants.py – all static configuration.
"""

BOX_TYPES = [
    "Play", "Excavate", "Hand", "Concentration",
    "Equipped", "Exhausted", "Fleeting", "Discard",
]

# B4: Enchantment merged into Concentration. Any stored data using the old
# key is transparently mapped on load. Do NOT reintroduce "Enchantment" to
# BOX_TYPES — it would split the merged sigil again.
BOX_TYPE_ALIASES = {
    "Enchantment": "Concentration",
}

ABILITY_TYPES = ["Trigger", "Play", "Continues", "Activate"]

ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Quinta"]

# ── Display labels (A1/A2/A3) ─────────────────────────────────────────────────
# Internal keys stay stable; only the rendered label changes.
CARD_TYPE_LABELS = {
    "Spells":  "Chant",   # A1: "Spell"  → "Chant"
    "Prowess": "Act",     # A2: "Skill"  → "Act"
}

# Sigil (box) rename table. Maps internal box-type names to what appears on
# the card. If a key is missing, the internal name is used verbatim.
SIGIL_LABELS = {
    "Forgotten": "Omen",  # A3: ONLY the sigil name changes
}

def card_type_label(card_type: str) -> str:
    """Display label for a card type (e.g. 'Spells' → 'Chant')."""
    return CARD_TYPE_LABELS.get(card_type, card_type)

def sigil_label(box_type: str) -> str:
    """Display label for a sigil/box (e.g. 'Forgotten' → 'Omen')."""
    return SIGIL_LABELS.get(box_type, box_type)

# Generic mana symbol (used when no element is specified)
GENERIC_MANA_ICON  = "◎"
GENERIC_MANA_COLOR = "#888888"

# The special Cost ID that renders as mana symbols instead of text
MANA_COST_ID = "Mana"

NO_ELEMENT_TYPES  = ["Supplies", "Equipment", "Alchemy", "Prowess",
                     "Potions", "Phials", "Tinctures"]
BOX_CARD_TYPES    = ["Spells", "Prowess"]

BOX_COLORS = {
    "Play":          "#1a3e8e",
    "Excavate":      "#8B6914",
    "Hand":          "#1a6e3c",
    "Concentration": "#2a4a6e",
    "Equipped":      "#3a5a3a",
    "Exhausted":     "#5a3a2a",
    "Fleeting":      "#1a5a5a",
    "Discard":       "#3a2a1a",
}

ELEMENT_COLORS = {
    "Fire":   "#c0392b",
    "Metal":  "#7f8c8d",
    "Ice":    "#2980b9",
    "Nature": "#27ae60",
    "Blood":  "#8e0000",
    "Quinta": "#8e44ad",
}

ELEMENT_ICONS = {
    "Fire":   "🔥",
    "Metal":  "⚙️",
    "Ice":    "❄️",
    "Nature": "🌿",
    "Blood":  "🩸",
    "Quinta": "✨",
}

BOX_SYMBOLS = {
    "Play":          "▶",
    "Excavate":      "⛏",
    "Hand":          "✋",
    "Concentration": "◉",
    "Equipped":      "⚔",
    "Exhausted":     "💤",
    "Fleeting":      "💨",
    "Discard":       "🗑",
}


def canonical_box_type(btype: str) -> str:
    """Apply box-type aliases (e.g. Enchantment → Concentration) for B4.

    Call this when reading persisted data; keep original keys only for
    error-path display.
    """
    return BOX_TYPE_ALIASES.get(btype, btype)

TYPE_SYMBOLS = {
    "Trigger":   "⚡",
    "Play":      "▶",
    "Continues": "∞",
    "Activate":  "⚙",
}

COND_SYMBOL   = "◈"
EFFECT_SYMBOL = "◆"
COST_SYMBOL   = "◉"

RECIPE_TYPES = ["Potions", "Phials", "Tinctures"]

RECIPE_TYPE_COLORS = {
    "Potions":   "#2980b9",
    "Phials":    "#c0392b",
    "Tinctures": "#27ae60",
}

RECIPE_TYPE_ICONS = {
    "Potions":   "🧪",
    "Phials":    "⚗️",
    "Tinctures": "🫧",
}

# Default CV per ingredient
INGREDIENT_CV = 4

CARD_W    = 476
CARD_H    = 666
ARTWORK_W = 88
