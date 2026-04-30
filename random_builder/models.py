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

# Re-export from central constants for convenience
from card_builder.constants import RECIPE_TYPES


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
        {"block_type": "Play",      "probability": 0.95},
        {"block_type": "Hand",      "probability": 0.15},
        {"block_type": "Forgotten", "probability": 0.10},
        {"block_type": "Exhausted", "probability": 0.10},
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
    # ── Effects / Groups ──────────────────────────────────────────────────────
    "max_effects":    -1,    # LEGACY: max effects per ability  (-1 = no limit)
    "min_effects":     0,    # LEGACY: min effects per ability  (0 = no minimum)
    "min_groups":      1,    # min effect groups per ability
    "max_groups":      3,    # max effect groups per ability
    "min_blocks":      1,    # min sigils per card      (1 = no minimum extra)
    # Distinct target_type buckets per sigil (groups with the same
    # target_type count as ONE effect because they merge in display).
    "max_effects_per_sigil": 3,
    # Number-of-sigils per card distribution. Same shape as
    # element_count_weights — {"1": 100, "2": 50, ...}. When unset, the
    # legacy independent block_rules rolls are used instead.
    "sigil_count_weights": {"1": 100, "2": 50, "3": 25, "4": 12,
                              "5": 0,   "6": 0},
    # Range-value distribution for force-attached Ranged modifier.
    # Values 0/1 are rendered as "no range text" by the card renderer.
    "range_value_weights": {"0": 30, "1": 0, "2": 30, "3": 20,
                              "4": 15, "5": 5},
    # ── Modifiers ──────────────────────────────────────────────────────────────
    "modifier_chance":          0.3,   # probability a group gains modifiers
    "max_modifiers_per_group":  2,     # hard cap on modifiers within one group
    "multi_primary_chance":     0.30,  # per slot — adds a 2nd/3rd primary
    "multi_primary_max":        2,     # max EXTRA primaries beyond the first
    # ── Target type weights ────────────────────────────────────────────────────
    # Note: "Target Neutral" is intentionally omitted — it is a permission
    # tag (effects with primary_types=["Target Neutral"] become eligible in
    # both Target Enemy AND Target Ally groups), never its own bucket.
    "target_type_weights": {
        "Target Enemy":   10,
        "Target Ally":     8,
        "Non Targeting":  10,
    },
    # ── Conditions / Choose N ──────────────────────────────────────────────────
    "condition_chance": 0.15,  # probability a sigil gets a condition
    "choose_n_chance":  0.10,  # probability a sigil uses "choose N of effects"
    # Max CV spread among choose options. (hi - lo) / hi must be <= this,
    # otherwise the choose is silently dropped — choosing only matters
    # when all options are roughly comparable.
    "choose_cv_tolerance": 0.20,
    # ── Sub-Sigils ─────────────────────────────────────────────────────────────
    "sub_sigil_chance":          0.10,  # max 10% of cards get a sub-sigil
    "sub_sigil_max_groups":      1,     # max effect groups in a sub-sigil
    "sub_sigil_cv_budget_frac":  0.3,   # fraction of remaining CV budget for sub-sigil
    # Sub-sigil flavor weights (mutually exclusive with each other and choose).
    "chance_sub_target_enemy":   0.05,
    "chance_sub_target_ally":    0.04,
    "chance_sub_choose":         0.04,
    # Per-target_type CV ranges for sub-sigils (overrides the global budget
    # frac when present). Target Neutral is NOT listed: it's a permission tag.
    "sub_sigil_cv_per_target": {
        "Target Enemy":  {"min": 1.0, "max": 3.0},
        "Target Ally":   {"min": 1.0, "max": 2.5},
        "Non Targeting": {"min": 0.5, "max": 2.0},
    },
    # Minimum CV of the *primary* part of a sigil (sub-sigil contribution
    # excluded). Cards whose only value is locked behind a paid sub-sigil
    # are rejected when this is > 0.
    "cv_primary_per_sigil_min": 0.5,
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
        # Backward compat: old min_effects/max_effects → min_groups/max_groups
        if "min_groups" not in cfg and "min_effects" in cfg:
            cfg["min_groups"] = cfg["min_effects"]
        if "max_groups" not in cfg and "max_effects" in cfg:
            me = cfg["max_effects"]
            cfg["max_groups"] = me if me > 0 else 3
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
