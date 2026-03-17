"""
template_parser.py – Template parsing, rendering, ID management, reference tracking.

Content Box syntax  (for structure):
    {X}          → free variable named X
    [a, b, c]    → dropdown with choices a, b, c

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


# ── Content Box parsing ────────────────────────────────────────────────────────

def parse_template(content_box: str) -> dict:
    variables = list(dict.fromkeys(re.findall(r"\{([A-Za-z0-9_]+)\}", content_box)))
    raw_opts  = re.findall(r"\[([^\]]+)\]", content_box)
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


def _render_block(text: str, var_values: dict, opt_selections: dict) -> str:
    """
    Process a single level of [if/elif/else/endif] tags and substitute {X}.
    Recursively handles nested blocks.
    """
    # Pattern: [if COND]...[elif COND]...[else]...[/if]
    IF_PAT = re.compile(
        r"\[if ([^\]]+)\](.*?)(?=\[elif |\[else\]|\[/if\])",
        re.DOTALL
    )

    result = text

    # Process if-blocks iteratively (outermost first)
    while True:
        # Find the next [if ...] ... [/if] block (non-greedy, handles nesting naively)
        m = re.search(r"\[if ([^\]]+)\](.*?)\[/if\]", result, re.DOTALL)
        if not m:
            break

        full_match = m.group(0)
        inner      = m.group(0)[m.group(0).index("]")+1 : -len("[/if]")]

        # Split into segments: [if cond]body [elif cond]body [else]body
        segments = []
        # prepend the first condition
        first_cond = m.group(1)
        # find all [elif ...] and [else] splits
        parts = re.split(r"\[elif ([^\]]+)\]|\[else\]", inner)
        # the splitter groups will interleave: cond, None, cond, None ...
        splitters = re.findall(r"\[elif ([^\]]+)\]|\[else\]", inner)

        # Build (condition|None, body) pairs
        pairs: list = [(first_cond, parts[0])]
        for i, body in enumerate(parts[1:]):
            if i < len(splitters):
                c = splitters[i] if splitters[i] else None  # None = else
            else:
                c = None
            pairs.append((c, body))

        # Evaluate
        replacement = ""
        for cond, body in pairs:
            if cond is None:  # else branch
                replacement = _render_block(body, var_values, opt_selections)
                break
            if _eval_condition(cond, var_values, opt_selections):
                replacement = _render_block(body, var_values, opt_selections)
                break

        result = result[:m.start()] + replacement + result[m.end():]

    # Substitute {X} variables
    def _sub(m):
        name = m.group(1)
        return str(var_values.get(name, f"{{{name}}}"))

    result = re.sub(r"\{([A-Za-z0-9_]+)\}", _sub, result)
    return result


def render_content_text(content_box: str,
                        var_values: dict,
                        opt_selections: dict) -> str:
    """
    Render content_box (structural template) into plain text.
    Used for the Content Box → Content Text preview.
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
        "cv1":        0,
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
    Returns flat dict: { id_str: {"type": "variable"|"choice", "item_id", "name"} }
    """
    registry = {}
    for type_name, items in data.items():
        for item in items:
            item_id = item.get("id", "")
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
    parsed   = parse_template(item.get("content_box", ""))
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