"""
materials.py – Central materials registry.

Materials are stored in two places:
  1. cards/materials.json   – manually curated central list
  2. Collected from all Loot card "materials" fields

This module manages loading, merging, and saving the central list.
"""

import json
import os

_MATERIALS_FILE: str = ""
_MATERIALS_DIR:  str = ""

DEFAULT_MATERIALS = [
    "Gold", "Silber", "Bronze", "Eisen", "Stahl",
    "Holz", "Leder", "Stoff", "Knochen", "Stein",
    "Minze", "Wasser", "Öl", "Erde", "Asche",
    "Kristall", "Glas", "Papier", "Seide", "Wolle",
]


def set_materials_dir(directory: str) -> None:
    global _MATERIALS_FILE, _MATERIALS_DIR
    _MATERIALS_DIR  = directory
    _MATERIALS_FILE = os.path.join(directory, "materials.json")


def load_central_materials() -> list:
    if _MATERIALS_FILE and os.path.exists(_MATERIALS_FILE):
        with open(_MATERIALS_FILE, encoding="utf-8") as f:
            return json.load(f).get("materials", DEFAULT_MATERIALS)
    return list(DEFAULT_MATERIALS)


def save_central_materials(materials: list) -> None:
    if not _MATERIALS_FILE:
        return
    os.makedirs(os.path.dirname(_MATERIALS_FILE), exist_ok=True)
    with open(_MATERIALS_FILE, "w", encoding="utf-8") as f:
        json.dump({"materials": sorted(set(materials))}, f,
                  indent=4, ensure_ascii=False)


def collect_from_loot_cards(loot_cards: list) -> list:
    """Gather all materials mentioned in Loot cards."""
    found = set()
    for card in loot_cards:
        for m in card.get("materials", []):
            if m:
                found.add(m)
    return sorted(found)


def merged_materials(loot_cards: list = None) -> list:
    """Central list ∪ Loot card materials, sorted."""
    central = set(load_central_materials())
    if loot_cards:
        central.update(collect_from_loot_cards(loot_cards))
    return sorted(central)
