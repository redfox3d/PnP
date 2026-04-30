"""
random_builder/generator/base.py – Shared generation infrastructure.

Contains:
  - CardGenerator: public façade that delegates to SpellGenerator / RecipeGenerator
  - Common helpers: name generation, variable picking, option selection,
    effect/cost building, container picking, profile filtering
"""

import math
import random

from random_builder.cv_calc import (
    cv_content_item, cv_ability, cv_card, cv_effect_group,
    complexity_content_item, complexity_card,
    max_x_for_budget,
)
from card_builder.constants import ELEMENTS, RECIPE_TYPES


# ── Card name generation ─────────────────────────────────────────────────────

_NAME_PREFIXES = {
    "Fire":    ["Blazing", "Inferno", "Smoldering", "Ashen", "Pyroclastic", "Embered"],
    "Metal":   ["Ironclad", "Forged", "Shattered", "Tempered", "Rusted", "Gilded"],
    "Ice":     ["Frozen", "Glacial", "Bitter", "Crystalline", "Frostbound", "Shivering"],
    "Nature":  ["Overgrown", "Withered", "Blooming", "Ancient", "Twisted", "Verdant"],
    "Blood":   ["Crimson", "Severed", "Pulsing", "Tainted", "Visceral", "Coagulated"],
    "Quinta":  ["Unraveling", "Fractured", "Hollow", "Echoing", "Null", "Paradox"],
    "Prowess": ["Arcane", "Stalwart", "Keen", "Swift", "Resolute", "Unyielding"],
}

_NAME_NOUNS = [
    "Strike", "Ward", "Surge", "Veil", "Oath", "Pact", "Brand", "Rite",
    "Sigil", "Grasp", "Edict", "Toll", "Shard", "Pulse", "Omen", "Chain",
    "Decree", "Burst", "Vow", "Lash", "Mark", "Curse", "Seal", "Hex",
]


def make_card_name(element: str) -> str:
    prefix = random.choice(_NAME_PREFIXES.get(element, ["Arcane"]))
    noun = random.choice(_NAME_NOUNS)
    return f"{prefix} {noun}"


def list_to_lookup(items: list) -> dict:
    return {item["id"]: item for item in items if "id" in item}


# ── Base generator ───────────────────────────────────────────────────────────

class BaseGenerator:
    """Shared state and helpers for all generators."""

    def __init__(self, content_data: dict, containers: dict,
                 box_config: dict, gen_config: dict):
        self.effects    = list_to_lookup(content_data.get("Effect",    []))
        self.costs      = list_to_lookup(content_data.get("Cost",      []))
        self.conditions = list_to_lookup(content_data.get("Condition", []))
        self.triggers   = list_to_lookup(content_data.get("Trigger",   []))
        self.containers = containers
        self.box_config = box_config
        self.cfg        = gen_config

        self.profile_name      = gen_config.get("profile_name", "Spells")
        self.card_type_output  = gen_config.get("card_type_output", "Spells")
        self.generic_mana_only = gen_config.get("generic_mana_only", False)
        self.generic_mana_cv   = gen_config.get("generic_mana_cv", None)

    # ── Profile filtering ────────────────────────────────────────────────────

    def allowed_for_profile(self, item: dict) -> bool:
        allowed = item.get("allowed_card_types", [])
        return not allowed or self.profile_name in allowed

    def allowed_in_block(self, item: dict, block_type: str) -> bool:
        """Check if item is allowed in the given block type (Play, Excavate, etc.).

        Empty/missing allowed_in_blocks → defaults to True (backward compat).
        """
        allowed_blocks = item.get("allowed_in_blocks", {})
        if not allowed_blocks:
            return True
        return allowed_blocks.get(block_type, True)

    def passes_block_filters(self, item: dict, block_type: str) -> bool:
        """Unified block-type filter combining legacy allowed_box_types (under
        'conditions') and the new allowed_in_blocks field.

        Returns True if the item is allowed in `block_type` (or block_type is
        empty, meaning "no filter applied").
        """
        if not block_type:
            return True
        # Legacy allowed_box_types check (inside "conditions" dict)
        allowed_bt = item.get("conditions", {}).get("allowed_box_types", [])
        if allowed_bt and block_type not in allowed_bt:
            return False
        # New allowed_in_blocks check
        return self.allowed_in_block(item, block_type)

    # ── ID conditions (item-to-item compatibility) ───────────────────────────
    #
    # The generator tracks one or more "id-condition scopes" that filter picks:
    #
    #   sigil scope  – resets at every ability, reads `id_conditions`
    #   card  scope  – spans whole card,        reads `card_id_conditions`
    #
    # `_active_id_scopes` is a list of dicts:
    #   {"used": set, "excluded": set, "key": "id_conditions"|"card_id_conditions"}
    #
    # `passes_all_id_conditions()` checks an item against every active scope,
    # `register_id_used_all()` updates every scope after a successful pick.

    @staticmethod
    def _iter_id_conditions(item: dict, key: str = "id_conditions"):
        """Yield (other_id, mode) tuples from an item's id_conditions list
        under the given key ("id_conditions" or "card_id_conditions")."""
        for entry in item.get("conditions", {}).get(key, []):
            if isinstance(entry, dict):
                other = entry.get("id")
                if other:
                    yield other, entry.get("mode", "required")
            elif isinstance(entry, str) and entry:
                yield entry, "required"

    def _get_id_scopes(self) -> list:
        """Lazy-init + return list of active id-condition scopes."""
        if not hasattr(self, "_active_id_scopes"):
            self._active_id_scopes = []
        return self._active_id_scopes

    def push_id_scope(self, key: str = "id_conditions",
                      used: set = None, excluded: set = None) -> dict:
        """Start a new id-condition scope. Returns the scope dict so the
        caller can reuse the same `used`/`excluded` sets across pushes
        (e.g. card-level scope reused across abilities)."""
        scope = {
            "used":     used if used is not None else set(),
            "excluded": excluded if excluded is not None else set(),
            "key":      key,
        }
        self._get_id_scopes().append(scope)
        return scope

    def pop_id_scope(self) -> None:
        scopes = self._get_id_scopes()
        if scopes:
            scopes.pop()

    def passes_all_id_conditions(self, item: dict) -> bool:
        """Check `item` against every active id-condition scope."""
        iid = item.get("id", "")
        for scope in self._get_id_scopes():
            if iid and iid in scope["excluded"]:
                return False
            for other_id, mode in self._iter_id_conditions(item, scope["key"]):
                if mode == "exclude" and other_id in scope["used"]:
                    return False
        return True

    def register_id_used_all(self, item: dict) -> None:
        """Register `item` in every active scope so later picks see its
        id (as "used") and the ids it excludes (as "excluded")."""
        iid = item.get("id", "")
        for scope in self._get_id_scopes():
            if iid:
                scope["used"].add(iid)
            for other_id, mode in self._iter_id_conditions(item, scope["key"]):
                if mode == "exclude":
                    scope["excluded"].add(other_id)

    def item_subcategory_weight(self, item: dict, sub: str) -> float:
        # B1: Per-element / per-recipe-type hard disable. When the content
        # editor marks a subcategory as off, the item is simply not available
        # in that subcategory.
        if not self.item_enabled_for(item, sub):
            return 0.0
        if self.profile_name == "Recipes":
            w_map = item.get("recipe_type_weights", {})
        else:
            w_map = item.get("element_weights", {})
        return float(w_map.get(sub, 10)) if w_map else 10.0

    def item_enabled_for(self, item: dict, sub: str) -> bool:
        """B1: Whether `item` is enabled for subcategory `sub` (element or
        recipe-type). Default on. A missing entry = True."""
        key = ("recipe_type_enabled" if self.profile_name == "Recipes"
               else "element_enabled")
        flags = item.get(key, {})
        if not isinstance(flags, dict):
            return True
        return bool(flags.get(sub, True))

    # ── Element / recipe type picking ────────────────────────────────────────

    def pick_element(self) -> str:
        mode = self.cfg.get("element_mode", "equal")
        if mode == "equal":
            return random.choice(ELEMENTS)
        weights = [float(self.cfg.get("custom_element_weights", {}).get(el, 10))
                   for el in ELEMENTS]
        total = sum(weights)
        if total <= 0:
            return random.choice(ELEMENTS)
        return random.choices(ELEMENTS, weights=weights)[0]

    def pick_elements(self) -> list:
        """Pick 1-6 unique elements based on element_count_weights config."""
        count_cfg = self.cfg.get("element_count_weights", {"1": 100})
        keys    = [k for k in count_cfg]
        wts     = [float(count_cfg[k]) for k in keys]
        total_w = sum(wts)
        if total_w <= 0:
            n = 1
        else:
            n = int(random.choices(keys, weights=wts)[0])
        n = max(1, min(6, n))

        # Build weighted pool, pick n unique elements
        mode = self.cfg.get("element_mode", "equal")
        if mode == "equal":
            el_weights = {el: 1.0 for el in ELEMENTS}
        else:
            cw = self.cfg.get("custom_element_weights", {})
            el_weights = {el: float(cw.get(el, 10)) for el in ELEMENTS}

        remaining = [(el, w) for el, w in el_weights.items() if w > 0]
        chosen: list = []
        for _ in range(min(n, len(remaining))):
            elems, ws = zip(*remaining)
            el = random.choices(list(elems), weights=list(ws))[0]
            chosen.append(el)
            remaining = [(e, w) for e, w in remaining if e != el]

        return chosen if chosen else [self.pick_element()]

    def pick_recipe_type(self) -> str:
        mode = self.cfg.get("recipe_type_mode", "equal")
        if mode == "equal":
            return random.choice(RECIPE_TYPES)
        weights = [float(self.cfg.get("recipe_type_weights", {}).get(rt, 10))
                   for rt in RECIPE_TYPES]
        total = sum(weights)
        if total <= 0:
            return random.choice(RECIPE_TYPES)
        return random.choices(RECIPE_TYPES, weights=weights)[0]

    # ── Effect / cost building ───────────────────────────────────────────────

    def build_effect(self, effect_id: str, element: str,
                     cv_budget: float, range_x: int | None = None) -> dict | None:
        item = self.effects.get(effect_id)
        if not item:
            return None
        opt_vals = self.pick_options(item, element)
        base_cv = float(item.get("cv", item.get("cv1", 0.0)))
        for opt_key, sel in opt_vals.items():
            stat = item.get("options", {}).get(opt_key, {}).get("per_choice", {}).get(sel, {})
            base_cv += float(stat.get("cv", stat.get("cv1", 0.0)))

        # C4: For damage-tagged effects, sample damage type from the
        # per-element ranking (or the dedicated "Prowess" ranking when this
        # generator is producing Prowess cards). When ``range_x`` is given,
        # the damage type's [range_min, range_max] interval is honoured so
        # e.g. Bash never appears at Range 5+.
        damage_type = None
        damage_cv_mod = 1.0
        is_prowess_run = (self.cfg.get("profile_name") == "Prowess")
        if "damage" in (item.get("tags") or []):
            try:
                from CardContent import damage_registry as _dreg
                if is_prowess_run:
                    damage_type, damage_cv_mod = _dreg.pick_damage_type(
                        "Prowess", section="prowess_cards", range_x=range_x)
                elif element:
                    damage_type, damage_cv_mod = _dreg.pick_damage_type(
                        element, range_x=range_x)
            except Exception:
                damage_type, damage_cv_mod = None, 1.0

        # Adjust the variable budget so X scales for the post-mod target CV.
        # Working CV = raw_cv * damage_cv_mod
        # We want raw_cv * damage_cv_mod ≈ cv_budget   →  raw target = budget / mod
        try:
            mod = float(damage_cv_mod) if damage_cv_mod else 1.0
        except (TypeError, ValueError):
            mod = 1.0
        remaining = (cv_budget - base_cv) / mod if mod else (cv_budget - base_cv)
        vals = self.pick_variable_values(item, remaining)

        eff: dict = {"effect_id": effect_id, "vals": vals, "opt_vals": opt_vals}
        if damage_type:
            eff["damage_type"]    = damage_type
            eff["damage_element"] = element
            eff["damage_cv_mod"]  = round(float(damage_cv_mod), 4)
        return eff

    def build_cost(self, cost_id: str, element: str) -> dict | None:
        item = self.costs.get(cost_id)
        if not item:
            return None

        if cost_id == "Mana":
            opt_vals = {}
            if self.generic_mana_only:
                allowed = {"Generic"}
            else:
                allowed = {"Generic", "Quinta", element}
            for opt_key, opt in item.get("options", {}).items():
                avail = [c for c in opt.get("choices", []) if c in allowed]
                if not avail:
                    avail = list(opt.get("choices", []))
                pc = opt.get("per_choice", {})
                weights = [math.sqrt(float(pc.get(c, {}).get("rarity", 10))) for c in avail]
                total_w = sum(weights)
                chosen_opt = (random.choices(avail, weights=weights)[0]
                              if total_w > 0 else random.choice(avail))
                opt_vals[opt_key] = chosen_opt
            vals = {"element": opt_vals.get("0", element)}
        else:
            vals = self.pick_variable_values(item, cv_budget=2.0)
            if "element" in item.get("variables", {}):
                vals["element"] = element
            opt_vals = self.pick_options(item, element)

        return {"cost_id": cost_id, "vals": vals, "opt_vals": opt_vals}

    # ── Option selection ─────────────────────────────────────────────────────

    def pick_options(self, item: dict, element: str) -> dict:
        opt_vals = {}
        for opt_key, opt in item.get("options", {}).items():
            choices = opt.get("choices", [])
            if not choices:
                continue
            pc = opt.get("per_choice", {})
            avail = [c for c in choices
                     if c not in pc.get(c, {}).get("conditions", {}).get("excluded_choices", [])]
            if not avail:
                avail = choices

            weights = []
            for c in avail:
                stat = pc.get(c, {})
                r = float(stat.get("rarity", 10))
                ew = stat.get("conditions", {}).get("element_weights", {})
                el_w = float(ew.get(element, 10)) if ew else 10.0
                weights.append(math.sqrt(r) * (max(el_w, 0) / 10.0))

            pool = [(c, w) for c, w in zip(avail, weights) if w > 0]
            if not pool:
                pool = [(c, 1.0) for c in avail]
            pool_c, pool_w = zip(*pool)
            opt_vals[opt_key] = random.choices(list(pool_c), weights=list(pool_w))[0]
        return opt_vals

    # ── Variable value picking ───────────────────────────────────────────────

    def pick_variable_values(self, item: dict, cv_budget: float) -> dict:
        from random_builder.dice_models import load_dice_config
        dice_cfg  = load_dice_config()
        dice_list = dice_cfg.get("dice", [])
        can_chance = float(dice_cfg.get("dice_can_chance", 0.5))

        vals = {}
        variables = item.get("variables", {})
        if not variables:
            return vals
        share = cv_budget / len(variables)
        for var_name, stat in variables.items():
            dice_only    = stat.get("dice_only", False)
            dice_allowed = stat.get("dice_allowed", False)
            potion_only  = stat.get("potion_only", False)
            use_dice     = dice_only or (dice_allowed and random.random() < can_chance)
            # E1: potion_only variables get dice **only** in recipe context.
            # In Spell/Prowess generation we fall back to a numeric value.
            if potion_only:
                use_dice = False

            if use_dice and dice_list:
                vals[var_name] = self._pick_dice_for_cv(stat, share, dice_list)
            else:
                cond  = stat.get("conditions", {})
                vmin  = max(1, int(float(cond.get("var_min", 1))))
                vmax  = int(float(cond.get("var_max", 10)))
                x_max = min(max_x_for_budget(stat, share), vmax)
                x_min = max(vmin, 1)
                x = random.randint(int(x_min), int(x_max)) if x_min <= x_max else x_min
                vals[var_name] = max(1, int(x))
        return vals

    @staticmethod
    def _pick_dice_for_cv(stat: dict, target_cv: float, dice_list: list) -> str:
        """Return a dice string like '2D6' whose expected CV is closest to target_cv.

        Each die entry has an 'id' (e.g. 'D6', '2D4') and an 'avg' (expected value
        of ONE roll of that expression).  The generator picks N so that N×avg ≈ target,
        then renders as 'N<id>' (or just '<id>' when N=1).
        """
        from random_builder.dice_models import die_avg as _die_avg
        c1 = float(stat.get("cv1", 1.0)) or 1.0
        target_expected = max(1.0, target_cv / c1)

        best_label = "1D6"
        best_diff  = float("inf")
        for die in dice_list:
            avg = _die_avg(die)
            if avg <= 0:
                continue
            n      = max(1, min(5, round(target_expected / avg)))
            actual = n * avg
            diff   = abs(actual - target_expected)
            if diff < best_diff:
                best_diff  = diff
                best_label = die["id"] if n == 1 else f"{n}{die['id']}"
        return best_label

    # ── Container picking ────────────────────────────────────────────────────

    def _get_containers_for_effects(self, effect_ids: set) -> set:
        """Return set of container IDs that contain any of the given effect IDs."""
        result = set()
        for container_id, container in self.containers.items():
            effects = container.get("effects", [])
            if any(eid in effects for eid in effect_ids):
                result.add(container_id)
        return result

    def pick_from_container(self, container_id: str, element: str,
                            used: dict, cv_budget: float, block_type: str = "",
                            forbidden_ids: set = None,
                            incompat_pairs: list = None,
                            current_effects: list = None):
        """Pick one item from a container. Returns (type_str, data_dict) or None."""
        forbidden_ids = forbidden_ids or set()
        incompat_pairs = incompat_pairs or []
        current_effects = current_effects or []
        current_eids = {e["effect_id"] for e in current_effects}

        container = self.containers.get(container_id, {})
        no_repeat = container.get("no_repeat", True)
        already = used.get(container_id, set())

        candidates = []
        for type_str, lookup, list_key in [
            ("effect", self.effects, "effects"),
            ("cost",   self.costs,   "costs"),
        ]:
            for iid in container.get(list_key, []):
                if iid not in lookup:
                    continue
                if no_repeat and iid in already:
                    continue
                if type_str == "effect":
                    if iid in forbidden_ids:
                        continue
                    if any(iid in pair and current_eids & (pair - {iid})
                           for pair in incompat_pairs):
                        continue
                item = lookup[iid]
                if not self.passes_block_filters(item, block_type):
                    continue
                if not self.allowed_for_profile(item):
                    continue
                if not self.passes_all_id_conditions(item):
                    continue
                # B1: hard disable per element / recipe-type
                if element and not self.item_enabled_for(item, element):
                    continue
                candidates.append((type_str, iid, item))

        if not candidates:
            return None

        weights = []
        for _, iid, item in candidates:
            rarity = float(item.get("rarity", 10))
            sub_w = self.item_subcategory_weight(item, element)
            weights.append(math.sqrt(rarity) * (max(sub_w, 0) / 10.0))

        pool = [(c, w) for c, w in zip(candidates, weights) if w > 0]
        if not pool:
            pool = list(zip(candidates, [1.0] * len(candidates)))

        pool_cands, pool_wts = zip(*pool)
        chosen = random.choices(list(pool_cands), weights=list(pool_wts))[0]

        type_str, iid, _ = chosen
        if no_repeat:
            used.setdefault(container_id, set()).add(iid)

        if type_str == "effect":
            return ("effect", self.build_effect(iid, element, cv_budget))
        elif type_str == "cost":
            return ("cost", self.build_cost(iid, element))
        return None

    def pick_from_effects_pool(self, effects_pool: list, element: str,
                               block_type: str, cv_budget: float,
                               forbidden_ids, incompat_pairs: list,
                               current_effects: list):
        """Pick one effect from an inline effects-pool list."""
        forbidden_ids = forbidden_ids or set()
        incompat_pairs = incompat_pairs or []
        current_eids = {e["effect_id"] for e in (current_effects or [])}

        candidates = []
        for eid in effects_pool:
            item = self.effects.get(eid)
            if not item:
                continue
            if eid in forbidden_ids:
                continue
            if any(eid in pair and current_eids & (pair - {eid}) for pair in incompat_pairs):
                continue
            allowed_bt = item.get("conditions", {}).get("allowed_box_types", [])
            if allowed_bt and block_type and block_type not in allowed_bt:
                continue
            if not self.allowed_for_profile(item):
                continue
            # B1: hard disable per element / recipe-type
            if element and not self.item_enabled_for(item, element):
                continue
            candidates.append((eid, item))

        if not candidates:
            return None

        weights = []
        for eid, item in candidates:
            rarity = float(item.get("rarity", 10))
            sub_w = self.item_subcategory_weight(item, element)
            weights.append(math.sqrt(rarity) * (max(sub_w, 0) / 10.0))

        pool = [(c, w) for c, w in zip(candidates, weights) if w > 0]
        if not pool:
            pool = [(c, 1.0) for c in candidates]
        pool_cands, pool_wts = zip(*pool)
        chosen_eid, _ = random.choices(list(pool_cands), weights=list(pool_wts))[0]

        return self.build_effect(chosen_eid, element, cv_budget)

    # ── Target type / group building ────────────────────────────────────────

    # Target types that *generate* their own bucket on a sigil. "Target
    # Neutral" is intentionally NOT one of them — it acts as a permission
    # tag (an effect tagged Target Neutral is eligible inside Target Enemy
    # AND Target Ally groups, never as its own bucket).
    _GENERATABLE_TARGET_TYPES = ("Target Enemy", "Target Ally", "Non Targeting")

    def pick_target_type(self, exclude: set = None) -> str:
        """Weighted random selection of target type, excluding already-used types.

        Target Neutral is filtered out — it's a permission tag, not a bucket.
        """
        weights_cfg = self.cfg.get("target_type_weights", {
            "Target Enemy": 10, "Target Ally": 8, "Non Targeting": 10,
        })
        # Hard filter: never produce Target Neutral as a target_type
        all_types = [t for t in weights_cfg.keys()
                     if t in self._GENERATABLE_TARGET_TYPES]
        if not all_types:
            all_types = list(self._GENERATABLE_TARGET_TYPES)
        # Prefer types not yet used; fall back to all if every type is taken
        avail = [t for t in all_types if not exclude or t not in exclude]
        if not avail:
            avail = all_types
        weights = [float(weights_cfg.get(t, 1.0)) for t in avail]
        total = sum(weights)
        if total <= 0:
            return random.choice(avail)
        return random.choices(avail, weights=weights)[0]

    def _build_aoe_modifier(self, primary_item: dict | None,
                              cv_budget: float, primary_cv: float
                              ) -> dict | None:
        """Pick an AoE pattern from the AOE Designer registry, weighted by
        per-pattern CV (capped at the budget remaining after the primary).

        Returns an effect-modifier dict with ``effect_id="AoE"`` plus the
        chosen pattern id and its CV stamped on. Returns None if no
        registered patterns or none fit the budget.
        """
        try:
            from aoe_designer.models import get_pattern_ids_with_cv
        except Exception:
            return None
        items = get_pattern_ids_with_cv()
        if not items:
            return None
        remaining = max(0.5, cv_budget - primary_cv)
        # Eligible = patterns whose CV is <= remaining; if none, take the
        # cheapest one (so we never silently lose AoE).
        affordable = [(pid, cv) for pid, cv in items if cv <= remaining]
        pool = affordable or [min(items, key=lambda t: t[1])]
        weights = [max(cv, 0.1) for _, cv in pool]
        pid, cv = random.choices(pool, weights=weights)[0]
        return {
            "effect_id":     "AoE",
            "vals":          {},
            "opt_vals":      {},
            "aoe_pattern":   pid,
            "aoe_cv":        round(float(cv), 2),
        }

    @staticmethod
    def _target_type_compatible(target_type: str,
                                  candidate_types: list) -> bool:
        """True if an item with ``primary_types``=candidate_types fits in a
        group of target_type. Target Neutral acts as a permission tag for
        Target Enemy AND Target Ally groups."""
        if not candidate_types:
            return True   # untyped item — accept anywhere
        if target_type in candidate_types:
            return True
        if target_type in ("Target Enemy", "Target Ally") and \
                "Target Neutral" in candidate_types:
            return True
        return False

    def _pick_weighted(self, candidates: list, element: str):
        """Pick one (eid, item) from candidates using rarity + element weights."""
        if not candidates:
            return None
        weights = []
        for eid, item in candidates:
            rarity = float(item.get("rarity", 10))
            sub_w = self.item_subcategory_weight(item, element)
            weights.append(math.sqrt(rarity) * (max(sub_w, 0) / 10.0))
        pool = [(c, w) for c, w in zip(candidates, weights) if w > 0]
        if not pool:
            pool = [(c, 1.0) for c in candidates]
        pool_cands, pool_wts = zip(*pool)
        return random.choices(list(pool_cands), weights=list(pool_wts))[0]

    def _filter_primaries(self, target_type, element: str,
                          block_type: str, forbidden_ids: set,
                          source_eids: list = None) -> list:
        """Return [(eid, item)] for primary effects matching target_type.
        Pass target_type=None to skip the target_type filter (any type accepted).
        Respects active id_condition scopes via passes_all_id_conditions()."""
        if source_eids is not None:
            base = [(eid, self.effects[eid]) for eid in source_eids
                    if eid in self.effects]
        else:
            base = list(self.effects.items())

        result = []
        for eid, item in base:
            if item.get("role", "primary") != "primary":
                continue
            if eid in forbidden_ids:
                continue
            if not self.allowed_for_profile(item):
                continue
            if not self.passes_block_filters(item, block_type):
                continue
            if not self.passes_all_id_conditions(item):
                continue
            if target_type is not None:
                ptypes = item.get("primary_types", [])
                # Target Neutral acts as a permission tag for Enemy/Ally groups
                if not self._target_type_compatible(target_type, ptypes):
                    continue
            allowed_el = item.get("conditions", {}).get("allowed_elements", [])
            if allowed_el and element and element not in allowed_el:
                continue
            # B1: hard disable per element / recipe-type
            if element and not self.item_enabled_for(item, element):
                continue
            result.append((eid, item))
        return result

    def _filter_modifiers(self, target_type: str, element: str,
                          block_type: str, forbidden_ids: set,
                          primary_item: dict = None) -> list:
        """
        Return [(eid, item)] for modifiers compatible with this group.
        Both conditions must pass when defined:
          - attaches_to:          group's target_type must be in this list
          - requires_primary_tags: primary effect must have at least one matching tag
        """
        primary_tags = set(primary_item.get("tags", [])) if primary_item else set()
        result = []
        for eid, item in self.effects.items():
            if item.get("role", "primary") != "modifier":
                continue
            if eid in forbidden_ids:
                continue
            if not self.allowed_for_profile(item):
                continue
            if not self.passes_block_filters(item, block_type):
                continue
            if not self.passes_all_id_conditions(item):
                continue
            # target_type filter — Target Neutral on attaches_to permits
            # both Target Enemy and Target Ally groups.
            attaches = item.get("attaches_to", [])
            if attaches and not self._target_type_compatible(target_type,
                                                              attaches):
                continue
            # tag filter: if modifier requires specific primary tags, check them
            req_tags = item.get("requires_primary_tags", [])
            if req_tags and not primary_tags.intersection(req_tags):
                continue
            allowed_el = item.get("conditions", {}).get("allowed_elements", [])
            if allowed_el and element and element not in allowed_el:
                continue
            # B1: hard disable per element / recipe-type
            if element and not self.item_enabled_for(item, element):
                continue
            result.append((eid, item))
        return result

    def build_effect_group(self, target_type: str, element: str,
                           cv_budget: float, block_type: str = "",
                           forbidden_ids: set = None,
                           source_eids: list = None) -> dict | None:
        """Build one effect group: primary + optional modifiers.

        Honors active id_condition scopes (see push_id_scope); every picked
        primary/modifier is registered via register_id_used_all() so later
        picks in the same scope respect its id_conditions.
        """
        forbidden_ids = forbidden_ids or set()

        primaries = self._filter_primaries(
            target_type, element, block_type, forbidden_ids, source_eids)
        if not primaries and source_eids is not None:
            # Container has no effects matching the desired target_type —
            # relax the target_type filter but keep the container's source list.
            primaries = self._filter_primaries(
                None, element, block_type, forbidden_ids, source_eids)
        if not primaries:
            # Last resort: any effect with the requested target_type.
            primaries = self._filter_primaries(
                target_type, element, block_type, forbidden_ids, None)
        if not primaries:
            return None

        chosen = self._pick_weighted(primaries, element)
        if not chosen:
            return None
        eid, chosen_item = chosen

        # NEW: pre-roll the Range X so build_effect can pick a damage type
        # whose [range_min, range_max] interval covers it. Range only
        # applies to Target Enemy buckets and only when AoE doesn't win
        # the modifier roll.
        pre_range_x: int | None = None
        pre_aoe = False
        if target_type == "Target Enemy":
            pre_aoe = random.random() < float(
                self.cfg.get("aoe_modifier_chance", 0.10))
            if not pre_aoe:
                rv_cfg = self.cfg.get("range_value_weights")
                if rv_cfg:
                    keys = [k for k in rv_cfg]
                    wts  = [float(rv_cfg[k]) for k in keys]
                    if sum(wts) > 0:
                        pre_range_x = int(random.choices(
                            keys, weights=wts)[0])

        primary = self.build_effect(eid, element, cv_budget,
                                      range_x=pre_range_x)
        if not primary:
            return None
        # Register picked primary for id_conditions tracking
        self.register_id_used_all(chosen_item)

        # Use the actual primary_type of the chosen effect (important when
        # target_type was relaxed above to accommodate a specific container).
        # Target Neutral is a permission tag — when an effect is tagged
        # only Target Neutral and we're filling a Target Enemy/Ally bucket,
        # keep the requested target_type instead of falling back to "Target
        # Neutral" (which would create a phantom bucket).
        actual_ptypes = chosen_item.get("primary_types", [])
        if not actual_ptypes or target_type in actual_ptypes:
            resolved_type = target_type
        elif target_type in ("Target Enemy", "Target Ally") and \
                "Target Neutral" in actual_ptypes:
            resolved_type = target_type
        else:
            # Fall back to the effect's first type, but never use Target
            # Neutral as a real bucket — promote it to Non Targeting.
            first = actual_ptypes[0]
            resolved_type = "Non Targeting" if first == "Target Neutral" else first

        # Deduct primary CV
        primary_item = self.effects.get(primary["effect_id"])
        primary_cv = 0.0
        if primary_item:
            primary_cv = cv_content_item(primary_item, primary.get("vals", {}),
                                         primary.get("opt_vals", {}))
            # C4: include damage-type CV multiplier
            try:
                primary_cv *= float(primary.get("damage_cv_mod", 1.0) or 1.0)
            except (TypeError, ValueError):
                pass

        # ── D: Range Reform — force-attach Ranged to every Target-Enemy group.
        # NEW: with ``aoe_modifier_chance`` (default 10%) we instead attach
        # an AoE pattern picked from the AOE Designer registry, weighted by
        # the patterns' CV. AoE replaces Range — never both.
        # The Range X / AoE coin flip was pre-rolled above so the damage
        # type pick could honour the chosen Range interval.
        modifiers = []
        ranged_forced = False
        aoe_forced    = False
        if resolved_type == "Target Enemy":
            if pre_aoe:
                eff_aoe = self._build_aoe_modifier(primary_item, cv_budget,
                                                    primary_cv)
                if eff_aoe is not None:
                    modifiers.append(eff_aoe)
                    aoe_forced = True

            if not aoe_forced:
                ranged_item = self.effects.get("Ranged")
                if ranged_item and "Ranged" not in forbidden_ids and \
                        self.allowed_for_profile(ranged_item) and \
                        self.passes_block_filters(ranged_item, block_type) and \
                        self.passes_all_id_conditions(ranged_item) and \
                        self.item_enabled_for(ranged_item, element):
                    # Check requires_primary_tags
                    req_tags = ranged_item.get("requires_primary_tags", [])
                    primary_tags = set(primary_item.get("tags", []) or []) if primary_item else set()
                    if not req_tags or primary_tags.intersection(req_tags):
                        if pre_range_x is not None:
                            eff = {"effect_id": "Ranged",
                                   "vals": {"X": pre_range_x}, "opt_vals": {}}
                        elif self.cfg.get("range_value_weights"):
                            rv_cfg = self.cfg["range_value_weights"]
                            keys = [k for k in rv_cfg]
                            wts  = [float(rv_cfg[k]) for k in keys]
                            x_pick = (int(random.choices(keys, weights=wts)[0])
                                      if sum(wts) > 0 else 0)
                            eff = {"effect_id": "Ranged",
                                   "vals": {"X": x_pick}, "opt_vals": {}}
                        else:
                            # Legacy: 40% → range 0; else solve from budget
                            range_zero_chance = float(
                                self.cfg.get("range_zero_chance", 0.40))
                            if random.random() < range_zero_chance:
                                eff = {"effect_id": "Ranged", "vals": {"X": 0},
                                       "opt_vals": {}}
                            else:
                                eff = self.build_effect("Ranged", element,
                                                        cv_budget - primary_cv)
                                if eff is None:
                                    eff = {"effect_id": "Ranged",
                                           "vals": {"X": 0}, "opt_vals": {}}
                                if int(eff.get("vals", {}).get("X", 0) or 0) < 1:
                                    eff["vals"]["X"] = 1
                        modifiers.append(eff)
                        ranged_forced = True
                        self.register_id_used_all(ranged_item)

        # Roll for further modifiers
        mod_chance = float(self.cfg.get("modifier_chance", 0.3))
        if random.random() < mod_chance:
            mod_forbidden = forbidden_ids | {primary["effect_id"]}
            if ranged_forced:
                mod_forbidden = mod_forbidden | {"Ranged"}
            if aoe_forced:
                # When AoE is the primary movement/spread modifier, also
                # forbid Ranged so we don't accidentally stack both.
                mod_forbidden = mod_forbidden | {"Ranged", "AoE"}
            mod_candidates = self._filter_modifiers(
                resolved_type, element, block_type, mod_forbidden,
                primary_item=primary_item)

            max_mods = int(self.cfg.get("max_modifiers_per_group", 2))
            remaining = cv_budget - primary_cv
            used_mod_ids = set()

            for _ in range(max_mods):
                avail = [(e, i) for e, i in mod_candidates
                         if e not in used_mod_ids
                         and self.passes_all_id_conditions(i)]
                if not avail:
                    break
                chosen_mod = self._pick_weighted(avail, element)
                if not chosen_mod:
                    break
                mod_eid, mod_item = chosen_mod
                eff = self.build_effect(mod_eid, element, remaining)
                if eff:
                    modifiers.append(eff)
                    used_mod_ids.add(mod_eid)
                    # Register modifier for id_conditions tracking
                    self.register_id_used_all(mod_item)
                    if mod_item:
                        mod_cv = cv_content_item(
                            mod_item, eff.get("vals", {}),
                            eff.get("opt_vals", {}))
                        try:
                            mod_cv *= float(eff.get("damage_cv_mod", 1.0) or 1.0)
                        except (TypeError, ValueError):
                            pass
                        remaining -= mod_cv

        result = {
            "target_type": resolved_type,
            "primaries":   [primary],
            "modifiers":   modifiers,
        }

        # NEW: Target Enemy / Target Ally buckets may carry multiple primary
        # effects (the renderer shows them as one bucket with several bullets).
        # We give each extra slot an independent roll so a card with a single
        # primary remains the common case.
        if resolved_type in ("Target Enemy", "Target Ally"):
            extra_chance = float(self.cfg.get("multi_primary_chance", 0.30))
            max_extras   = int(self.cfg.get("multi_primary_max", 2))
            extras_added = 0
            for _ in range(max_extras):
                if random.random() >= extra_chance:
                    break
                # Budget left = whatever remained after the primary + modifiers
                left = max(0.5, remaining if 'remaining' in locals() else
                            (cv_budget - primary_cv))
                # Banned: primary + already-used modifier ids (avoid dupes)
                banned = set(forbidden_ids) | {primary["effect_id"]} | {
                    m.get("effect_id") for m in modifiers
                    if m.get("effect_id")
                }
                added = self.add_primary_to_group(result, element, left,
                                                    block_type,
                                                    forbidden_ids=banned,
                                                    source_eids=source_eids)
                if not added:
                    break
                # Migrate the canonical-key slot if the helper used `effects`
                if "effects" in result and "primaries" in result:
                    # Merge into 'primaries' so the rest of the pipeline
                    # (cv_calc, renderer) sees a single canonical key.
                    extras = result.pop("effects", [])
                    result["primaries"].extend(extras)
                extras_added += 1

        return result

    def add_primary_to_group(self, group: dict, element: str,
                              cv_budget: float, block_type: str = "",
                              forbidden_ids: set = None,
                              source_eids: list = None) -> dict | None:
        """
        Add another primary effect to an existing group.
        CONSTRAINT: Never add effects from the same container to one group.
        Returns the new primary dict on success, None on failure.
        """
        target_type = group.get("target_type", "Non Targeting")
        forbidden_ids = forbidden_ids or set()

        # Exclude effects already in this group
        existing = {p.get("effect_id") for p in group.get("primaries", [])}
        old_p = group.get("primary", {})
        if old_p.get("effect_id"):
            existing.add(old_p["effect_id"])
        all_forbidden = forbidden_ids | existing

        # NEW CONSTRAINT: Exclude effects from containers already in this group
        used_containers = self._get_containers_for_effects(existing)
        for container_id in used_containers:
            if container_id in self.containers:
                container = self.containers[container_id]
                # Add all effects from this container to forbidden list
                all_forbidden.update(container.get("effects", []))

        primaries = self._filter_primaries(
            target_type, element, block_type, all_forbidden, source_eids)
        if not primaries:
            primaries = self._filter_primaries(
                target_type, element, block_type, all_forbidden, None)
        if not primaries:
            return None

        chosen = self._pick_weighted(primaries, element)
        if not chosen:
            return None
        eid, _ = chosen
        new_primary = self.build_effect(eid, element, cv_budget)
        if not new_primary:
            return None

        group.setdefault("primaries", []).append(new_primary)
        return new_primary

    def add_effect_to_group(self, group: dict, element: str,
                            cv_budget: float, block_type: str = "",
                            forbidden_ids: set = None,
                            source_eids: list = None) -> dict | None:
        """
        Pick an additional effect and append it to group['effects'].
        Returns the new effect dict on success, None if nothing suitable found.
        """
        target_type  = group.get("target_type", "Non Targeting")
        forbidden_ids = forbidden_ids or set()

        # Exclude effect IDs already in this group (all format variants)
        existing = {e.get("effect_id") for e in group.get("effects", [])}
        existing.update(p.get("effect_id") for p in group.get("primaries", []))
        if "primary" in group:
            existing.add(group["primary"].get("effect_id", ""))

        all_forbidden = forbidden_ids | existing
        candidates = self._filter_primaries(
            target_type, element, block_type, all_forbidden, source_eids)
        if not candidates:
            candidates = self._filter_primaries(
                target_type, element, block_type, all_forbidden, None)
        if not candidates:
            return None

        chosen = self._pick_weighted(candidates, element)
        if not chosen:
            return None
        eid, _ = chosen
        new_eff = self.build_effect(eid, element, cv_budget)
        if not new_eff:
            return None

        group.setdefault("effects", []).append(new_eff)
        return new_eff

    def build_sub_sigil(self, element: str, cv_budget: float,
                        block_type: str = "",
                        target_type: str | None = None,
                        restrict_to_targets: set | None = None,
                        sub_type: str = "enhance",
                        forbid_target_types: set | None = None) -> dict | None:
        """Build a sub-sigil.

        sub_type:
            - "enhance"      : costs + (opt) condition + 1 effect_group  (classic)
            - "doublecast"   : costs + (opt) condition, NO effects
            - "multicast"    : costs + (opt) condition, NO effects   (×3)
            - "target_enemy" : costs + 1 effect_group with target_type=Target Enemy
            - "target_ally"  : same with Target Ally
            - "choose"       : costs + N effect_groups; player picks one each
                               cast. Each option may target different things,
                               and damage types are allowed to differ
                               ("einmalig"-Choose).

        forbid_target_types:
            Set of target_types the sub-sigil's own effect_group(s) must NOT
            use (to enforce "one Target Enemy / one Target Ally per sigil
            incl sub-sigil").
        """
        costs = []
        if "Mana" in self.costs:
            cost = self.build_cost("Mana", element)
            if cost:
                costs.append(cost)
        if not costs:
            return None

        condition_id, condition_vals, condition_opt_vals = None, {}, {}
        if self.conditions and random.random() < 0.15:
            allowed = {k: v for k, v in self.conditions.items()
                       if self.allowed_for_profile(v)}
            if allowed:
                cid = random.choice(list(allowed.keys()))
                citem = allowed[cid]
                condition_id = cid
                condition_opt_vals = self.pick_options(citem, element)
                condition_vals = self.pick_variable_values(citem, cv_budget=1.0)

        # Doublecast / Multicast: no effects, just cost + condition
        if sub_type in ("doublecast", "multicast"):
            return {
                "sub_sigil_type":     sub_type,
                "target_type":        "",
                "condition_id":       condition_id,
                "condition_vals":     condition_vals,
                "condition_opt_vals": condition_opt_vals,
                "costs":              costs,
                "effect_groups":      [],
            }

        # NEW: target_enemy / target_ally — fixed target, otherwise like enhance
        if sub_type == "target_enemy":
            target_type = "Target Enemy"
        elif sub_type == "target_ally":
            target_type = "Target Ally"

        # NEW: choose sub-sigil — produces 2..N effect_groups with different
        # target_types or damage variations. Allowed to use different damage
        # types since this is a one-time decision per cast.
        if sub_type == "choose":
            return self._build_choose_sub_sigil(
                element, cv_budget, block_type, costs,
                condition_id, condition_vals, condition_opt_vals,
                forbid_target_types or set())

        # Enhance: pick target_type honoring the forbid set
        forbid = forbid_target_types or set()
        if target_type is None:
            if restrict_to_targets:
                pool = [t for t in restrict_to_targets if t not in forbid]
                if not pool:
                    pool = list(restrict_to_targets)
                target_type = random.choice(pool)
            else:
                target_type = self.pick_target_type(exclude=forbid)
        elif target_type in forbid:
            # Requested target is forbidden → fall back
            target_type = self.pick_target_type(exclude=forbid) or target_type

        # Override budget by per-target-type CV range if configured
        per_target = self.cfg.get("sub_sigil_cv_per_target", {})
        tt_cfg = per_target.get(target_type) if isinstance(per_target, dict) else None
        if isinstance(tt_cfg, dict):
            try:
                mn = float(tt_cfg.get("min", 0.0))
                mx = float(tt_cfg.get("max", cv_budget))
                if mx < mn:
                    mn, mx = mx, mn
                if mx > 0:
                    cv_budget = random.uniform(max(mn, 0.0), max(mx, 0.0))
            except (TypeError, ValueError):
                pass

        group = self.build_effect_group(target_type, element, cv_budget, block_type)
        if not group:
            return None

        # Map back to a stable sub_sigil_type label
        out_type = sub_type if sub_type in ("target_enemy", "target_ally",
                                              "enhance") else "enhance"
        return {
            "sub_sigil_type":     out_type,
            "target_type":        target_type,
            "condition_id":       condition_id,
            "condition_vals":     condition_vals,
            "condition_opt_vals": condition_opt_vals,
            "costs":              costs,
            "effect_groups":      [group],
        }

    def _build_choose_sub_sigil(self, element: str, cv_budget: float,
                                  block_type: str, costs: list,
                                  cond_id, cond_vals, cond_opt_vals,
                                  forbid: set) -> dict | None:
        """Build a sub-sigil that offers a one-time choice between several
        effect_groups (different target types or damage flavors).

        Tolerance: the option CVs must be within
        ``choose_cv_tolerance`` of the highest, otherwise we drop the
        long-tail ones until they fit.
        """
        # Aim for 2..3 options
        n_options = random.randint(2, 3)
        # Each option burns roughly 1/n of the budget; allow ±20% jitter.
        per_opt   = cv_budget / max(1, n_options)
        groups: list = []
        used_targets: set = set()
        candidate_targets = ["Target Enemy", "Target Ally", "Non Targeting"]
        # Bias towards different targets but allow the same one twice
        # (e.g. both Target Enemy with different damage types).
        for _ in range(n_options):
            tt_pool = [t for t in candidate_targets if t not in forbid]
            if not tt_pool:
                tt_pool = list(candidate_targets)
            # Prefer unused targets first, fall back to any if exhausted
            unused = [t for t in tt_pool if t not in used_targets]
            tt = random.choice(unused or tt_pool)
            used_targets.add(tt)

            jitter = per_opt * random.uniform(0.85, 1.15)
            grp = self.build_effect_group(tt, element, jitter, block_type)
            if grp:
                groups.append(grp)

        if len(groups) < 2:
            return None

        # Tolerance check: drop options whose CV is too low. (Per user spec:
        # all options should be within 20% of the max so the choice matters.)
        try:
            from random_builder.cv_calc import cv_effect_group as _cg
        except Exception:
            _cg = lambda g, l: 1.0
        cvs = [(g, _cg(g, self.effects)) for g in groups]
        if not cvs:
            return None
        hi = max(c for _, c in cvs) or 1.0
        tol = float(self.cfg.get("choose_cv_tolerance", 0.20))
        kept = [g for g, c in cvs if (hi - c) / hi <= tol]
        if len(kept) < 2:
            return None

        return {
            "sub_sigil_type":     "choose",
            "target_type":        "",
            "condition_id":       cond_id,
            "condition_vals":     cond_vals,
            "condition_opt_vals": cond_opt_vals,
            "costs":              costs,
            "effect_groups":      kept,
            # Choose-Y-of-X:
            "choose_n":           1,
            "choose_total":       len(kept),
        }

    # ── Generate (to be implemented by subclass) ─────────────────────────────

    def generate_one(self) -> dict | None:
        raise NotImplementedError


# ── Public façade ────────────────────────────────────────────────────────────

class CardGenerator:
    """
    Delegates to the appropriate profile-specific generator.

    Usage:
        gen = CardGenerator(content_data, containers, box_config, gen_config)
        cards = gen.generate(count=10)
    """

    def __init__(self, content_data: dict, containers: dict,
                 box_config: dict, gen_config: dict):
        profile = gen_config.get("profile_name", "Spells")
        if profile == "Recipes":
            from .recipe_gen import RecipeGenerator
            self._impl = RecipeGenerator(content_data, containers, box_config, gen_config)
        else:
            from .spell_gen import SpellGenerator
            self._impl = SpellGenerator(content_data, containers, box_config, gen_config)

    def generate(self, count: int) -> list:
        cfg = self._impl.cfg
        cv_min = float(cfg.get("cv_card_min",  0.0))
        cv_max = float(cfg.get("cv_card_max",  float(cfg.get("cv_target", 999.0))))
        cards = []
        too_low = too_high = 0
        max_attempts = count * 100
        attempts = 0
        while len(cards) < count and attempts < max_attempts:
            attempts += 1
            card = self._impl.generate_one()
            if card is None:
                continue
            cv = card.get("_cv", 0)
            if cv < cv_min:
                too_low += 1
                continue
            if cv > cv_max:
                too_high += 1
                continue
            cards.append(card)
        rejected = too_low + too_high
        print(f"  [gen] Ergebnis: {len(cards)}/{count} Karten in {attempts} Versuchen "
              f"(CV Fenster [{cv_min:.1f}, {cv_max:.1f}])")
        if rejected:
            print(f"  [gen] Verworfen: {rejected} ({too_low}x CV zu niedrig, "
                  f"{too_high}x CV zu hoch)")
        if len(cards) < count:
            print(f"  [gen] WARNUNG: Nur {len(cards)}/{count} erzeugt! "
                  f"CV-Fenster [{cv_min:.1f}, {cv_max:.1f}] ist zu eng.")
        return cards
