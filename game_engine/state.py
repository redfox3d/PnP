"""Game state dataclasses."""
from __future__ import annotations
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .constants import Zone, EquipSlot, Element, ELEMENT_COMBAT_STAT, ELEMENT_HIT_SKILL

# --- unique instance ID counter -------------------------------------------
_next_iid: int = 0


def _new_iid() -> int:
    global _next_iid
    _next_iid += 1
    return _next_iid


# ---------------------------------------------------------------------------

@dataclass
class CardInstance:
    """A specific copy of a card currently in the game."""
    card_id: str
    card_data: dict
    iid: int = field(default_factory=_new_iid)
    zone: Zone = Zone.HAND

    def __repr__(self) -> str:
        return f"Card({self.card_id}:{self.iid}@{self.zone.value})"


@dataclass
class Stats:
    # Combat stats (each contributes to max HP)
    ausdauer:        int = 0   # Fire combat
    kraft:           int = 0   # Metal combat
    beweglichkeit:   int = 0   # Blood combat
    wahrnehmung:     int = 0   # Nature combat
    geschwindigkeit: int = 0   # Ice combat
    basteln:         int = 0   # Meta combat
    # Hit skills
    empathie:             int = 0   # Fire hit
    wissen:               int = 0   # Metal hit
    ueberzeugungskraft:   int = 0   # Blood hit
    naturwissen:          int = 0   # Nature hit
    selbstbewusstsein:    int = 0   # Ice hit
    intelligenz:          int = 0   # Meta hit

    @property
    def max_hp(self) -> int:
        return (self.ausdauer + self.kraft + self.beweglichkeit
                + self.wahrnehmung + self.geschwindigkeit + self.basteln)

    def combat(self, element: Element) -> int:
        return getattr(self, ELEMENT_COMBAT_STAT.get(element, ""), 0)

    def hit(self, element: Element) -> int:
        return getattr(self, ELEMENT_HIT_SKILL.get(element, ""), 0)


@dataclass
class PlayerState:
    player_id: int
    stats: Stats
    hp: int
    position: tuple              # (q, r) axial hex coordinates
    equipment: Dict[str, Optional[CardInstance]] = field(default_factory=dict)

    # Card zones
    hand:          List[CardInstance] = field(default_factory=list)
    skills_deck:   List[CardInstance] = field(default_factory=list)
    backpack_deck: List[CardInstance] = field(default_factory=list)
    play_zone:     List[CardInstance] = field(default_factory=list)
    enchanted:     List[CardInstance] = field(default_factory=list)
    concentration: List[CardInstance] = field(default_factory=list)
    discard:       List[CardInstance] = field(default_factory=list)
    forgotten:     List[CardInstance] = field(default_factory=list)
    lost:          List[CardInstance] = field(default_factory=list)

    # Supplies drawn this round (paid as mana)
    available_supplies: List[CardInstance] = field(default_factory=list)

    # Per-turn flags (reset each round)
    movement_remaining: int = 2
    has_played:  bool = False
    has_rested:  bool = False
    has_attacked: bool = False
    turn_done:   bool = False

    # -----------------------------------------------------------------------

    def _zone_list(self, zone: Zone) -> List[CardInstance]:
        return {
            Zone.HAND:          self.hand,
            Zone.SKILLS_DECK:   self.skills_deck,
            Zone.BACKPACK_DECK: self.backpack_deck,
            Zone.PLAY:          self.play_zone,
            Zone.ENCHANTED:     self.enchanted,
            Zone.CONCENTRATION: self.concentration,
            Zone.DISCARD:       self.discard,
            Zone.FORGOTTEN:     self.forgotten,
            Zone.LOST:          self.lost,
        }[zone]

    def find_card(self, iid: int) -> Optional[tuple[CardInstance, Zone]]:
        """Return (CardInstance, Zone) or None."""
        for zone in Zone:
            for c in self._zone_list(zone):
                if c.iid == iid:
                    return c, zone
        for c in self.available_supplies:
            if c.iid == iid:
                return c, None   # supplies are not in a named zone
        return None

    def move_card(self, iid: int, target_zone: Zone) -> bool:
        """Move a card from wherever it is to target_zone. Returns True if found."""
        result = self.find_card(iid)
        if result is None:
            return False
        card, src_zone = result
        if src_zone is not None:
            lst = self._zone_list(src_zone)
            if card in lst:
                lst.remove(card)
        card.zone = target_zone
        self._zone_list(target_zone).append(card)
        return True

    def all_cards_in_zones(self, *zones: Zone) -> List[CardInstance]:
        cards = []
        for z in zones:
            cards.extend(self._zone_list(z))
        return cards


@dataclass
class GameState:
    players: List[PlayerState]
    grid_radius: int = 5

    # Shared initiative deck: list of tokens (e.g. "p0", "p1", custom strings)
    initiative_deck:    List[str] = field(default_factory=lambda: ["p0", "p1"])
    current_initiative: Optional[str] = None

    round_num:          int = 0
    active_player_idx:  int = 0
    first_player_idx:   int = 0
    turns_done_this_round: int = 0    # 0, 1, or 2

    phase:  str = "start"   # "start" | "player_turn" | "done"
    winner: Optional[int] = None
    log:    List[str] = field(default_factory=list)

    def clone(self) -> GameState:
        return copy.deepcopy(self)

    @property
    def active_player(self) -> PlayerState:
        return self.players[self.active_player_idx]

    @property
    def inactive_player(self) -> PlayerState:
        return self.players[1 - self.active_player_idx]
