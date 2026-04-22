"""
CardTypes – per-type editor and renderer classes.

Usage:
    from card_builder.CardTypes import get_editor, get_renderer

    EditorClass   = get_editor(card_type)
    RendererClass = get_renderer(card_type)
"""

from card_builder.CardTypes.spell_card       import SpellCardEditor,     SpellCardRenderer
from card_builder.CardTypes.loot_editor      import LootCardEditor
from card_builder.CardTypes.equipment_editor import EquipmentCardEditor, SuppliesCardEditor
from card_builder.CardTypes.loot_renderer    import LootCardRenderer
# AlchemyCard kept for data migration only (not in card type dropdown)
from card_builder.CardTypes.alchemy_card     import AlchemyCardEditor,   AlchemyCardRenderer
from card_builder.CardTypes.recipe_card      import RecipeCardEditor,    RecipeCardRenderer


_EDITORS = {
    "Spells":     SpellCardEditor,
    "Prowess":    SpellCardEditor,
    "Loot":       LootCardEditor,
    "Supplies":   SuppliesCardEditor,
    "Equipment":  EquipmentCardEditor,
    "Potions":    RecipeCardEditor,
    "Phials":     RecipeCardEditor,
    "Tinctures":  RecipeCardEditor,
}

_RENDERERS = {
    "Spells":     SpellCardRenderer,
    "Prowess":    SpellCardRenderer,
    "Loot":       LootCardRenderer,
    "Supplies":   LootCardRenderer,
    "Equipment":  LootCardRenderer,
    "Potions":    RecipeCardRenderer,
    "Phials":     RecipeCardRenderer,
    "Tinctures":  RecipeCardRenderer,
}


def get_editor(card_type: str):
    return _EDITORS.get(card_type, SpellCardEditor)


def get_renderer(card_type: str):
    return _RENDERERS.get(card_type, SpellCardRenderer)
