"""
random_builder/cv_calc.py – CV and complexity calculation.

User's naming (mental model → stored field):
  "cv"  → cv1   (constant term)
  "cv1" → cv2   (linear coefficient)
  "cv2" → cv3   (quadratic coefficient)

So for a variable/choice with value X:
    cv_contribution = stat["cv1"] + stat["cv2"] * X + stat["cv3"] * X²

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
    """CV contribution of a stat dict given variable value x."""
    return (float(stat.get("cv1", 0.0))
            + float(stat.get("cv2", 0.0)) * x
            + float(stat.get("cv3", 0.0)) * x * x)


# ── Content item CV ────────────────────────────────────────────────────────────

def cv_content_item(item: dict, vals: dict, opt_vals: dict) -> float:
    """
    Total CV of a content item (effect or cost) with given values.
    vals:     {var_name: numeric_value}
    opt_vals: {opt_index_str: selected_choice_str}
    """
    # Item-level constant (cv1 = constant term)
    total = float(item.get("cv1", 0.0))

    # Variable contributions
    for var_name, stat in item.get("variables", {}).items():
        x = _to_float(vals.get(var_name, 0))
        total += cv_stat(stat, x)

    # Option contributions: selected choice's cv1 (constant, no variable dimension)
    for opt_key, opt in item.get("options", {}).items():
        choices = opt.get("choices", [])
        selected = opt_vals.get(opt_key, choices[0] if choices else "")
        stat = opt.get("per_choice", {}).get(selected, {})
        if stat:
            total += cv_stat(stat, 0.0)

    return total


# ── Ability / box CV ──────────────────────────────────────────────────────────

def cv_ability(ability: dict,
               effects_lookup: dict,
               costs_lookup: dict,
               condition_mult: float = 1.0,
               trigger_mult: float = 1.0) -> float:
    """CV of a single ability (one box entry)."""
    cv_eff = 0.0
    for eff in ability.get("effects", []):
        item = effects_lookup.get(eff.get("effect_id", ""))
        if item:
            cv_eff += cv_content_item(item, eff.get("vals", {}),
                                      eff.get("opt_vals", {}))

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
    Find the maximum integer X such that cv_stat(stat, X) ≤ cv_budget.
    Returns the maximum allowed X within [var_min, var_max] from conditions.
    If cv increases with X, constrains X accordingly.
    If cv decreases or is flat with X, returns var_max freely.
    """
    cond = stat.get("conditions", {})
    vmin = float(cond.get("var_min", 1))
    vmax = float(cond.get("var_max", 10))

    c0 = float(stat.get("cv1", 0.0))  # constant term
    c1 = float(stat.get("cv2", 0.0))  # linear coeff
    c2 = float(stat.get("cv3", 0.0))  # quadratic coeff

    remaining = cv_budget - c0

    # If CV doesn't depend on X at all, pick freely
    if abs(c1) < 1e-9 and abs(c2) < 1e-9:
        return vmax

    # If increasing X decreases CV (negative coefficients), pick max freely
    if c1 <= 0 and c2 <= 0:
        return vmax

    # Solve c1*X + c2*X² ≤ remaining  →  find X_max
    if remaining <= 0:
        return vmin

    if abs(c2) < 1e-9:
        # Linear: X_max = remaining / c1
        x_budget = remaining / c1 if c1 > 0 else vmax
    else:
        # Quadratic (c2 > 0): c2*X² + c1*X - remaining = 0
        disc = c1 * c1 + 4.0 * c2 * remaining
        if disc < 0:
            x_budget = vmin
        else:
            x_budget = (-c1 + math.sqrt(disc)) / (2.0 * c2)

    return max(vmin, min(vmax, x_budget))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
