"""
random_builder/cv_calc.py – CV and complexity calculation.

Formula:
  Item-level constant (single value, stored as "cv"):
      cv_item

  Per variable with value x:
      cv_var = cv1·x  +  cv2·x²  +  cv3·x³

  Total CV of a content item:
      cv_total = cv_item  +  Σ_vars(cv1·x + cv2·x² + cv3·x³)
               + Σ_options(selected_choice.cv)

CV of a box (one ability):
    CV_box = CV_condition * CV_trigger * (sum_cv_effects - sum_cv_costs)

CV of a card:
    CV_card = -1.0 + sum(CV_box_i * box_cv_modifier_i)

Targets:  CV_box ≤ 3.0   CV_card ≤ 3.0

Complexity of choices:
    cmplx_option = sum(choice.complexity for all choices in option) * 1.05 ^ n_choices
"""

import math


# ── Stat helpers ──────────────────────────────────────────────────────────────

def cv_stat(stat: dict, x: float = 0.0) -> float:
    """
    CV contribution of a variable/choice stat for value x.
    Formula:  cv1·x  +  cv2·x²  +  cv3·x³
    (no constant term – constants live at item level only)
    """
    c1 = float(stat.get("cv1", 0.0))
    c2 = float(stat.get("cv2", 0.0))
    c3 = float(stat.get("cv3", 0.0))
    return c1 * x + c2 * x * x + c3 * x * x * x


# ── Content item CV ────────────────────────────────────────────────────────────

def cv_content_item(item: dict, vals: dict, opt_vals: dict) -> float:
    """
    Total CV of a content item (effect or cost) with given values.
    vals:     {var_name: numeric_value}
    opt_vals: {opt_index_str: selected_choice_str}
    """
    # Item-level constant – stored as "cv"; fall back to "cv1" for legacy data
    total = float(item.get("cv", item.get("cv1", 0.0)))

    # Variable contributions:  cv1·x + cv2·x² + cv3·x³
    for var_name, stat in item.get("variables", {}).items():
        x = _to_float(vals.get(var_name, 0))
        total += cv_stat(stat, x)

    # Option contributions: selected choice's cv (constant, evaluated at x=0)
    for opt_key, opt in item.get("options", {}).items():
        choices  = opt.get("choices", [])
        selected = opt_vals.get(opt_key, choices[0] if choices else "")
        stat     = opt.get("per_choice", {}).get(selected, {})
        if stat:
            total += float(stat.get("cv", stat.get("cv1", 0.0)))

    return total


# ── Effect CV (legacy flat list) ──────────────────────────────────────────────

def _effects_cv(effects: list, effects_lookup: dict) -> float:
    """
    Compute the total CV of a flat list of ability effects (legacy format).
    """
    total = 0.0
    for eff in effects:
        item = effects_lookup.get(eff.get("effect_id", ""))
        if item:
            total += cv_content_item(item, eff.get("vals", {}), eff.get("opt_vals", {}))
    return total


# ── Effect Group CV ──────────────────────────────────────────────────────────

def cv_effect_group(group: dict, effects_lookup: dict) -> float:
    """
    CV of one effect group = sum(primaries CVs) + sum(modifier CVs).
    Backward compat: falls back to 'primary' if 'primaries' not present.
    Also handles legacy 'effects' key for old data.
    """
    total = 0.0
    # Check 'effects' first (new canonical key), then 'primaries', then old 'primary'
    effs = group.get("effects")
    if effs is None:
        effs = group.get("primaries")
    if effs is None:
        p = group.get("primary", {})
        effs = [p] if p.get("effect_id") else []
    for primary in effs:
        item = effects_lookup.get(primary.get("effect_id", ""))
        if item:
            total += cv_content_item(item, primary.get("vals", {}),
                                     primary.get("opt_vals", {}))
    for mod in group.get("modifiers", []):
        item = effects_lookup.get(mod.get("effect_id", ""))
        if item:
            total += cv_content_item(item, mod.get("vals", {}),
                                     mod.get("opt_vals", {}))
    return total


def _effect_groups_cv(groups: list, effects_lookup: dict) -> float:
    """Sum CV across all effect groups."""
    return sum(cv_effect_group(g, effects_lookup) for g in groups)


# ── Choose Y of X CV ─────────────────────────────────────────────────────────

def cv_choose(group_cvs: list, choose_n: int, choose_repeat: bool = False) -> float:
    """
    CV when player picks choose_n groups from len(group_cvs) available.
    Placeholder: best choose_n groups summed.
    Real formula TBD – will involve expected value / max calculations.
    """
    if not group_cvs or not choose_n:
        return sum(group_cvs)
    sorted_cvs = sorted(group_cvs, reverse=True)
    if choose_repeat:
        # Can pick same group multiple times → best group × choose_n
        return sorted_cvs[0] * choose_n if sorted_cvs else 0.0
    return sum(sorted_cvs[:choose_n])


# ── Sub-Sigil CV ─────────────────────────────────────────────────────────────

def cv_sub_sigil(sub_sigil: dict, effects_lookup: dict,
                 costs_lookup: dict) -> float:
    """
    CV of a sub-sigil = sum(group CVs) - sum(cost CVs).
    Sub-sigils are optional (player chooses to pay), so their CV contribution
    is additive to the parent ability. Exact formula TBD.
    """
    if not sub_sigil:
        return 0.0
    eff_cv = _effect_groups_cv(sub_sigil.get("effect_groups", []),
                               effects_lookup)
    cost_cv = 0.0
    for cost in sub_sigil.get("costs", []):
        item = costs_lookup.get(cost.get("cost_id", ""))
        if item:
            cost_cv += cv_content_item(item, cost.get("vals", {}),
                                       cost.get("opt_vals", {}))
    return max(0.0, eff_cv - cost_cv)


# ── Ability / box CV ──────────────────────────────────────────────────────────

def _trigger_multiplier(ability: dict, triggers_lookup: dict | None) -> float:
    """Look up the trigger's `cv_mult` value (default 1.0)."""
    tid = ability.get("trigger_id")
    if not tid or not triggers_lookup:
        return 1.0
    titem = triggers_lookup.get(tid)
    if not titem:
        return 1.0
    return float(titem.get("cv_mult", 1.0))


def cv_ability(ability: dict,
               effects_lookup: dict,
               costs_lookup: dict,
               condition_mult: float = 1.0,
               trigger_mult: float | None = None,
               triggers_lookup: dict | None = None) -> float:
    """CV of a single ability (one box entry). Supports both old and new format.

    The trigger multiplier is looked up from `triggers_lookup[trigger_id].cv_mult`
    when `trigger_mult` is not supplied explicitly.
    """
    # New format: effect_groups
    if "effect_groups" in ability and ability["effect_groups"]:
        groups = ability["effect_groups"]
        group_cvs = [cv_effect_group(g, effects_lookup) for g in groups]

        choose_n = ability.get("choose_n")
        if choose_n and len(groups) > 1:
            cv_eff = cv_choose(group_cvs, choose_n,
                               ability.get("choose_repeat", False))
        else:
            cv_eff = sum(group_cvs)

        cv_eff += cv_sub_sigil(ability.get("sub_sigil"), effects_lookup,
                               costs_lookup)
    else:
        # Legacy flat effects list
        cv_eff = _effects_cv(ability.get("effects", []), effects_lookup)

    cv_cost = 0.0
    for cost in ability.get("costs", []):
        item = costs_lookup.get(cost.get("cost_id", ""))
        if item:
            cv_cost += cv_content_item(item, cost.get("vals", {}),
                                       cost.get("opt_vals", {}))

    if trigger_mult is None:
        trigger_mult = _trigger_multiplier(ability, triggers_lookup)

    return condition_mult * trigger_mult * (cv_eff - cv_cost)


# ── Card CV ───────────────────────────────────────────────────────────────────

def cv_card(card: dict, box_config: dict,
            effects_lookup: dict, costs_lookup: dict,
            triggers_lookup: dict | None = None) -> float:
    """
    Total CV of a card.
    Base value = -1.0; each block adds CV_ability * cv_modifier.
    """
    total = -1.0
    for block in card.get("blocks", []):
        modifier = float(box_config.get(block["type"], {}).get("cv_modifier", 1.0))
        for ability in block.get("abilities", []):
            total += cv_ability(ability, effects_lookup, costs_lookup,
                                triggers_lookup=triggers_lookup) * modifier
    return total


# ── Complexity ────────────────────────────────────────────────────────────────

def complexity_content_item(item: dict) -> float:
    """
    Complexity of a content item.
    = complexity_base
      + sum(variable.complexity)
      + sum(choice.complexity for all choices) * 1.05^n_choices   (per option)
    """
    total = float(item.get("complexity_base", 1.0))

    for stat in item.get("variables", {}).values():
        total += float(stat.get("complexity", 0.0))

    for opt in item.get("options", {}).values():
        choices = opt.get("choices", [])
        n = len(choices)
        pc = opt.get("per_choice", {})
        choice_sum = sum(float(pc.get(c, {}).get("complexity", 0.0))
                         for c in choices)
        total += choice_sum * (1.05 ** n)

    return total


def _complexity_effects_from_groups(groups: list, effects_lookup: dict) -> float:
    """Complexity from effect groups (primary + modifiers)."""
    total = 0.0
    for g in groups:
        primary = g.get("primary", {})
        item = effects_lookup.get(primary.get("effect_id", ""))
        if item:
            total += complexity_content_item(item)
        for mod in g.get("modifiers", []):
            item = effects_lookup.get(mod.get("effect_id", ""))
            if item:
                total += complexity_content_item(item)
    return total


def complexity_card(card: dict, effects_lookup: dict, costs_lookup: dict) -> float:
    """Total complexity of a card.

    Multi-element bonus:  raw * (1 + (N_elements - 1) * 0.1)
    """
    total = 0.0
    for block in card.get("blocks", []):
        for ability in block.get("abilities", []):
            # New format
            if "effect_groups" in ability and ability["effect_groups"]:
                total += _complexity_effects_from_groups(
                    ability["effect_groups"], effects_lookup)
                sub = ability.get("sub_sigil")
                if sub:
                    total += _complexity_effects_from_groups(
                        sub.get("effect_groups", []), effects_lookup)
            else:
                # Legacy flat effects
                for eff in ability.get("effects", []):
                    item = effects_lookup.get(eff.get("effect_id", ""))
                    if item:
                        total += complexity_content_item(item)
            for cost in ability.get("costs", []):
                item = costs_lookup.get(cost.get("cost_id", ""))
                if item:
                    total += complexity_content_item(item)

    # Multi-element complexity multiplier
    elements = card.get("elements")
    if elements is None:
        old = card.get("element")
        elements = [old] if old else []
    n = len(elements)
    if n > 1:
        total *= 1 + (n - 1) * 0.1

    return total


# ── Variable value picking ────────────────────────────────────────────────────

def max_x_for_budget(stat: dict, cv_budget: float) -> float:
    """
    Find the largest x in [var_min, var_max] such that
    cv_stat(stat, x) = cv1·x + cv2·x² + cv3·x³  ≤  cv_budget.

    Uses binary search for robustness with the cubic formula.
    """
    cond = stat.get("conditions", {})
    vmin = float(cond.get("var_min", 1))
    vmax = float(cond.get("var_max", 10))

    c1 = float(stat.get("cv1", 0.0))
    c2 = float(stat.get("cv2", 0.0))
    c3 = float(stat.get("cv3", 0.0))

    def _cv(x):
        return c1 * x + c2 * x * x + c3 * x * x * x

    # If all coefficients ≤ 0, increasing x doesn't raise CV → pick max freely
    if c1 <= 0 and c2 <= 0 and c3 <= 0:
        return vmax

    # If even vmin already exceeds budget, stay at vmin
    if _cv(vmin) > cv_budget:
        return vmin

    # If vmax is within budget, pick max freely
    if _cv(vmax) <= cv_budget:
        return vmax

    # Binary search
    lo, hi = vmin, vmax
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if _cv(mid) <= cv_budget:
            lo = mid
        else:
            hi = mid
    return lo


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_float(v) -> float:
    """Convert a value to float.
    Handles dice notation:
      '2D6'  → expected value 7.0   (2 × 3.5)
      'D6'   → expected value 3.5   (1 × 3.5)
      '4D4'  → expected value 10.0  (4 × 2.5)
    """
    if isinstance(v, str):
        import re
        # Optional leading N, then D/d, then sides
        m = re.fullmatch(r"(\d*)[dD](\d+)", v.strip())
        if m:
            n     = int(m.group(1)) if m.group(1) else 1
            sides = int(m.group(2))
            return n * (sides + 1) / 2.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
