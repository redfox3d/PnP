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


# ── J: usage-based rarity / CV derivation ────────────────────────────────────

def compute_material_usage(loot_cards: list) -> dict:
    """Return {material: usage_count} based on Loot card 'materials' lists.

    A material's usage is simply how many Loot cards mention it. Used by the
    Ingredient editor to derive a default CV multiplier in [0.9, 1.1].
    """
    counts: dict = {}
    for card in loot_cards or []:
        seen = set()
        for m in card.get("materials", []):
            if m and m not in seen:
                seen.add(m)
                counts[m] = counts.get(m, 0) + 1
    return counts


def derive_cv_multiplier(usage_count: int, max_usage: int,
                          lo: float = 0.9, hi: float = 1.1) -> float:
    """Map a usage count to a CV multiplier in [lo, hi].

    Materials with the **lowest** usage are *rarest* and receive the highest
    CV. Materials with the **highest** usage are commonest and receive the
    lowest. Interpolation is linear over the observed [0, max_usage] range.
    """
    if max_usage <= 0:
        return 1.0
    # Clamp usage into the observed range.
    u = max(0, min(int(usage_count), max_usage))
    # Inverse-linear: 0 usage → hi, max usage → lo.
    return hi - (hi - lo) * (u / max_usage)


def merged_materials(loot_cards: list = None) -> list:
    """Central list ∪ Loot card materials, sorted."""
    central = set(load_central_materials())
    if loot_cards:
        central.update(collect_from_loot_cards(loot_cards))
    return sorted(central)


def load_material_effects() -> dict:
    """Return {material_name: {"effect_id": str, "vals": dict, "opt_vals": dict}}"""
    if _MATERIALS_FILE and os.path.exists(_MATERIALS_FILE):
        with open(_MATERIALS_FILE, encoding="utf-8") as f:
            return json.load(f).get("material_effects", {})
    return {}


def save_material_effects(effects: dict) -> None:
    """Persist material_effects dict into materials.json (merges with existing data)."""
    if not _MATERIALS_FILE:
        return
    existing = {}
    if os.path.exists(_MATERIALS_FILE):
        with open(_MATERIALS_FILE, encoding="utf-8") as f:
            existing = json.load(f)
    existing["material_effects"] = effects
    os.makedirs(os.path.dirname(_MATERIALS_FILE), exist_ok=True)
    with open(_MATERIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=4, ensure_ascii=False)
