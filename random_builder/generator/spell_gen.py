"""
random_builder/generator/spell_gen.py – Spell & Prowess card generation.

Produces effect_groups (target_type + primary + modifiers) instead of flat
effects lists.  Supports choose-Y-of-X and optional sub-sigils.
"""

import math
import random

from random_builder.cv_calc import (
    cv_content_item, cv_ability, cv_card, cv_effect_group,
    complexity_card,
)
from .base import BaseGenerator, make_card_name


class SpellGenerator(BaseGenerator):
    """Generates Spell and Prowess cards with blocks/sigils."""

    def generate_one(self) -> dict:
        is_prowess  = (self.profile_name == "Prowess")
        elements    = [] if is_prowess else self.pick_elements()
        element     = elements[0] if elements else ""   # primary element
        block_types = self._pick_blocks()

        used_containers: dict = {}
        blocks = []
        min_grp = max(1, int(self.cfg.get("min_groups", 1)))

        # Card-wide id-condition scope: shared across every ability/sigil
        # of this card. Reads 'card_id_conditions' from content items.
        card_scope = self.push_id_scope(key="card_id_conditions")
        sigil_min = float(self.cfg.get("cv_per_sigil_min", 0.0))
        try:
            for btype in block_types:
                ability = None
                best = None
                best_cv = float("-inf")
                for _ in range(8):
                    used_solo: dict = {}
                    ab = self._build_ability(btype, element,
                                             used_containers, used_solo, elements)
                    ok_groups = len(ab.get("effect_groups", [])) >= min_grp
                    ab_cv = cv_ability(ab, self.effects, self.costs,
                                       triggers_lookup=self.triggers)
                    if ok_groups and ab_cv >= sigil_min:
                        ability = ab
                        break
                    # Keep the best candidate we've seen as a fallback
                    if ok_groups and ab_cv > best_cv:
                        best, best_cv = ab, ab_cv
                if ability is None:
                    ability = best if best is not None else ab
                blocks.append({"type": btype, "abilities": [ability]})
        finally:
            self.pop_id_scope()

        card = {
            "name": make_card_name(element or "Prowess"),
            "card_type": self.card_type_output,
            "artwork": "",
            "blocks": blocks,
        }
        if elements:
            card["elements"] = elements

        card["_cv"] = round(cv_card(card, self.box_config,
                                    self.effects, self.costs,
                                    triggers_lookup=self.triggers), 3)
        card["_complexity"] = round(complexity_card(card, self.effects,
                                                    self.costs), 3)
        return card

    # ── Blocks ───────────────────────────────────────────────────────────────

    def _pick_blocks(self) -> list:
        rules = self.cfg.get("block_rules", [])
        min_blks = max(1, int(self.cfg.get("min_blocks", 1)))

        for _attempt in range(10):
            chosen = []
            for rule in rules:
                bt = rule.get("block_type", "")
                if not bt:
                    continue
                prob = float(rule.get("probability", 0.5))
                if random.random() < prob:
                    chosen.append(bt)
            if not chosen:
                chosen = ["Play"]
            chosen = chosen[:4]
            chosen = self._remove_incompatible(chosen)
            if len(chosen) >= min_blks:
                break
        return chosen

    def _remove_incompatible(self, block_types: list) -> list:
        result = []
        for bt in block_types:
            incompatible = set(
                self.box_config.get(bt, {}).get("incompatible_with", []))
            if not incompatible.intersection(result):
                result.append(bt)
        return result if result else ["Play"]

    def _sub_sigil_group_chance(self, target_type: str,
                                is_manual_trigger: bool) -> float:
        """Return the chance for a per-group sub-sigil based on target type
        and trigger kind. Config keys:
          - sub_sigil_group_chance (default 0.15): baseline for all groups
          - sub_sigil_target_enemy_manual_chance (default 0.80): Target Enemy + Manual Trigger
          - sub_sigil_target_ally_chance (default 0.10): Target Ally groups
        """
        if target_type == "Target Enemy" and is_manual_trigger:
            return float(self.cfg.get("sub_sigil_target_enemy_manual_chance", 0.80))
        if target_type == "Target Ally":
            return float(self.cfg.get("sub_sigil_target_ally_chance", 0.10))
        return float(self.cfg.get("sub_sigil_group_chance", 0.15))

    # ── Ability ──────────────────────────────────────────────────────────────

    def _build_ability(self, block_type: str, element: str,
                       used_containers: dict, used_solo: dict,
                       elements: list = None) -> dict:
        is_play = (block_type == "Play")

        # Sigil-level id-condition scope: resets every ability. Reads the
        # standard 'id_conditions' field. Card-level scope (pushed in
        # generate_one) stays active underneath.
        self.push_id_scope(key="id_conditions")
        try:
            return self._build_ability_inner(
                block_type, element, used_containers, used_solo,
                elements, is_play)
        finally:
            self.pop_id_scope()

    def _build_ability_inner(self, block_type: str, element: str,
                             used_containers: dict, used_solo: dict,
                             elements: list, is_play: bool) -> dict:
        # ── Trigger: ALL abilities must have one ─────────────────────────────
        # Manual triggers (symbol-only, no text): Manual_Trigger / _Half / _Third
        # - Play blocks: pick ONE of the manual triggers (weighted by config)
        # - Non-Play blocks: with `manual_trigger_chance` pick a manual one,
        #   else pick a text trigger (respecting profile + block filters).
        MANUAL_IDS = ("Manual_Trigger", "Manual_Trigger_Half",
                      "Manual_Trigger_Third")

        def _pick_manual_trigger() -> str:
            """Weighted pick among the three manual-trigger variants."""
            weights = {
                "Manual_Trigger":        float(self.cfg.get("manual_full_weight",  10.0)),
                "Manual_Trigger_Half":   float(self.cfg.get("manual_half_weight",   2.0)),
                "Manual_Trigger_Third":  float(self.cfg.get("manual_third_weight",  1.0)),
            }
            # Keep only those present in triggers and allowed in this block
            pool = []
            wts  = []
            for mid in MANUAL_IDS:
                titem = self.triggers.get(mid)
                if not titem:
                    continue
                if not self.passes_block_filters(titem, block_type):
                    continue
                pool.append(mid)
                wts.append(max(0.0, weights.get(mid, 0.0)))
            if not pool or sum(wts) <= 0:
                return "Manual_Trigger"
            return random.choices(pool, weights=wts, k=1)[0]

        trigger_id = _pick_manual_trigger()
        trigger_vals, trigger_opt_vals = {}, {}

        if not is_play:
            manual_chance = float(self.cfg.get("manual_trigger_chance", 0.6))
            if random.random() >= manual_chance:
                allowed_triggers = {
                    k: v for k, v in self.triggers.items()
                    if k not in MANUAL_IDS
                    and self.allowed_for_profile(v)
                    and self.passes_block_filters(v, block_type)
                    and self.passes_all_id_conditions(v)
                }
                if allowed_triggers:
                    tid   = random.choice(list(allowed_triggers.keys()))
                    titem = allowed_triggers[tid]
                    trigger_id       = tid
                    trigger_opt_vals = self.pick_options(titem, element)
                    trigger_vals     = self.pick_variable_values(titem, cv_budget=2.0)
                    self.register_id_used_all(titem)
                # else: fallback to the manual trigger already picked above

        condition_id, condition_vals, condition_opt_vals = None, {}, {}
        cond_chance = float(self.cfg.get("condition_chance", 0.15))
        if self.conditions and random.random() < cond_chance:
            allowed_conditions = {k: v for k, v in self.conditions.items()
                                  if self.allowed_for_profile(v)
                                  and self.passes_block_filters(v, block_type)
                                  and self.passes_all_id_conditions(v)}
            if allowed_conditions:
                cid = random.choice(list(allowed_conditions.keys()))
                citem = allowed_conditions[cid]
                condition_id = cid
                condition_opt_vals = self.pick_options(citem, element)
                condition_vals = self.pick_variable_values(citem, cv_budget=1.0)
                self.register_id_used_all(citem)

        ability = {
            "condition_id":       condition_id,
            "condition_vals":     condition_vals,
            "condition_opt_vals": condition_opt_vals,
            "trigger_id":         trigger_id,
            "trigger_vals":       trigger_vals,
            "trigger_opt_vals":   trigger_opt_vals,
            "ability_type":       "Play" if trigger_id in MANUAL_IDS else "Trigger",
            "costs":              [],
            "effect_groups":      [],
            "choose_n":           None,
            "choose_total":       None,
            "choose_repeat":      False,
            "sub_sigil":          None,
        }

        # ── Costs (only on Play boxes) ───────────────────────────────────────
        if is_play:
            mana_chance = float(self.cfg.get("mana_chance", 0.95))
            mana_main = int(self.cfg.get("mana_main_count", 2))
            mana_max_count = int(self.cfg.get("mana_max_count", 6))
            # Check if Mana cost is allowed in this block type
            mana_item = self.costs.get("Mana", {})
            mana_allowed = self.passes_block_filters(mana_item, block_type) if mana_item else False
            if mana_allowed and random.random() < mana_chance and "Mana" in self.costs:
                hi = max(mana_max_count, mana_main)
                counts = list(range(1, hi + 1))
                wts = [math.exp(-0.7 * (n - mana_main) ** 2) for n in counts]
                count = random.choices(counts, weights=wts)[0]
                for _ in range(count):
                    cost = self.build_cost("Mana", element)
                    if cost:
                        ability["costs"].append(cost)

            max_other = int(self.cfg.get("max_other_costs", 1))
            other_added = 0
            for rule in self.cfg.get("cost_rules", []):
                if other_added >= max_other:
                    break
                cost_id = rule.get("cost_id", "")
                if not cost_id or cost_id == "Mana":
                    continue
                # Check if this cost is allowed in this block type
                cost_item = self.costs.get(cost_id, {})
                if cost_item and not self.passes_block_filters(cost_item, block_type):
                    continue
                prob = float(rule.get("probability", 1.0))
                if random.random() >= prob:
                    continue
                cost = self.build_cost(cost_id, element)
                if cost:
                    ability["costs"].append(cost)
                    other_added += 1

        # ── CV budget ────────────────────────────────────────────────────────
        cv_per_box = float(self.cfg.get("cv_per_box_max", 3.0))
        cost_cv = 0.0
        for c in ability["costs"]:
            if c["cost_id"] == "Mana" and self.generic_mana_cv is not None:
                cost_cv += self.generic_mana_cv
            elif c["cost_id"] in self.costs:
                cost_cv += cv_content_item(self.costs[c["cost_id"]],
                                           c.get("vals", {}), c.get("opt_vals", {}))
        effect_budget = cv_per_box + cost_cv

        # Multi-element: ensure all elements have at least one mana cost
        if elements and len(elements) > 1 and is_play and "Mana" in self.costs:
            covered_elements = {c.get("vals", {}).get("element", "") for c in ability["costs"] if c.get("cost_id") == "Mana"}
            for elem in elements:
                if elem not in covered_elements:
                    ability["costs"].append({"cost_id": "Mana", "vals": {"element": elem}, "opt_vals": {"0": elem}})
                    covered_elements.add(elem)
            # Also ensure total mana count >= number of elements
            mana_count = sum(1 for c in ability["costs"] if c.get("cost_id") == "Mana")
            while mana_count < len(elements):
                elem = random.choice(elements)
                ability["costs"].append({"cost_id": "Mana", "vals": {"element": elem}, "opt_vals": {"0": elem}})
                mana_count += 1

        # ── Constraint helpers ───────────────────────────────────────────────
        sig_constraints = self.cfg.get("sigil_constraints", {})
        bt_constraints = sig_constraints.get(block_type, {})
        forbidden_ids = set(bt_constraints.get("forbidden", []))
        required_ids = list(bt_constraints.get("required", []))

        # required_groups: for each group (playlist) pick exactly one effect
        for grp in bt_constraints.get("required_groups", []):
            pool = [e for e in grp if e not in forbidden_ids]
            if pool:
                required_ids.append(random.choice(pool))
        # backward-compat: old required_one_of field
        rone_pool = [e for e in bt_constraints.get("required_one_of", [])
                     if e not in forbidden_ids]
        if rone_pool:
            required_ids.append(random.choice(rone_pool))

        incompat_pairs = [set(p) for p in self.cfg.get("incompatible_pairs", [])]

        # Non-repeatable target types: only one group allowed per type
        NON_REPEATABLE = {"Target Enemy", "Target Ally"}

        # Track all effect IDs used across groups for no-repeat / incompatibility
        used_eids: set = set()
        # Track which containers have already been used on this sigil (CONSTRAINT)
        used_containers: set = set()
        # Track which target types already have a group (for deduplication)
        # Only populated for NON_REPEATABLE types
        used_target_types: set  = set()
        groups_by_type:    dict = {}  # target_type → group dict (only for NON_REPEATABLE)

        def _update_used(group: dict):
            effs = group.get("effects") or group.get("primaries")
            if effs is None:
                p = group.get("primary", {})
                effs = [p] if p.get("effect_id") else []
            for e in effs:
                if e.get("effect_id"):
                    used_eids.add(e["effect_id"])
            for m in group.get("modifiers", []):
                if m.get("effect_id"):
                    used_eids.add(m["effect_id"])

        def _get_container_for_effects(effect_ids: set) -> set:
            """Return container IDs that contain any of the given effect IDs."""
            result = set()
            for cid, container in self.containers.items():
                if any(eid in container.get("effects", []) for eid in effect_ids):
                    result.add(cid)
            return result

        def _is_incompatible(eid: str) -> bool:
            return any(eid in pair and used_eids & (pair - {eid})
                       for pair in incompat_pairs)

        # ── Effect Groups ────────────────────────────────────────────────────
        min_groups = max(1, int(self.cfg.get("min_groups", 1)))
        max_groups_cfg = int(self.cfg.get("max_groups", 3))
        target_groups = random.randint(min_groups,
                                       max(min_groups, max_groups_cfg))
        groups_added = 0

        sigil_rules = self.cfg.get("sigil_rules", {}).get(block_type, [])

        if sigil_rules:
            for rule in sigil_rules:
                prob = float(rule.get("probability", 1.0))
                if random.random() >= prob:
                    continue
                r_min = int(rule.get("min", 1))
                r_max = max(int(rule.get("max", 1)), r_min)
                n_picks = random.randint(r_min, r_max)
                container_id = rule.get("container", "")
                effects_pool = rule.get("effects", [])

                # CONSTRAINT: Skip if this container has already been used on this sigil
                if container_id and container_id in used_containers:
                    continue

                # Resolve source effect IDs
                if effects_pool:
                    source_eids = effects_pool
                elif container_id:
                    container = self.containers.get(container_id, {})
                    source_eids = container.get("effects", [])
                else:
                    source_eids = None

                for _ in range(n_picks):
                    if groups_added >= target_groups:
                        break
                    target_type = self.pick_target_type(exclude=used_target_types)
                    if (target_type in NON_REPEATABLE
                            and target_type in groups_by_type
                            and len(groups_by_type[target_type].get("primaries", [])) < 3):
                        # Add another primary to existing non-repeatable group (up to 3)
                        existing_grp = groups_by_type[target_type]
                        new_p = self.add_primary_to_group(
                            existing_grp, element, effect_budget, block_type,
                            forbidden_ids | used_eids, source_eids)
                        if new_p:
                            used_eids.add(new_p["effect_id"])
                            new_p_item = self.effects.get(new_p["effect_id"])
                            if new_p_item:
                                effect_budget -= cv_content_item(
                                    new_p_item, new_p.get("vals", {}),
                                    new_p.get("opt_vals", {}))
                            groups_added += 1
                    else:
                        group = self.build_effect_group(
                            target_type, element, effect_budget, block_type,
                            forbidden_ids | used_eids, source_eids)
                        if group:
                            if target_type in NON_REPEATABLE:
                                used_target_types.add(target_type)
                                groups_by_type[target_type] = group
                            ability["effect_groups"].append(group)
                            _update_used(group)
                            # Track container for this group
                            group_eids = {p.get("effect_id") for p in group.get("primaries", [])}
                            used_containers.update(_get_container_for_effects(group_eids))
                            groups_added += 1
                            effect_budget -= cv_effect_group(group, self.effects)
        else:
            content_rules = list(self.cfg.get("content_rules", []))
            # Build weighted pool: probability field used as weight
            rule_pool = [(r, max(0.0, float(r.get("probability", 1.0)))) for r in content_rules
                         if "container" in r or "effect_id" in r]
            rule_pool = [(r, w) for r, w in rule_pool if w > 0]

            attempts = 0
            while groups_added < target_groups and rule_pool and attempts < 30:
                attempts += 1
                rule_weights = [w for _, w in rule_pool]
                rule = random.choices([r for r, _ in rule_pool], weights=rule_weights)[0]

                if "container" in rule:
                    # CONSTRAINT: Skip if this container has already been used on this sigil
                    if rule["container"] in used_containers:
                        continue
                    container = self.containers.get(rule["container"], {})
                    source_eids = container.get("effects", [])
                elif "effect_id" in rule:
                    eid = rule["effect_id"]
                    if eid in forbidden_ids or eid in used_eids:
                        continue
                    if _is_incompatible(eid):
                        continue
                    source_eids = [eid]
                else:
                    continue

                target_type = self.pick_target_type(exclude=used_target_types)
                if (target_type in NON_REPEATABLE
                        and target_type in groups_by_type
                        and len(groups_by_type[target_type].get("primaries", [])) < 3):
                    existing_grp = groups_by_type[target_type]
                    new_p = self.add_primary_to_group(
                        existing_grp, element, effect_budget, block_type,
                        forbidden_ids | used_eids, source_eids)
                    if new_p:
                        used_eids.add(new_p["effect_id"])
                        new_p_item = self.effects.get(new_p["effect_id"])
                        if new_p_item:
                            effect_budget -= cv_content_item(
                                new_p_item, new_p.get("vals", {}),
                                new_p.get("opt_vals", {}))
                        groups_added += 1
                else:
                    group = self.build_effect_group(
                        target_type, element, effect_budget, block_type,
                        forbidden_ids | used_eids, source_eids)
                    if group:
                        if target_type in NON_REPEATABLE:
                            used_target_types.add(target_type)
                            groups_by_type[target_type] = group
                        ability["effect_groups"].append(group)
                        _update_used(group)
                        # Track container for this group
                        group_eids = {p.get("effect_id") for p in group.get("primaries", [])}
                        used_containers.update(_get_container_for_effects(group_eids))
                        groups_added += 1
                        effect_budget -= cv_effect_group(group, self.effects)

        # ── Required effects (merged into existing group or standalone) ─────────
        for req_id in required_ids:
            if req_id in used_eids:
                continue
            if _is_incompatible(req_id):
                continue
            req_item = self.effects.get(req_id)
            if not req_item:
                continue
            eff = self.build_effect(req_id, element, effect_budget)
            if not eff:
                continue
            ptypes = req_item.get("primary_types", ["Non Targeting"])
            target = ptypes[0] if ptypes else "Non Targeting"
            eff_cv = cv_content_item(req_item, eff.get("vals", {}),
                                     eff.get("opt_vals", {}))
            if target in groups_by_type:
                # Merge into existing group for this target type
                groups_by_type[target].setdefault("primaries", []).append(eff)
            else:
                group = {"target_type": target, "primaries": [eff], "modifiers": []}
                ability["effect_groups"].append(group)
                used_target_types.add(target)
                groups_by_type[target] = group
                groups_added += 1
            used_eids.add(req_id)
            effect_budget -= eff_cv

        # ── Guarantee at least 1 effect group ─────────────────────────────────────
        if not ability["effect_groups"]:
            for _tt in ["Non Targeting", "Target Enemy", "Target Ally", None]:
                _g = self.build_effect_group(
                    _tt if _tt else "Non Targeting",
                    element, effect_budget, block_type,
                    forbidden_ids, None)
                if _g:
                    ability["effect_groups"].append(_g)
                    break

        # ── Choose N of X ────────────────────────────────────────────────────
        n_groups = len(ability["effect_groups"])
        if n_groups >= 2 and random.random() < 0.40:
            ability["choose_total"] = n_groups
            ability["choose_n"] = random.randint(1, n_groups - 1)
            ability["choose_repeat"] = random.random() < 0.25

        # ── Sub-Sigils (Option A: per effect group) ──────────────────────────
        # Attach sub-sigils to individual effect groups (Target Enemy/Ally/Non Targeting)
        sub_budget_frac = float(self.cfg.get("sub_sigil_cv_budget_frac", 0.3))
        is_manual_trigger = trigger_id in MANUAL_IDS

        for group in ability["effect_groups"]:
            target_type = group.get("target_type", "Non Targeting")
            group_sub_chance = self._sub_sigil_group_chance(target_type, is_manual_trigger)

            # Build sub-sigil for this group if roll succeeds
            if random.random() < group_sub_chance:
                sub_budget = max(0.5, effect_budget * sub_budget_frac)
                sub = self.build_sub_sigil(
                    element, sub_budget, block_type,
                    target_type=target_type  # Sub-sigil matches group's target type
                )
                if sub:
                    group["sub_sigil"] = sub

        # ── Sub-Sigil (Option B/C: global overload) ─────────────────────────
        # Global sub-sigil that can have its own target type (overload effect)
        sub_global_chance = float(self.cfg.get("sub_sigil_global_chance", 0.20))
        if ability["effect_groups"] and random.random() < sub_global_chance:
            sub_budget = max(0.5, effect_budget * sub_budget_frac)
            # Global sub-sigil can be any target type (Non Targeting, Target Enemy, Target Ally, Target Neutral)
            global_sub = self.build_sub_sigil(
                element, sub_budget, block_type,
                restrict_to_targets={"Non Targeting", "Target Enemy", "Target Ally", "Target Neutral"}
            )
            if global_sub:
                ability["sub_sigil_global"] = global_sub

        return ability
