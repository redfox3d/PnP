"""Combat resolution: attack rolls, dodge, armor, weapon damage."""
from __future__ import annotations
import random as _random

from .state import PlayerState
from .constants import Element, ELEMENT_DIE, ARMOR_SLOTS, BASE_MOVEMENT, DEFAULT_WEAPON_SIDES
from .dice import roll


def _slot_value(player: PlayerState, slot, key: str, default: int = 0) -> int:
    slot_key = slot.value if hasattr(slot, "value") else slot
    card = player.equipment.get(slot_key)
    if card is not None:
        return card.card_data.get(key, default)
    return default


def calc_dodge(player: PlayerState) -> int:
    """Sum dodge modifiers from armor slots (head, chest, legs)."""
    return sum(_slot_value(player, s, "dodge_modifier") for s in ARMOR_SLOTS)


def calc_armor(player: PlayerState) -> int:
    """Sum flat armor reduction from armor slots."""
    return sum(_slot_value(player, s, "armor") for s in ARMOR_SLOTS)


def calc_movement(player: PlayerState) -> int:
    """Movement points this turn (from shoes equipment, or base 2)."""
    card = player.equipment.get("shoes")
    if card is not None:
        return card.card_data.get("movement", BASE_MOVEMENT)
    return BASE_MOVEMENT


def get_weapon_stats(player: PlayerState, slot: str = "right_hand") -> tuple:
    """
    Returns (damage_sides, damage_count, element_str).
    Defaults to d4, 1 die, None element (becomes GENERIC in attack).
    """
    card = player.equipment.get(slot)
    if card is not None:
        return (
            card.card_data.get("damage_sides",  DEFAULT_WEAPON_SIDES),
            card.card_data.get("damage_count",  1),
            card.card_data.get("element",       None),
        )
    return (DEFAULT_WEAPON_SIDES, 1, None)


def resolve_attack(
    attacker:      PlayerState,
    defender:      PlayerState,
    element:       Element,
    weapon_sides:  int  = DEFAULT_WEAPON_SIDES,
    weapon_count:  int  = 1,
    rng:           _random.Random = None,
) -> dict:
    """
    Resolve one attack.

    Attack roll = combat_stat + hit_skill + d{element_die}
    Hit if attack_roll > dodge_val
    Damage = sum(weapon_count × d{weapon_sides}) − armor

    Returns:
        hit (bool), damage (int), attack_roll (int), dodge_val (int)
    """
    die_sides   = ELEMENT_DIE.get(element, 6)
    combat_stat = attacker.stats.combat(element)
    hit_skill   = attacker.stats.hit(element)
    attack_roll = combat_stat + hit_skill + roll(die_sides, rng=rng)
    dodge_val   = calc_dodge(defender)

    if attack_roll > dodge_val:
        raw_dmg    = sum(roll(weapon_sides, rng=rng) for _ in range(weapon_count))
        actual_dmg = max(0, raw_dmg - calc_armor(defender))
        return {"hit": True,  "damage": actual_dmg,
                "attack_roll": attack_roll, "dodge_val": dodge_val}
    else:
        return {"hit": False, "damage": 0,
                "attack_roll": attack_roll, "dodge_val": dodge_val}
