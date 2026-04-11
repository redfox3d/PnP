"""
CardTypes – per-type editor and renderer classes.

Usage:
    from card_builder.CardTypes import get_editor, get_renderer

    EditorClass   = get_editor(card_type)
    RendererClass = get_renderer(card_type)
"""

from card_builder.CardTypes.spell_card import SpellCardEditor,    SpellCardRenderer
from card_builder.CardTypes.loot_card  import LootCardEditor,     LootCardRenderer
from card_builder.CardTypes.loot_card  import EquipmentCardEditor
from card_builder.CardTypes.alchemy_card import AlchemyCardEditor, AlchemyCardRenderer
from card_builder.CardTypes.trank_card import TrankCardEditor, TrankCardRenderer


_EDITORS = {
    "Spells":    SpellCardEditor,
    "Prowess":   SpellCardEditor,
    "Loot":      LootCardEditor,
    "Equipment": EquipmentCardEditor,
    "Alchemy":   AlchemyCardEditor,
    "Trank":     TrankCardEditor,
}

_RENDERERS = {
    "Spells":    SpellCardRenderer,
    "Prowess":   SpellCardRenderer,
    "Loot":      LootCardRenderer,
    "Equipment": LootCardRenderer,
    "Alchemy":   AlchemyCardRenderer,
    "Trank":     TrankCardRenderer,
}


def get_editor(card_type: str):
    return _EDITORS.get(card_type, SpellCardEditor)


def get_renderer(card_type: str):
    return _RENDERERS.get(card_type, SpellCardRenderer)
