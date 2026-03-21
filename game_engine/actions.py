"""Action definitions for the game engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ActionType(str, Enum):
    REST       = "rest"
    PLAY_CARD  = "play_card"
    MOVE       = "move"
    USE_WEAPON = "use_weapon"
    ACTIVATE   = "activate"
    END_TURN   = "end_turn"


@dataclass
class Action:
    type:       ActionType
    player_idx: int

    # PLAY_CARD / ACTIVATE
    card_iid:               Optional[int]       = None
    box_idx:                Optional[int]        = None
    ability_idx:            Optional[int]        = None
    chosen_effect_indices:  List[int]            = field(default_factory=list)
    variable_values:        Dict[str, Any]       = field(default_factory=dict)
    option_values:          Dict[str, Any]       = field(default_factory=dict)

    # MOVE
    target_hex: Optional[tuple] = None   # (q, r)

    # USE_WEAPON
    target_player_idx: Optional[int] = None
    hand_slot:         str           = "right_hand"

    def __repr__(self) -> str:
        if self.type == ActionType.PLAY_CARD:
            return f"Action(PLAY iid={self.card_iid} box={self.box_idx} ab={self.ability_idx})"
        if self.type == ActionType.MOVE:
            return f"Action(MOVE {self.target_hex})"
        if self.type == ActionType.USE_WEAPON:
            return f"Action(WEAPON {self.hand_slot} → P{self.target_player_idx})"
        return f"Action({self.type.value} P{self.player_idx})"
