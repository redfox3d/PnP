"""
Turn structure and action validation / application.

Turn flow per round:
  1. _start_round()  – draw initiative, distribute draws + supplies, reset flags
  2. active_player takes actions (MOVE, PLAY_CARD or REST, USE_WEAPON, END_TURN)
  3. END_TURN -> switch to other player
  4. Other player takes actions -> END_TURN
  5. Both done -> _start_round() again
"""
from __future__ import annotations
import random

from .state   import GameState, Zone
from .actions import Action, ActionType
from .combat  import resolve_attack, calc_movement, get_weapon_stats
from .hex_grid import Hex
from .card_resolver import resolve_ability, check_conditions, can_afford
from .constants import Element


# ---------------------------------------------------------------------------
# Round initialisation
# ---------------------------------------------------------------------------

def _start_round(state: GameState, rng: random.Random = None) -> GameState:
    """
    Begin a new round:
      • shuffle & draw top initiative token -> who goes first
      • each player draws 1 skill card
      • each player gets 2 random supplies from their backpack
      • reset all per-turn flags
    """
    r = rng or random
    state.round_num += 1
    state.turns_done_this_round = 0

    # Initiative ---------------------------------------------------------
    r.shuffle(state.initiative_deck)
    token = state.initiative_deck[0] if state.initiative_deck else "p0"
    state.current_initiative = token
    if "p0" in token:
        state.first_player_idx = 0
    elif "p1" in token:
        state.first_player_idx = 1
    else:
        state.first_player_idx = r.randint(0, 1)
    state.active_player_idx = state.first_player_idx

    # Per-player setup ---------------------------------------------------
    for player in state.players:
        # Draw 1 skill card
        if player.skills_deck:
            card = player.skills_deck.pop(0)
            card.zone = Zone.HAND
            player.hand.append(card)

        # Draw 2 random supplies from backpack deck
        player.available_supplies = []
        if player.backpack_deck:
            n = min(2, len(player.backpack_deck))
            idxs = set(r.sample(range(len(player.backpack_deck)), n))
            remaining = []
            for i, c in enumerate(player.backpack_deck):
                if i in idxs:
                    player.available_supplies.append(c)
                else:
                    remaining.append(c)
            player.backpack_deck = remaining

        # Reset turn flags
        player.has_played    = False
        player.has_rested    = False
        player.has_attacked  = False
        player.turn_done     = False
        player.movement_remaining = calc_movement(player)

    state.phase = "player_turn"
    state.log.append(f"=== Round {state.round_num} | initiative: {token} | first: P{state.first_player_idx} ===")
    return state


# ---------------------------------------------------------------------------
# Valid action enumeration
# ---------------------------------------------------------------------------

def get_valid_actions(state: GameState) -> list[Action]:
    """Return all legal Actions for the currently active player."""
    if state.winner is not None:
        return []

    p_idx  = state.active_player_idx
    player = state.players[p_idx]

    actions: list[Action] = []

    # REST or PLAY (mutually exclusive, each only once)
    if not player.has_played and not player.has_rested:
        actions.append(Action(ActionType.REST, p_idx))

        for card in player.hand:
            for b_idx, box in enumerate(card.card_data.get("boxes", [])):
                if box.get("type") not in ("Play",):
                    continue
                for a_idx, ability in enumerate(box.get("abilities", [])):
                    if ability.get("type") not in ("Play", "Activate"):
                        continue
                    if not check_conditions(state, p_idx, ability.get("conditions", {})):
                        continue
                    if not can_afford(player, ability.get("costs", [])):
                        continue
                    # Build one action per valid choice combination
                    effects   = ability.get("effects", [])
                    choose_n  = ability.get("choose_n")
                    if choose_n is not None and int(choose_n) < len(effects):
                        # Generate all choose_n subsets (up to a cap for tractability)
                        from itertools import combinations
                        choose_n = int(choose_n)
                        for combo in combinations(range(len(effects)), choose_n):
                            actions.append(Action(
                                ActionType.PLAY_CARD, p_idx,
                                card_iid=card.iid,
                                box_idx=b_idx,
                                ability_idx=a_idx,
                                chosen_effect_indices=list(combo),
                            ))
                    else:
                        actions.append(Action(
                            ActionType.PLAY_CARD, p_idx,
                            card_iid=card.iid,
                            box_idx=b_idx,
                            ability_idx=a_idx,
                        ))

    # MOVE  (only within grid_radius of origin)
    if player.movement_remaining > 0:
        origin = Hex(0, 0)
        pos    = Hex(*player.position)
        for nb in pos.neighbors():
            if origin.distance(nb) <= state.grid_radius:
                actions.append(Action(ActionType.MOVE, p_idx, target_hex=(nb.q, nb.r)))

    # USE_WEAPON (once per turn, melee range = 1)
    if not player.has_attacked:
        opp     = state.players[1 - p_idx]
        my_hex  = Hex(*player.position)
        opp_hex = Hex(*opp.position)
        if my_hex.distance(opp_hex) <= 1:
            for slot in ("right_hand", "left_hand"):
                actions.append(Action(
                    ActionType.USE_WEAPON, p_idx,
                    target_player_idx=1 - p_idx,
                    hand_slot=slot,
                ))

    # Always legal: end your turn
    actions.append(Action(ActionType.END_TURN, p_idx))

    return actions


# ---------------------------------------------------------------------------
# Action application
# ---------------------------------------------------------------------------

def apply_action(state: GameState, action: Action,
                 rng: random.Random = None) -> GameState:
    """Apply `action` to a *clone* of `state` and return the new state."""
    r     = rng or random
    state = state.clone()
    p_idx  = action.player_idx
    player = state.players[p_idx]
    tag    = f"[R{state.round_num} P{p_idx}]"

    # -------------------------------------------------------------------
    if action.type == ActionType.REST:
        # All cards in discard + play_zone + hand -> skills_deck; shuffle; draw 5
        to_return = player.discard + player.play_zone + player.hand
        for c in to_return:
            c.zone = Zone.SKILLS_DECK
        player.skills_deck.extend(to_return)
        r.shuffle(player.skills_deck)
        player.discard.clear()
        player.play_zone.clear()
        player.hand.clear()

        drawn = player.skills_deck[:5]
        player.skills_deck = player.skills_deck[5:]
        for c in drawn:
            c.zone = Zone.HAND
        player.hand.extend(drawn)

        player.has_rested = True
        state.log.append(f"{tag} REST -> drew {len(drawn)}")

    # -------------------------------------------------------------------
    elif action.type == ActionType.PLAY_CARD:
        card = next((c for c in player.hand if c.iid == action.card_iid), None)
        if card is None:
            state.log.append(f"{tag} PLAY_CARD: card not found")
            return state

        boxes = card.card_data.get("boxes", [])
        if action.box_idx is None or action.box_idx >= len(boxes):
            return state
        abilities = boxes[action.box_idx].get("abilities", [])
        if action.ability_idx is None or action.ability_idx >= len(abilities):
            return state

        ability = abilities[action.ability_idx]
        ctx = {"rng": r, "hand_slot": "right_hand"}
        state, logs = resolve_ability(
            state, p_idx, ability, card,
            chosen_indices=action.chosen_effect_indices or None,
            ctx=ctx,
        )
        # Propagate winner from effect resolution
        if state.winner is not None:
            state.phase = "done"
        # Move card to play zone
        player.hand.remove(card)
        card.zone = Zone.PLAY
        player.play_zone.append(card)
        player.has_played = True
        state.log.append(f"{tag} PLAY {card.card_id}: {' | '.join(str(l) for l in logs)}")

    # -------------------------------------------------------------------
    elif action.type == ActionType.MOVE:
        if player.movement_remaining > 0 and action.target_hex:
            player.position = action.target_hex
            player.movement_remaining -= 1
            state.log.append(f"{tag} MOVE -> {action.target_hex}")

    # -------------------------------------------------------------------
    elif action.type == ActionType.USE_WEAPON:
        opp_idx = action.target_player_idx
        if opp_idx is None:
            return state
        opp = state.players[opp_idx]

        sides, count, el_str = get_weapon_stats(player, action.hand_slot)
        element = _parse_element(el_str)

        result = resolve_attack(player, opp, element, sides, count, rng=r)
        if result["hit"]:
            opp.hp = max(0, opp.hp - result["damage"])
            state.log.append(
                f"{tag} HIT {result['damage']} dmg "
                f"(roll {result['attack_roll']} > dodge {result['dodge_val']})"
            )
            if opp.hp <= 0:
                state.winner = p_idx
                state.phase  = "done"
                state.log.append(f"*** P{p_idx} WINS in round {state.round_num} ***")
        else:
            state.log.append(
                f"{tag} MISS "
                f"(roll {result['attack_roll']} ≤ dodge {result['dodge_val']})"
            )
        player.has_attacked = True

    # -------------------------------------------------------------------
    elif action.type == ActionType.END_TURN:
        player.turn_done = True
        state.turns_done_this_round += 1
        state.log.append(f"{tag} END_TURN")

        if state.winner is None:
            if state.turns_done_this_round >= 2:
                # Both players finished -> start new round
                state = _start_round(state, rng=r)
            else:
                # Other player's turn
                state.active_player_idx = 1 - p_idx

    return state


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_element(el_str) -> Element:
    if el_str:
        try:
            return Element(el_str)
        except ValueError:
            pass
    return Element.GENERIC
