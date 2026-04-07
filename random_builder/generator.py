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

# ── Card name generation ──────────────────────────────────────────────────────
_NAME_PREFIXES = {
    "Fire":   ["Blazing", "Inferno", "Smoldering", "Ashen", "Pyroclastic", "Embered"],
    "Metal":  ["Ironclad", "Forged", "Shattered", "Tempered", "Rusted", "Gilded"],
    "Ice":    ["Frozen", "Glacial", "Bitter", "Crystalline", "Frostbound", "Shivering"],
    "Nature": ["Overgrown", "Withered", "Blooming", "Ancient", "Twisted", "Verdant"],
    "Blood":  ["Crimson", "Severed", "Pulsing", "Tainted", "Visceral", "Coagulated"],
    "Meta":   ["Unraveling", "Fractured", "Hollow", "Echoing", "Null", "Paradox"],
}
_NAME_NOUNS = [
    "Strike", "Ward", "Surge", "Veil", "Oath", "Pact", "Brand", "Rite",
    "Sigil", "Grasp", "Edict", "Toll", "Shard", "Pulse", "Omen", "Chain",
    "Decree", "Burst", "Vow", "Lash", "Mark", "Curse", "Seal", "Hex",
]

def _make_card_name(element: str) -> str:
    prefix = random.choice(_NAME_PREFIXES.get(element, ["Arcane"]))
    noun   = random.choice(_NAME_NOUNS)
    return f"{prefix} {noun}"


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
        self.effects    = _list_to_lookup(content_data.get("Effect",    []))
        self.costs      = _list_to_lookup(content_data.get("Cost",      []))
        self.conditions = _list_to_lookup(content_data.get("Condition", []))
        self.triggers   = _list_to_lookup(content_data.get("Trigger",   []))
        self.containers = containers
        self.box_config = box_config
        self.cfg        = gen_config

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self, count: int) -> list:
        cv_min = float(self.cfg.get("cv_card_min", -999.0))
        cv_max = float(self.cfg.get("cv_target",    999.0))
        cards = []
        attempts = 0
        max_attempts = count * 30  # more attempts since both min and max must be satisfied
        while len(cards) < count and attempts < max_attempts:
            attempts += 1
            card = self._generate_one()
            if card is None:
                continue
            cv = card.get("_cv", 0)
            if cv < cv_min:
                print(f"  [gen] Verworfen: CV={cv:.2f} < min={cv_min:.2f}")
                continue
            if cv > cv_max:
                print(f"  [gen] Verworfen: CV={cv:.2f} > max={cv_max:.2f}")
                continue
            cards.append(card)
        if len(cards) < count:
            print(f"  [gen] Warnung: nur {len(cards)}/{count} Karten in [{cv_min}, {cv_max}]")
        return cards

    # ── Card generation ───────────────────────────────────────────────────────

    def _generate_one(self) -> dict:
        element = self._pick_element()
        block_types = self._pick_blocks(element)
        print(f"  [gen_one] Element={element}, Boxen={block_types}")

        # Container no_repeat dedup is shared across all boxes on a card.
        # Solo-item dedup is per-box (same effect can appear in different boxes).
        used_containers: dict = {}  # container_id → set of used effect_ids (card-wide)

        blocks = []
        min_eff = int(self.cfg.get("min_effects", 0))
        for btype in block_types:
            # Fresh solo-dedup dict for each box; retry up to 3× if min_effects not met
            ability = None
            for _ in range(3):
                used_solo: dict = {}
                ab = self._build_ability(btype, element, used_containers, used_solo)
                if len(ab.get("effects", [])) >= min_eff:
                    ability = ab
                    break
            if ability is None:
                ability = ab   # use last attempt regardless
            n_eff  = len(ability.get("effects", []))
            n_cost = len(ability.get("costs",   []))
            print(f"    [gen_one] Sigil={btype}: {n_eff} Effekte, {n_cost} Kosten, "
                  f"trigger={ability.get('trigger_id')}")
            block = {"type": btype, "abilities": [ability]}
            blocks.append(block)

        card = {
            "name": _make_card_name(element),
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
        rules     = self.cfg.get("block_rules", [])
        min_blks  = max(1, int(self.cfg.get("min_blocks", 1)))

        # Try up to 10× until min_blocks is reached
        for _attempt in range(10):
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

            if len(chosen) >= min_blks:
                break

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
                       used_containers: dict,
                       used_solo: dict) -> dict:
        """
        used_containers : shared across all boxes on this card (container no_repeat)
        used_solo       : fresh per box (solo-item within-box dedup only)
        """
        is_play = (block_type == "Play")

        # Non-Play sigils get a random trigger with proper vals/opts
        trigger_id, trigger_vals, trigger_opt_vals = None, {}, {}
        if not is_play and self.triggers:
            tid   = random.choice(list(self.triggers.keys()))
            titem = self.triggers[tid]
            trigger_id       = tid
            trigger_opt_vals = self._pick_options(titem, element)
            trigger_vals     = self._pick_variable_values(titem, cv_budget=2.0)

        # Optional condition on any sigil
        condition_id, condition_vals, condition_opt_vals = None, {}, {}
        cond_chance = float(self.cfg.get("condition_chance", 0.15))
        if self.conditions and random.random() < cond_chance:
            cid   = random.choice(list(self.conditions.keys()))
            citem = self.conditions[cid]
            condition_id       = cid
            condition_opt_vals = self._pick_options(citem, element)
            condition_vals     = self._pick_variable_values(citem, cv_budget=1.0)

        ability = {
            "condition_id":       condition_id,
            "condition_vals":     condition_vals,
            "condition_opt_vals": condition_opt_vals,
            "trigger_id":         trigger_id,
            "trigger_vals":       trigger_vals,
            "trigger_opt_vals":   trigger_opt_vals,
            "ability_type":       "Play" if is_play else "Trigger",
            "costs":              [],
            "effects":            [],
            "choose_n":           None,
            "choose_repeat":      False,
        }

        # ── Costs (only on Play boxes) ─────────────────────────────────────────
        if is_play:
            # Mana is handled independently – almost always present, uncapped by cost_rules
            mana_chance    = float(self.cfg.get("mana_chance",    0.95))
            mana_main      = int(self.cfg.get("mana_main_count", 2))
            mana_max_count = int(self.cfg.get("mana_max_count",  6))
            if random.random() < mana_chance and "Mana" in self.costs:
                # Bell-curve distribution centred at mana_main, capped at mana_max_count.
                # weight(n) = exp(-0.7 · (n − main)²)  →  peak at main, falls off quickly
                hi     = max(mana_max_count, mana_main)
                counts = list(range(1, hi + 1))
                wts    = [math.exp(-0.7 * (n - mana_main) ** 2) for n in counts]
                count  = random.choices(counts, weights=wts)[0]
                for _ in range(count):
                    cost = self._build_cost("Mana", element)
                    if cost:
                        ability["costs"].append(cost)

            # Other costs from cost_rules, limited by max_other_costs
            max_other  = int(self.cfg.get("max_other_costs", 1))
            other_added = 0
            for rule in self.cfg.get("cost_rules", []):
                if other_added >= max_other:
                    break
                cost_id = rule.get("cost_id", "")
                if not cost_id or cost_id == "Mana":
                    continue   # Mana handled above
                prob = float(rule.get("probability", 1.0))
                if random.random() >= prob:
                    continue
                cost = self._build_cost(cost_id, element)
                if cost:
                    ability["costs"].append(cost)
                    other_added += 1

        # ── CV budget for this box ─────────────────────────────────────────────
        cv_per_box = float(self.cfg.get("cv_per_box_max", 3.0))
        cost_cv = sum(
            cv_content_item(self.costs[c["cost_id"]],
                            c.get("vals", {}), c.get("opt_vals", {}))
            for c in ability["costs"]
            if c["cost_id"] in self.costs
        )
        effect_budget = cv_per_box + cost_cv

        # ── Constraint helpers ────────────────────────────────────────────────
        sig_constraints = self.cfg.get("sigil_constraints", {})
        bt_constraints  = sig_constraints.get(block_type, {})
        forbidden_ids   = set(bt_constraints.get("forbidden", []))
        required_ids    = list(bt_constraints.get("required", []))
        incompat_pairs  = [set(p) for p in self.cfg.get("incompatible_pairs", [])]

        def _is_forbidden(eid: str) -> bool:
            return eid in forbidden_ids

        def _is_incompatible(eid: str, current_effects: list) -> bool:
            current_ids = {e["effect_id"] for e in current_effects}
            for pair in incompat_pairs:
                if eid in pair and current_ids & (pair - {eid}):
                    return True
            return False

        # ── Effects ───────────────────────────────────────────────────────────
        max_effects  = int(self.cfg.get("max_effects", -1))
        min_effects  = int(self.cfg.get("min_effects",  0))
        effects_added = 0

        sigil_rules = self.cfg.get("sigil_rules", {}).get(block_type, [])

        if sigil_rules:
            # ── Per-sigil container rules (overrides global content_rules) ────
            for rule in sigil_rules:
                prob = float(rule.get("probability", 1.0))
                if random.random() >= prob:
                    continue
                container_id = rule.get("container", "")
                if not container_id:
                    continue
                r_min   = int(rule.get("min", 0))
                r_max   = max(int(rule.get("max", 1)), r_min)
                n_picks = random.randint(r_min, r_max)
                for _ in range(n_picks):
                    if 0 <= max_effects <= effects_added:
                        break
                    result = self._pick_from_container(
                        container_id, element, used_containers,
                        cv_budget=effect_budget, block_type=block_type,
                        forbidden_ids=forbidden_ids,
                        incompat_pairs=incompat_pairs,
                        current_effects=ability["effects"])
                    if result:
                        rtype, rdata = result
                        self._apply_content_item(ability, rtype, rdata, effect_budget)
                        if rtype == "effect":
                            effects_added += 1
                            item = self.effects.get(rdata["effect_id"])
                            if item:
                                effect_budget -= cv_content_item(
                                    item, rdata.get("vals", {}), rdata.get("opt_vals", {}))
        else:
            # ── Global content_rules with random target count ─────────────────
            if max_effects < 0:
                target_effects = 999
            else:
                target_effects = random.randint(max(0, min_effects),
                                                max(min_effects, max_effects))
            content_rules = list(self.cfg.get("content_rules", []))
            random.shuffle(content_rules)
            for rule in content_rules:
                if effects_added >= target_effects:
                    break
                prob = float(rule.get("probability", 1.0))
                if random.random() >= prob:
                    continue

                if "container" in rule:
                    result = self._pick_from_container(
                        rule["container"], element, used_containers,
                        cv_budget=effect_budget, block_type=block_type,
                        forbidden_ids=forbidden_ids,
                        incompat_pairs=incompat_pairs,
                        current_effects=ability["effects"])
                    if result:
                        rtype, rdata = result
                        self._apply_content_item(ability, rtype, rdata, effect_budget)
                        if rtype == "effect":
                            effects_added += 1
                            item = self.effects.get(rdata["effect_id"])
                            if item:
                                effect_budget -= cv_content_item(
                                    item, rdata.get("vals", {}), rdata.get("opt_vals", {}))
                elif "effect_id" in rule:
                    eid = rule["effect_id"]
                    if _is_forbidden(eid) or _is_incompatible(eid, ability["effects"]):
                        continue
                    item = self.effects.get(eid)
                    if item:
                        allowed_bt = item.get("conditions", {}).get("allowed_box_types", [])
                        if allowed_bt and block_type and block_type not in allowed_bt:
                            continue
                    solo_key = f"__solo__{eid}"
                    if eid in used_solo.get(solo_key, set()):
                        continue
                    used_solo.setdefault(solo_key, set()).add(eid)
                    eff = self._build_effect(eid, element, effect_budget)
                    if eff:
                        effects_added += 1
                        if item:
                            effect_budget -= cv_content_item(
                                item, eff.get("vals", {}), eff.get("opt_vals", {}))
                        ability["effects"].append(eff)
                elif "cost_id" in rule:
                    cid = rule["cost_id"]
                    cost_item = self.costs.get(cid)
                    if cost_item:
                        allowed_bt = cost_item.get("conditions", {}).get("allowed_box_types", [])
                        if allowed_bt and block_type and block_type not in allowed_bt:
                            continue
                    solo_key = f"__solo_cost__{cid}"
                    if cid in used_solo.get(solo_key, set()):
                        continue
                    used_solo.setdefault(solo_key, set()).add(cid)
                    cost = self._build_cost(cid, element)
                    if cost:
                        ability["costs"].append(cost)

        # ── Required effects (ensure at least one appears) ────────────────────
        current_eids = {e["effect_id"] for e in ability["effects"]}
        for req_id in required_ids:
            if req_id in current_eids:
                continue  # already present
            if _is_incompatible(req_id, ability["effects"]):
                continue  # would conflict – skip
            req_item = self.effects.get(req_id)
            if not req_item:
                continue
            eff = self._build_effect(req_id, element, effect_budget)
            if eff:
                ability["effects"].append(eff)
                effects_added += 1
                effect_budget -= cv_content_item(
                    req_item, eff.get("vals", {}), eff.get("opt_vals", {}))

        # ── Choose N ──────────────────────────────────────────────────────────
        choose_chance = float(self.cfg.get("choose_n_chance", 0.10))
        n_eff = len(ability["effects"])
        if n_eff >= 2 and random.random() < choose_chance:
            ability["choose_n"]      = random.randint(1, n_eff - 1)
            ability["choose_repeat"] = random.random() < 0.3

        return ability

    # ── Effect picking ────────────────────────────────────────────────────────

    def _pick_from_container(self, container_id: str, element: str,
                              used: dict, cv_budget: float, block_type: str = "",
                              forbidden_ids: set = None,
                              incompat_pairs: list = None,
                              current_effects: list = None):
        """
        Pick one item from a container.
        Returns (type_str, data_dict) or None.
        type_str: "effect" | "cost"
        """
        forbidden_ids    = forbidden_ids or set()
        incompat_pairs   = incompat_pairs or []
        current_effects  = current_effects or []
        current_eids     = {e["effect_id"] for e in current_effects}

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
                # Forbidden / incompatible checks (effects only)
                if type_str == "effect":
                    if iid in forbidden_ids:
                        continue
                    incompatible = any(
                        iid in pair and current_eids & (pair - {iid})
                        for pair in incompat_pairs
                    )
                    if incompatible:
                        continue
                item = lookup[iid]
                # Filter by allowed_box_types (empty list = all allowed)
                allowed_bt = item.get("conditions", {}).get("allowed_box_types", [])
                if allowed_bt and block_type and block_type not in allowed_bt:
                    continue
                candidates.append((type_str, iid, item))

        if not candidates:
            return None

        # Weight by rarity × element_weight.
        # Items with element_weight == 0 for this element are element-exclusive
        # to other elements → exclude them entirely. Only fall back to unfiltered
        # set if every single candidate is element-exclusive (shouldn't happen in
        # practice, but avoids empty-pool crashes).
        weights = []
        for _, iid, item in candidates:
            rarity   = float(item.get("rarity", 10))
            el_w_map = item.get("element_weights", {})
            el_w     = float(el_w_map.get(element, 10)) if el_w_map else 10.0
            weights.append(math.sqrt(rarity) * (max(el_w, 0) / 10.0))

        # Filter out zero-weight (element-forbidden) items
        pool = [(c, w) for c, w in zip(candidates, weights) if w > 0]
        if not pool:
            pool = list(zip(candidates, [1.0] * len(candidates)))  # all equal fallback

        pool_cands, pool_wts = zip(*pool)
        chosen = random.choices(list(pool_cands), weights=list(pool_wts))[0]

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

        # Calculate base CV so far (item constant + selected options)
        base_cv = float(item.get("cv", item.get("cv1", 0.0)))
        for opt_key, sel in opt_vals.items():
            stat = item.get("options", {}).get(opt_key, {}).get("per_choice", {}).get(sel, {})
            base_cv += float(stat.get("cv", stat.get("cv1", 0.0)))

        remaining = cv_budget - base_cv

        # Pick variable values within remaining CV budget
        vals = self._pick_variable_values(item, remaining)

        return {"effect_id": effect_id, "vals": vals, "opt_vals": opt_vals}

    def _build_cost(self, cost_id: str, element: str) -> dict:
        item = self.costs.get(cost_id)
        if not item:
            return None
        vals = {}

        if cost_id == "Mana":
            # Restrict mana choices to Generic, Meta, or the card's own element.
            # Then record the chosen type in vals["element"] so the renderer
            # can draw the correct symbol/color for each mana pip.
            opt_vals = {}
            allowed = {"Generic", "Meta", element}
            for opt_key, opt in item.get("options", {}).items():
                avail = [c for c in opt.get("choices", []) if c in allowed]
                if not avail:
                    avail = list(opt.get("choices", []))
                pc = opt.get("per_choice", {})
                weights = [math.sqrt(float(pc.get(c, {}).get("rarity", 10)))
                           for c in avail]
                total_w = sum(weights)
                if total_w <= 0:
                    chosen_opt = random.choice(avail)
                else:
                    chosen_opt = random.choices(avail, weights=weights)[0]
                opt_vals[opt_key] = chosen_opt
            # Drive the renderer: vals["element"] = the chosen mana type
            vals["element"] = opt_vals.get("0", element)
        else:
            # Generic cost: pass card element through variable if the item uses it
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
                r  = float(stat.get("rarity", 10))
                ew = stat.get("conditions", {}).get("element_weights", {})
                el_w = float(ew.get(element, 10)) if ew else 10.0
                weights.append(math.sqrt(r) * (max(el_w, 0) / 10.0))

            # Exclude choices that are element-forbidden (weight == 0)
            pool = [(c, w) for c, w in zip(avail, weights) if w > 0]
            if not pool:
                pool = [(c, 1.0) for c in avail]  # fallback: all equal
            pool_c, pool_w = zip(*pool)
            opt_vals[opt_key] = random.choices(list(pool_c), weights=list(pool_w))[0]
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
            # Default range 0–10 if not specified
            vmin = int(float(cond.get("var_min", 0)))
            vmax = int(float(cond.get("var_max", 10)))

            x_max = max_x_for_budget(stat, share)
            x_max = min(x_max, vmax)
            x_min = max(vmin, 0)

            if x_min > x_max:
                x = x_min
            else:
                x = random.randint(int(x_min), int(x_max))

            vals[var_name] = int(x)

        return vals
