"""An independent native 32×32 BOLT, drawn with a script via AgentSprite."""
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageDraw
from pixaac import api
from pixaac.model import Sprite

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "mechanic-robot-32-script.sprite.json"
COLORS = {
    "k": "#172332", "s": "#435c6a", "m": "#819da6", "w": "#e5ece0",
    "r": "#b85837", "o": "#e8833e", "y": "#ffcb75", "t": "#164653",
    "c": "#43c8c4", "i": "#adfff0",
}
started = perf_counter()
if not PATH.exists():
    api.new(PATH, 32, 32, name="BOLT — scripted pocket mechanic", layer="robot")
    api.layer_add(PATH, "wrench")
api.palette_set_many(PATH, COLORS)
im = Image.new("L", (32, 32), ord("."))
d = ImageDraw.Draw(im)


def rect(box, key):
    d.rectangle(box, fill=ord(key))


def poly(points, key):
    d.polygon(points, fill=ord(key))


def line(points, key, width=1):
    d.line(points, fill=ord(key), width=width)


def stamp(x, y, rows):
    for dy, row in enumerate(rows):
        for dx, key in enumerate(row):
            if key != ".":
                rect((x + dx, y + dy, x + dx, y + dy), key)


def save(layer):
    pixels = list(im.get_flattened_data())
    grid = "\n".join(
        "".join(chr(v) for v in pixels[y * 32:(y + 1) * 32])
        for y in range(32)
    )
    api.draw_set(PATH, grid, layer=layer, show="none")


# Legs use the same construction, with a one-pixel wider far boot.
rect((10, 22, 20, 25), "k")
rect((11, 23, 18, 24), "s")
for x in (10, 17):
    rect((x, 24, x + 3, 28), "k")
    rect((x + 1, 24, x + 2, 27), "m")
    rect((x + 2, 25, x + 2, 26), "s")
    stamp(x - 1, 26, ["kkkkk", "kyook", "korrk"])
    stamp(x - 2, 29, ["kwmmsk", "kkkkkk"])

# Arms underneath the chest: plated shoulders, exposed joints, open gripper.
stamp(4, 15, [
    "..kkkk",
    ".kyyok",
    "kyorok",
    "kmorrk",
    ".kkkk.",
    ".kmsk.",
    ".ksmk.",
    ".kyok.",
    ".kork.",
    "kmkkk.",
    "kwksk.",
    ".k.k..",
])
stamp(20, 15, [
    "kkkk..",
    "kyyok.",
    "korok.",
    "korrk.",
    ".ksk..",
    ".kmkkk",
    "..ksmk",
    "...kkk",
])

# Chamfered enamel chest.
poly([(10, 15), (19, 15), (21, 17), (21, 21),
      (19, 23), (10, 23), (8, 21), (8, 17)], "k")
poly([(10, 16), (18, 16), (20, 18), (20, 21),
      (18, 22), (10, 22), (9, 20), (9, 17)], "o")
line([(10, 16), (18, 16), (19, 17)], "y")
line([(20, 18), (20, 21), (18, 22), (10, 22)], "r")
rect((10, 18, 18, 20), "k")
rect((11, 18, 17, 19), "w")
rect((12, 18, 12, 19), "s")
rect((17, 20, 18, 20), "c")
for x in (11, 13, 15):
    rect((x, 21, x, 21), "k")
# Belt, square buckle, and a tool clipped on the left.
rect((10, 23, 19, 24), "k")
rect((11, 23, 18, 23), "s")
stamp(14, 23, ["mwm", "msm"])
rect((10, 23, 10, 25), "w")
rect((10, 25, 10, 26), "r")

# Neck and helmet, with a beacon antenna.
rect((13, 13, 17, 15), "k")
rect((14, 14, 16, 14), "m")
line([(18, 5), (20, 3), (20, 2)], "k")
stamp(19, 1, [".kk.", "kyok", ".kk."])
poly([(10, 4), (18, 4), (21, 6), (22, 9),
      (21, 12), (19, 14), (10, 14), (7, 11), (7, 7)], "k")
poly([(10, 5), (18, 5), (20, 7), (20, 11),
      (18, 13), (10, 13), (8, 10), (8, 7)], "o")
line([(9, 7), (10, 6), (18, 6), (19, 7)], "y")
line([(20, 8), (20, 11), (18, 13)], "r")
rect((13, 5, 14, 6), "w")
# Glass, evenly spaced two-pixel eyes, and a small expressive mouth.
poly([(10, 7), (18, 7), (20, 8), (20, 10),
      (18, 12), (10, 12), (9, 11), (9, 8)], "k")
rect((10, 8, 18, 11), "t")
for x in (11, 16):
    rect((x, 8, x + 1, 8), "i")
    rect((x, 9, x + 1, 9), "c")
line([(13, 11), (15, 11), (16, 10)], "c")
stamp(7, 8, ["kk", "wm", "sk", "kk"])
stamp(21, 8, ["k", "m", "s", "k"])
save("robot")

# Steel wrench and fingers wrapping over its handle.
im = Image.new("L", (32, 32), ord("."))
d = ImageDraw.Draw(im)
stamp(24, 7, [
    ".k...k.",
    "kwk.kmk",
    "kwk.kmk",
    "kmkkkmk",
    ".kwmmk.",
    "..kmk..",
    "..kwk..",
    "..kwk..",
    "..kmk..",
    "..kmk..",
    "..kmk..",
    "..kmk..",
    "..kmk..",
    "..kmk..",
    "..ksk..",
    "..kkk..",
])
stamp(24, 19, [".kkk.", "kmwmk", ".ksmk", "..kk."])
save("wrench")
api.set_notes(
    PATH,
    "Independent 32×32 script-drawn BOLT. Same ten-color palette and robot/wrench "
    "layer structure as the MCP version. Native pixels, no downsampling or antialiasing."
)
api.export_png(PATH, ROOT / "mechanic-robot-32-script.png")
api.export_png(
    PATH, ROOT / "mechanic-robot-32-script-preview.png",
    scale=12, background="#243342"
)

# A comparison with identical scale, background, and padding.
comparison = Image.new("RGB", (816, 432), "#243342")
cd = ImageDraw.Draw(comparison)
for x, title, source in (
    (16, "MCP", ROOT.parent / "mechanic-robot-32/mechanic-robot-32.png"),
    (416, "SCRIPT", ROOT / "mechanic-robot-32-script.png"),
):
    sprite = Image.open(source).convert("RGBA")
    assert sprite.size == (32, 32)
    cd.text((x + 8, 12), title, fill="#e5ece0")
    enlarged = sprite.resize((384, 384), Image.Resampling.NEAREST)
    comparison.paste(enlarged, (x, 32), enlarged)
comparison.save(ROOT / "comparison.png")
output = Image.open(ROOT / "mechanic-robot-32-script.png")
assert output.mode == "RGBA" and output.getpixel((0, 0))[3] == 0
assert len(Sprite.load(PATH).frames[0].layers) == 2
print(f"Built and verified 32×32 RGBA sprite and comparison in {perf_counter()-started:.3f}s")
