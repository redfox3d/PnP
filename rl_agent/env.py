"""
Gymnasium environment wrapping the card game engine.

Observation:  flat float32 vector (STATE_DIM,)
Action space: Discrete(ACTION_DIM) with action mask

Agent always plays as P0.
Opponent policy is injectable; defaults to uniform-random over valid actions.

Install deps:
    pip install gymnasium numpy
"""
from __future__ import annotations
import random
from typing import Callable, Optional

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    raise ImportError("Install gymnasium: pip install gymnasium")

from game_engine import Game, make_player, Stats, sample_cards
from game_engine.actions import Action, ActionType
from game_engine.hex_grid import Hex
from rl_agent.encoder import (
    encode_state, get_state_dim, ACTION_DIM, MAX_HAND, HEX_DIRS
)


class CardGameEnv(gym.Env):
    """
    Single-agent environment.  Agent = P0, opponent = injectable policy.

    Extra method:
        action_masks() -> np.ndarray[bool, ACTION_DIM]
            For use with MaskablePPO (sb3-contrib) or custom masking.
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        player_stats:    Stats    = None,
        skill_cards:     list     = None,
        backpack_cards:  list     = None,
        opponent_policy: Callable = None,   # fn(obs, mask) -> action_idx
        max_rounds:      int      = 150,
        reward_shaping:  bool     = True,
    ):
        super().__init__()
        self.player_stats    = player_stats   or _default_stats()
        self.skill_cards     = skill_cards    if skill_cards    is not None else list(sample_cards.DEFAULT_SKILL_DECK)
        self.backpack_cards  = backpack_cards if backpack_cards is not None else list(sample_cards.DEFAULT_BACKPACK)
        self.opponent_policy = opponent_policy
        self.max_rounds      = max_rounds
        self.reward_shaping  = reward_shaping

        self.observation_space = spaces.Box(
            low=-2.0, high=2.0,
            shape=(get_state_dim(),), dtype=np.float32
        )
        self.action_space = spaces.Discrete(ACTION_DIM)

        self._game: Optional[Game] = None
        self._rng  = random.Random()
        self._prev_hp = [0, 0]

    # ------------------------------------------------------------------
    # Gym interface
    # ------------------------------------------------------------------

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = random.Random(seed)

        p0 = make_player(0, self.player_stats,
                         list(self.skill_cards), list(self.backpack_cards),
                         equipment=sample_cards.DEFAULT_EQUIPMENT, rng=self._rng)
        p1 = make_player(1, self.player_stats,
                         list(self.skill_cards), list(self.backpack_cards),
                         position=(1, 0),
                         equipment=sample_cards.DEFAULT_EQUIPMENT, rng=self._rng)
        self._game = Game(p0, p1, seed=seed)
        self._prev_hp = [p0.stats.max_hp, p1.stats.max_hp]

        # Advance through any initial opponent turns
        self._let_opponent_play()

        obs  = encode_state(self._game.state, pov_player=0)
        info = {}
        return obs, info

    def step(self, action_idx: int):
        assert self._game is not None, "call reset() first"

        # Map index → Action; if invalid fall back to END_TURN
        act = self._idx_to_action(action_idx, player_idx=0)
        if act is None:
            act = Action(ActionType.END_TURN, 0)

        cur_hp = [self._game.player_hp(i) for i in range(2)]
        self._game.step(act)
        new_hp = [self._game.player_hp(i) for i in range(2)]

        # Opponent plays until it's P0's turn again (or game ends)
        self._let_opponent_play()

        terminated = self._game.done
        truncated  = (not terminated
                      and self._game.state.round_num > self.max_rounds)
        if truncated:
            self._game.resolve_by_hp()
            terminated = True
            truncated  = False

        reward = self._reward(cur_hp, new_hp, terminated)

        obs  = encode_state(self._game.state, pov_player=0)
        info = {
            "winner": self._game.winner,
            "round":  self._game.state.round_num,
            "p0_hp":  self._game.player_hp(0),
            "p1_hp":  self._game.player_hp(1),
        }
        self._prev_hp = new_hp
        return obs, reward, terminated, truncated, info

    def render(self, mode="ansi"):
        s = self._game.state
        p = s.players
        lines = [
            f"=== Round {s.round_num} | Active: P{s.active_player_idx} ===",
            f"P0: {p[0].hp}/{p[0].stats.max_hp} HP  pos={p[0].position}  "
            f"hand={len(p[0].hand)}  mv={p[0].movement_remaining}",
            f"P1: {p[1].hp}/{p[1].stats.max_hp} HP  pos={p[1].position}  "
            f"hand={len(p[1].hand)}  mv={p[1].movement_remaining}",
        ]
        if s.log:
            lines.append(f"  last: {s.log[-1].encode('ascii', errors='replace').decode()}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Action mask
    # ------------------------------------------------------------------

    def action_masks(self) -> np.ndarray:
        """Boolean mask: True = this action index is currently valid for P0."""
        mask = np.zeros(ACTION_DIM, dtype=bool)
        if self._game is None or self._game.done:
            mask[1] = True   # END_TURN always safe
            return mask
        if self._game.active_player_idx != 0:
            mask[1] = True
            return mask

        for act in self._game.valid_actions():
            idx = self._action_to_idx(act)
            if idx is not None:
                mask[idx] = True
        return mask

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _let_opponent_play(self):
        """Auto-play P1 turns until it is P0's turn (or game ends)."""
        while not self._game.done and self._game.active_player_idx == 1:
            acts = self._game.valid_actions()
            if not acts:
                break
            if self.opponent_policy is not None:
                obs  = encode_state(self._game.state, pov_player=1)
                mask = self._action_mask_for(1)
                idx  = self.opponent_policy(obs, mask)
                act  = self._idx_to_action(idx, player_idx=1)
                if act is None:
                    act = self._rng.choice(acts)
            else:
                act = self._rng.choice(acts)
            self._game.step(act)

    def _action_mask_for(self, player_idx: int) -> np.ndarray:
        mask = np.zeros(ACTION_DIM, dtype=bool)
        for act in self._game.valid_actions():
            idx = self._action_to_idx(act, player_idx=player_idx)
            if idx is not None:
                mask[idx] = True
        return mask

    def _reward(self, prev_hp, new_hp, terminated: bool) -> float:
        if terminated:
            if self._game.winner == 0:
                return 1.0
            if self._game.winner == 1:
                return -1.0
            return 0.0   # truncated draw

        if not self.reward_shaping:
            return 0.0

        max_hp = max(self._game.state.players[0].stats.max_hp,
                     self._game.state.players[1].stats.max_hp, 1)
        dmg_dealt = max(0, prev_hp[1] - new_hp[1])
        dmg_taken = max(0, prev_hp[0] - new_hp[0])
        return (dmg_dealt - dmg_taken) / max_hp * 0.05

    # ------------------------------------------------------------------
    # Action index ↔ Action object
    # ------------------------------------------------------------------

    def _action_to_idx(self, action: Action, player_idx: int = 0) -> Optional[int]:
        t = action.type
        if t == ActionType.REST:     return 0
        if t == ActionType.END_TURN: return 1
        if t == ActionType.MOVE:
            pos  = self._game.state.players[player_idx].position
            diff = (action.target_hex[0] - pos[0], action.target_hex[1] - pos[1])
            try:    return 2 + HEX_DIRS.index(diff)
            except ValueError: return None
        if t == ActionType.USE_WEAPON:
            return 8 if action.hand_slot == "right_hand" else 9
        if t == ActionType.PLAY_CARD:
            hand = self._game.state.players[player_idx].hand
            for k, c in enumerate(hand):
                if c.iid == action.card_iid and k < MAX_HAND:
                    return 10 + k
        return None

    def _idx_to_action(self, idx: int, player_idx: int = 0) -> Optional[Action]:
        valid = self._game.valid_actions()

        if idx == 0:
            return next((a for a in valid if a.type == ActionType.REST), None)
        if idx == 1:
            return next((a for a in valid if a.type == ActionType.END_TURN), None)
        if 2 <= idx <= 7:
            d      = HEX_DIRS[idx - 2]
            pos    = self._game.state.players[player_idx].position
            target = (pos[0] + d[0], pos[1] + d[1])
            return next((a for a in valid
                         if a.type == ActionType.MOVE
                         and a.target_hex == target), None)
        if idx == 8:
            return next((a for a in valid
                         if a.type == ActionType.USE_WEAPON
                         and a.hand_slot == "right_hand"), None)
        if idx == 9:
            return next((a for a in valid
                         if a.type == ActionType.USE_WEAPON
                         and a.hand_slot == "left_hand"), None)
        if 10 <= idx < 10 + MAX_HAND:
            k    = idx - 10
            hand = self._game.state.players[player_idx].hand
            if k < len(hand):
                card_iid = hand[k].iid
                return next((a for a in valid
                             if a.type == ActionType.PLAY_CARD
                             and a.card_iid == card_iid), None)
        return None


# ---------------------------------------------------------------------------

def _default_stats() -> Stats:
    return Stats(
        ausdauer=5, kraft=4, beweglichkeit=3,
        wahrnehmung=3, geschwindigkeit=4, basteln=3,
        empathie=2, wissen=2, ueberzeugungskraft=2,
        naturwissen=2, selbstbewusstsein=2, intelligenz=2,
    )
