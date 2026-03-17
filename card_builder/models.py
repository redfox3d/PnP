"""
models.py – card data model (factory functions) and JSON persistence.
"""

import json
import os
import copy

from .constants import ELEMENTS

# ── File paths ─────────────────────────────────────────────────────────────────
# BASE_DIR is set at runtime by main.py so that cards.json always lands next to
# the script, regardless of where the card_builder/ package lives.
_CARDS_FILE: str = ""

"""
models.py – card data model (factory functions) and JSON persistence.
"""

import json
import os
import copy

from card_builder.constants import ELEMENTS   # ← war: from constants import ELEMENTS

# ── File paths ─────────────────────────────────────────────────────────────────
_CARDS_FILE: str = ""


def set_cards_file(path: str) -> None:
    global _CARDS_FILE
    _CARDS_FILE = path
    print(f"[models] set_cards_file → '{_CARDS_FILE}'")


# ── Factory functions ──────────────────────────────────────────────────────────

def empty_card() -> dict:
    return {
        "name":    "New Card",
        "element": "Fire",
        "blocks":  [],
    }


def empty_block(btype: str = "Play") -> dict:
    return {
        "type":      btype,
        "abilities": [],
    }


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


# ── Persistence ────────────────────────────────────────────────────────────────

def load_cards() -> list:
    print(f"[models] load_cards → '{_CARDS_FILE}'  exists={os.path.exists(_CARDS_FILE) if _CARDS_FILE else 'N/A'}")
    if _CARDS_FILE and os.path.exists(_CARDS_FILE):
        with open(_CARDS_FILE, encoding="utf-8") as f:
            return json.load(f).get("cards", [])
    return []


def save_cards(cards: list) -> None:
    if not _CARDS_FILE:
        raise RuntimeError("cards file path not set – call set_cards_file() first")
    os.makedirs(os.path.dirname(_CARDS_FILE), exist_ok=True)  # Ordner anlegen falls nötig
    with open(_CARDS_FILE, "w", encoding="utf-8") as f:
        json.dump({"cards": cards}, f, indent=4, ensure_ascii=False)
    print(f"[models] saved {len(cards)} cards → '{_CARDS_FILE}'")