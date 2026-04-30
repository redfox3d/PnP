"""
constants.py – all static configuration.
"""

BOX_TYPES = [
    "Play", "Excavate", "Hand", "Concentration", "Enchant",
    "Equipped", "Exhausted", "Forgotten", "Sacrifice",
    "Ingredient", "Materials",
    # World/Status sigils (also usable on Creatures / Tokens where
    # allowed_card_types says so). "Enter" is analogous to "Play": fires
    # once when the entity enters the world / takes effect.
    "Counter", "Enter", "Activate", "Condition",
    # Creature-exclusive
    "Attack", "Passive",
]

# Legacy sigil names get rewritten on load. NEVER add the alias key back to
# BOX_TYPES — that would split a merged sigil.
#   Enchantment → Concentration  (B4)
#   Discard     → Exhausted       (merged: same effect on the player)
#   Lost        → Forgotten       (Lost retired; replace with Forgotten)
#   Fleeting    → Forgotten       (Fleeting retired)
BOX_TYPE_ALIASES = {
    "Enchantment": "Concentration",
    "Discard":     "Exhausted",
    "Lost":        "Forgotten",
    "Fleeting":    "Forgotten",
    # Tick was the old name for the on-enter-style sigil; renamed to
    # "Enter" to match the analogy with "Play".
    "Tick":        "Enter",
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

# Per-card-type sigil renames. Take precedence over SIGIL_LABELS when the
# caller passes the card_type. Internal sigil ID stays "Play" so existing
# data and gen_config keep working unchanged.
SIGIL_LABELS_PER_CARD_TYPE = {
    "Spells":         {"Play": "Chant"},
    "Prowess":        {"Play": "Act"},
    # Tränke + Items: "Play" sigil is rendered as "Use".
    "Potions":        {"Play": "Use"},
    "Phials":         {"Play": "Use"},
    "Tinctures":      {"Play": "Use"},
    "Equipment":      {"Play": "Use"},
    "Supplies":       {"Play": "Use"},
    "Alchemy":        {"Play": "Use"},
    # World cards: "Play" sigil = "Trigger" — the sigil that fires when the
    # token / creature / status enters or activates each turn.
    "Tokens":         {"Play": "Trigger"},
    "Creatures":      {"Play": "Turn"},
    # NOTE: StatusEffects no longer alias Play. They use the dedicated
    # Tick / Counter / Activate / Condition / Sacrifice sigils below.
}

# Per-card-type sigil whitelist — which sigils may appear on which card type.
# When the list is empty / missing, all sigils are allowed (legacy fallback).
# These mirror the ``allowed_card_types`` in ``box_config.json`` and are
# used by the editor and generator UI to filter dropdowns.
SIGILS_FOR_CARD_TYPE = {
    "Spells":         ["Play", "Excavate", "Hand", "Concentration",
                        "Enchant", "Equipped", "Exhausted", "Forgotten",
                        "Sacrifice"],
    "Prowess":        ["Play", "Excavate", "Hand", "Concentration",
                        "Equipped", "Exhausted", "Forgotten", "Sacrifice"],
    "Potions":        ["Play", "Ingredient"],
    "Phials":         ["Play", "Ingredient"],
    "Tinctures":      ["Play", "Ingredient"],
    "Equipment":      ["Materials", "Play", "Equipped", "Sacrifice"],
    "Supplies":       ["Materials", "Play", "Sacrifice"],
    "Alchemy":        ["Materials", "Play"],
    # World cards keep Play + on-enter ("Enter") + Activate.
    "Tokens":         ["Play", "Enter", "Activate"],
    "Creatures":      ["Play", "Attack", "Passive", "Enter", "Activate",
                        "Sacrifice"],
    # StatusEffects expose a dedicated set of sigils the player turns on
    # case-by-case. Counter / Enter / Activate / Sacrifice / Condition are
    # all optional — none mandatory.
    "StatusEffects":  ["Counter", "Enter", "Activate", "Sacrifice",
                        "Condition"],
}


def sigils_for_card_type(card_type: str) -> list:
    """Return the list of sigil ids legal for the given card type."""
    return list(SIGILS_FOR_CARD_TYPE.get(card_type, BOX_TYPES))

def card_type_label(card_type: str) -> str:
    """Display label for a card type (e.g. 'Spells' → 'Chant')."""
    return CARD_TYPE_LABELS.get(card_type, card_type)

def sigil_label(box_type: str, card_type: str = "") -> str:
    """Display label for a sigil/box.

    Lookup order:
      1. ``box_config.json`` per-sigil ``card_type_labels`` (Sigil-Manager edit)
      2. Code-level ``SIGIL_LABELS_PER_CARD_TYPE`` table
      3. Global ``SIGIL_LABELS`` table
      4. The raw box_type string
    """
    # 1) Live override from box_config (set in the Sigil Manager)
    if card_type:
        try:
            from CardContent.sigil_registry import sigil_label_override
            override = sigil_label_override(box_type, card_type)
            if override:
                return override
        except Exception:
            pass
        # 2) Code-level table
        per_type = SIGIL_LABELS_PER_CARD_TYPE.get(card_type, {})
        if box_type in per_type:
            return per_type[box_type]
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
    "Enchant":       "#5a2a8e",
    "Equipped":      "#3a5a3a",
    "Exhausted":     "#5a3a2a",
    "Forgotten":     "#1a5a5a",
    "Sacrifice":     "#5a1a1a",
    "Ingredient":    "#2e3a1e",
    "Materials":     "#3a2a1a",
    "Counter":       "#3a3a8a",
    "Enter":         "#1a4a6a",
    "Activate":      "#7a4a1a",
    "Condition":     "#4a4a4a",
    "Attack":        "#7a1a1a",
    "Passive":       "#3a5a8a",
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
    "Enchant":       "✦",
    "Equipped":      "⚔",
    "Exhausted":     "💤",
    "Forgotten":     "💨",
    "Sacrifice":     "🩸",
    "Ingredient":    "🧪",
    "Materials":     "◆",
    "Counter":       "⏲",
    "Enter":         "↪",
    "Activate":      "⚡",
    "Condition":     "❓",
    "Attack":        "⚔",
    "Passive":       "✦",
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
