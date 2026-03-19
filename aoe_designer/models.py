"""
aoe_designer/models.py – Persistence for AOE hex patterns.
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
