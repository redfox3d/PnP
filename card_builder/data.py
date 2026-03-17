"""
data.py – loads content JSON files and exposes a singleton ContentData.
"""

import json
import os
import re

_DATA_DIR: str = ""


def set_data_dir(path: str) -> None:
    global _DATA_DIR
    _DATA_DIR = path
    print(f"[data] set_data_dir → '{_DATA_DIR}'")


def _cc_data_path(filename: str) -> str:
    return os.path.join(_DATA_DIR, "CardContent", "cc_data", filename)


def load_json_list(path: str, key: str) -> list:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f).get(key, [])
    return []


def parse_placeholders(text: str) -> list:
    return list(dict.fromkeys(re.findall(r"\{([A-Za-z0-9_]+)\}", text)))


def fill_placeholders(text: str, values: dict) -> str:
    def repl(m):
        return str(values.get(m.group(1), m.group(0)))
    return re.sub(r"\{([A-Za-z0-9_]+)\}", repl, text)


class ContentData:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.effects    = load_json_list(_cc_data_path("effects.json"),    "Effect")
        self.triggers   = load_json_list(_cc_data_path("triggers.json"),   "Trigger")
        self.conditions = load_json_list(_cc_data_path("conditions.json"), "Condition")
        self.costs      = load_json_list(_cc_data_path("costs.json"),      "Cost")

    def effect_ids(self)    -> list: return [i["id"] for i in self.effects]
    def trigger_ids(self)   -> list: return [i["id"] for i in self.triggers]
    def condition_ids(self) -> list: return [i["id"] for i in self.conditions]
    def cost_ids(self)      -> list: return [i["id"] for i in self.costs]

    def get(self, kind: str, id_: str):
        lst = getattr(self, kind + "s", [])
        return next((i for i in lst if i.get("id") == id_), None)

    def get_content_text(self, kind: str, id_: str) -> str:
        item = self.get(kind, id_)
        if not item:
            return ""
        return item.get("content_text") or item.get("effect_text", "")


_cd: ContentData | None = None


def get_content_data() -> ContentData:
    global _cd
    if _cd is None:
        _cd = ContentData()
    elif not _cd.effects and _DATA_DIR:
        _cd.reload()
    return _cd
