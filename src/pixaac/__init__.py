"""PixaaC — Pixel Art as a Code."""

from .model import Palette, SpriteError, Tag
from .sdk import Frame, Layer, Sprite

__all__ = ["Frame", "Layer", "Palette", "Sprite", "SpriteError", "Tag"]
__version__ = "0.1.0"
