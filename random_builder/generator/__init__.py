"""
random_builder/generator/ – Card generation engine.

Public API:
    from random_builder.generator import CardGenerator
    gen = CardGenerator(content_data, containers, box_config, gen_config)
    cards = gen.generate(count=10)
"""
from .base import CardGenerator

__all__ = ["CardGenerator"]
