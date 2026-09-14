"""Regenerate the README showcase: python -m scripts.build_readme_art."""
from pathlib import Path

from examples.moonlit_market import PALETTE, preview_assets
from pixaac import Sprite


def main():
    destination = Path(__file__).resolve().parents[1] / "docs" / "images"
    assets = preview_assets()
    for name in ("fox", "arctic", "shop"):
        assets[name].export_gif(
            destination / f"moonlit-{name}.gif",
            tag="night" if name == "shop" else "idle",
            scale=6 if name == "shop" else 4,
        )
    # Keep each potion's liquid palette distinct when assembling the row.
    potions = Sprite(80, 24, palette=PALETTE, name="moonlit-potions")
    for name, x, mapping in (
        ("mint", 0, {}),
        ("rose", 28, {"t": "1", "c": "2", "g": "3"}),
        ("amber", 56, {"t": "4", "c": "5", "g": "6"}),
    ):
        for layer in assets[name].frame().layers:
            potions.layer(f"{name}/{layer.name}").blit(layer, x=x, mapping=mapping)
    potions.export_png(destination / "moonlit-potions.png", scale=3)


if __name__ == "__main__":
    main()
