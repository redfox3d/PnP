"""
sigil_registry.py – Single source of truth for sigil (box) types (B3).

The Content Editor, Card Builder, and Random Generator all need the same
list of sigil types. Historically BOX_TYPES in ``card_builder.constants``
was the canonical source, but ``box_config.json`` is what the generator
actually reads. When a user adds a new sigil they expect it to appear in:

  * every content item's "allowed_in_blocks" grid,
  * the per-variable allowed_box_types grid,
  * the generator's block rules,
  * the card editor's block dropdown.

This module provides one function the whole app can call:

    >>> get_sigil_names()
    ['Play', 'Excavate', 'Hand', 'Concentration', 'Enchant',
     'Equipped', 'Exhausted', 'Forgotten', 'Sacrifice',
     'Ingredient', 'Materials']

Source of truth is ``box_config.json``; ``BOX_TYPES`` from
``card_builder.constants`` is only used as a fallback when the file
is missing or empty.
"""

from __future__ import annotations

import json
import os
from typing import Callable, List

_DATA_PATH = os.path.join(os.path.dirname(__file__), "cc_data", "box_config.json")

# Observer callbacks — UI panels subscribe here so they refresh when the
# sigil list changes (adding/removing a sigil).
_subscribers: list[Callable[[list[str]], None]] = []


def _load_json_keys() -> List[str]:
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return list(data.keys())
    except Exception:
        pass
    return []


def get_sigil_names() -> List[str]:
    """Return the canonical sigil name list.

    Source of truth is ``box_config.json`` — the file the generator and the
    sigil-manager UI actually edit. ``BOX_TYPES`` is only consulted as a
    *fallback* when ``box_config.json`` is missing or empty (first-run /
    broken install). This means sigils removed from ``box_config.json``
    (e.g. legacy "Fleeting") no longer appear in the editor anywhere.
    """
    keys = _load_json_keys()
    if keys:
        return list(keys)
    # Fallback: only used when box_config.json doesn't exist yet
    try:
        from card_builder.constants import BOX_TYPES
        return list(BOX_TYPES)
    except Exception:
        return ["Play", "Excavate", "Hand", "Concentration", "Enchant",
                "Equipped", "Exhausted", "Forgotten", "Sacrifice",
                "Ingredient", "Materials"]


def load_box_config() -> dict:
    """Return the full box_config dict (sigil → settings)."""
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_box_config(data: dict) -> None:
    """Persist the full box_config dict back to disk."""
    with open(_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    _notify()


def update_sigil(name: str, **fields) -> bool:
    """Merge the given fields into the named sigil's entry.

    Use ``None`` for a field to delete it. Returns True if anything changed.
    """
    d = load_box_config()
    if name not in d:
        return False
    entry = d[name]
    changed = False
    for k, v in fields.items():
        if v is None:
            if k in entry:
                entry.pop(k); changed = True
        elif entry.get(k) != v:
            entry[k] = v
            changed = True
    if changed:
        save_box_config(d)
    return changed


# ── Sigil property getters with fallbacks ─────────────────────────────────────

def sigil_allowed_card_types(name: str) -> list:
    """Return the list of card types this sigil is allowed on. Falls back
    to ``card_builder.constants.SIGILS_FOR_CARD_TYPE`` lookup."""
    cfg = load_box_config().get(name, {})
    if isinstance(cfg.get("allowed_card_types"), list):
        return list(cfg["allowed_card_types"])
    # Fallback: scan SIGILS_FOR_CARD_TYPE
    try:
        from card_builder.constants import SIGILS_FOR_CARD_TYPE
        return [ct for ct, sigs in SIGILS_FOR_CARD_TYPE.items()
                if name in sigs]
    except Exception:
        return []


def sigil_card_type_weight(name: str, card_type: str,
                            subtype: str = "") -> float:
    """Per-card-type frequency weight for this sigil.

    Lookup order:
      1. box_config[name]["subtype_weights"][f"{card_type}.{subtype}"]
      2. box_config[name]["card_type_weights"][card_type]
      3. 1.0 if card_type is allowed at all (allowed_card_types check), else 0.
    """
    cfg = load_box_config().get(name, {})
    if subtype:
        sw = cfg.get("subtype_weights") or {}
        key = f"{card_type}.{subtype}"
        if key in sw:
            try: return float(sw[key])
            except (TypeError, ValueError): pass
    ctw = cfg.get("card_type_weights") or {}
    if card_type in ctw:
        try: return float(ctw[card_type])
        except (TypeError, ValueError): pass
    # Fallback: allowed → 1.0, otherwise 0
    return 1.0 if card_type in sigil_allowed_card_types(name) else 0.0


def sigil_label_override(name: str, card_type: str) -> str | None:
    """Return the per-card-type display label override for this sigil, or
    None if the caller should fall back to the constants.py default."""
    cfg = load_box_config().get(name, {})
    labels = cfg.get("card_type_labels") or {}
    return labels.get(card_type) if labels else None


def sigil_color(name: str) -> str | None:
    """Per-sigil colour override (None → fall back to BOX_COLORS)."""
    cfg = load_box_config().get(name, {})
    return cfg.get("color")


def sigil_symbol(name: str) -> str | None:
    """Per-sigil symbol override (None → fall back to BOX_SYMBOLS)."""
    cfg = load_box_config().get(name, {})
    return cfg.get("symbol")


def add_sigil(name: str, rarity: int = 5, cv_modifier: float = 1.0) -> bool:
    """Append a new sigil to box_config.json. Returns True on success."""
    name = name.strip()
    if not name:
        return False
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    if name in data:
        return False
    data[name] = {
        "rarity": rarity,
        "cv_modifier": cv_modifier,
        "element_weights": {},
        "incompatible_with": [],
    }
    with open(_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    _propagate_to_content(name)
    _notify()
    return True


def remove_sigil(name: str) -> bool:
    """Remove a sigil from box_config.json. Returns True on success."""
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False
    if name not in data:
        return False
    data.pop(name)
    with open(_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    _notify()
    return True


def subscribe(cb: Callable[[list[str]], None]) -> None:
    """Register a callback that fires with the new list when sigils change."""
    if cb not in _subscribers:
        _subscribers.append(cb)


def unsubscribe(cb: Callable[[list[str]], None]) -> None:
    if cb in _subscribers:
        _subscribers.remove(cb)


def _notify() -> None:
    names = get_sigil_names()
    for cb in list(_subscribers):
        try:
            cb(names)
        except Exception:
            pass


# ── Propagation ──────────────────────────────────────────────────────────────

_CONTENT_FILES = ["effects.json", "triggers.json", "costs.json", "conditions.json"]


def prune_stale_allowed_blocks(item: dict) -> bool:
    """Normalise ``allowed_in_blocks`` keys: rewrite legacy aliases
    (Discard→Exhausted, Lost/Fleeting→Forgotten, Enchantment→Concentration),
    drop names that no longer exist as sigils.

    Returns True if anything changed.
    """
    aib = item.get("allowed_in_blocks")
    if not isinstance(aib, dict):
        return False
    try:
        from card_builder.constants import BOX_TYPE_ALIASES as _aliases
    except Exception:
        _aliases = {}
    valid = set(get_sigil_names())
    changed = False

    # Pass 1: alias rewrite (preserve the existing value, OR with the new
    # key's value if both exist — usually the new key is missing).
    for old_name, new_name in _aliases.items():
        if old_name in aib:
            old_val = aib.pop(old_name)
            if new_name not in aib:
                aib[new_name] = old_val
            else:
                aib[new_name] = bool(aib[new_name]) or bool(old_val)
            changed = True

    # Pass 2: drop anything still not in the registry
    stale = [k for k in aib if k not in valid]
    for k in stale:
        aib.pop(k, None)
        changed = True
    return changed


def _propagate_to_content(new_name: str) -> None:
    """When a sigil is added, default it to True in every existing
    allowed_in_blocks dict so old content opts in by default."""
    root = os.path.join(os.path.dirname(__file__), "cc_data")
    for fn in _CONTENT_FILES:
        path = os.path.join(root, fn)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        changed = False
        for cat, items in (d.items() if isinstance(d, dict) else []):
            if not isinstance(items, list):
                continue
            for it in items:
                aib = it.get("allowed_in_blocks")
                if isinstance(aib, dict) and new_name not in aib:
                    aib[new_name] = True
                    changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
