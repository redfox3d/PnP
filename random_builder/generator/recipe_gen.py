"""
random_builder/generator/recipe_gen.py – Recipe card generation.

Recipe logic:
  1. Pick a total ingredient count (weighted toward configured average).
  2. Pick materials with replacement → allows duplicates (2x Gold, etc.).
  3. Each *unique* material contributes its effect once.
  4. Variable values (X, etc.) are solved so that the card's net CV
     lands inside the configured target window.  More copies of a
     material → larger share of the effect budget for that effect.

     CV_recipe = Σ(effect_cv_i) − Σ(ingredient_cv)

  Complexity = 1.05^n_total × (Σ effect_complexity + Σ ingredient_complexity)
"""

import math
import random
from collections import Counter

from random_builder.cv_calc import cv_stat, cv_content_item, complexity_content_item
from .base import BaseGenerator


class RecipeGenerator(BaseGenerator):
    """Generates Recipe cards (Potions / Phials / Tinctures)."""

    _RECIPE_NAMES = {
        "Potions":   ["Healing Brew", "Restoration Draft", "Soothing Elixir",
                      "Cleansing Tonic", "Fortifying Flask", "Calm Draught"],
        "Phials":    ["Venom Phial", "Burning Flask", "Corrosion Vial",
                      "Blight Essence", "Toxic Serum", "Wrath Tincture"],
        "Tinctures": ["Strange Tincture", "Exotic Blend", "Arcane Mixture"],
    }

    def generate_one(self) -> dict:
        recipe_type = self.pick_recipe_type()
        ingredient_cv = int(self.cfg.get("ingredient_cv", 4))

        # ── 1. Pick materials (with duplicates) ────────────────────────────
        from card_builder.materials import (
            load_central_materials, load_material_effects,
        )
        all_mats = load_central_materials()
        mat_effects = load_material_effects()

        # Only materials that have an effect assigned are eligible
        eligible = [m for m in all_mats
                    if m in mat_effects and mat_effects[m].get("effect_id")]
        if not eligible:
            return None

        n_total = self._pick_ingredient_count()
        # Pick with replacement (duplicates allowed)
        chosen = random.choices(eligible, k=n_total)
        counts = Counter(chosen)  # {material: count}

        # Build grouped ingredient list
        ingredients = [
            {"material": mat, "cv": ingredient_cv, "count": cnt}
            for mat, cnt in counts.items()
        ]

        # Ingredients are COSTS  (total = Σ count_i × cv)
        ingredients_cost = sum(ing["cv"] * ing["count"] for ing in ingredients)

        # ── 2. Desired net CV (random inside the target window) ────────────
        cv_min = float(self.cfg.get("cv_card_min", 0.0))
        cv_max = float(self.cfg.get("cv_target", 3.0))
        desired_net = random.uniform(cv_min, cv_max)

        # Effects must produce: desired_net + ingredients_cost
        target_effects_cv = desired_net + ingredients_cost

        # ── 3. Build effects from material definitions ─────────────────────
        effects = []
        use_parts = []
        effects_total_cv = 0.0

        # Collect (material, count, effect_id, item) for unique materials
        mat_effect_items = []
        for ing in ingredients:
            mat = ing["material"]
            me = mat_effects[mat]
            eid = me["effect_id"]
            item = self.effects.get(eid)
            if item:
                mat_effect_items.append((mat, ing["count"], eid, item, me))

        if not mat_effect_items:
            return None

        # Distribute effect budget proportional to ingredient count
        for mat, cnt, eid, item, me in mat_effect_items:
            cv_mult = float(me.get("cv_multiplier", 1.0))
            share = cnt / n_total          # fraction of total ingredients
            per_effect_target = target_effects_cv * share

            # Solve for raw CV, then multiply:
            #   actual_cv = raw_cv * cv_mult  →  raw_cv = target / cv_mult
            raw_target = per_effect_target / cv_mult if cv_mult else per_effect_target
            opt_vals = self.pick_options(item, recipe_type)

            vals = self._solve_vals_for_target(item, raw_target, opt_vals)

            eff = {"effect_id": eid, "vals": vals, "opt_vals": opt_vals}
            effects.append(eff)

            raw_cv = cv_content_item(item, vals, opt_vals)
            effects_total_cv += raw_cv * cv_mult

            # Build use-text
            ct = item.get("content_text", "")
            for k, v in vals.items():
                ct = ct.replace(f"{{{k}}}", str(v))
            if ct:
                use_parts.append(ct)

        # ── 4. Assemble card ───────────────────────────────────────────────
        name = random.choice(self._RECIPE_NAMES.get(recipe_type, ["Recipe"]))

        card = {
            "name":        name,
            "card_type":   recipe_type,
            "recipe_type": recipe_type,
            "artwork":     "",
            "ingredients": ingredients,
            "effects":     effects,
            "use_text":    "\n".join(use_parts),
            "trigger_id":  "Manual_Trigger",   # using a potion always costs an action
        }

        # CV = effects gained − ingredients spent
        card["_cv"] = round(effects_total_cv - ingredients_cost, 3)

        # Complexity = 1.05^n × (Σ effect_complexity + Σ ingredient_complexity)
        eff_cmplx = sum(
            complexity_content_item(self.effects[e["effect_id"]])
            for e in effects if e["effect_id"] in self.effects
        )
        ing_cmplx = sum(
            float(mat_effects.get(ing["material"], {}).get("complexity", 0))
            * ing["count"]
            for ing in ingredients
        )
        card["_complexity"] = round(
            (1.05 ** n_total) * (eff_cmplx + ing_cmplx), 3
        )
        return card

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _pick_ingredient_count(self) -> int:
        """Pick total ingredient count using Gaussian weights
        centred on the configured average."""
        ing_max = max(1, int(self.cfg.get("ingredient_max", 6)))
        ing_avg = float(self.cfg.get("ingredient_avg", 2.4))
        counts = list(range(1, ing_max + 1))
        weights = [math.exp(-0.7 * (n - ing_avg) ** 2) for n in counts]
        return random.choices(counts, weights=weights)[0]

    def _solve_vals_for_target(self, item: dict, target_cv: float,
                               opt_vals: dict) -> dict:
        """Pick variable values so the effect's total CV ~ target_cv."""
        base_cv = float(item.get("cv", item.get("cv1", 0.0)))

        opt_cv = 0.0
        for opt_key, opt in item.get("options", {}).items():
            selected = opt_vals.get(opt_key, "")
            stat = opt.get("per_choice", {}).get(selected, {})
            if stat:
                opt_cv += float(stat.get("cv", stat.get("cv1", 0.0)))

        var_budget = target_cv - base_cv - opt_cv

        variables = item.get("variables", {})
        if not variables:
            return {}

        per_var = var_budget / len(variables)

        from random_builder.dice_models import load_dice_config
        dice_cfg  = load_dice_config()
        dice_list = dice_cfg.get("dice", [])
        can_chance = float(dice_cfg.get("dice_can_chance", 0.5))

        vals = {}
        for var_name, stat in variables.items():
            dice_only    = stat.get("dice_only", False)
            dice_allowed = stat.get("dice_allowed", False)
            use_dice     = dice_only or (dice_allowed and random.random() < can_chance)
            if use_dice and dice_list:
                vals[var_name] = self._pick_dice_for_cv(stat, per_var, dice_list)
            else:
                cond = stat.get("conditions", {})
                vmin = max(1, int(float(cond.get("var_min", 1))))
                vmax = int(float(cond.get("var_max", 10)))
                x = self._find_x_for_cv(stat, per_var, vmin, vmax)
                vals[var_name] = max(1, x)
        return vals

    @staticmethod
    def _find_x_for_cv(stat: dict, target_var_cv: float,
                       vmin: int, vmax: int) -> int:
        """Binary-search for the integer X in [vmin, vmax]
        whose cv contribution is closest to target_var_cv."""
        c1 = float(stat.get("cv1", 0.0))
        c2 = float(stat.get("cv2", 0.0))
        c3 = float(stat.get("cv3", 0.0))

        def _cv(x):
            return c1 * x + c2 * x * x + c3 * x * x * x

        if c1 == 0 and c2 == 0 and c3 == 0:
            return random.randint(vmin, vmax)

        if _cv(vmin) >= target_var_cv:
            return vmin
        if _cv(vmax) <= target_var_cv:
            return vmax

        lo, hi = float(vmin), float(vmax)
        for _ in range(60):
            mid = (lo + hi) / 2.0
            if _cv(mid) < target_var_cv:
                lo = mid
            else:
                hi = mid

        x_float = (lo + hi) / 2.0
        x_lo = max(vmin, int(x_float))
        x_hi = min(vmax, x_lo + 1)
        if abs(_cv(x_lo) - target_var_cv) <= abs(_cv(x_hi) - target_var_cv):
            return x_lo
        return x_hi
