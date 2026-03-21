"""
Encode a GameState as a flat float32 numpy array for the RL policy.

Layout (per player, own player first):
  [hp_norm, stats x12, position x2, turn_flags x4, zone_sizes x6,
   hand_cards x (MAX_HAND * CARD_FEAT),
   play_cards x (MAX_PLAY * CARD_FEAT),
   equip_slots x (8 * CARD_FEAT)]
  + global: [round_norm, is_active, initiative_deck_size]
"""
from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_engine.state import GameState, PlayerState, CardInstance

# ---- layout constants -------------------------------------------------------
MAX_HAND  = 10
MAX_PLAY  = 5
CARD_FEAT = 8      # features per card slot

EQUIP_SLOTS = ["head", "backpack", "chest", "belt",
               "left_hand", "legs", "right_hand", "shoes"]
ELEMENTS    = ["Fire", "Metal", "Ice", "Nature", "Blood", "Meta", "Generic"]

# ---- action space definition ------------------------------------------------
# 0       REST
# 1       END_TURN
# 2-7     MOVE direction 0-5  (fixed hex direction order)
# 8       USE_WEAPON right_hand
# 9       USE_WEAPON left_hand
# 10..19  PLAY card k from hand (k = 0..MAX_HAND-1)
ACTION_DIM = 2 + 6 + 2 + MAX_HAND   # = 20

HEX_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

# ---- computed dim -----------------------------------------------------------
_PLAYER_FEATURES_DIM = (
    1           # hp_norm
    + 12        # stats
    + 2         # position
    + 4         # turn flags
    + 6         # zone sizes
    + MAX_HAND * CARD_FEAT
    + MAX_PLAY  * CARD_FEAT
    + len(EQUIP_SLOTS) * CARD_FEAT
)
STATE_DIM = 2 * _PLAYER_FEATURES_DIM + 3   # 2 players + global


# ---------------------------------------------------------------------------

def _card_vec(card) -> np.ndarray:
    """8-float encoding for one card slot (or zeros if empty)."""
    v = np.zeros(CARD_FEAT, dtype=np.float32)
    if card is None:
        return v
    v[0] = 1.0   # present
    el = card.card_data.get("element", "Generic")
    v[1] = ELEMENTS.index(el) / max(len(ELEMENTS) - 1, 1) if el in ELEMENTS else 0.0
    v[2] = min(float(card.card_data.get("cv", 0.0)) / 10.0, 1.0)
    box_types = {b.get("type", "") for b in card.card_data.get("boxes", [])}
    v[3] = float("Play"          in box_types)
    v[4] = float("Enchantment"   in box_types)
    v[5] = float("Concentration" in box_types)
    v[6] = float("Hand"          in box_types)
    v[7] = float("Trigger"       in box_types or any(
        any(a.get("type") == "Trigger" for a in b.get("abilities", []))
        for b in card.card_data.get("boxes", [])
    ))
    return v


def _player_vec(player, max_hp: float) -> np.ndarray:
    parts: list[np.ndarray] = []

    # HP
    parts.append(np.array([player.hp / max(max_hp, 1)], dtype=np.float32))

    # Stats (normalised /20)
    s = player.stats
    parts.append(np.array([
        s.ausdauer / 20, s.kraft / 20, s.beweglichkeit / 20,
        s.wahrnehmung / 20, s.geschwindigkeit / 20, s.basteln / 20,
        s.empathie / 20, s.wissen / 20, s.ueberzeugungskraft / 20,
        s.naturwissen / 20, s.selbstbewusstsein / 20, s.intelligenz / 20,
    ], dtype=np.float32))

    # Position
    parts.append(np.array([player.position[0] / 10.0, player.position[1] / 10.0],
                           dtype=np.float32))

    # Turn flags
    parts.append(np.array([
        player.movement_remaining / 5.0,
        float(player.has_played),
        float(player.has_rested),
        float(player.has_attacked),
    ], dtype=np.float32))

    # Zone sizes
    parts.append(np.array([
        len(player.skills_deck)   / 100.0,
        len(player.backpack_deck) / 100.0,
        len(player.discard)       / 50.0,
        len(player.forgotten)     / 50.0,
        len(player.lost)          / 50.0,
        len(player.available_supplies) / 5.0,
    ], dtype=np.float32))

    # Hand cards
    hand_vecs = [_card_vec(player.hand[i] if i < len(player.hand) else None)
                 for i in range(MAX_HAND)]
    parts.append(np.concatenate(hand_vecs))

    # Play zone
    play_vecs = [_card_vec(player.play_zone[i] if i < len(player.play_zone) else None)
                 for i in range(MAX_PLAY)]
    parts.append(np.concatenate(play_vecs))

    # Equipment
    for slot in EQUIP_SLOTS:
        parts.append(_card_vec(player.equipment.get(slot)))

    result = np.concatenate(parts)
    assert len(result) == _PLAYER_FEATURES_DIM, (
        f"player vec size mismatch: {len(result)} != {_PLAYER_FEATURES_DIM}"
    )
    return result


def encode_state(state: GameState, pov_player: int = 0) -> np.ndarray:
    """
    Encode GameState as a fixed-size float32 vector.
    pov_player's features always come first so the policy is consistent.
    """
    max_hp = float(max((p.stats.max_hp for p in state.players), default=1) or 1)
    own  = _player_vec(state.players[pov_player],     max_hp)
    opp  = _player_vec(state.players[1 - pov_player], max_hp)
    meta = np.array([
        state.round_num / 100.0,
        float(state.active_player_idx == pov_player),
        len(state.initiative_deck) / 10.0,
    ], dtype=np.float32)
    return np.concatenate([own, opp, meta])


def get_state_dim() -> int:
    return STATE_DIM
