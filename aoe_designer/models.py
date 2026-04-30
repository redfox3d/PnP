"""
aoe_designer/models.py – Persistence for AOE hex patterns.

Each pattern now stores a CV value (default = number of cells × 0.5)
that the spell generator uses when AoE replaces the Range modifier.
"""
import json
import os

_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aoe_patterns.json")


def load_patterns() -> dict:
    if not os.path.exists(_DATA_FILE):
        return {}
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_patterns(patterns: dict):
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)


def get_pattern_ids() -> list:
    return sorted(load_patterns().keys())


def default_cv_for(pattern: dict) -> float:
    """Heuristic default CV from cell count when the pattern has no cv yet.

    Tunable: 0.5 CV per affected cell, with a tiny rounding safety net.
    """
    cells = pattern.get("cells") or []
    return round(0.5 * max(1, len(cells)), 2)


def get_cv(pattern_id: str) -> float:
    """Return the CV value for an AoE pattern (0 if unknown)."""
    pat = load_patterns().get(pattern_id)
    if not pat:
        return 0.0
    if "cv" in pat:
        try:
            return float(pat["cv"])
        except (TypeError, ValueError):
            pass
    return default_cv_for(pat)


def set_cv(pattern_id: str, cv: float) -> bool:
    """Persist a new CV for the named pattern. Returns True on success."""
    patterns = load_patterns()
    if pattern_id not in patterns:
        return False
    patterns[pattern_id]["cv"] = float(cv)
    save_patterns(patterns)
    return True


def get_pattern_ids_with_cv() -> list:
    """Return [(pattern_id, cv)] tuples — used by the generator to weight
    AoE picks roughly by their power level."""
    out: list = []
    for pid, pat in load_patterns().items():
        cv = pat.get("cv")
        if cv is None:
            cv = default_cv_for(pat)
        out.append((pid, float(cv)))
    return sorted(out, key=lambda t: t[0])
