"""
template_parser.py – Template parsing and rendering logic.

Syntax:
    {X}          → free numeric/text variable
    [a, b, c]    → dropdown with fixed choices

No tkinter dependency – safe to import from anywhere (auto-builder, etc.)
"""

import re


def parse_template(content_box: str) -> dict:
    """
    Parse a content_box string into variables and options.

    Returns:
        {
            "variables": ["X", "Y"],
            "options":   [["top","random","bottom"], ...]
        }
    """
    variables = list(dict.fromkeys(re.findall(r"\{([A-Za-z0-9_]+)\}", content_box)))
    raw_opts  = re.findall(r"\[([^\]]+)\]", content_box)
    options   = [
        [c.strip() for c in raw.split(",") if c.strip()]
        for raw in raw_opts
    ]
    return {"variables": variables, "options": options}


def render_content_text(content_box: str,
                        var_values: dict,
                        opt_selections: dict) -> str:
    """
    Render a content_box template into plain text.

    var_values:     {"X": "3"}          – replaces {X} with 3
    opt_selections: {"0": "top"}        – replaces first [..] block with "top"
    If a variable/option has no supplied value the placeholder is kept as-is.
    """
    text = content_box

    for name, val in var_values.items():
        text = text.replace(f"{{{name}}}", str(val) if val else name)

    opt_idx = 0

    def _replace(m):
        nonlocal opt_idx
        default = m.group(1).split(",")[0].strip()
        choice  = opt_selections.get(str(opt_idx), default)
        opt_idx += 1
        return choice

    text = re.sub(r"\[([^\]]+)\]", _replace, text)
    return text


def make_default_stat() -> dict:
    """Default rarity/complexity/conditions block for a variable or choice."""
    return {"rarity": 10, "complexity": 1.0, "conditions": {}}


def sync_item_template(item: dict) -> None:
    """
    Re-parse item["content_box"] and sync item["variables"] / item["options"]
    so that new placeholders get default stats and removed ones are dropped.
    Existing stats are preserved.
    """
    parsed    = parse_template(item.get("content_box", ""))
    old_vars  = item.get("variables", {})
    old_opts  = item.get("options",   {})

    item["variables"] = {
        v: old_vars.get(v, make_default_stat())
        for v in parsed["variables"]
    }

    new_opts = {}
    for i, choices in enumerate(parsed["options"]):
        key     = str(i)
        old_opt = old_opts.get(key, {})
        old_pc  = old_opt.get("per_choice", {})
        new_opts[key] = {
            "choices":   choices,
            "per_choice": {
                c: old_pc.get(c, make_default_stat())
                for c in choices
            },
        }
    item["options"] = new_opts
