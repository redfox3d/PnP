"""
Main Game class — the public API used by RL agents and simulations.

Minimal usage:
    from game_engine import Game, make_player, Stats

    p0 = make_player(0, Stats(ausdauer=5, kraft=5, ...), skill_cards, backpack_cards)
    p1 = make_player(1, Stats(ausdauer=4, kraft=6, ...), skill_cards, backpack_cards)
    game = Game(p0, p1)

    while not game.done:
        actions = game.valid_actions()
        game.step(actions[0])   # or pick with RL policy
"""
from __future__ import annotations
import random

from .state   import GameState, PlayerState
from .actions import Action, ActionType
from .rules   import get_valid_actions, apply_action, _start_round


class Game:
    """
    Encapsulates one complete game instance.

    Attributes:
        state   – current GameState (read-only externally; use step() to advance)
        done    – True once a winner is decided
        winner  – player index (0 or 1) of the winner, or None
    """

    def __init__(
        self,
        player0:         PlayerState,
        player1:         PlayerState,
        grid_radius:     int  = 5,
        initiative_deck: list = None,
        seed:            int  = None,
    ):
        self._rng = random.Random(seed)
        self.state = GameState(
            players=[player0, player1],
            grid_radius=grid_radius,
            initiative_deck=list(initiative_deck or ["p0", "p1"]),
        )
        # Start round 1
        self.state = _start_round(self.state, rng=self._rng)

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def valid_actions(self) -> list[Action]:
        """Return all legal actions for the current active player."""
        return get_valid_actions(self.state)

    def step(self, action: Action) -> dict:
        """
        Apply `action` and advance the game state.

        Returns an info dict:
            done        – bool
            winner      – int | None
            hp          – [p0_hp, p1_hp]
            hp_delta    – [Δp0, Δp1] (negative = damage taken)
            log         – last log entry string
            round       – current round number
        """
        old_hp = [p.hp for p in self.state.players]
        self.state = apply_action(self.state, action, rng=self._rng)
        new_hp = [p.hp for p in self.state.players]
        return {
            "done":     self.done,
            "winner":   self.winner,
            "hp":       list(new_hp),
            "hp_delta": [new_hp[i] - old_hp[i] for i in range(2)],
            "log":      self.state.log[-1] if self.state.log else "",
            "round":    self.state.round_num,
        }

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def done(self) -> bool:
        return self.state.winner is not None

    @property
    def winner(self) -> int | None:
        return self.state.winner

    @property
    def active_player_idx(self) -> int:
        return self.state.active_player_idx

    def player_hp(self, idx: int) -> int:
        return self.state.players[idx].hp

    def resolve_by_hp(self) -> int | None:
        """
        Declare winner by HP when the round limit is reached.
        Sets state.winner to the higher-HP player, or the first player (0)
        on a tie (rare — could also be left as None for a true draw).
        Returns the winner index.
        """
        hp = [p.hp for p in self.state.players]
        if hp[0] > hp[1]:
            self.state.winner = 0
        elif hp[1] > hp[0]:
            self.state.winner = 1
        else:
            self.state.winner = 0  # tie-break: player 0
        self.state.phase = "done"
        self.state.log.append(
            f"*** Rundenlimit: P{self.state.winner} gewinnt per HP "
            f"({hp[0]} vs {hp[1]}) ***"
        )
        return self.state.winner

    # ------------------------------------------------------------------
    # Gym-style reset (for RL environments)
    # ------------------------------------------------------------------

    def reset(self, player0: PlayerState = None, player1: PlayerState = None,
              seed: int = None) -> GameState:
        """Re-initialise the game with the same or new players."""
        if seed is not None:
            self._rng = random.Random(seed)
        p0 = player0 or self.state.players[0]
        p1 = player1 or self.state.players[1]
        self.state = GameState(
            players=[p0, p1],
            grid_radius=self.state.grid_radius,
            initiative_deck=list(self.state.initiative_deck),
        )
        self.state = _start_round(self.state, rng=self._rng)
        return self.state

    def __repr__(self) -> str:
        p = self.state.players
        return (f"Game(R{self.state.round_num} "
                f"P0:{p[0].hp}/{p[0].stats.max_hp}hp "
                f"P1:{p[1].hp}/{p[1].stats.max_hp}hp "
                f"active=P{self.state.active_player_idx})")
