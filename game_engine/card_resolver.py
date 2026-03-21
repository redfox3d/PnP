"""
Card / ability resolution.

Handles:
  - Condition checking
  - Cost affordability and payment (mana = sacrifice supplies → Lost)
  - Effect dispatching (with X-of-Y choice support)
"""
from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState, CardInstance

from .constants import Zone
from .effects import apply_effect


# ---------------------------------------------------------------------------
# Condition checking
# ---------------------------------------------------------------------------

def check_conditions(state: GameState, player_idx: int, conditions: dict) -> bool:
    """
    Evaluate all id_conditions in `conditions`.
    Returns True if all are satisfied (or there are none).

    Stub implementation: always returns True until conditions are fully defined.
    TODO: implement per-condition checks when condition content is populated.
    """
    if not conditions:
        return True
    id_conds = conditions.get("id_conditions", [])
    for entry in id_conds:
        if not isinstance(entry, dict):
            continue
        # Each entry: {id, val_min, val_max, ...}
        # TODO: look up the referenced stat/variable value and range-check it
        pass
    return True


# ---------------------------------------------------------------------------
# Cost handling
# ---------------------------------------------------------------------------

def can_afford(player, costs: list) -> bool:
    """Return True if player's available_supplies can cover all mana costs."""
    if not costs:
        return True

    # Build required {element: count}
    required: dict[str, int] = {}
    for cost in costs:
        if cost.get("effect_id") != "Mana":
            continue
        el  = cost.get("variable_values", {}).get("element", "Generic")
        amt = int(cost.get("variable_values", {}).get("X", 1))
        required[el] = required.get(el, 0) + amt

    # Build available {element: count}
    available: dict[str, int] = {}
    for s in player.available_supplies:
        el = s.card_data.get("element", "Generic")
        available[el] = available.get(el, 0) + 1

    generic_pool = sum(available.values())  # any supply can pay Generic

    for el, amt in required.items():
        if el == "Generic":
            if generic_pool < amt:
                return False
            generic_pool -= amt
        else:
            have = available.get(el, 0)
            if have < amt:
                return False
    return True


def pay_costs(state: GameState, player_idx: int, costs: list) -> tuple:
    """Sacrifice supplies to pay mana costs (supplies → Lost zone)."""
    player = state.players[player_idx]
    log_parts = []

    for cost in costs:
        if cost.get("effect_id") != "Mana":
            continue
        el  = cost.get("variable_values", {}).get("element", "Generic")
        amt = int(cost.get("variable_values", {}).get("X", 1))
        paid = 0
        remaining = []
        for supply in player.available_supplies:
            s_el = supply.card_data.get("element", "Generic")
            if paid < amt and (el == "Generic" or s_el == el):
                supply.zone = Zone.LOST
                player.lost.append(supply)
                paid += 1
                log_parts.append(supply.card_id)
            else:
                remaining.append(supply)
        player.available_supplies = remaining

    return state, f"paid costs ({', '.join(log_parts)})" if log_parts else "no mana cost"


# ---------------------------------------------------------------------------
# Ability resolution
# ---------------------------------------------------------------------------

def resolve_ability(
    state:            GameState,
    player_idx:       int,
    ability:          dict,
    source_card:      CardInstance,
    chosen_indices:   Optional[List[int]] = None,
    ctx:              Optional[dict]      = None,
) -> tuple[GameState, list]:
    """
    Fully resolve one ability block:
      1. Check costs are affordable
      2. Pay costs
      3. Apply chosen effects
      4. Apply continuous effects (always active while card stays in play)

    `chosen_indices` selects which effect entries to execute when choose_n < len(effects).
    If None, all effects are executed.

    Returns (new_state, list_of_log_strings).
    """
    ctx = dict(ctx or {})
    ctx["source_card"] = source_card
    logs: list = []

    # -- costs ---------------------------------------------------------------
    costs = ability.get("costs", [])
    if not can_afford(state.players[player_idx], costs):
        return state, ["cannot afford costs – ability cancelled"]
    state, log = pay_costs(state, player_idx, costs)
    logs.append(log)

    # -- effects -------------------------------------------------------------
    effects    = ability.get("effects", [])
    choose_n   = ability.get("choose_n")

    if chosen_indices is not None and choose_n is not None:
        active_effects = [effects[i] for i in chosen_indices if i < len(effects)]
    else:
        active_effects = effects

    for eff in active_effects:
        state, log = apply_effect(state, player_idx, eff, ctx)
        logs.append(log)

    # -- continuous effects are stored on the card in play zone;
    #    they are evaluated lazily by rules.py when needed
    return state, logs
