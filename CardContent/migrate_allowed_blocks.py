"""
migrate_allowed_blocks.py – One-time migration to add 'allowed_in_blocks' field
to all content items (Effects, Triggers, Costs, Conditions).

Default: all blocks enabled (true). Items can be customized later via the
Content Editor UI (checkbox section).

Can be safely re-run — only items missing the field get updated.
"""

import json
import os
import sys

# Use the centrally-defined BOX_TYPES list
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    from card_builder.constants import BOX_TYPES
except ImportError:
    # Fallback if run standalone without proper project path
    BOX_TYPES = [
        "Play", "Excavate", "Hand", "Concentration",
        "Enchantment", "Equipped", "Exhausted", "Fleeting", "Discard",
    ]

DATA_DIR = "cc_data"
FILES_TO_MIGRATE = [
    "effects.json",
    "triggers.json",
    "costs.json",
    "conditions.json",
]

def migrate_file(filepath: str) -> int:
    """Migrate one JSON file, return count of updated items."""
    if not os.path.exists(filepath):
        print(f"  - {filepath} not found")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Data structure is {TypeKey: [items]}
    total_updated = 0
    for type_key, items in data.items():
        if not isinstance(items, list):
            continue

        for item in items:
            if isinstance(item, dict) and "allowed_in_blocks" not in item:
                # Add field with all blocks enabled
                item["allowed_in_blocks"] = {block: True for block in BOX_TYPES}
                total_updated += 1

    if total_updated > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  OK {filepath}: {total_updated} items updated")
    else:
        print(f"  OK {filepath}: all items already have allowed_in_blocks")

    return total_updated

def main():
    os.chdir(DATA_DIR)

    total = 0
    for filename in FILES_TO_MIGRATE:
        count = migrate_file(filename)
        total += count

    print(f"\n[Done] Total items migrated: {total}")

if __name__ == "__main__":
    main()
