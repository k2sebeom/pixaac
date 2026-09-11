"""agentsprite: a pixel-art sprite editor for AI agents (CLI + MCP server)."""

from .model import Frame, Layer, Palette, Sprite, SpriteError, Tag

__all__ = ["Frame", "Layer", "Palette", "Sprite", "SpriteError", "Tag", "main"]
__version__ = "0.1.0"


def main() -> None:
    from .cli import main as _main

    _main()
