"""
random_builder/dice_models.py – Load/save dice configuration.

Dice file: random_builder/dice_config.json
Schema:
  {
    "dice": [{"id": "D6", "value": 6}, ...],   // sorted by value
    "dice_can_chance": 0.5                      // prob. a "can" variable uses dice
  }
"""

import json
import os

_DIR  = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_DIR, "dice_config.json")

_DEFAULTS = {
    "dice": [
        {"id": "D4",  "avg": 2.5},
        {"id": "D6",  "avg": 3.5},
        {"id": "D8",  "avg": 4.5},
        {"id": "D10", "avg": 5.5},
        {"id": "D12", "avg": 6.5},
        {"id": "D20", "avg": 10.5},
    ],
    "dice_can_chance": 0.5,
}


def load_dice_config() -> dict:
    if os.path.exists(_PATH):
        try:
            with open(_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(_DEFAULTS)


def save_dice_config(cfg: dict) -> None:
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def die_avg(d: dict) -> float:
    """Return the average (expected) value of a die entry.
    Supports new 'avg' key and falls back to old 'value' key (avg = (value+1)/2)."""
    if "avg" in d:
        return float(d["avg"])
    return (float(d.get("value", 6)) + 1) / 2.0


def nearest_die(target: float, dice: list) -> dict | None:
    """Return the die whose avg × best_N is closest to *target*.  None if dice is empty."""
    if not dice:
        return None
    return min(dice, key=lambda d: abs(die_avg(d) * max(1, round(target / die_avg(d))) - target))
