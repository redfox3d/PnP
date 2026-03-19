"""
container_manager/models.py – Persistence for Content Containers.

A container groups semantically similar effects (e.g. all Damage effects).
The no_repeat flag means: only one effect from this container can appear per card.
"""
import json
import os

_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "containers.json")


def load_containers() -> dict:
    """Return {container_id: {id, name, description, effects: [...], no_repeat: bool}}"""
    if not os.path.exists(_DATA_FILE):
        return {}
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_containers(data: dict):
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_container_ids() -> list:
    return sorted(load_containers().keys())
