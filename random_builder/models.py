"""
random_builder/models.py – Persistence for randomly generated cards and gen config.

Generated cards are stored separately from hand-crafted ones in:
    cards/Random/Spells/cards.json

Generation config (settings) is stored in:
    random_builder/gen_config.json

Box config is read from:
    CardContent/cc_data/box_config.json
"""
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RANDOM_CARDS_FILE = os.path.join(_ROOT, "cards", "Random", "Spells", "cards.json")
_GEN_CONFIG_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen_config.json")
_BOX_CONFIG_FILE   = os.path.join(_ROOT, "CardContent", "cc_data", "box_config.json")

_DEFAULT_GEN_CONFIG = {
    "count": 10,
    "element_mode": "equal",        # "equal" | "custom"
    "custom_element_weights": {},   # {element: weight}
    "block_rules": [
        {"block_type": "Play",    "probability": 0.95},
        {"block_type": "Hand",    "probability": 0.15},
        {"block_type": "Lost",    "probability": 0.15},
        {"block_type": "Fleeting","probability": 0.10},
    ],
    "content_rules": [],   # [{container: str, probability: float}]
    "cost_rules":    [],   # [{cost_id: str, probability: float}]
    "cv_target":     3.0,
    "cv_per_box_max": 3.0,
}


# ── Generated cards ───────────────────────────────────────────────────────────

def load_random_cards() -> list:
    if not os.path.exists(_RANDOM_CARDS_FILE):
        return []
    try:
        with open(_RANDOM_CARDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_random_cards(cards: list):
    os.makedirs(os.path.dirname(_RANDOM_CARDS_FILE), exist_ok=True)
    with open(_RANDOM_CARDS_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)


def clear_random_cards():
    save_random_cards([])


# ── Generation config ─────────────────────────────────────────────────────────

def load_gen_config() -> dict:
    if not os.path.exists(_GEN_CONFIG_FILE):
        return dict(_DEFAULT_GEN_CONFIG)
    try:
        with open(_GEN_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # Fill in any missing keys from default
        for k, v in _DEFAULT_GEN_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return dict(_DEFAULT_GEN_CONFIG)


def save_gen_config(cfg: dict):
    with open(_GEN_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ── Box config ────────────────────────────────────────────────────────────────

def load_box_config() -> dict:
    if not os.path.exists(_BOX_CONFIG_FILE):
        return {}
    try:
        with open(_BOX_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_box_config(cfg: dict):
    with open(_BOX_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
