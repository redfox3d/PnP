"""Load card data from JSON and construct PlayerState objects."""
from __future__ import annotations
import json
import os
import random as _random

from .state import CardInstance, Stats, PlayerState, Zone
from .combat import calc_movement


def load_cards(path: str) -> list[dict]:
    """
    Load a cards JSON file.
    Accepts either a list [ {...}, ... ] or a dict {"id": {...}, ...}.
    Returns a flat list of card dicts.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        print(f"[loader] WARNING: could not load {path}: {exc}")
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Could be {"Cards": [...]} wrapper or {"id": card_dict, ...}
        for key in ("Cards", "cards", "data"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return list(data.values())
    return []


def normalize_card(card: dict) -> dict:
    """
    Normalize from card_builder format → game engine format.

    card_builder uses:
        blocks, ability_type, cost_id/vals, effect_id/vals,
        condition_id + condition_vals on ability
    game engine expects:
        boxes, type (on ability), effect_id/variable_values,
        conditions: {id_conditions: [...]}
    """
    c = dict(card)

    # id from name if missing
    if "id" not in c:
        c["id"] = c.get("name", "unknown")

    # blocks → boxes
    if "blocks" in c and "boxes" not in c:
        c["boxes"] = c.pop("blocks")

    for box in c.get("boxes", []):
        for ab in box.get("abilities", []):
            # ability_type → type
            if "ability_type" in ab and "type" not in ab:
                ab["type"] = ab.pop("ability_type")

            # normalize costs: cost_id → effect_id, vals → variable_values
            norm_costs = []
            for cost in ab.get("costs", []):
                nc = dict(cost)
                if "cost_id" in nc:
                    nc["effect_id"] = nc.pop("cost_id")
                if "vals" in nc and "variable_values" not in nc:
                    nc["variable_values"] = nc.pop("vals")
                nc.setdefault("option_values", {})
                if nc.get("effect_id"):
                    norm_costs.append(nc)
            ab["costs"] = norm_costs

            # normalize effects: vals → variable_values
            norm_effects = []
            for eff in ab.get("effects", []):
                ne = dict(eff)
                if "vals" in ne and "variable_values" not in ne:
                    ne["variable_values"] = ne.pop("vals")
                ne.setdefault("option_values", {})
                if ne.get("effect_id"):
                    norm_effects.append(ne)
            ab["effects"] = norm_effects

            # condition_id + condition_vals → conditions dict
            if "conditions" not in ab:
                cid   = ab.pop("condition_id",   None)
                cvals = ab.pop("condition_vals", {})
                if cid:
                    ab["conditions"] = {"id_conditions": [{"id": cid, **cvals}]}
                else:
                    ab["conditions"] = {}
            else:
                ab.pop("condition_id",   None)
                ab.pop("condition_vals", None)
    return c


def cards_to_instances(cards: list[dict]) -> list[CardInstance]:
    """Convert raw card dicts to CardInstance objects (normalizing format)."""
    return [CardInstance(card_id=c.get("id", c.get("name", "unknown")),
                         card_data=normalize_card(c))
            for c in cards]


def make_player(
    player_id:     int,
    stats:         dict | Stats,
    skills_cards:  list[dict],
    backpack_cards: list[dict],
    position:      tuple = None,
    equipment:     dict  = None,
    rng:           _random.Random = None,
) -> PlayerState:
    """
    Build a PlayerState ready for game start.

    Args:
        player_id:      0 or 1
        stats:          dict of stat values OR Stats instance
        skills_cards:   list of card dicts for the skills deck
        backpack_cards: list of card dicts for the backpack deck
        position:       (q, r) starting hex; defaults to (0,0) for P0, (2,-2) for P1
        equipment:      dict mapping slot_name → card_dict (optional)
        rng:            random instance for deck shuffling
    """
    r = rng or _random

    if isinstance(stats, dict):
        valid_fields = {f for f in Stats.__dataclass_fields__}
        s = Stats(**{k: v for k, v in stats.items() if k in valid_fields})
    else:
        s = stats

    if position is None:
        position = (0, 0) if player_id == 0 else (2, -2)

    # Build equipped cards
    equip: dict = {}
    if equipment:
        for slot, card_data in equipment.items():
            if card_data is not None:
                equip[slot] = CardInstance(
                    card_id=card_data.get("id", slot),
                    card_data=card_data,
                    zone=Zone.HAND,  # zone not meaningful for equipped cards
                )

    # Build decks
    sk = cards_to_instances(skills_cards)
    bk = cards_to_instances(backpack_cards)
    r.shuffle(sk)
    r.shuffle(bk)
    for c in sk:
        c.zone = Zone.SKILLS_DECK
    for c in bk:
        c.zone = Zone.BACKPACK_DECK

    p = PlayerState(
        player_id=player_id,
        stats=s,
        hp=s.max_hp,
        position=position,
        equipment=equip,
        skills_deck=sk,
        backpack_deck=bk,
    )
    # Movement is set properly at round start; pre-set from equipment here too
    p.movement_remaining = calc_movement(p)
    return p
