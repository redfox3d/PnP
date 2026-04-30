"""
models.py – card data model, factory functions, and JSON persistence.

Categories:
    Items   → Equipment, Supplies
    Skills  → Spells, Prowess
    Recipes → Potions, Phials, Tinctures
"""

import json
import os

from .constants import ELEMENTS

CARD_CATEGORIES = {
    "Loot":    ["Equipment", "Supplies"],
    "Skills":  ["Spells", "Prowess"],
    "Recipes": ["Potions", "Phials", "Tinctures"],
    # NEW: in-play references the player accumulates / discards.
    "World":   ["Tokens", "Creatures", "StatusEffects"],
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
        base.update({"elements": ["Fire"], "blocks": []})
    elif card_type == "Prowess":
        # No artwork for Prowess
        base.pop("artwork", None)
        base.update({"blocks": []})
    elif card_type in ("Supplies", "Equipment"):
        base.update({
            "element_sources": [],
            "object_type":     [],
            "materials":       [],
            "weight":          0,
            "value":           0,
            "_count":          1,
            # NEW: block-based content. Empty list = blank card; the editor
            # adds optional Play/Equipped/Sacrifice/etc blocks. Materials
            # is implicit (always rendered from card.materials) — no block
            # entry needed.
            "blocks":          [],
        })
    elif card_type in ("Tokens", "Creatures", "StatusEffects"):
        # Same block-based shape as Supplies, but no weight/value/materials.
        base.update({
            "element_sources": [],
            "tags":            [],
            "blocks":          [],
        })
        if card_type == "Creatures":
            # Creatures get HP, movement, and lists of elements they are
            # strong / weak against (rendered on the right of the artwork).
            base["hp"]            = 1
            base["move"]          = 1
            base["strong_against"] = []
            base["weak_against"]   = []
        elif card_type == "StatusEffects":
            # Status effects optionally last for N turns + a sub-category
            # (one of "Condition", "Curse", "Blessing").
            base["duration"] = 1
            base["subtype"]  = "Condition"
    elif card_type == "Alchemy":
        base.update({
            "ingredients":       [],
            "result_content_id": "",
            "result_text":       "",
            "on_field_effect":   "",
        })
    elif card_type in ("Potions", "Phials", "Tinctures"):
        base.update({
            "recipe_type":  card_type,
            "ingredients":  [],       # list of {"material": str, "cv": 4}
            "effects":      [],       # list of {"effect_id": str, "vals": {}}
            "use_text":     "",       # rendered use/effect text
            "trigger_id":   "Manual_Trigger",   # always costs an action to use
        })
    return base


def empty_box(btype: str = "Play") -> dict:
    return {"type": btype, "abilities": []}


def _migrate_group(group: dict) -> None:
    """Migrate a single effect group to the current 'effects: [...]' list format (in-place)."""
    if "effects" in group:
        return
    if "primaries" in group:
        group["effects"] = group.pop("primaries")
    elif "primary" in group:
        group["effects"] = [group.pop("primary")]
    else:
        group["effects"] = [{"effect_id": "", "vals": {}, "opt_vals": {}}]


def empty_effect_group() -> dict:
    """One targeting group: list of primary effects + optional modifiers + optional sub-sigil."""
    return {
        "target_type": "Non Targeting",
        "primaries":   [{"effect_id": "", "vals": {}, "opt_vals": {}}],
        "modifiers":   [],
        "sub_sigil":   None,  # Optional sub-sigil attached to this group
    }


def empty_sub_sigil() -> dict:
    """Mini-ability attached to a parent sigil or effect group (must have >= 1 cost).

    Can be used in 3 ways:
    1. Attached to effect_group (Option A) - sub_sigil per group
    2. Global on ability with target_type (Option B) - sub_sigil_global with specific target
    3. Global on ability with Non Targeting (Option C) - sub_sigil_global for draw/neutral effects
    """
    return {
        "target_type":        None,  # Optional: if set, this sub-sigil has a target type
        "condition_id":       None,
        "condition_vals":     {},
        "condition_opt_vals": {},
        "costs":              [],
        "effect_groups":      [],
    }


def empty_ability() -> dict:
    return {
        "condition_id":       None,
        "condition_vals":     {},
        "condition_opt_vals": {},
        "ability_type":       "Play",
        "trigger_id":         None,
        "trigger_vals":       {},
        "trigger_opt_vals":   {},
        "costs":              [],
        "effect_groups":      [],
        "choose_n":           None,
        "choose_total":       None,
        "choose_repeat":      False,
        "sub_sigil":          None,  # OLD: global sub-sigil (for backward compat)
        "sub_sigil_global":   None,  # NEW: global sub-sigil with optional target_type
    }


def migrate_ability(ability: dict, effects_lookup: dict = None) -> dict:
    """Migrate old flat-effects ability to effect_groups format in place."""
    if "effect_groups" in ability:
        # Also migrate any groups that still use old 'primary' key
        for group in ability["effect_groups"]:
            if "primaries" not in group and "effects" not in group:
                old = group.pop("primary", {})
                group["primaries"] = [old] if old.get("effect_id") else [{"effect_id": "", "vals": {}, "opt_vals": {}}]
        return ability
    groups = []
    for eff in ability.get("effects", []):
        eid    = eff.get("effect_id", "")
        target = "Non Targeting"
        if effects_lookup:
            item   = effects_lookup.get(eid, {})
            ptypes = item.get("primary_types", [])
            if ptypes:
                target = ptypes[0]
        groups.append({"target_type": target, "primaries": [eff], "modifiers": []})
    ability["effect_groups"] = groups
    ability.setdefault("choose_total",       None)
    ability.setdefault("sub_sigil",          None)
    ability.setdefault("condition_opt_vals", {})
    ability.setdefault("trigger_id",         None)
    ability.setdefault("trigger_vals",       {})
    ability.setdefault("trigger_opt_vals",   {})
    return ability


def migrate_item_card(card: dict) -> bool:
    """Convert legacy item-card text fields into the block-based model.

    Old shape stored ``effect_text`` (the on-Play description) and
    ``equip_text`` / ``equip_cost_text`` (the persistent equip rules) as
    free-form strings. New shape stores them as block ``raw_text`` /
    ``raw_cost_text`` fields under sigil-typed blocks. Idempotent.
    """
    ct = card.get("card_type")
    if ct not in ("Equipment", "Supplies", "Alchemy"):
        return False
    blocks = card.setdefault("blocks", [])
    changed = False

    eff = (card.get("effect_text") or "").strip()
    if eff and not any(b.get("type") == "Play" for b in blocks):
        blocks.append({"type": "Play",
                        "abilities": [{"raw_text": eff,
                                        "effect_groups": [],
                                        "costs": []}]})
        changed = True

    equip = (card.get("equip_text") or "").strip()
    cost  = (card.get("equip_cost_text") or "").strip()
    if (equip or cost) and not any(b.get("type") == "Equipped" for b in blocks):
        blocks.append({"type": "Equipped",
                        "abilities": [{"raw_text": equip,
                                        "raw_cost_text": cost,
                                        "effect_groups": [],
                                        "costs": []}]})
        changed = True

    # Strip the legacy text fields so they no longer appear in saved JSON.
    if changed:
        for legacy in ("effect_text", "equip_text", "equip_cost_text"):
            card.pop(legacy, None)
    return changed


def _apply_box_aliases(cards: list) -> None:
    """B4: Rewrite Enchantment → Concentration on load (in-place).

    Also migrates legacy item cards (Equipment / Supplies / Alchemy) into
    the block-based model on load.
    """
    from .constants import canonical_box_type
    for card in cards:
        # Item-card migration must run BEFORE the alias loop so any blocks
        # produced from legacy text get the same alias rewriting.
        migrate_item_card(card)
        for blk in card.get("blocks", []):
            t = blk.get("type")
            if t:
                blk["type"] = canonical_box_type(t)


def load_cards(card_type: str) -> list:
    if not _CARDS_DIR:
        return []
    path = _cards_file(card_type)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cards = json.load(f).get("cards", [])
        _apply_box_aliases(cards)
        return cards
    return []


def save_cards(cards: list, card_type: str) -> None:
    if not _CARDS_DIR:
        raise RuntimeError("cards dir not set")
    path = _cards_file(card_type)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"cards": cards}, f, indent=4, ensure_ascii=False)
    print(f"[models] saved {len(cards)} → '{path}'")
