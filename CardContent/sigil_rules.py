"""
sigil_rules.py – Cross-sigil rules at the card level.

Each rule has the shape::

    {
      "id":        "sacrifice_needs_concentration",
      "if":        { "sigil": "Sacrifice",
                     "card_type_in": ["Spells", "Prowess"] },
      "require":   [ { "sigil": "Concentration" } ],
      "or_satisfy_by": [ { "interactable": "Source" } ]
    }

Semantics
---------
* ``if`` is the trigger predicate. The rule fires when *all* its sub-clauses
  match the card-under-construction.
* ``require`` is a list of clauses that must ALL be satisfied for the rule
  to pass (AND).
* ``or_satisfy_by`` is an OR-fallback: if any clause in this list matches,
  the rule passes too (regardless of ``require``).

Predicate clauses
-----------------
* ``"sigil": "X"``                — card has a sigil with type==X
* ``"card_type": "Spells"``        — card.card_type == this
* ``"card_type_in": [...]``        — card.card_type in list
* ``"element": "Fire"``            — element appears in card.elements
* ``"interactable": "Source"``     — registered interactable id (informational
                                       only; the runtime can't actually verify
                                       in-world objects, so the rule just
                                       *passes* unconditionally on this clause)
* ``"id_required": "X"`` / ``"id_excluded": "X"`` — passes through to the
                                       generator's id_condition system

Storage: ``cc_data/sigil_rules.json``::

    {"rules": [ <Rule>, ... ]}
"""

from __future__ import annotations

import json
import os

_DIR  = os.path.join(os.path.dirname(__file__), "cc_data")
_PATH = os.path.join(_DIR, "sigil_rules.json")


def _load() -> dict:
    if os.path.exists(_PATH):
        try:
            with open(_PATH, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and "rules" in d:
                return d
        except Exception:
            pass
    return {"rules": []}


def _save(d: dict) -> None:
    os.makedirs(_DIR, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


# ── Public read / write API ──────────────────────────────────────────────────

def list_rules() -> list:
    return list(_load().get("rules", []))


def save_rules(rules: list) -> None:
    _save({"rules": list(rules)})


def add_rule(rule: dict) -> None:
    d = _load()
    d.setdefault("rules", []).append(rule)
    _save(d)


def remove_rule(rule_id: str) -> bool:
    d = _load()
    before = len(d.get("rules", []))
    d["rules"] = [r for r in d.get("rules", []) if r.get("id") != rule_id]
    if len(d["rules"]) == before:
        return False
    _save(d)
    return True


# ── Evaluation ───────────────────────────────────────────────────────────────

def _card_sigils(card: dict) -> set:
    return {b.get("type", "") for b in card.get("blocks", [])}


def _card_elements(card: dict) -> set:
    return set(card.get("elements", []) or [])


def _card_interactables(card: dict) -> set:
    """Interactables actually mentioned on the card's blocks/abilities.

    Walks every effect/cost/trigger/condition that has an ``interactable``
    field stamped by the generator (or that references one in its
    ``opt_vals``) and yields the union.
    """
    found: set = set()
    for blk in card.get("blocks", []):
        for ab in blk.get("abilities", []):
            for grp in ab.get("effect_groups", []):
                for prim in (grp.get("primaries", [])
                             or ([grp.get("primary")] if grp.get("primary") else [])):
                    if not prim:
                        continue
                    if prim.get("interactable"):
                        found.add(prim["interactable"])
                    for v in (prim.get("opt_vals") or {}).values():
                        if isinstance(v, str) and v:
                            found.add(v)
    # Also accept an explicit card-level list (set by the user / generator)
    for it in (card.get("interactables") or []):
        if it:
            found.add(it)
    return found


def _clause_matches(clause: dict, card: dict) -> bool:
    if not isinstance(clause, dict):
        return False
    if "sigil" in clause and clause["sigil"] not in _card_sigils(card):
        return False
    if "card_type" in clause and \
            card.get("card_type", "") != clause["card_type"]:
        return False
    if "card_type_in" in clause:
        if card.get("card_type", "") not in clause["card_type_in"]:
            return False
    if "element" in clause and clause["element"] not in _card_elements(card):
        return False
    if "interactable" in clause:
        if clause["interactable"] not in _card_interactables(card):
            return False
    return True


def evaluate(card: dict, rules: list | None = None) -> list[str]:
    """Return a list of violation messages for ``card``.

    Empty list = card passes all rules.
    """
    if rules is None:
        rules = list_rules()
    violations: list[str] = []
    for rule in rules:
        if_clause = rule.get("if")
        if if_clause and not _clause_matches(if_clause, card):
            continue   # rule does not apply

        # Either ALL `require` clauses pass, OR any `or_satisfy_by` does.
        req = rule.get("require") or []
        ok_req = all(_clause_matches(c, card) for c in req) if req else True

        alt = rule.get("or_satisfy_by") or []
        ok_alt = any(_clause_matches(c, card) for c in alt) if alt else False

        if not (ok_req or ok_alt):
            violations.append(
                rule.get("message")
                or rule.get("id")
                or "Sigil rule violated")
    return violations
