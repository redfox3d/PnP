"""Dice rolling utilities."""
import random as _stdlib_random

_rng = _stdlib_random.Random()


def roll(sides: int, n: int = 1, *, rng: _stdlib_random.Random = None) -> int:
    """Roll n dice with `sides` sides each, return total."""
    r = rng or _rng
    return sum(r.randint(1, sides) for _ in range(n))


def seed(s: int) -> None:
    _rng.seed(s)
