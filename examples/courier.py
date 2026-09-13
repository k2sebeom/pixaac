"""A frog courier with planted feet: python examples/courier.py [output-directory].

Every drawing function uses (x, y) as the top-left of the whole character's
32×32 bounding box. Parts share that origin and keep their own local offsets.
"""
from pathlib import Path
import sys

from pixaas import Layer, Sprite


PALETTE = {
    "k": "#20352e", "g": "#70b85d", "l": "#c3df85", "d": "#3e7955",
    "w": "#fff1ce", "b": "#a76840", "h": "#e4af65",
}


def draw_feet(layer: Layer, x: int, y: int) -> None:
    for offset in (7, 19):
        layer.ellipse((x + offset, y + 25, x + offset + 5, y + 27), "g")
    layer.outline("k")


def draw_body(layer: Layer, x: int, y: int) -> None:
    layer.ellipse((x + 9, y + 16, x + 22, y + 25), "g")
    layer.ellipse((x + 12, y + 18, x + 19, y + 24), "l")
    layer.outline("k")


def draw_head(layer: Layer, x: int, y: int) -> None:
    layer.ellipse((x + 7, y + 8, x + 24, y + 18), "g")
    for offset in (9, 19):
        layer.ellipse((x + offset, y + 5, x + offset + 3, y + 10), "g")
        layer.rect((x + offset + 1, y + 6, x + offset + 2, y + 8), "w")
        layer.pixel(x + offset + 2, y + 7, "k")
    layer.line((x + 12, y + 15), (x + 19, y + 15), "d")
    layer.outline("k")


def draw_bag(layer: Layer, x: int, y: int) -> None:
    layer.line((x + 11, y + 18), (x + 23, y + 24), "b")
    layer.rect((x + 21, y + 20, x + 27, y + 25), "b")
    layer.line((x + 21, y + 20), (x + 27, y + 20), "h")
    layer.pixel(x + 24, y + 22, "w")


def build_courier() -> Sprite:
    sprite = Sprite(32, 32, name="courier", palette=PALETTE)
    for name, draw in (("feet", draw_feet), ("body", draw_body),
                       ("head", draw_head), ("bag", draw_bag)):
        draw(sprite.layer(name), 0, 0)
    sprite.frame().duration_ms = 220
    up = sprite.add_frame("up", copy_from=0, duration_ms=140)
    up.shift_layers(["head", "body", "bag"], 0, -2)
    sprite.tag("bounce", 0, 1, direction="pingpong")
    return sprite


def preview_assets() -> dict[str, Sprite]:
    courier = build_courier()
    blue = courier.copy(name="river-courier")
    blue.palette.set("g", "#63b8bd")
    blue.palette.set("l", "#b2e0d5")
    return {"courier": courier, "river": blue}


def build(output: Path) -> None:
    for name, sprite in preview_assets().items():
        sprite.export_png(output / f"{name}.png", scale=8)
        sprite.export_gif(output / f"{name}-bounce.gif", tag="bounce", scale=8)
        sprite.export_sheet(output / f"{name}-sheet.png", tag="bounce")
        sprite.save(output / f"{name}.sprite.json")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/courier"))
