"""
Startet ein Testspiel zwischen zwei zufälligen KI-Spielern.
Zeigt jeden Zug im Terminal.

Verwendung:
    python test_game.py
    python test_game.py --seed 42
    python test_game.py --games 5 --quiet
"""
import random
import argparse

from game_engine import Game, make_player, Stats, sample_cards


def run_game(seed: int = None, verbose: bool = True) -> dict:
    rng = random.Random(seed)

    stats = Stats(
        ausdauer=5, kraft=4, beweglichkeit=3,
        wahrnehmung=3, geschwindigkeit=4, basteln=3,
        empathie=3, wissen=2, ueberzeugungskraft=2,
        naturwissen=2, selbstbewusstsein=2, intelligenz=2,
    )

    p0 = make_player(0, stats,
                     list(sample_cards.DEFAULT_SKILL_DECK),
                     list(sample_cards.DEFAULT_BACKPACK),
                     equipment=sample_cards.DEFAULT_EQUIPMENT,
                     rng=rng)
    p1 = make_player(1, stats,
                     list(sample_cards.DEFAULT_SKILL_DECK),
                     list(sample_cards.DEFAULT_BACKPACK),
                     position=(1, 0),
                     equipment=sample_cards.DEFAULT_EQUIPMENT,
                     rng=rng)

    game = Game(p0, p1, seed=seed)
    last_round = 0

    max_rounds = 150
    while not game.done:
        if game.state.round_num > max_rounds:
            game.resolve_by_hp()
            break

        acts = game.valid_actions()
        if not acts:
            game.resolve_by_hp()
            break

        action = rng.choice(acts)
        info   = game.step(action)

        if verbose:
            # Rundentrennlinie
            if game.state.round_num != last_round:
                last_round = game.state.round_num
                s = game.state
                print(f"\n--- Runde {s.round_num} | Initiative: {s.current_initiative} ---")
                print(f"  P0: {s.players[0].hp}/{s.players[0].stats.max_hp} HP  "
                      f"pos={s.players[0].position}  hand={len(s.players[0].hand)}")
                print(f"  P1: {s.players[1].hp}/{s.players[1].stats.max_hp} HP  "
                      f"pos={s.players[1].position}  hand={len(s.players[1].hand)}")

            # Letzten Log-Eintrag ausgeben
            log = game.state.log[-1] if game.state.log else ""
            print("  " + log.encode("ascii", errors="replace").decode())

    result = {
        "winner": game.winner,
        "rounds": game.state.round_num,
        "hp":     [game.player_hp(0), game.player_hp(1)],
        "seed":   seed,
    }

    if verbose:
        print(f"\n{'='*40}")
        print(f"  GEWINNER: Spieler {game.winner}  "
              f"(HP: P0={result['hp'][0]}  P1={result['hp'][1]})")
        print(f"  Runden gespielt: {result['rounds']}")
        print(f"{'='*40}\n")

    return result


def main():
    parser = argparse.ArgumentParser(description="Kartenspiel Testlauf")
    parser.add_argument("--seed",   type=int, default=42,  help="Zufalls-Seed")
    parser.add_argument("--games",  type=int, default=1,   help="Anzahl Spiele")
    parser.add_argument("--quiet",  action="store_true",   help="Nur Zusammenfassung")
    args = parser.parse_args()

    if args.games == 1:
        run_game(seed=args.seed, verbose=not args.quiet)
    else:
        wins = [0, 0]
        for i in range(args.games):
            r = run_game(seed=args.seed + i, verbose=False)
            if r["winner"] is not None:
                wins[r["winner"]] += 1
            if not args.quiet:
                print(f"Spiel {i+1:3d}: Gewinner P{r['winner']}  "
                      f"Runden={r['rounds']}  HP={r['hp']}")

        print(f"\nErgebnis aus {args.games} Spielen:")
        print(f"  P0 Siege: {wins[0]}  ({wins[0]/args.games:.0%})")
        print(f"  P1 Siege: {wins[1]}  ({wins[1]/args.games:.0%})")


if __name__ == "__main__":
    main()
