"""Build BOLT and an idle animation: python examples/robot.py [output-directory]."""
from pathlib import Path
import sys

from pixaas import Layer, Sprite


PALETTE = {
    "k": "#172332", "s": "#435c6a", "m": "#819da6", "w": "#e5ece0",
    "r": "#b85837", "o": "#e8833e", "y": "#ffcb75", "t": "#164653",
    "c": "#43c8c4", "i": "#adfff0",
}


def boot(layer: Layer, x: int, y: int) -> None:
    layer.stamp("kkkkk\nkyook\nkorrk\nkwmsk\nkkkkk", x=x, y=y)


def build_robot(*, armor: str = "#e8833e", name: str = "bolt") -> Sprite:
    robot = Sprite(32, 32, name=name, palette={**PALETTE, "o": armor})
    legs = robot.layer("legs")
    for x in (10, 17):
        legs.rect((x, 23, x + 3, 27), "k")
        legs.rect((x + 1, 24, x + 2, 26), "m")
        boot(legs, x - 1, 26)

    body = robot.layer("body")
    body.polygon([(10, 15), (19, 15), (21, 17), (21, 21),
                  (19, 24), (10, 24), (8, 21), (8, 17)], "k")
    body.rect((10, 16, 19, 22), "o")
    body.line((10, 16), (19, 16), "y")
    body.line((19, 18), (19, 22), "r")
    body.rect((11, 18, 17, 20), "w")
    body.pixel(12, 19, "s")
    body.pixel(18, 21, "c")
    for x in (11, 13, 15):
        body.pixel(x, 22, "k")
    body.stamp("kkmwmkk\nkkmsmkk", x=11, y=23)

    arms = robot.layer("arms")
    arms.stamp(
        "..kkkk\n.kyyok\nkyorok\nkmorrk\n.kkkk\n.kmsk\n.ksmk\n"
        ".kyok\n.kork\nkmkkk\nkwksk\n.k.k",
        x=4, y=15,
    )
    arms.stamp("kkkk\nkyyok\nkorok\nkorrk\n.ksk\n.kmkkk\n..ksmk\n...kkk", x=20, y=15)

    head = robot.layer("head")
    head.rect((13, 13, 17, 15), "k")
    head.line((14, 14), (16, 14), "m")
    head.line((18, 5), (20, 3), "k")
    head.stamp(".kk\nkyok\n.kk", x=19, y=1)
    head.polygon([(10, 4), (18, 4), (21, 6), (22, 9),
                  (21, 12), (19, 14), (10, 14), (7, 11), (7, 7)], "k")
    head.rect((9, 6, 20, 12), "o")
    head.line((10, 5), (18, 5), "y")
    head.rect((13, 5, 14, 6), "w")
    head.rect((9, 7, 20, 11), "k")
    head.rect((10, 8, 19, 11), "t")
    for x in (11, 16):
        head.line((x, 8), (x + 1, 8), "i")
        head.line((x, 9), (x + 1, 9), "c")
    head.line((13, 11), (15, 11), "c")
    head.stamp("k\nm\ns\nk", x=7, y=8)
    head.stamp("k\nm\ns\nk", x=21, y=8)

    tool = robot.layer("tool")
    tool.stamp(
        ".k...k\nkwk.kmk\nkwk.kmk\nkmkkkmk\n.kwmmk\n..kmk\n..kwk\n..kwk\n"
        "..kmk\n..kmk\n..kmk\n..kmk\n..kmk\n..kmk\n..ksk\n..kkk",
        x=24, y=7,
    )
    tool.stamp(".kkk\nkmwmk\n.ksmk\n..kk", x=24, y=19)
    return robot


def build(output: Path) -> None:
    robot = build_robot()
    robot.export_png(output / "bolt.png")
    robot.export_png(output / "bolt-preview.png", scale=12, background="#243342")
    robot.frame().duration_ms = 200
    up = robot.add_frame("up", copy_from=0, duration_ms=140)
    up.layer("head").shift(0, -1)
    blink = robot.add_frame("blink", copy_from=0, duration_ms=100)
    face = blink.layer("head")
    face.replace({"i": "t", "c": "t"})
    for x in (11, 16):
        face.line((x, 9), (x + 1, 9), "c")
    robot.tag("idle", 0, 2, direction="pingpong")
    robot.export_apng(output / "bolt-idle.png", tag="idle", scale=8)
    robot.export_gif(output / "bolt-idle.gif", tag="idle", scale=8, background="#243342")
    for name, armor, highlight in (("ice", "#468fb5", "#9de1ed"),
                                   ("rose", "#b65e8b", "#ffb8d1")):
        variant = robot.copy(name=f"bolt-{name}")
        variant.palette.set("o", armor)
        variant.palette.set("y", highlight)
        variant.export_png(output / f"bolt-{name}.png", scale=8, background="#243342")
    robot.export_sheet(output / "bolt-sheet.png", columns=3, padding=1)
    robot.save(output / "bolt.sprite.json")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out"))
