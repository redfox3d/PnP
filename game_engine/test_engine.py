"""
Quick smoke-test for the game engine.
Run: python -m game_engine.test_engine
"""
import random
from game_engine import Game, make_player, Stats


def random_game(max_steps: int = 500, seed: int = 42) -> dict:
    """Play one game with random action selection."""
    rng = random.Random(seed)

    # Dummy cards
    dummy_skill = {"id": "TestSpell", "boxes": []}
    dummy_supply = {"id": "TestSupply", "element": "Fire"}

    stats = Stats(
        ausdauer=5, kraft=4, beweglichkeit=3,
        wahrnehmung=3, geschwindigkeit=4, basteln=3,
        empathie=2, wissen=2, ueberzeugungskraft=2,
        naturwissen=2, selbstbewusstsein=2, intelligenz=2,
    )

    p0 = make_player(0, stats, [dict(dummy_skill)] * 10, [dict(dummy_supply)] * 20, rng=rng)
    p1 = make_player(1, stats, [dict(dummy_skill)] * 10, [dict(dummy_supply)] * 20,
                     position=(3, -3), rng=rng)

    game = Game(p0, p1, seed=seed)
    steps = 0

    while not game.done and steps < max_steps:
        acts = game.valid_actions()
        action = rng.choice(acts)
        info = game.step(action)
        steps += 1

    return {
        "winner": game.winner,
        "rounds": game.state.round_num,
        "steps":  steps,
        "p0_hp":  game.player_hp(0),
        "p1_hp":  game.player_hp(1),
        "done":   game.done,
    }


if __name__ == "__main__":
    print("Running smoke test...")
    result = random_game()
    print(f"Result: {result}")
    if result["done"]:
        print(f"[OK] Game finished: P{result['winner']} won in round {result['rounds']}")
    else:
        print(f"[OK] Game ran {result['steps']} steps without crashing (no winner yet - need combat cards)")
    print("Engine OK")
