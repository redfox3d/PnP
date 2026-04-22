"""
template_parser.py – Template parsing, rendering, ID management, reference tracking.

Sigil syntax  (for structure):
    {X}          → free variable named X
    [a, b, c]    → dropdown with choices a, b, c
    [\\Elements] → expands to all game elements as choices
    [\\AOE]      → expands to all saved AOE pattern IDs as choices

Content Text / Reminder Text syntax  (for conditional rendering):
    {X}                         → insert value of variable X
    [if X=1]...[/if]            → show if X equals 1
    [if X!=2]...[/if]           → show if X not equals 2
    [if X>3]...[/if]            → show if X greater than 3
    [if X<3]...[/if]            → show if X less than 3
    [if X=1-5]...[/if]          → show if X is in range 1 to 5 (inclusive)
    [if OPT0=top]...[/if]       → show if option 0 is "top"
    [if OPT0=]...[/if]          → show if option 0 is empty string ""
    [if X=1]...[elif X=2]...[else]...[/if]   → full if/elif/else chain
"""

import re
from typing import Any

from card_builder.constants import ELEMENTS


# ── Special marker expansion ───────────────────────────────────────────────────

def _expand_special_markers(text: str) -> str:
    """
    Expand special markers inside bracket groups before parsing/rendering.
        \\Elements  →  Fire, Metal, Ice, Nature, Blood, Meta
        \\AOE       →  <comma-separated list of saved AOE pattern IDs>
    """
    elements_csv = ", ".join(ELEMENTS)
    text = re.sub(r"\\Elements", elements_csv, text)

    # \\AOE – load pattern IDs lazily so the import doesn't fail if the
    # aoe_designer package isn't on the path yet.
    if r"\AOE" in text:
        try:
            import sys, os
            # aoe_designer lives one level above CardContent
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _root not in sys.path:
                sys.path.insert(0, _root)
            from aoe_designer.models import get_pattern_ids
            ids = get_pattern_ids()
            replacement = ", ".join(ids) if ids else "no_aoe_pattern"
            text = re.sub(r"\\AOE", replacement, text)
        except Exception:
            pass

    return text


# ── Sigil parsing ────────────────────────────────────────────────────────

def parse_template(sigil: str) -> dict:
    expanded  = _expand_special_markers(sigil)
    variables = list(dict.fromkeys(re.findall(r"\{([A-Za-z0-9_]+)\}", expanded)))
    raw_opts  = re.findall(r"\[([^\]]+)\]", expanded)
    options   = [
        [c.strip() for c in raw.split(",") if c.strip()]
        for raw in raw_opts
    ]
    return {"variables": variables, "options": options}


# ── Conditional text rendering ─────────────────────────────────────────────────

def _eval_condition(cond_str: str, var_values: dict, opt_selections: dict) -> bool:
    """
    Evaluate a single condition like:
        X=1   X!=2   X>3   X<4   X=1-5   OPT0=top   OPT0=
    """
    cond_str = cond_str.strip()

    # Detect operator
    for op in ["!=", ">=", "<=", ">", "<", "="]:
        if op in cond_str:
            name, _, val = cond_str.partition(op)
            name = name.strip()
            val  = val.strip()
            break
    else:
        return False

    # Get actual value
    if name.upper().startswith("OPT"):
        idx = name[3:]
        actual = opt_selections.get(idx, "")
    else:
        actual = var_values.get(name, "")

    # Range check: X=1-5
    if op == "=" and re.match(r"^-?\d+\.?\d*--?\d+\.?\d*$", val):
        lo, hi = val.split("-", 1)
        try:
            av = float(actual)
            return float(lo) <= av <= float(hi)
        except (ValueError, TypeError):
            return False

    # Numeric vs string comparison
    try:
        a_num = float(actual)
        v_num = float(val) if val != "" else None
        if v_num is not None:
            if op == "=":  return a_num == v_num
            if op == "!=": return a_num != v_num
            if op == ">":  return a_num >  v_num
            if op == "<":  return a_num <  v_num
            if op == ">=": return a_num >= v_num
            if op == "<=": return a_num <= v_num
    except (ValueError, TypeError):
        pass

    # String comparison
    actual_s = str(actual)
    if op == "=":  return actual_s == val
    if op == "!=": return actual_s != val
    return False


def _find_block(text: str) -> tuple | None:
    """
    Find the first outermost [if ...]...[/if] block in text, respecting nesting depth.
    Returns (block_start, block_end, first_cond, inner) or None.
      block_start  – index of the opening '[' of [if ...]
      block_end    – index just AFTER the closing ']' of [/if]
      first_cond   – condition string from [if <first_cond>]
      inner        – text between [if ...] and the matching [/if]
    """
    m = re.search(r"\[if ([^\]]+)\]", text)
    if not m:
        return None

    first_cond  = m.group(1)
    block_start = m.start()
    inner_start = m.end()

    # Walk forward counting depth to find the matching [/if]
    depth = 1
    pos   = inner_start
    while pos < len(text) and depth > 0:
        next_open  = text.find("[if ", pos)
        next_close = text.find("[/if]", pos)

        if next_close == -1:
            # No matching close – treat end-of-string as close
            return (block_start, len(text), first_cond, text[inner_start:])

        if next_open != -1 and next_open < next_close:
            # Verify it is a real [if tag] (has a closing bracket)
            end_bracket = text.find("]", next_open + 4)
            if end_bracket != -1:
                depth += 1
                pos = end_bracket + 1
            else:
                pos = next_close + 5
        else:
            depth -= 1
            if depth == 0:
                block_end = next_close + 5   # include the '[/if]'
                return (block_start, block_end, first_cond, text[inner_start:next_close])
            pos = next_close + 5

    return (block_start, len(text), first_cond, text[inner_start:])


def _split_top_level(inner: str) -> tuple:
    """
    Split *inner* text by top-level [elif ...] / [else] tags only
    (those NOT inside nested [if]...[/if] blocks).

    Returns:
        body_parts : list[str]       – text segments between the branch tags
        splitters  : list[str|None]  – condition string per [elif], None per [else]
    """
    body_parts: list = []
    splitters:  list = []
    current_start = 0
    pos   = 0
    depth = 0

    while pos < len(inner):
        if inner[pos:pos+4] == "[if ":
            end_b = inner.find("]", pos + 4)
            if end_b != -1:
                depth += 1
                pos = end_b + 1
            else:
                pos += 1
        elif inner[pos:pos+5] == "[/if]":
            if depth > 0:
                depth -= 1
            pos += 5
        elif depth == 0 and inner[pos:pos+6] == "[elif ":
            end_b = inner.find("]", pos + 6)
            if end_b != -1:
                body_parts.append(inner[current_start:pos])
                splitters.append(inner[pos+6:end_b])
                pos = end_b + 1
                current_start = pos
            else:
                pos += 1
        elif depth == 0 and inner[pos:pos+7] == "[else]":
            body_parts.append(inner[current_start:pos])
            splitters.append(None)
            pos += 7
            current_start = pos
        else:
            pos += 1

    body_parts.append(inner[current_start:])
    return body_parts, splitters


def _render_block(text: str, var_values: dict, opt_selections: dict) -> str:
    """
    Process [if/elif/else/endif] tags and substitute {X}.
    Handles arbitrarily nested [if] blocks correctly.
    Unclosed [if ...] blocks (missing [/if]) are auto-closed at end of string.
    """
    result = text

    # Auto-close any unclosed [if ...] blocks
    open_count  = len(re.findall(r"\[if [^\]]+\]", result))
    close_count = len(re.findall(r"\[/if\]", result))
    result += "[/if]" * max(0, open_count - close_count)

    # Process if-blocks iteratively (outermost first)
    while True:
        block = _find_block(result)
        if not block:
            break

        block_start, block_end, first_cond, inner = block

        # Split inner text at top-level [elif]/[else] tags only
        body_parts, splitters = _split_top_level(inner)

        # Build (condition|None, body) pairs
        pairs: list = [(first_cond, body_parts[0])]
        for i, cond_str in enumerate(splitters):
            body = body_parts[i + 1] if (i + 1) < len(body_parts) else ""
            pairs.append((cond_str, body))

        # Evaluate – first matching branch wins
        replacement = ""
        for cond, body in pairs:
            if cond is None:  # else branch
                replacement = _render_block(body, var_values, opt_selections)
                break
            if _eval_condition(cond, var_values, opt_selections):
                replacement = _render_block(body, var_values, opt_selections)
                break

        result = result[:block_start] + replacement + result[block_end:]

    # Substitute {X} variables
    def _sub(m):
        name = m.group(1)
        return str(var_values.get(name, f"{{{name}}}"))

    result = re.sub(r"\{([A-Za-z0-9_]+)\}", _sub, result)
    return result


def render_content_text(sigil: str,
                        var_values: dict,
                        opt_selections: dict) -> str:
    """
    Render sigil (structural template) into plain text.
    Used for the Sigil → Content Text preview.
    """
    text = _expand_special_markers(sigil)

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


def render_display_text(template: str,
                        var_values: dict,
                        opt_selections: dict) -> str:
    """
    Render Content Text / Reminder Text with full if/elif/else logic.
    This is what the Card Builder calls at runtime.

    var_values:     {"X": "3"}
    opt_selections: {"0": "top"}    – keys are option indices as strings
    """
    return _render_block(template, var_values, opt_selections)


# ── Stat blocks ────────────────────────────────────────────────────────────────

def make_default_stat(stat_id: str = "") -> dict:
    return {
        "id":         stat_id,
        "rarity":     10,
        "complexity": 1.0,
        "cv1":        1,
        "cv2":        0,
        "cv3":        0,
        "conditions": {},
    }


def generate_stat_id(effect_id: str, counter: int,
                     kind: str = "v") -> str:
    """
    Auto-generate ID like 'Draw.v0' for variables or 'Draw.o0' for options.
    kind: 'v' = variable, 'o' = option/choice
    """
    return f"{effect_id}.{kind}{counter}"


# ── ID registry & reference tools ─────────────────────────────────────────────

def collect_all_ids(data: dict) -> dict:
    """
    Returns flat dict: { id_str: {"type": "variable"|"choice"|"item", "item_id", "name"} }

    - 'variable' / 'choice' = stat IDs inside variables/options (for conditional text)
    - 'item'                = the content item's own ID (Effect/Trigger/Cost/Condition name),
                              so id_conditions can reference other content items for
                              generator exclusion/requirement rules.
    """
    registry = {}
    for type_name, items in data.items():
        for item in items:
            item_id = item.get("id", "")
            if item_id:
                # Item-level IDs are registered too (used by generator id_conditions)
                registry.setdefault(item_id, {
                    "type": "item", "item_id": item_id, "name": type_name})
            for vname, stat in item.get("variables", {}).items():
                sid = stat.get("id", "")
                if sid:
                    registry[sid] = {"type": "variable", "item_id": item_id, "name": vname}
            for opt in item.get("options", {}).values():
                for choice, stat in opt.get("per_choice", {}).items():
                    sid = stat.get("id", "")
                    if sid:
                        registry[sid] = {"type": "choice", "item_id": item_id, "name": choice}
    return registry


def find_references(target_id: str, data: dict) -> list:
    refs = []

    def _check(cond: dict, location: str):
        for entry in cond.get("id_conditions", []):
            if isinstance(entry, dict) and entry.get("id") == target_id:
                refs.append({"location": location, "cond": cond})

    for type_name, items in data.items():
        for item in items:
            iid = item.get("id", "")
            _check(item.get("conditions", {}), f"{type_name}/{iid} [item]")
            for vname, stat in item.get("variables", {}).items():
                _check(stat.get("conditions", {}), f"{type_name}/{iid}/var:{vname}")
            for ok, opt in item.get("options", {}).items():
                for choice, stat in opt.get("per_choice", {}).items():
                    _check(stat.get("conditions", {}), f"{type_name}/{iid}/opt{ok}:{choice}")
    return refs


def rename_id_everywhere(old_id: str, new_id: str, data: dict) -> int:
    """Rename old_id → new_id in all stat IDs and all condition references."""
    count = 0

    def _fix_cond(cond: dict):
        nonlocal count
        for entry in cond.get("id_conditions", []):
            if isinstance(entry, dict) and entry.get("id") == old_id:
                entry["id"] = new_id
                count += 1

    for items in data.values():
        for item in items:
            # fix stat IDs
            for stat in item.get("variables", {}).values():
                if stat.get("id") == old_id:
                    stat["id"] = new_id
                    count += 1
                _fix_cond(stat.get("conditions", {}))
            for opt in item.get("options", {}).values():
                for stat in opt.get("per_choice", {}).values():
                    if stat.get("id") == old_id:
                        stat["id"] = new_id
                        count += 1
                    _fix_cond(stat.get("conditions", {}))
            _fix_cond(item.get("conditions", {}))
    return count


def has_broken_refs(item: dict, all_ids: dict) -> bool:
    """
    Returns True if any id_condition entry in this item references a stat ID
    that does not exist in all_ids (as returned by collect_all_ids).
    """
    def _check_cond(cond: dict) -> bool:
        for entry in cond.get("id_conditions", []):
            if isinstance(entry, dict) and entry.get("id") and entry["id"] not in all_ids:
                return True
        return False

    if _check_cond(item.get("conditions", {})):
        return True
    for stat in item.get("variables", {}).values():
        if _check_cond(stat.get("conditions", {})):
            return True
    for opt in item.get("options", {}).values():
        for stat in opt.get("per_choice", {}).values():
            if _check_cond(stat.get("conditions", {})):
                return True
    return False


def rename_content_id(old_id: str, new_id: str, data: dict) -> int:
    """
    Rename a content item's ID and update all child stat IDs that start
    with old_id + "." (e.g. Draw.0 → Discard.0).
    Returns total number of changes.
    """
    count = 0
    prefix = old_id + "."
    new_prefix = new_id + "."

    for items in data.values():
        for item in items:
            if item.get("id") == old_id:
                item["id"] = new_id
                count += 1
            # rename child stat IDs
            for stat in item.get("variables", {}).values():
                sid = stat.get("id", "")
                if sid.startswith(prefix):
                    new_sid = new_prefix + sid[len(prefix):]
                    rename_id_everywhere(sid, new_sid, data)
                    count += 1
            for opt in item.get("options", {}).values():
                for stat in opt.get("per_choice", {}).values():
                    sid = stat.get("id", "")
                    if sid.startswith(prefix):
                        new_sid = new_prefix + sid[len(prefix):]
                        rename_id_everywhere(sid, new_sid, data)
                        count += 1
    return count


# ── Template sync ──────────────────────────────────────────────────────────────

def sync_item_template(item: dict) -> None:
    parsed   = parse_template(item.get("sigil", ""))
    old_vars = item.get("variables", {})
    old_opts = item.get("options",   {})
    item_id  = item.get("id", "item")

    used_ids: set = set()
    var_counter  = [0]
    opt_counter  = [0]

    def _collect(stat):
        if stat.get("id"):
            used_ids.add(stat["id"])

    for stat in old_vars.values(): _collect(stat)
    for opt in old_opts.values():
        for stat in opt.get("per_choice", {}).values(): _collect(stat)

    def _next_var_id() -> str:
        while generate_stat_id(item_id, var_counter[0], "v") in used_ids:
            var_counter[0] += 1
        sid = generate_stat_id(item_id, var_counter[0], "v")
        used_ids.add(sid)
        var_counter[0] += 1
        return sid

    def _next_opt_id() -> str:
        while generate_stat_id(item_id, opt_counter[0], "o") in used_ids:
            opt_counter[0] += 1
        sid = generate_stat_id(item_id, opt_counter[0], "o")
        used_ids.add(sid)
        opt_counter[0] += 1
        return sid

    new_vars: dict = {}
    for v in parsed["variables"]:
        if v in old_vars:
            new_vars[v] = old_vars[v]
            if not new_vars[v].get("id"):
                new_vars[v]["id"] = _next_var_id()
        else:
            new_vars[v] = make_default_stat(_next_var_id())
    item["variables"] = new_vars

    new_opts: dict = {}
    for i, choices in enumerate(parsed["options"]):
        key    = str(i)
        old_pc = old_opts.get(key, {}).get("per_choice", {})
        pc: dict = {}
        for c in choices:
            if c in old_pc:
                pc[c] = old_pc[c]
                if not pc[c].get("id"):
                    pc[c]["id"] = _next_opt_id()
            else:
                pc[c] = make_default_stat(_next_opt_id())
        new_opts[key] = {"choices": choices, "per_choice": pc}
    item["options"] = new_opts