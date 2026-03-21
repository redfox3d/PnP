"""
Minimal hard-coded sample cards for testing/training before real cards are designed.
All cards follow the game engine's normalized format (boxes, variable_values, etc.)
"""

# --- Spell cards (skills deck) -------------------------------------------

SPELL_BASIC_ATTACK = {
    "id": "BasicAttack",
    "name": "Basic Attack",
    "element": "Fire",
    "card_type": "Spells",
    "cv": 2.0,
    "boxes": [{
        "type": "Play",
        "abilities": [{
            "type": "Play",
            "conditions": {},
            "costs": [{
                "effect_id": "Mana",
                "variable_values": {"X": 1, "element": "Fire"},
                "option_values": {},
            }],
            "effects": [{
                "effect_id": "Use_Weapon",
                "variable_values": {},
                "option_values": {},
            }],
            "choose_n": None,
            "choose_repeat": False,
        }],
    }],
}

SPELL_DRAW_TWO = {
    "id": "DrawTwo",
    "name": "Draw Two",
    "element": "Ice",
    "card_type": "Spells",
    "cv": 1.5,
    "boxes": [{
        "type": "Play",
        "abilities": [{
            "type": "Play",
            "conditions": {},
            "costs": [{
                "effect_id": "Mana",
                "variable_values": {"X": 1, "element": "Ice"},
                "option_values": {},
            }],
            "effects": [{
                "effect_id": "Draw",
                "variable_values": {"X": 2},
                "option_values": {},
            }],
            "choose_n": None,
            "choose_repeat": False,
        }],
    }],
}

SPELL_FREE_ATTACK = {
    "id": "FreeStrike",
    "name": "Free Strike",
    "element": "Metal",
    "card_type": "Spells",
    "cv": 1.0,
    "boxes": [{
        "type": "Play",
        "abilities": [{
            "type": "Play",
            "conditions": {},
            "costs": [],   # no mana cost
            "effects": [{
                "effect_id": "Use_Weapon",
                "variable_values": {},
                "option_values": {},
            }],
            "choose_n": None,
            "choose_repeat": False,
        }],
    }],
}

SPELL_DRAW_ONE_FREE = {
    "id": "QuickThought",
    "name": "Quick Thought",
    "element": "Nature",
    "card_type": "Spells",
    "cv": 0.8,
    "boxes": [{
        "type": "Play",
        "abilities": [{
            "type": "Play",
            "conditions": {},
            "costs": [],
            "effects": [{
                "effect_id": "Draw",
                "variable_values": {"X": 1},
                "option_values": {},
            }],
            "choose_n": None,
            "choose_repeat": False,
        }],
    }],
}

# --- Supply cards (backpack deck) ----------------------------------------

def _supply(element: str) -> dict:
    return {
        "id":       f"Supply_{element}",
        "name":     f"{element} Supply",
        "element":  element,
        "card_type": "Supplies",
        "cv": 0.0,
        "boxes": [],
    }

SUPPLY_FIRE   = _supply("Fire")
SUPPLY_METAL  = _supply("Metal")
SUPPLY_ICE    = _supply("Ice")
SUPPLY_NATURE = _supply("Nature")
SUPPLY_BLOOD  = _supply("Blood")
SUPPLY_META   = _supply("Meta")

# --- Equipment cards ------------------------------------------------------

WEAPON_SWORD = {
    "id":           "IronSword",
    "name":         "Iron Sword",
    "element":      "Metal",
    "card_type":    "Equipment",
    "damage_sides": 6,
    "damage_count": 1,
    "dodge_modifier": 0,
    "armor":        0,
    "movement":     2,
    "cv": 1.0,
    "boxes": [],
}

ARMOR_LEATHER = {
    "id":             "LeatherArmor",
    "name":           "Leather Armor",
    "card_type":      "Equipment",
    "dodge_modifier": 3,
    "armor":          1,
    "cv": 1.0,
    "boxes": [],
}

SHOES_BOOTS = {
    "id":       "Boots",
    "name":     "Boots",
    "card_type": "Equipment",
    "movement": 3,
    "cv": 0.5,
    "boxes": [],
}

# --- Convenience lists ----------------------------------------------------

DEFAULT_SKILL_DECK = (
    [SPELL_BASIC_ATTACK] * 4
    + [SPELL_FREE_ATTACK] * 3
    + [SPELL_DRAW_TWO] * 2
    + [SPELL_DRAW_ONE_FREE] * 3
)

DEFAULT_BACKPACK = (
    [SUPPLY_FIRE]   * 5
    + [SUPPLY_METAL]  * 5
    + [SUPPLY_ICE]    * 3
    + [SUPPLY_NATURE] * 3
    + [SUPPLY_BLOOD]  * 2
    + [SUPPLY_META]   * 2
)

DEFAULT_EQUIPMENT = {
    "right_hand": WEAPON_SWORD,
    "chest":      ARMOR_LEATHER,
    "shoes":      SHOES_BOOTS,
}
