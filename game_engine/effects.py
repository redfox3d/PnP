"""
Effect handlers.

Each handler signature:
    handler(state, player_idx, vars_, opts_, ctx) -> (GameState, str)

`ctx` is a dict that may contain:
    source_card     – CardInstance that triggered this effect
    target_card_iid – iid of a targeted card (for Change_Any_Cards_Position etc.)
    rng             – optional random.Random
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState

from .constants import Zone


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _zone_from_position_name(name: str) -> Zone:
    return {
        "Add to Hand": Zone.HAND,
        "Discard":     Zone.DISCARD,
        "Forget":      Zone.FORGOTTEN,
        "Lose":        Zone.LOST,
    }.get(name, Zone.DISCARD)


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------

def _draw(state: GameState, player_idx: int, vars_: dict, opts_: dict, ctx: dict):
    player = state.players[player_idx]
    n = int(vars_.get("X", 1))
    drawn = []
    for _ in range(n):
        if player.skills_deck:
            card = player.skills_deck.pop(0)
            card.zone = Zone.HAND
            player.hand.append(card)
            drawn.append(card.card_id)
    return state, f"P{player_idx} draws {len(drawn)}"


def _change_this_card_position(state, player_idx, vars_, opts_, ctx):
    card = ctx.get("source_card")
    if card is None:
        return state, "[change_this] no source_card in ctx"
    target_name = opts_.get("0", "Discard")
    zone = _zone_from_position_name(target_name)
    state.players[player_idx].move_card(card.iid, zone)
    return state, f"P{player_idx} moves {card.card_id} -> {zone.value}"


def _change_any_card_position(state, player_idx, vars_, opts_, ctx):
    iid = ctx.get("target_card_iid")
    if iid is None:
        return state, "[change_any] no target_card_iid in ctx"
    target_name = opts_.get("0", "Discard")
    zone = _zone_from_position_name(target_name)
    for p in state.players:
        if p.move_card(iid, zone):
            return state, f"Card {iid} -> {zone.value}"
    return state, f"[change_any] card {iid} not found"


def _use_weapon(state, player_idx, vars_, opts_, ctx):
    """Attack the opponent using the equipped weapon (or d4 unarmed)."""
    from .combat import resolve_attack, get_weapon_stats
    from .constants import Element

    opp_idx = 1 - player_idx
    player  = state.players[player_idx]
    opp     = state.players[opp_idx]

    slot              = ctx.get("hand_slot", "right_hand")
    sides, count, el  = get_weapon_stats(player, slot)
    try:
        element = Element(el) if el else Element.GENERIC
    except ValueError:
        element = Element.GENERIC

    result = resolve_attack(player, opp, element, sides, count, rng=ctx.get("rng"))
    if result["hit"]:
        opp.hp = max(0, opp.hp - result["damage"])
        if opp.hp <= 0:
            state.winner = player_idx
            state.phase  = "done"
        return state, (f"P{player_idx} weapon HIT {result['damage']} dmg "
                       f"(roll {result['attack_roll']} > dodge {result['dodge_val']})")
    return state, (f"P{player_idx} weapon MISS "
                   f"(roll {result['attack_roll']} <= dodge {result['dodge_val']})")


def _generate_meta_mana_token(state, player_idx, vars_, opts_, ctx):
    token = f"p{player_idx}_meta_token"
    state.initiative_deck.append(token)
    return state, f"P{player_idx} adds Meta Mana Token to initiative deck"


# Add stubs for future effects so the resolver never hard-errors
def _stub(state, player_idx, vars_, opts_, ctx):
    return state, "[effect not yet implemented]"


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

EFFECT_HANDLERS: dict = {
    "Draw":                        _draw,
    "Change_This_Card_Position":   _change_this_card_position,
    "Change_Any_Cards_Position":   _change_any_card_position,
    "Use_Weapon":                  _use_weapon,
    "Generate_Meta_Mana_Token":    _generate_meta_mana_token,
    # placeholders
    "Grow":          _stub,
    "ApplyPotion":   _stub,
    "Pulverize":     _stub,
}


def apply_effect(state: GameState, player_idx: int,
                 effect_data: dict, ctx: dict) -> tuple:
    """Dispatch effect_data to its handler. Returns (state, log_str)."""
    eid     = effect_data.get("effect_id", "")
    vars_   = effect_data.get("variable_values",  {})
    opts_   = effect_data.get("option_values",    {})
    handler = EFFECT_HANDLERS.get(eid, _stub)
    return handler(state, player_idx, vars_, opts_, ctx)


def register_effect(effect_id: str, handler) -> None:
    """Allow external code to register new effect handlers at runtime."""
    EFFECT_HANDLERS[effect_id] = handler
