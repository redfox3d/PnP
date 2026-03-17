import random
import math


def draw(options: list):
    weights = []
    for option in options:
        rarity = getattr(option, "rarity", 100)
        weights.append(math.sqrt(rarity))

    total = sum(weights)
    r = random.uniform(0, total)

    cumulative = 0
    for option, weight in zip(options, weights):
        cumulative += weight
        if r <= cumulative:
            return option

    return options[-1]  # fallback