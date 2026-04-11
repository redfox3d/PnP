"""
random_builder/models.py – Persistence for randomly generated cards and gen config.

Generated cards are stored separately from hand-crafted ones in:
    cards/Random/{profile}/cards.json

Generation config (settings) is stored in:
    random_builder/gen_config_{profile}.json

Box config is read from:
    CardContent/cc_data/box_config.json
"""
import json
import os

_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HERE     = os.path.dirname(os.path.abspath(__file__))
_BOX_CONFIG_FILE    = os.path.join(_ROOT, "CardContent", "cc_data", "box_config.json")
_CONTENT_PROBS_FILE = os.path.join(_HERE, "content_probs.json")

# All available generator profiles
GENERATOR_PROFILES = ["Spells", "Prowess", "Recipes"]

# Recipe sub-types (treated as element-parallel subcategories within Recipes profile)
RECIPE_TYPES = ["Potions", "Phials", "Tinctures"]


def _gen_config_file(profile: str) -> str:
    """Return the path to the gen config JSON for the given profile."""
    safe = profile.replace(" ", "_")
    return os.path.join(_HERE, f"gen_config_{safe}.json")


def _random_cards_file(profile: str) -> str:
    """Return the path to the random cards JSON for the given profile."""
    return os.path.join(_ROOT, "cards", "Random", profile, "cards.json")


_DEFAULT_GEN_CONFIG = {
    "profile_name": "Spells",
    "card_type_output": "Spells",
    "generic_mana_only": False,
    "generic_mana_cv": None,
    "count": 10,
    "element_mode": "equal",        # "equal" | "custom"
    "custom_element_weights": {},   # {element: weight}
    "recipe_type_mode": "equal",    # "equal" | "custom"  (Recipes profile only)
    "recipe_type_weights": {},      # {recipe_type: weight}
    "block_rules": [
        {"block_type": "Play",    "probability": 0.95},
        {"block_type": "Hand",    "probability": 0.15},
        {"block_type": "Lost",    "probability": 0.15},
        {"block_type": "Discard","probability": 0.10},
    ],
    "content_rules": [],   # [{container: str, probability: float}]
    "cost_rules":    [],   # [{cost_id: str, probability: float}]  (Mana excluded – see below)
    "cv_target":      3.0,
    "cv_per_box_max": 3.0,
    # ── Mana (independent of other costs) ──────────────────────────────────────
    "mana_chance":     0.95,  # probability mana appears at all (per Play-ability)
    "mana_main_count": 2,    # mode of the mana-count bell curve (most likely count)
    "mana_max_count":  6,    # hard cap on mana-cost entries
    # ── Other costs ────────────────────────────────────────────────────────────
    "max_other_costs": 1,    # max number of non-mana costs per ability
    # ── Effects ────────────────────────────────────────────────────────────────
    "max_effects":    -1,    # max effects per ability  (-1 = no limit)
    "min_effects":     0,    # min effects per ability  (0 = no minimum)
    "min_blocks":      1,    # min sigils per card      (1 = no minimum extra)
    # ── Conditions / Choose N ──────────────────────────────────────────────────
    "condition_chance": 0.15,  # probability a sigil gets a condition
    "choose_n_chance":  0.10,  # probability a sigil uses "choose N of effects"
    # ── Sigil Constraints ──────────────────────────────────────────────────────
    # sigil_rules: {block_type: [{container, probability, min, max}, ...]}
    "sigil_rules": {},
    # incompatible_pairs: [[eid1, eid2], ...]  (cannot appear together on same sigil)
    "incompatible_pairs": [],
}

# Extra defaults applied on top of _DEFAULT_GEN_CONFIG per profile
_PROFILE_OVERRIDES = {
    "Prowess": {"card_type_output": "Prowess", "generic_mana_only": True, "generic_mana_cv": 1.1},
    "Recipes": {"card_type_output": "Spells"},
}


# ── Generated cards ───────────────────────────────────────────────────────────

def load_random_cards(profile: str = "Spells") -> list:
    path = _random_cards_file(profile)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_random_cards(cards: list, profile: str = "Spells"):
    path = _random_cards_file(profile)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)


def clear_random_cards(profile: str = "Spells"):
    save_random_cards([], profile)


# ── Generation config ─────────────────────────────────────────────────────────

def load_gen_config(profile: str = "Spells") -> dict:
    # Backward compat: migrate old gen_config.json → gen_config_Spells.json
    old_path   = os.path.join(_HERE, "gen_config.json")
    spells_path = _gen_config_file("Spells")
    if os.path.exists(old_path) and not os.path.exists(spells_path):
        try:
            import shutil
            shutil.move(old_path, spells_path)
        except Exception:
            pass

    path = _gen_config_file(profile)

    # Build profile-specific defaults
    base = dict(_DEFAULT_GEN_CONFIG)
    base.update(_PROFILE_OVERRIDES.get(profile, {}))
    base["profile_name"] = profile

    if not os.path.exists(path):
        return base
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # Fill in any missing keys from profile-specific defaults
        for k, v in base.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return base


def save_gen_config(cfg: dict, profile: str = "Spells"):
    path = _gen_config_file(profile)
    with open(path, "w", encoding="utf-8") as f:
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


# ── Content rule probabilities (separate from gen_config, shared across profiles) ──

def load_content_probs() -> dict:
    """Returns {key: float} of saved probability overrides. Default = 1.0 for all."""
    if not os.path.exists(_CONTENT_PROBS_FILE):
        return {}
    try:
        with open(_CONTENT_PROBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_content_probs(probs: dict):
    with open(_CONTENT_PROBS_FILE, "w", encoding="utf-8") as f:
        json.dump(probs, f, indent=2, ensure_ascii=False)
