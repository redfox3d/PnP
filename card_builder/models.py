"""
models.py – card data model, factory functions, and JSON persistence.

Categories:
    Items   → Equipment, Supplies
    Skills  → Spells, Alchemy, Prowess
"""

import json
import os

from .constants import ELEMENTS

CARD_CATEGORIES = {
    "Items":  ["Equipment", "Supplies"],
    "Skills": ["Spells", "Alchemy", "Prowess"],
}

ALL_CARD_TYPES = [sub for subs in CARD_CATEGORIES.values() for sub in subs]

CARD_TYPE_PARENT = {
    sub: cat
    for cat, subs in CARD_CATEGORIES.items()
    for sub in subs
}

_CARDS_DIR: str = ""


def set_cards_dir(directory: str) -> None:
    global _CARDS_DIR
    _CARDS_DIR = directory
    print(f"[models] set_cards_dir → '{_CARDS_DIR}'")


def _cards_file(card_type: str) -> str:
    category = CARD_TYPE_PARENT.get(card_type, "Misc")
    return os.path.join(_CARDS_DIR, category, card_type, "cards.json")


def empty_card(card_type: str = "Spells") -> dict:
    """Default card – Spells is the default type."""
    base = {
        "name":      "New Card",
        "card_type": card_type,
        "artwork":   "",
    }
    if card_type == "Spells":
        base.update({"element": "Fire", "blocks": []})
    elif card_type == "Prowess":
        # No artwork for Prowess
        base.pop("artwork", None)
        base.update({"blocks": []})
    elif card_type in ("Supplies", "Equipment"):
        base.update({
            "element_sources": [],
            "object_type":     [],
            "materials":       [],
            "effect_text":     "",
            "value":           0,
        })
        if card_type == "Equipment":
            base["equip_text"]      = ""
            base["equip_cost_text"] = ""
    elif card_type == "Alchemy":
        base.update({
            "ingredients":       [],
            "result_content_id": "",
            "result_text":       "",
            "on_field_effect":   "",
        })
    return base


def empty_block(btype: str = "Play") -> dict:
    return {"type": btype, "abilities": []}


def empty_ability() -> dict:
    return {
        "condition_id":   None,
        "condition_vals": {},
        "ability_type":   "Play",
        "costs":          [],
        "effects":        [],
        "choose_n":       None,
        "choose_repeat":  False,
    }


def load_cards(card_type: str) -> list:
    if not _CARDS_DIR:
        return []
    path = _cards_file(card_type)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("cards", [])
    return []


def save_cards(cards: list, card_type: str) -> None:
    if not _CARDS_DIR:
        raise RuntimeError("cards dir not set")
    path = _cards_file(card_type)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"cards": cards}, f, indent=4, ensure_ascii=False)
    print(f"[models] saved {len(cards)} → '{path}'")
