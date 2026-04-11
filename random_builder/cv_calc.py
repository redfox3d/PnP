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


# ── Effect CV grouping ────────────────────────────────────────────────────────

def _effects_cv(effects: list, effects_lookup: dict) -> float:
    """
    Compute the total CV of a list of ability effects.
    primary_types on each effect item are informational (for generation grouping);
    CV is simply summed across all effects.
    """
    total = 0.0
    for eff in effects:
        item = effects_lookup.get(eff.get("effect_id", ""))
        if item:
            total += cv_content_item(item, eff.get("vals", {}), eff.get("opt_vals", {}))
    return total


# ── Ability / box CV ──────────────────────────────────────────────────────────

def cv_ability(ability: dict,
               effects_lookup: dict,
               costs_lookup: dict,
               condition_mult: float = 1.0,
               trigger_mult: float = 1.0) -> float:
    """CV of a single ability (one box entry)."""
    cv_eff = _effects_cv(ability.get("effects", []), effects_lookup)

    cv_cost = 0.0
    for cost in ability.get("costs", []):
        item = costs_lookup.get(cost.get("cost_id", ""))
        if item:
            cv_cost += cv_content_item(item, cost.get("vals", {}),
                                       cost.get("opt_vals", {}))

    return condition_mult * trigger_mult * (cv_eff - cv_cost)


# ── Card CV ───────────────────────────────────────────────────────────────────

def cv_card(card: dict, box_config: dict,
            effects_lookup: dict, costs_lookup: dict) -> float:
    """
    Total CV of a card.
    Base value = -1.0; each block adds CV_ability * cv_modifier.
    """
    total = -1.0
    for block in card.get("blocks", []):
        modifier = float(box_config.get(block["type"], {}).get("cv_modifier", 1.0))
        for ability in block.get("abilities", []):
            total += cv_ability(ability, effects_lookup, costs_lookup) * modifier
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


def complexity_card(card: dict, effects_lookup: dict, costs_lookup: dict) -> float:
    """Total complexity of a card (sum over all effects and costs)."""
    total = 0.0
    for block in card.get("blocks", []):
        for ability in block.get("abilities", []):
            for eff in ability.get("effects", []):
                item = effects_lookup.get(eff.get("effect_id", ""))
                if item:
                    total += complexity_content_item(item)
            for cost in ability.get("costs", []):
                item = costs_lookup.get(cost.get("cost_id", ""))
                if item:
                    total += complexity_content_item(item)
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
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
