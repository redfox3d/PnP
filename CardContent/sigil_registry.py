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
    ['Play', 'Excavate', 'Hand', 'Concentration', 'Equipped',
     'Exhausted', 'Fleeting', 'Discard']

The list is built by UNIONing the static ``BOX_TYPES`` constant with the
keys of ``box_config.json``. Order matches ``BOX_TYPES`` where possible
and appends new entries at the end.
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
    """Return the canonical sigil name list (BOX_TYPES ∪ box_config keys)."""
    try:
        from card_builder.constants import BOX_TYPES
        base = list(BOX_TYPES)
    except Exception:
        base = ["Play", "Excavate", "Hand", "Concentration",
                "Equipped", "Exhausted", "Fleeting", "Discard"]

    seen = set(base)
    for k in _load_json_keys():
        if k not in seen:
            base.append(k)
            seen.add(k)
    return base


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
