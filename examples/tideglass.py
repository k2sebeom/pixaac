"""Tideglass Station — hand-placed pixel clusters, authored entirely in PixaaC.

Run: uv run python examples/tideglass.py
Preview: uv run python -m pixaac.preview examples/tideglass.py --sprite station
"""
from pathlib import Path
import sys

from PIL import Image, ImageDraw

from pixaac import Sprite


PALETTE = {
    "k": "#111b30", "d": "#23334d", "s": "#354b65", "v": "#62738a",
    "b": "#244f65", "t": "#327c89", "c": "#6cb4b0", "i": "#b3dad0",
    "r": "#703f53", "o": "#ae6156", "a": "#e39a70", "y": "#f4ca88",
    "w": "#fff0c4", "g": "#41675c", "h": "#81a779",
    # Distinct roles: the beacon can change without recoloring plaster or stars.
    "L": "#fff0c4", "G": "#f4ca88",
    "R": "#f4ca8818", "B": "#f4ca8810",
}


def build_lighthouse():
    sprite = Sprite(32, 48, name="tideglass-lighthouse", palette=PALETTE)
    wall = sprite.layer("masonry")
    wall.polygon([(12, 18), (22, 18), (25, 44), (8, 44)], "v")
    wall.polygon([(12, 18), (17, 18), (17, 42), (9, 42)], "i")
    wall.line((12, 20), (11, 30), "w")
    wall.polygon([(10, 30), (23, 30), (23, 34), (10, 34)], "r")
    wall.rect((10, 30, 17, 33), "o")
    wall.line((10, 30), (16, 30), "a")
    wall.rect((14, 37, 19, 43), "k")
    wall.rect((15, 38, 18, 43), "r")
    wall.pixel(17, 40, "y")
    wall.rect((16, 23, 18, 26), "k")
    wall.line((16, 24), (16, 25), "G")
    for x, y in ((20, 28), (10, 36), (21, 38), (12, 22)):
        wall.line((x, y), (x + 1, y), "s")
    wall.line((7, 44), (26, 44), "k")
    wall.line((8, 43), (25, 43), "s")
    glass = sprite.layer("beacon")
    glass.rect((10, 10, 23, 17), "k")
    glass.rect((11, 11, 22, 16), "G")
    glass.rect((12, 11, 17, 15), "L")
    for x in (10, 16, 23):
        glass.line((x, 10), (x, 17), "d")
    glass.line((10, 17), (23, 17), "a")
    roof = sprite.layer("roof")
    roof.polygon([(8, 9), (16, 4), (19, 4), (25, 9)], "r")
    roof.line((11, 7), (16, 4), "a")
    roof.line((8, 10), (25, 10), "k")
    roof.line((17, 1), (17, 4), "k")
    roof.pixel(17, 1, "y")
    rail = sprite.layer("balcony")
    rail.line((7, 18), (26, 18), "k")
    rail.line((7, 21), (26, 21), "k")
    for x in (7, 11, 22, 26):
        rail.line((x, 18), (x, 21), "k")
    rail.line((8, 18), (15, 18), "a")
    sprite.frame().duration_ms = 240
    for index, position in enumerate((18, 20, 18), 1):
        frame = sprite.add_frame(f"sweep-{index}", copy_from=0, duration_ms=240)
        lamp = frame.get_layer("beacon")
        lamp.replace({"L": "G"})
        lamp.line((position, 11), (position, 15), "L")
    sprite.tag("beacon", 0, 3)
    return sprite


def build_boat():
    sprite = Sprite(32, 24, name="tideglass-cutter", palette=PALETTE)
    sail = sprite.layer("sail")
    sail.line((17, 2), (17, 19), "k")
    sail.polygon([(15, 3), (5, 15), (15, 14)], "i")
    sail.polygon([(14, 5), (8, 13), (14, 12)], "w")
    sail.polygon([(19, 6), (25, 15), (19, 14)], "o")
    sail.line((19, 8), (22, 13), "a")
    sail.line((6, 16), (24, 16), "k")
    hull = sprite.layer("hull")
    hull.polygon([(3, 18), (28, 18), (24, 22), (8, 22)], "k")
    hull.line((5, 18), (27, 18), "a")
    hull.line((7, 19), (25, 19), "o")
    hull.line((9, 20), (23, 20), "r")
    hull.pixels([(11, 19), (20, 19)], "y")
    sprite.frame().duration_ms = 240
    for index, dy in enumerate((-1, 0, 1), 1):
        pose = sprite.add_frame(f"bob-{index}", copy_from=0, duration_ms=240)
        pose.shift_layers(["sail", "hull"], 0, dy)
    sprite.tag("bob", 0, 3)
    return sprite


def place(frame, source, x, y, pose=0, prefix="prop", mapping=None):
    """Keep source parts editable and enforce explicit palette compatibility."""
    for layer in source.frame(pose).layers:
        frame.layer(f"{prefix}/{layer.name}").blit(layer, x=x, y=y, mapping=mapping)


def build_station():
    sprite = Sprite(160, 96, name="tideglass-station", palette=PALETTE)
    sky = sprite.layer("sky")
    sky.rect((0, 0, 159, 95), "k")
    sky.rect((0, 22, 159, 40), "d")
    sky.rect((0, 41, 159, 55), "s")
    # Small clusters and asymmetry keep the sky quiet around the landmark.
    for x, y in ((8, 13), (20, 7), (35, 19), (52, 6), (69, 15),
                 (82, 5), (103, 12), (122, 6), (149, 17), (137, 30)):
        sky.pixel(x, y, "v")
    sky.stamp(".i.\niwi\n.i.", x=39, y=8)
    sky.ellipse((125, 9, 139, 23), "i")
    sky.ellipse((121, 6, 135, 20), "k")
    cloud = sprite.layer("clouds")
    for x, y, width in ((3, 31, 29), (36, 26, 20), (111, 35, 28)):
        cloud.line((x, y), (x + width, y), "s")
        cloud.line((x + 5, y - 1), (x + width - 5, y - 1), "s")
        cloud.line((x + 9, y + 2), (x + width + 4, y + 2), "d")
    rays = sprite.layer("beacon-rays")
    rays.polygon([(57, 18), (0, 8), (0, 27), (57, 22)], "B")
    rays.polygon([(57, 19), (0, 14), (0, 23), (57, 21)], "R")
    coast = sprite.layer("distant-coast")
    coast.polygon([(0, 47), (12, 39), (21, 42), (32, 36), (48, 45),
                   (59, 42), (77, 53), (0, 55)], "d")
    coast.polygon([(117, 52), (133, 43), (143, 46), (152, 40), (159, 43),
                   (159, 56)], "d")
    sea = sprite.layer("sea")
    sea.rect((0, 55, 159, 95), "b")
    sea.line((0, 55), (159, 55), "t")
    for y in (58, 63, 70, 79, 89):
        for x in range((y * 7) % 19 - 6, 160, 23):
            sea.line((x, y), (x + 8 + y % 5, y), "t")
            if y > 66:
                sea.line((x + 3, y + 1), (x + 6, y + 1), "s")
    # Short broken crests avoid a uniform horizontal stripe texture.
    for x, y, width in ((8, 67, 5), (19, 81, 8), (42, 87, 3),
                         (85, 83, 6), (148, 75, 4), (107, 91, 7)):
        sea.line((x + 2, y), (x + width, y), "c")
        sea.line((x, y + 1), (x + width + 3, y + 1), "t")
    moonlight = sprite.layer("moon-path")
    for x, y, width in ((128, 57, 6), (125, 60, 13), (130, 64, 7),
                        (124, 68, 15), (128, 73, 11), (120, 79, 20),
                        (125, 86, 14), (117, 93, 25)):
        moonlight.line((x, y), (x + width, y), "c")
        moonlight.line((x + 2, y + 1), (x + width - 3, y + 1), "t")
    rock = sprite.layer("island")
    rock.polygon([(44, 55), (52, 49), (66, 48), (78, 52), (88, 62),
                  (82, 72), (65, 78), (44, 75), (34, 65)], "k")
    rock.polygon([(43, 57), (55, 51), (76, 53), (83, 62), (73, 68),
                  (60, 72), (42, 67)], "s")
    rock.polygon([(43, 58), (53, 54), (51, 62), (45, 68), (39, 64)], "v")
    rock.polygon([(57, 58), (64, 55), (62, 65), (56, 72), (52, 69)], "d")
    rock.polygon([(69, 58), (78, 57), (81, 63), (74, 68), (68, 72)], "d")
    rock.line((44, 70), (50, 73), "b")
    rock.line((64, 75), (72, 73), "t")
    foam = sprite.layer("shore-foam")
    for x, y, length in ((34, 68, 4), (39, 73, 8), (47, 77, 9), (62, 79, 10),
                         (77, 73, 6), (83, 68, 4)):
        foam.line((x, y), (x + length, y), "t")
        foam.line((x + 1, y), (x + length - 2, y), "c")
        foam.pixel(x + length + 2, y - 1, "t")
    grass = sprite.layer("turf")
    grass.polygon([(44, 53), (51, 49), (68, 49), (77, 52), (79, 56),
                   (67, 59), (53, 57), (44, 58)], "g")
    grass.line((46, 53), (53, 50), "h")
    grass.line((68, 50), (75, 52), "h")
    grass.line((50, 55), (59, 56), "h")
    grass.polygon([(58, 49), (64, 49), (68, 55), (63, 59), (60, 57)], "v")
    for x, y in ((45, 51), (72, 50), (77, 54), (49, 56)):
        grass.stamp(".h.\nghg", x=x, y=y)
    dock = sprite.layer("pier")
    for x in (78, 87, 97):
        dock.line((x, 64), (x, 73), "k")
        dock.line((x + 1, 65), (x + 1, 70), "r")
    dock.polygon([(73, 59), (100, 63), (100, 66), (73, 62)], "k")
    dock.line((74, 59), (100, 63), "a")
    dock.line((76, 61), (99, 64), "o")
    for x in (79, 84, 89, 94):
        dock.pixel(x, 61 + (x - 79) // 6, "r")
    lighthouse, boat = build_lighthouse(), build_boat()
    place(sprite.frame(), lighthouse, 44, 6, prefix="tower")
    place(sprite.frame(), boat, 96, 51, prefix="boat")
    foreground = sprite.layer("foreground")
    foreground.polygon([(0, 83), (8, 85), (14, 90), (25, 93), (29, 95), (0, 95)], "k")
    foreground.line((0, 83), (8, 85), "g")
    for x, y in ((3, 80), (10, 86), (18, 90)):
        foreground.line((x, y + 5), (x - 2, y - 2), "k")
        foreground.line((x, y + 5), (x + 2, y), "k")
        foreground.pixel(x - 2, y - 2, "g")
    # Rebuild each pose from independent source parts, retaining editable layers.
    sprite.frame().duration_ms = 240
    for index in range(1, 4):
        frame = sprite.add_frame(f"tide-{index}", copy_from=0, duration_ms=240)
        for name in sprite.layer_names():
            if name.startswith(("tower/", "boat/")):
                frame.get_layer(name).clear()
        place(frame, lighthouse, 44, 6, pose=index, prefix="tower")
        place(frame, boat, 96, 51, pose=index, prefix="boat")
        frame.get_layer("moon-path").shift((0, 1, 0, -1)[index], 0)
        # Small wave changes and beacon values preserve the composition.
        frame.get_layer("shore-foam").replace({"c": "i" if index == 2 else "t"})
        if index in (1, 2):
            frame.get_layer("beacon-rays").replace({"R": "B"})
    sprite.tag("night-watch", 0, 3)
    return sprite


def preview_assets():
    tower = build_lighthouse()
    storm = tower.copy(name="tideglass-storm-beacon")
    storm.palette.set("L", "#d3f6ed")
    storm.palette.set("G", "#6cb4b0")
    return {"station": build_station(), "lighthouse": tower,
            "storm-beacon": storm, "cutter": build_boat()}


def export(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    assets = preview_assets()
    for name, sprite in assets.items():
        sprite.export_png(directory / f"{name}.png")
        sprite.export_png(directory / f"{name}-preview.png", scale=6)
        sprite.export_apng(directory / f"{name}-motion.png", scale=4)
        sprite.export_gif(directory / f"{name}-motion.gif", scale=4)
        sprite.export_sheet(directory / f"{name}-sheet.png", columns=2, padding=2, extrude=1)
        sprite.save(directory / f"{name}.sprite.json")
    # Pillow arranges review imagery only; every art pixel comes from PixaaC.
    board = Image.new("RGB", (1040, 790), "#101827")
    draw = ImageDraw.Draw(board)
    draw.text((40, 20), "TIDEGLASS STATION  /  coastal asset study", fill="#b3dad0")
    board.paste(assets["station"].render(scale=6).convert("RGB"), (40, 48))
    draw.text((40, 646), "NATIVE 160 x 96", fill="#b3dad0")
    board.paste(assets["station"].render().convert("RGB"), (40, 670))
    for name, x in (("lighthouse", 275), ("storm-beacon", 475), ("cutter", 710)):
        image = assets[name].render(scale=2)
        board.paste(image, (x, 674), image)
        draw.text((x, 650), name.upper(), fill="#b3dad0")
    board.save(directory / "review.png")
    poses = Image.new("RGB", (1000, 820), "#101827")
    labels = ImageDraw.Draw(poses)
    for index, frame in enumerate(assets["station"].frames):
        x, y = 20 + index % 2 * 490, 32 + index // 2 * 316
        labels.text((x, y - 18), f"{frame.name} / {frame.duration_ms} ms", fill="#b3dad0")
        poses.paste(assets["station"].render(frame=index, scale=3).convert("RGB"), (x, y))
    for row, name in enumerate(("lighthouse", "storm-beacon", "cutter")):
        x = 30 + row * 330
        labels.text((x, 674), name.upper(), fill="#b3dad0")
        for index in range(4):
            image = assets[name].render(frame=index, scale=2)
            poses.paste(image, (x + index * 76, 700), image)
    poses.save(directory / "poses.png")


if __name__ == "__main__":
    export(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/tideglass"))
