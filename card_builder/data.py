"""
data.py – loads the four content JSON files and exposes a singleton ContentData.
"""

import json
import os
import re

_DATA_DIR: str = ""


def set_data_dir(path: str) -> None:
    global _DATA_DIR
    _DATA_DIR = path
    print(f"[data] set_data_dir → '{_DATA_DIR}'")


def _json_path(filename: str) -> str:
    full = os.path.join(_DATA_DIR, filename)
    return full


def load_json_list(path: str, key: str) -> list:
    print(f"[data] load_json_list: path='{path}'  exists={os.path.exists(path)}")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            result = data.get(key, [])
            print(f"[data]   → key='{key}'  found {len(result)} items")
            return result
    print(f"[data]   → FILE NOT FOUND!")
    return []


def parse_placeholders(text: str) -> list:
    return list(dict.fromkeys(re.findall(r"\{([A-Za-z0-9_]+)\}", text)))


def fill_placeholders(text: str, values: dict) -> str:
    def repl(m):
        return str(values.get(m.group(1), m.group(0)))
    return re.sub(r"\{([A-Za-z0-9_]+)\}", repl, text)


class ContentData:
    _instance = None

    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        print(f"[ContentData] reload() called, _DATA_DIR='{_DATA_DIR}'")
        cc_data = os.path.join(_DATA_DIR, "cc_builder", "cc_data")
        self.effects = load_json_list(os.path.join(cc_data, "effects.json"), "Effect")
        self.triggers = load_json_list(os.path.join(cc_data, "triggers.json"), "Trigger")
        self.conditions = load_json_list(os.path.join(cc_data, "conditions.json"), "Condition")
        self.costs = load_json_list(os.path.join(cc_data, "costs.json"), "Cost")

    def effect_ids(self)    -> list: return [i["id"] for i in self.effects]
    def trigger_ids(self)   -> list: return [i["id"] for i in self.triggers]
    def condition_ids(self) -> list: return [i["id"] for i in self.conditions]
    def cost_ids(self)      -> list: return [i["id"] for i in self.costs]

    def get(self, kind: str, id_: str):
        lst = getattr(self, kind + "s", [])
        return next((i for i in lst if i.get("id") == id_), None)


_cd: ContentData | None = None


def get_content_data() -> ContentData:
    global _cd
    if _cd is None:
        print("[data] get_content_data() → creating ContentData for first time")
        _cd = ContentData()
    return _cd


def reload_content_data() -> ContentData:
    global _cd
    _cd = ContentData()
    return _cd