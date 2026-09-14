"""Moonlit Market: python examples/moonlit_market.py.

All artwork is drawn with PixaaC. Pillow only arranges the review contact sheet.
"""
from pathlib import Path
import sys

from PIL import Image, ImageDraw
from pixaac import Sprite


PALETTE = {
    "k": "#191c32", "d": "#34344f", "v": "#605175", "m": "#a17a97",
    "o": "#c66846", "a": "#ee9e58", "y": "#ffd28a", "w": "#fff0c9",
    "b": "#294e65", "t": "#42868c", "c": "#83c5bb", "g": "#bde3b7",
    "r": "#b65170", "p": "#ee8d9a",
    # Material roles can share RGB values without sharing recoloring behavior.
    # F/O/H/C = fur base/shadow/highlight/cream; L/E/G/I = lantern brass/ember/glow/core.
    "F": "#ee9e58", "O": "#c66846", "H": "#ffd28a", "C": "#fff0c9",
    "L": "#ffd28a", "E": "#c66846", "G": "#ffd28a", "I": "#fff0c9",
}


def star(layer, x, y, color="y"):
    layer.stamp(f".{color}.\n{color}{color}{color}\n.{color}.", x=x - 1, y=y - 1)


def fox_tail(layer, *, curled=False):
    """Redraw an independently editable tail: the tip curls inward on inhalation."""
    layer.clear()
    if curled:
        layer.polygon([(24, 29), (30, 27), (32, 22), (30, 19), (33, 18),
                       (36, 22), (36, 29), (32, 34), (24, 34)], "O")
        layer.polygon([(30, 19), (33, 18), (36, 22), (35, 26),
                       (32, 27), (32, 22)], "C")
    else:
        layer.polygon([(24, 29), (31, 26), (34, 19), (36, 22), (36, 29),
                       (32, 34), (24, 34)], "O")
        layer.polygon([(31, 26), (34, 19), (36, 22), (36, 27), (34, 29)], "C")
    layer.outline("k")


def fox_arm(layer, *, raised=False):
    layer.clear()
    if raised:
        layer.line((12, 25), (9, 27), "k")
        layer.line((12, 24), (9, 26), "F")
    else:
        layer.line((12, 26), (8, 28), "k")
        layer.line((12, 25), (8, 27), "F")


def build_fox():
    s = Sprite(40, 40, name="lantern-fox", palette=PALETTE)
    shadow = s.layer("shadow")
    shadow.ellipse((7, 34, 32, 37), "d")
    tail = s.layer("tail")
    fox_tail(tail)
    feet = s.layer("feet")
    feet.rect((12, 32, 16, 34), "O")
    feet.rect((22, 32, 26, 34), "O")
    feet.outline("k")
    coat = s.layer("coat")
    coat.polygon([(13, 21), (23, 21), (27, 31), (24, 33), (10, 33)], "b")
    coat.polygon([(13, 23), (16, 24), (14, 31), (11, 31)], "t")
    coat.line((19, 24), (19, 31), "t")
    coat.pixels([(20, 26), (20, 30)], "L")
    coat.outline("k")
    head = s.layer("head")
    head.polygon([(8, 6), (15, 10), (23, 10), (29, 5), (29, 18),
                  (24, 23), (14, 23), (8, 18)], "F")
    head.polygon([(9, 7), (13, 11), (10, 13)], "O")
    head.polygon([(25, 11), (28, 7), (28, 13)], "O")
    head.polygon([(8, 17), (14, 18), (18, 21), (19, 23), (13, 22)], "C")
    head.polygon([(29, 17), (24, 18), (20, 21), (19, 23), (25, 22)], "C")
    head.line((15, 11), (22, 11), "H")
    head.outline("k")
    face = s.layer("face")
    face.stamp("kk........kk\nkC........kC", x=13, y=15)
    face.line((18, 19), (20, 19), "k")
    face.pixel(19, 20, "k")
    scarf = s.layer("scarf")
    scarf.line((13, 23), (24, 23), "r")
    scarf.line((14, 24), (23, 24), "p")
    scarf.polygon([(24, 24), (29, 25), (29, 28), (25, 26)], "r")
    arm = s.layer("arm")
    fox_arm(arm)
    lantern = s.layer("lantern")
    lantern.rect((4, 27, 8, 29), "L", fill=False)
    lantern.rect((3, 30, 9, 35), "k")
    lantern.rect((4, 30, 8, 34), "E")
    lantern.rect((5, 30, 7, 33), "G")
    lantern.line((6, 31), (6, 33), "I")
    lantern.line((3, 29), (9, 29), "L")
    lantern.line((4, 35), (8, 35), "L")
    # Exercise live handles across a rename and structural changes across frames.
    s.rename_layer("coat", "body")
    s.frame().duration_ms = 420
    up = s.add_frame("breathe-in", copy_from=0, duration_ms=180)
    up.shift_layers(["body", "head", "face", "scarf"], 0, -1)
    fox_tail(up.get_layer("tail"), curled=True)
    fox_arm(up.get_layer("arm"), raised=True)
    up.get_layer("lantern").shift(1, -1)
    blink = s.add_frame("blink", copy_from="breathe-in", duration_ms=100)
    blink.get_layer("face").clear(region=(13, 14, 24, 15))
    blink.get_layer("face").line((13, 15), (14, 15), "k")
    blink.get_layer("face").line((23, 15), (24, 15), "k")
    exhale = s.add_frame("exhale", copy_from=0, duration_ms=180)
    # The scarf settles a beat after the body; feet and shadow stay planted.
    cloth = exhale.get_layer("scarf")
    cloth.clear(region=(24, 24, 30, 29))
    cloth.polygon([(24, 24), (28, 26), (27, 29), (25, 27)], "r")
    cloth.pixel(26, 26, "p")
    s.tag("idle", 0, 3)
    s.tag("reverse-reaction", 1, 3, direction="reverse", loop=False)
    s.tag("breathing", 0, 1, direction="pingpong")
    return s


def build_potion():
    s = Sprite(24, 24, name="potion-mint", palette=PALETTE)
    glass = s.layer("glass")
    glass.polygon([(9, 5), (14, 5), (14, 9), (18, 13), (19, 18),
                   (16, 21), (7, 21), (4, 18), (5, 13), (9, 9)], "b")
    glass.outline("k")
    liquid = s.layer("liquid")
    liquid.polygon([(6, 14), (17, 14), (18, 18), (15, 20), (8, 20), (5, 18)], "t")
    liquid.line((7, 14), (16, 14), "g")
    liquid.line((8, 19), (15, 19), "c")
    liquid.pixels([(9, 16), (14, 18)], "g")
    shine = s.layer("shine")
    shine.line((7, 11), (6, 13), "c")
    shine.line((6, 15), (6, 17), "w")
    shine.pixel(8, 19, "w")
    cork = s.layer("cork")
    cork.rect((9, 3, 14, 6), "o")
    cork.line((9, 3), (14, 3), "y")
    cork.line((10, 5), (12, 5), "a")
    cork.outline("k")
    seal = s.layer("seal")
    seal.rect((10, 10, 13, 12), "y")
    seal.pixel(11, 11, "o")
    return s


def pine(layer, x, y, height, color):
    for top, width in ((0, 3), (height // 4, 5), (height // 2, 7)):
        layer.polygon([(x, y + top), (x - width, y + top + height // 2),
                       (x + width, y + top + height // 2)], color)
    layer.rect((x - 1, y + height - 3, x + 1, y + height + 3), color)


def build_scene():
    s = Sprite(96, 64, name="moonlit-apothecary", palette=PALETTE)
    sky = s.layer("sky")
    sky.rect((0, 0, 95, 63), "k")
    sky.rect((0, 23, 95, 40), "d")
    sky.ellipse((67, 5, 81, 19), "y")
    sky.ellipse((63, 2, 77, 16), "k")
    for x, y in ((8, 9), (24, 5), (44, 12), (58, 5), (87, 22), (33, 17)):
        sky.pixel(x, y, "m")
    star(sky, 51, 7, "w")
    star(sky, 89, 10)
    trees = s.layer("trees")
    for x, y, h in ((3, 23, 21), (16, 19, 25), (85, 26, 20), (94, 19, 29)):
        pine(trees, x, y, h, "b")
    ground = s.layer("ground")
    ground.rect((0, 46, 95, 63), "b")
    ground.polygon([(32, 48), (53, 48), (70, 63), (16, 63)], "d")
    for x, y in ((4, 51), (13, 55), (80, 53), (89, 59), (8, 62), (73, 49)):
        ground.stamp(".t.\nttt", x=x, y=y)
    for x, y in ((36, 54), (44, 58), (29, 60), (56, 62)):
        ground.line((x, y), (x + 4, y), "v")
    light = s.layer("ground-light")
    # Broken pools and reflections lead the eye to the warm doorway.
    light.polygon([(41, 48), (50, 48), (59, 57), (33, 57)], "v")
    light.polygon([(43, 48), (48, 48), (52, 53), (39, 53)], "m")
    light.line((39, 54), (47, 54), "a")
    light.line((50, 56), (55, 56), "o")
    light.line((36, 58), (42, 58), "m")
    house = s.layer("shop")
    house.rect((27, 30, 65, 48), "o")
    house.rect((29, 32, 63, 47), "a")
    house.rect((40, 33, 51, 48), "k")
    house.rect((42, 35, 49, 46), "b")
    house.rect((43, 36, 48, 41), "y")
    house.line((45, 36), (45, 41), "o")
    house.pixel(48, 44, "y")
    for x in (30, 55):
        house.rect((x, 35, x + 7, 41), "k")
        house.rect((x + 1, 36, x + 6, 40), "y")
        house.line((x + 3, 36), (x + 3, 40), "o")
        house.line((x - 1, 42), (x + 8, 42), "r")
    timber = s.layer("timber")
    timber.line((28, 32), (64, 32), "o")
    for x in (28, 39, 52, 64):
        timber.line((x, 33), (x, 47), "o")
    for x, y in ((31, 44), (34, 46), (56, 45), (60, 43)):
        timber.line((x, y), (x + 2, y), "y")
    windows = s.layer("window-display")
    for x in (31, 56):
        windows.line((x, 36), (x + 5, 36), "w")
        windows.rect((x, 39, x + 1, 40), "t")
        windows.pixel(x + 1, 38, "b")
        windows.rect((x + 4, 39, x + 5, 40), "r")
        windows.pixel(x + 4, 38, "o")
    roof = s.layer("roof")
    roof.polygon([(23, 31), (33, 19), (61, 19), (70, 31)], "k")
    roof.polygon([(25, 29), (34, 20), (60, 20), (67, 29)], "r")
    roof.line((34, 20), (60, 20), "p")
    for y in (23, 26, 29):
        roof.line((34 - (y - 20), y), (60 + (y - 20) // 2, y), "o")
        for x in range(35 + y % 2 * 3, 60, 7):
            roof.line((x, y - 2), (x, y), "p")
    roof.line((24, 31), (68, 31), "d")
    roof.line((29, 30), (39, 30), "y")
    roof.line((54, 30), (63, 30), "a")
    for x, y in ((27, 28), (29, 27), (63, 27), (65, 29)):
        roof.line((x, y), (x + 1, y), "t")
    sign = s.layer("sign")
    sign.line((66, 32), (75, 32), "y")
    sign.line((73, 32), (73, 35), "o")
    sign.rect((69, 35, 78, 44), "k")
    sign.rect((70, 36, 77, 43), "a")
    sign.stamp("..tt..\n..tt..\n.tggt.\ntggggt\n.tttt.", x=71, y=37)
    details = s.layer("details")
    for x in (23, 64):
        details.rect((x, 46, x + 5, 49), "o")
        details.stamp("..g..\n.ctc.\n..t..", x=x, y=43)
    details.line((38, 49), (53, 49), "m")
    details.line((40, 48), (51, 48), "y")
    details.line((40, 50), (51, 50), "d")
    fireflies = s.layer("fireflies")
    for x, y in ((17, 39), (80, 47), (10, 48)):
        fireflies.pixel(x, y, "g")
    s.frame().duration_ms = 400
    for i, (dx, dy) in enumerate(((1, -1), (2, 0), (1, 1)), 1):
        frame = s.add_frame(f"fireflies-{i}", copy_from=0, duration_ms=240)
        frame.shift_layers(["fireflies"], dx, dy)
    s.tag("night", 0, 3)
    return s


def preview_assets():
    fox = build_fox()
    arctic = fox.copy(name="arctic-fox")
    for key, color in {"F": "#c9e0dd", "O": "#799cac", "H": "#e8eac1",
                       "r": "#655986", "p": "#a397bb"}.items():
        arctic.palette.set(key, color)
    potion = build_potion()
    rose = potion.copy(name="potion-rose")
    amber = potion.copy(name="potion-amber")
    for sprite, colors in ((rose, ("#9a476f", "#ee8d9a", "#ffd0b0")),
                           (amber, ("#b66a39", "#eead52", "#ffe3a0"))):
        for key, color in zip(("t", "c", "g"), colors):
            sprite.palette.set(key, color)
    return {"fox": fox, "arctic": arctic, "mint": potion, "rose": rose,
            "amber": amber, "shop": build_scene()}


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    assets = preview_assets()
    for name, sprite in assets.items():
        assert sprite.validate() == [], (name, sprite.validate())
        sprite.export_png(output / f"{name}.png")
        sprite.export_png(output / f"{name}-preview.png", scale=6)
        sprite.export_sheet(output / f"{name}-sheet.png", columns=4, padding=1)
        sprite.save(output / f"{name}.sprite.json")
        if len(sprite.frames) > 1:
            tag = "night" if name == "shop" else "idle"
            sprite.export_gif(output / f"{name}.gif", tag=tag, scale=6)
            sprite.export_apng(output / f"{name}-animated.png", tag=tag, scale=6)
    # Presentation only: every source pixel above was authored using PixaaC.
    board = Image.new("RGB", (880, 710), "#121726")
    text = ImageDraw.Draw(board)
    text.text((32, 20), "MOONLIT MARKET  /  A PIXAAC FIELD TRIAL", fill="#fff0c9")
    text.text((32, 43), "Original Python-authored assets  |  nearest-neighbor enlargement", fill="#83c5bb")
    for name, x, label in (("fox", 40, "LANTERN FOX"), ("arctic", 300, "ARCTIC PALETTE")):
        board.paste(assets[name].render(scale=6), (x, 85), assets[name].render(scale=6))
        text.text((x + 40, 340), label, fill="#fff0c9")
    for name, x in (("mint", 595), ("rose", 675), ("amber", 755)):
        image = assets[name].render(scale=3)
        board.paste(image, (x, 160), image)
        text.text((x + 12, 250), name.upper(), fill="#83c5bb")
    text.text((595, 285), "ONE FACTORY / THREE ELIXIRS", fill="#fff0c9")
    scene = assets["shop"].render(scale=4)
    board.paste(scene, (40, 405))
    text.text((455, 430), "THE MOONLIT APOTHECARY", fill="#fff0c9")
    text.text((455, 457), "96 x 64  /  14-color shared palette", fill="#83c5bb")
    text.text((455, 485), "4-frame firefly loop", fill="#83c5bb")
    text.text((455, 533), "FOX: tail curl, lantern swing + blink", fill="#ee9e58")
    text.text((455, 558), "POTIONS: shared geometry, palette swaps", fill="#ee9e58")
    text.text((455, 583), "SCENE: layered procedural composition", fill="#ee9e58")
    board.save(output / "contact-sheet.png")
    review = Image.new("RGB", (880, 590), "#121726")
    labels = ImageDraw.Draw(review)
    labels.text((24, 16), "FOX POSES / native size above, 4x below", fill="#fff0c9")
    for i, frame in enumerate(assets["fox"].frames):
        x = 24 + i * 212
        native = assets["fox"].render(frame=i)
        enlarged = assets["fox"].render(frame=i, scale=4)
        review.paste(native, (x, 42), native)
        labels.text((x, 90), f"{frame.name} / {frame.duration_ms} ms", fill="#83c5bb")
        review.paste(enlarged, (x, 112), enlarged)
    labels.text((24, 300), "SHOP / native and 4x: window stock, worn eaves, warm doorstep", fill="#fff0c9")
    review.paste(assets["shop"].render(), (24, 338))
    review.paste(assets["shop"].render(scale=4), (190, 326))
    review.save(output / "pose-review.png")
    print(f"Built {len(assets)} assets in {output}")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/moonlit-market"))
