"""
random_builder/generator.py – Random Spell card generator.

Algorithm per card:
  1. Pick element (equal distribution or custom weights)
  2. Pick block types via block_rules probabilities
     · Ensure no incompatible combinations (from box_config)
     · Max 4 blocks
  3. For each block build one ability:
     a. Apply content_rules: for each rule roll probability → pick effect from container
     b. Apply cost_rules: for each rule roll probability → add cost
     c. Pick variable values within CV budget
  4. Compute CV and complexity; store on card as "_cv" / "_complexity"
"""

import math
import random

from .cv_calc import (
    cv_content_item, cv_ability, cv_card,
    complexity_content_item, complexity_card,
    max_x_for_budget,
)

ELEMENTS = ["Fire", "Metal", "Ice", "Nature", "Blood", "Meta"]


# ── Data helpers ──────────────────────────────────────────────────────────────

def _list_to_lookup(items: list) -> dict:
    return {item["id"]: item for item in items if "id" in item}


# ── Main generator class ──────────────────────────────────────────────────────

class CardGenerator:
    """
    Generates random Spell cards according to generation config.

    Parameters
    ----------
    content_data : dict
        {"Effect": [...], "Cost": [...], "Condition": [...], "Trigger": [...]}
        (as loaded from cc_data/*.json)
    containers : dict
        {container_id: {"effects": [...], "no_repeat": bool, ...}}
    box_config : dict
        {block_type: {"rarity": int, "cv_modifier": float, "element_weights": {},
                      "incompatible_with": [...]}}
    gen_config : dict
        Generation settings (see models._DEFAULT_GEN_CONFIG)
    """

    def __init__(self, content_data: dict, containers: dict,
                 box_config: dict, gen_config: dict):
        self.effects   = _list_to_lookup(content_data.get("Effect",    []))
        self.costs     = _list_to_lookup(content_data.get("Cost",      []))
        self.conditions= _list_to_lookup(content_data.get("Condition", []))
        self.containers = containers
        self.box_config = box_config
        self.cfg        = gen_config

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self, count: int) -> list:
        cards = []
        for _ in range(count):
            card = self._generate_one()
            if card is not None:
                cards.append(card)
        return cards

    # ── Card generation ───────────────────────────────────────────────────────

    def _generate_one(self) -> dict:
        element = self._pick_element()
        block_types = self._pick_blocks(element)

        # Track which containers have been used (for no_repeat)
        used_container_effects: dict = {}  # container_id → set of used effect_ids

        blocks = []
        for btype in block_types:
            ability = self._build_ability(btype, element, used_container_effects)
            block = {"type": btype, "abilities": [ability]}
            blocks.append(block)

        card = {
            "name": f"Spell_{element}_{random.randint(1000, 9999)}",
            "card_type": "Spells",
            "artwork": "",
            "element": element,
            "blocks": blocks,
        }

        # Attach computed metrics
        card["_cv"]         = round(cv_card(card, self.box_config,
                                            self.effects, self.costs), 3)
        card["_complexity"] = round(complexity_card(card, self.effects,
                                                    self.costs), 3)
        return card

    # ── Element ───────────────────────────────────────────────────────────────

    def _pick_element(self) -> str:
        mode = self.cfg.get("element_mode", "equal")
        if mode == "equal":
            return random.choice(ELEMENTS)
        weights = [float(self.cfg.get("custom_element_weights", {}).get(el, 10))
                   for el in ELEMENTS]
        total = sum(weights)
        if total <= 0:
            return random.choice(ELEMENTS)
        return random.choices(ELEMENTS, weights=weights)[0]

    # ── Blocks ────────────────────────────────────────────────────────────────

    def _pick_blocks(self, element: str) -> list:
        rules = self.cfg.get("block_rules", [])
        chosen = []
        for rule in rules:
            bt = rule.get("block_type", "")
            if not bt:
                continue
            prob = float(rule.get("probability", 0.5))
            if random.random() < prob:
                chosen.append(bt)

        # Enforce at least 1 block
        if not chosen:
            chosen = ["Play"]

        # Enforce max 4 blocks
        chosen = chosen[:4]

        # Remove incompatible combinations (check box_config)
        chosen = self._remove_incompatible(chosen)
        return chosen

    def _remove_incompatible(self, block_types: list) -> list:
        """Remove blocks that are incompatible with already-chosen ones."""
        result = []
        for bt in block_types:
            incompatible = set(
                self.box_config.get(bt, {}).get("incompatible_with", []))
            if not incompatible.intersection(result):
                result.append(bt)
        return result if result else ["Play"]

    # ── Ability ───────────────────────────────────────────────────────────────

    def _build_ability(self, block_type: str, element: str,
                       used_container_effects: dict) -> dict:
        ability = {
            "condition_id":   None,
            "condition_vals": {},
            "ability_type":   "Play",
            "costs":          [],
            "effects":        [],
            "choose_n":       None,
            "choose_repeat":  False,
        }

        # ── Costs ─────────────────────────────────────────────────────────────
        for rule in self.cfg.get("cost_rules", []):
            prob = float(rule.get("probability", 1.0))
            if random.random() >= prob:
                continue
            cost_id = rule.get("cost_id", "")
            if cost_id:
                cost = self._build_cost(cost_id, element)
                if cost:
                    ability["costs"].append(cost)

        # ── CV budget for this box ─────────────────────────────────────────────
        cv_per_box = float(self.cfg.get("cv_per_box_max", 3.0))
        # Base cost CV (costs reduce the budget available for effects)
        cost_cv = sum(
            cv_content_item(self.costs[c["cost_id"]],
                            c.get("vals", {}), c.get("opt_vals", {}))
            for c in ability["costs"]
            if c["cost_id"] in self.costs
        )
        effect_budget = cv_per_box + cost_cv  # effects can eat this much

        # ── Effects ───────────────────────────────────────────────────────────
        for rule in self.cfg.get("content_rules", []):
            prob = float(rule.get("probability", 1.0))
            if random.random() >= prob:
                continue

            if "container" in rule:
                # Pick one item from a named container (no_repeat enforced)
                result = self._pick_from_container(
                    rule["container"], element, used_container_effects,
                    cv_budget=effect_budget)
                if result:
                    rtype, rdata = result
                    self._apply_content_item(ability, rtype, rdata, effect_budget)
                    if rtype == "effect":
                        item = self.effects.get(rdata["effect_id"])
                        if item:
                            effect_budget -= cv_content_item(
                                item, rdata.get("vals", {}), rdata.get("opt_vals", {}))
            elif "effect_id" in rule:
                eid = rule["effect_id"]
                solo_key = f"__solo__{eid}"
                if eid in used_container_effects.get(solo_key, set()):
                    continue
                used_container_effects.setdefault(solo_key, set()).add(eid)
                eff = self._build_effect(eid, element, effect_budget)
                if eff:
                    item = self.effects.get(eid)
                    if item:
                        effect_budget -= cv_content_item(
                            item, eff.get("vals", {}), eff.get("opt_vals", {}))
                    ability["effects"].append(eff)
            elif "cost_id" in rule:
                cid = rule["cost_id"]
                solo_key = f"__solo_cost__{cid}"
                if cid in used_container_effects.get(solo_key, set()):
                    continue
                used_container_effects.setdefault(solo_key, set()).add(cid)
                cost = self._build_cost(cid, element)
                if cost:
                    ability["costs"].append(cost)
            # condition_id / trigger_id rules – reserved for future use

        return ability

    # ── Effect picking ────────────────────────────────────────────────────────

    def _pick_from_container(self, container_id: str, element: str,
                              used: dict, cv_budget: float):
        """
        Pick one item from a container.
        Returns (type_str, data_dict) or None.
        type_str: "effect" | "cost"
        """
        container  = self.containers.get(container_id, {})
        no_repeat  = container.get("no_repeat", True)
        already    = used.get(container_id, set())

        # Gather all available items across types, with their lookup
        candidates = []  # (type_str, item_id, item_dict)
        for type_str, lookup, list_key in [
            ("effect", self.effects, "effects"),
            ("cost",   self.costs,   "costs"),
        ]:
            for iid in container.get(list_key, []):
                if iid not in lookup:
                    continue
                if no_repeat and iid in already:
                    continue
                candidates.append((type_str, iid, lookup[iid]))

        if not candidates:
            return None

        # Weight by rarity × element_weight
        weights = []
        for _, iid, item in candidates:
            rarity = float(item.get("rarity", 10))
            el_w_map = item.get("element_weights", {})
            el_w = float(el_w_map.get(element, 10)) if el_w_map else 10.0
            weights.append(math.sqrt(rarity) * (max(el_w, 0) / 10.0))

        total_w = sum(weights)
        if total_w <= 0:
            chosen = random.choice(candidates)
        else:
            chosen = random.choices(candidates, weights=weights)[0]

        type_str, iid, _ = chosen
        if no_repeat:
            used.setdefault(container_id, set()).add(iid)

        if type_str == "effect":
            return ("effect", self._build_effect(iid, element, cv_budget))
        elif type_str == "cost":
            return ("cost", self._build_cost(iid, element))
        return None

    def _apply_content_item(self, ability: dict, type_str: str, data, cv_budget: float):
        """Add a picked container item to the ability."""
        if not data:
            return
        if type_str == "effect":
            ability["effects"].append(data)
        elif type_str == "cost":
            ability["costs"].append(data)

    # ── Effect / cost building ────────────────────────────────────────────────

    def _build_effect(self, effect_id: str, element: str,
                      cv_budget: float) -> dict:
        item = self.effects.get(effect_id)
        if not item:
            return None

        # Pick option selections first (flat CV, no variable)
        opt_vals = self._pick_options(item, element)

        # Calculate base CV so far (constant terms + selected options)
        base_cv = float(item.get("cv1", 0.0))
        for opt_key, sel in opt_vals.items():
            stat = item.get("options", {}).get(opt_key, {}).get("per_choice", {}).get(sel, {})
            base_cv += float(stat.get("cv1", 0.0))

        remaining = cv_budget - base_cv

        # Pick variable values within remaining CV budget
        vals = self._pick_variable_values(item, remaining)

        return {"effect_id": effect_id, "vals": vals, "opt_vals": opt_vals}

    def _build_cost(self, cost_id: str, element: str) -> dict:
        item = self.costs.get(cost_id)
        if not item:
            return None
        vals = {}
        # Special: Mana cost uses card's element
        if "element" in item.get("variables", {}):
            vals["element"] = element
        opt_vals = self._pick_options(item, element)
        return {"cost_id": cost_id, "vals": vals, "opt_vals": opt_vals}

    # ── Option selection ──────────────────────────────────────────────────────

    def _pick_options(self, item: dict, element: str) -> dict:
        opt_vals = {}
        for opt_key, opt in item.get("options", {}).items():
            choices = opt.get("choices", [])
            if not choices:
                continue
            pc = opt.get("per_choice", {})
            # Filter out excluded choices
            avail = []
            for c in choices:
                stat = pc.get(c, {})
                excluded = stat.get("conditions", {}).get("excluded_choices", [])
                if c not in excluded:
                    avail.append(c)
            if not avail:
                avail = choices

            # Weight by rarity × element weight
            weights = []
            for c in avail:
                stat = pc.get(c, {})
                r = float(stat.get("rarity", 10))
                ew = stat.get("conditions", {}).get("element_weights", {})
                el_w = float(ew.get(element, 10)) if ew else 10.0
                weights.append(math.sqrt(r) * (el_w / 10.0))

            total_w = sum(weights)
            if total_w <= 0:
                opt_vals[opt_key] = random.choice(avail)
            else:
                opt_vals[opt_key] = random.choices(avail, weights=weights)[0]
        return opt_vals

    # ── Variable value picking ────────────────────────────────────────────────

    def _pick_variable_values(self, item: dict, cv_budget: float) -> dict:
        vals = {}
        variables = item.get("variables", {})
        if not variables:
            return vals

        # Distribute CV budget equally among variables
        share = cv_budget / len(variables) if variables else 0

        for var_name, stat in variables.items():
            cond = stat.get("conditions", {})
            vmin = float(cond.get("var_min", 1))
            vmax = float(cond.get("var_max", 10))

            x_max = max_x_for_budget(stat, share)
            x_max = min(x_max, vmax)
            x_min = max(vmin, 1)

            if x_min > x_max:
                x = x_min
            else:
                x = random.uniform(x_min, x_max)

            # Round to int if no decimal variance
            if abs(x - round(x)) < 0.05:
                x = int(round(x))
            else:
                x = round(x, 1)

            vals[var_name] = x

        return vals
