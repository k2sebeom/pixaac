"""Regenerate documented artwork: python -m assets.build_showcase."""
from pathlib import Path
import shutil

from assets.moonlit_market.build import PALETTE, build as build_market, preview_assets
from assets.tideglass.build import export as build_coast
from pixaac import Sprite


def main():
    root = Path(__file__).resolve().parent
    destination = root / "moonlit_market" / "showcase"
    destination.mkdir(parents=True, exist_ok=True)
    assets = preview_assets()
    for name in ("fox", "arctic", "shop"):
        assets[name].export_gif(
            destination / f"{name}.gif",
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
    potions.export_png(destination / "potions.png", scale=3)
    # Build once per collection; publish only images referenced by documentation.
    for collection, builder, names in (
        ("moonlit_market", build_market, ("contact-sheet.png", "pose-review.png")),
        ("tideglass", build_coast, ("review.png", "poses.png", "station-motion.gif")),
    ):
        generated = root / collection / "generated"
        showcase = root / collection / "showcase"
        builder(generated)
        showcase.mkdir(parents=True, exist_ok=True)
        for name in names:
            shutil.copyfile(generated / name, showcase / name)


if __name__ == "__main__":
    main()
