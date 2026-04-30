"""
damage_registry.py – Single source of truth for Damage-Types and their
per-element / per-prowess-card rankings (C1).

File layout (next to box_config.json):
    cc_data/damage_types.json
    cc_data/damage_type_rankings.json

Ranking semantics:
    rankings[element] = [ rank0, rank1, ..., rankN ]
    Each rank is a list of {type: str, cv: float}.
    Rank k has probability weight  1 / 2**k  (normalised per draw).
    Multiple entries in one rank are equally likely within that rank.

Helpers:
    pick_damage_type(element)        -> (type_id, cv_multiplier)
    list_damage_types()              -> ["Physical", "Fire", ...]
    get_rankings(element)            -> full ranking list
    add_type(type_id, description="")
    set_rankings(element, rankings)  # persists to disk
    cv_for(element, type_id)         -> float (1.0 if unknown)
"""

from __future__ import annotations

import json
import os
import random
from typing import Tuple

_DIR = os.path.join(os.path.dirname(__file__), "cc_data")
_TYPES_PATH   = os.path.join(_DIR, "damage_types.json")
_RANKING_PATH = os.path.join(_DIR, "damage_type_rankings.json")

_MAX_RANKS_DEFAULT = 4


def _load_types() -> dict:
    try:
        with open(_TYPES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"types": []}


def _save_types(d: dict) -> None:
    with open(_TYPES_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def _load_rankings() -> dict:
    try:
        with open(_RANKING_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"max_ranks": _MAX_RANKS_DEFAULT, "elements": {}, "prowess_cards": {}}


def _save_rankings(d: dict) -> None:
    with open(_RANKING_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


# ── Public read API ─────────────────────────────────────────────────────────

def list_damage_types() -> list[str]:
    return [t["id"] for t in _load_types().get("types", [])]


def max_ranks() -> int:
    return int(_load_rankings().get("max_ranks", _MAX_RANKS_DEFAULT))


def get_rankings(element: str, section: str = "elements") -> list[list[dict]]:
    d = _load_rankings()
    return list(d.get(section, {}).get(element, []))


def cv_for(element: str, type_id: str, section: str = "elements") -> float:
    for rank in get_rankings(element, section):
        for entry in rank:
            if entry.get("type") == type_id:
                return float(entry.get("cv", 1.0))
    return 1.0


def get_range_for_type(type_id: str) -> tuple[int, int]:
    """Return ``(range_min, range_max)`` for a damage type.

    Defaults: min=0 (no lower bound), max=99 (effectively unlimited).
    Used by the generator to skip damage types whose allowed range
    interval doesn't include the chosen Range X.
    """
    for t in _load_types().get("types", []):
        if t.get("id") == type_id:
            try:
                rmin = int(t.get("range_min", 0))
            except (TypeError, ValueError):
                rmin = 0
            try:
                rmax = int(t.get("range_max", 99))
            except (TypeError, ValueError):
                rmax = 99
            return (rmin, rmax)
    return (0, 99)


def set_range_for_type(type_id: str, range_min: int | None,
                        range_max: int | None) -> bool:
    """Set/clear the allowed range interval for a damage type."""
    d = _load_types()
    for t in d.get("types", []):
        if t.get("id") != type_id:
            continue
        if range_min is None:
            t.pop("range_min", None)
        else:
            t["range_min"] = int(range_min)
        if range_max is None:
            t.pop("range_max", None)
        else:
            t["range_max"] = int(range_max)
        _save_types(d)
        return True
    return False


def _range_allows(type_id: str, range_x: int | None) -> bool:
    """True if ``range_x`` falls inside the type's [range_min, range_max]."""
    if range_x is None:
        return True
    rmin, rmax = get_range_for_type(type_id)
    return rmin <= int(range_x) <= rmax


def pick_damage_type(element: str, section: str = "elements",
                     rng: random.Random | None = None,
                     range_x: int | None = None) -> Tuple[str, float]:
    """Pick a damage type for ``element``. Returns ``(type_id, cv_mult)``.

    Rank k is weighted 1/2**k; items inside a rank are uniform.

    NEW: when ``range_x`` is given, types whose allowed range interval
    excludes this value are skipped. If filtering removes ALL options,
    we fall back to the unfiltered pool so we never return empty.
    """
    rng = rng or random
    ranks = get_rankings(element, section)
    if not ranks:
        return ("", 1.0)
    # Per-rank probability weights: 1, 1/2, 1/4, 1/8 ...
    flat: list[tuple[dict, float]] = []
    for k, rank in enumerate(ranks):
        if not rank:
            continue
        per = (1.0 / (2 ** k)) / len(rank)
        for entry in rank:
            flat.append((entry, per))
    if not flat:
        return ("", 1.0)

    if range_x is not None:
        filtered = [(e, w) for e, w in flat
                    if _range_allows(e.get("type", ""), range_x)]
        if filtered:
            flat = filtered
        # else: keep the unfiltered list as a soft fallback

    items, weights = zip(*flat)
    pick = rng.choices(items, weights=weights, k=1)[0]
    return (pick.get("type", ""), float(pick.get("cv", 1.0)))


# ── Public write API ────────────────────────────────────────────────────────

def add_type(type_id: str, description: str = "") -> bool:
    d = _load_types()
    if any(t.get("id") == type_id for t in d.get("types", [])):
        return False
    d.setdefault("types", []).append({"id": type_id, "description": description})
    _save_types(d)
    return True


def remove_type(type_id: str) -> bool:
    d = _load_types()
    before = len(d.get("types", []))
    d["types"] = [t for t in d.get("types", []) if t.get("id") != type_id]
    if len(d["types"]) == before:
        return False
    _save_types(d)
    # also scrub from rankings
    r = _load_rankings()
    for section in ("elements", "prowess_cards"):
        for el, ranks in list(r.get(section, {}).items()):
            new_ranks = []
            for rank in ranks:
                new_rank = [e for e in rank if e.get("type") != type_id]
                new_ranks.append(new_rank)
            r[section][el] = new_ranks
    _save_rankings(r)
    return True


def set_rankings(element: str, ranks: list[list[dict]],
                 section: str = "elements") -> None:
    d = _load_rankings()
    d.setdefault(section, {})[element] = ranks
    _save_rankings(d)
