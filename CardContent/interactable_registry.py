"""
interactable_registry.py – Single source of truth for "Interactables" (L).

Interactables are generic in-world objects that effects can reference:
``Source``, ``Door``, ``Switch``, ``Lever``, ``Lock``, ``Crystal``, etc.
The ``\\Interactable`` token in sigils / content text expands to the list of
registered IDs (mirroring the ``\\Elements`` and ``\\AOE`` mechanism), so the
generator can pick one as a normal option choice.

Storage: ``cc_data/interactables.json``::

    {
      "interactables": [
        {"id": "Source",  "weight": 10, "description": "..."},
        {"id": "Door",    "weight":  5},
        ...
      ]
    }

Public API (mirrors damage_registry.py style):
    list_interactables()                 -> ["Source", "Door", ...]
    get_interactables()                  -> full dict list
    get_weight(interactable_id)          -> float (default 10)
    pick_interactable(rng=None)          -> id (weighted)
    add_interactable(id, weight=10, description="")
    remove_interactable(id)
    set_weight(id, weight)
"""

from __future__ import annotations

import json
import os
import random

_DIR  = os.path.join(os.path.dirname(__file__), "cc_data")
_PATH = os.path.join(_DIR, "interactables.json")

DEFAULT_WEIGHT = 10.0

# Seeded so a fresh install ships with at least *some* registered objects.
_DEFAULTS: list[dict] = [
    {"id": "Source",    "weight": 10, "description": "Resource node"},
    {"id": "Door",      "weight":  6, "description": "Passage that can be opened/closed"},
    {"id": "Switch",    "weight":  6, "description": "Generic toggle"},
    {"id": "Lever",     "weight":  4, "description": "Mechanical lever"},
    {"id": "Lock",      "weight":  4, "description": "Lock requiring a key"},
    {"id": "Crystal",   "weight":  4, "description": "Magical crystal"},
    {"id": "Chest",     "weight":  4, "description": "Container with loot"},
    {"id": "Altar",     "weight":  3, "description": "Ritual altar"},
]


def _load() -> dict:
    if os.path.exists(_PATH):
        try:
            with open(_PATH, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and "interactables" in d:
                return d
        except Exception:
            pass
    # First-run: write defaults so the file exists for editors to read/edit.
    d = {"interactables": list(_DEFAULTS)}
    _save(d)
    return d


def _save(d: dict) -> None:
    os.makedirs(_DIR, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


# ── Read API ────────────────────────────────────────────────────────────────

def get_interactables() -> list[dict]:
    return list(_load().get("interactables", []))


def list_interactables() -> list[str]:
    return [it["id"] for it in get_interactables() if it.get("id")]


def get_weight(interactable_id: str) -> float:
    for it in get_interactables():
        if it.get("id") == interactable_id:
            try:
                return float(it.get("weight", DEFAULT_WEIGHT))
            except (TypeError, ValueError):
                return DEFAULT_WEIGHT
    return DEFAULT_WEIGHT


def pick_interactable(rng: random.Random | None = None) -> str:
    rng = rng or random
    items = get_interactables()
    if not items:
        return ""
    weights: list[float] = []
    ids: list[str] = []
    for it in items:
        try:
            w = float(it.get("weight", DEFAULT_WEIGHT))
        except (TypeError, ValueError):
            w = DEFAULT_WEIGHT
        if w <= 0:
            continue
        ids.append(it.get("id", ""))
        weights.append(w)
    if not ids:
        return ""
    return rng.choices(ids, weights=weights, k=1)[0]


# ── Write API ───────────────────────────────────────────────────────────────

def add_interactable(interactable_id: str, weight: float = DEFAULT_WEIGHT,
                      description: str = "") -> bool:
    if not interactable_id:
        return False
    d = _load()
    items = d.setdefault("interactables", [])
    if any(it.get("id") == interactable_id for it in items):
        return False
    items.append({"id": interactable_id, "weight": float(weight),
                  "description": description})
    _save(d)
    return True


def remove_interactable(interactable_id: str) -> bool:
    d = _load()
    items = d.get("interactables", [])
    new_items = [it for it in items if it.get("id") != interactable_id]
    if len(new_items) == len(items):
        return False
    d["interactables"] = new_items
    _save(d)
    return True


def set_weight(interactable_id: str, weight: float) -> bool:
    d = _load()
    for it in d.get("interactables", []):
        if it.get("id") == interactable_id:
            it["weight"] = float(weight)
            _save(d)
            return True
    return False


def set_description(interactable_id: str, description: str) -> bool:
    d = _load()
    for it in d.get("interactables", []):
        if it.get("id") == interactable_id:
            it["description"] = description
            _save(d)
            return True
    return False
