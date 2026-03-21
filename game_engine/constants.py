from enum import Enum


class Element(str, Enum):
    FIRE    = "Fire"
    METAL   = "Metal"
    ICE     = "Ice"
    NATURE  = "Nature"
    BLOOD   = "Blood"
    META    = "Meta"
    GENERIC = "Generic"


class Zone(str, Enum):
    HAND          = "hand"
    SKILLS_DECK   = "skills_deck"
    BACKPACK_DECK = "backpack_deck"
    PLAY          = "play"
    ENCHANTED     = "enchanted"
    CONCENTRATION = "concentration"
    DISCARD       = "discard"
    FORGOTTEN     = "forgotten"
    LOST          = "lost"


class EquipSlot(str, Enum):
    HEAD        = "head"
    BACKPACK    = "backpack"
    CHEST       = "chest"
    BELT        = "belt"
    LEFT_HAND   = "left_hand"
    LEGS        = "legs"
    RIGHT_HAND  = "right_hand"
    SHOES       = "shoes"


# stat attribute name for each element (on Stats dataclass)
ELEMENT_COMBAT_STAT: dict[Element, str] = {
    Element.FIRE:   "ausdauer",
    Element.METAL:  "kraft",
    Element.BLOOD:  "beweglichkeit",
    Element.NATURE: "wahrnehmung",
    Element.ICE:    "geschwindigkeit",
    Element.META:   "basteln",
}

ELEMENT_HIT_SKILL: dict[Element, str] = {
    Element.FIRE:   "empathie",
    Element.METAL:  "wissen",
    Element.BLOOD:  "ueberzeugungskraft",
    Element.NATURE: "naturwissen",
    Element.ICE:    "selbstbewusstsein",
    Element.META:   "intelligenz",
}

# Die sides for attack roll per element
ELEMENT_DIE: dict[Element, int] = {
    Element.FIRE:    6,
    Element.METAL:   8,
    Element.BLOOD:   6,
    Element.NATURE:  6,
    Element.ICE:     6,
    Element.META:    6,
    Element.GENERIC: 6,
}

ARMOR_SLOTS  = [EquipSlot.HEAD, EquipSlot.CHEST, EquipSlot.LEGS]
WEAPON_SLOTS = [EquipSlot.RIGHT_HAND, EquipSlot.LEFT_HAND]

BASE_MOVEMENT = 2
DEFAULT_WEAPON_SIDES = 4   # d4 unarmed
