"""Build BOLT with palette-key grids through the AgentSprite Python API."""
from pathlib import Path
from PIL import Image, ImageDraw
from pixaas import api

ROOT = Path(__file__).resolve().parent
SPRITE = ROOT / "mechanic-robot.sprite.json"
COLORS = {
    "k": "#172332",  # ink
    "d": "#293b4b",  # deep steel
    "s": "#435c6a",
    "m": "#698591",
    "l": "#a6bdc2",
    "w": "#e5ece0",
    "b": "#733e35",  # warm shadow
    "r": "#b85837",
    "o": "#e8833e",
    "y": "#ffb657",
    "h": "#ffe0a0",
    "t": "#164653",  # visor
    "u": "#23747b",
    "c": "#43c8c4",
    "i": "#adfff0",
    "n": "#9b7859",  # leather
    "a": "#554337",
    "e": "#ee6154",
}
if not SPRITE.exists():
    api.new(SPRITE, 128, 128, name="BOLT — workshop mechanic", layer="legs")
api.palette_set_many(SPRITE, COLORS)
from pixaas.model import Sprite
existing = [layer.name for layer in Sprite.load(SPRITE).frames[0].layers]


def layer(name):
    global im, draw
    if name not in existing:
        api.layer_add(SPRITE, name)
        existing.append(name)
    im = Image.new("L", (128, 128), ord("."))
    draw = ImageDraw.Draw(im)


def poly(points, key):
    draw.polygon(points, fill=ord(key))


def rect(box, key):
    draw.rectangle(box, fill=ord(key))


def line(points, key, width=1):
    draw.line(points, fill=ord(key), width=width)


def ellipse(box, key):
    draw.ellipse(box, fill=ord(key))


def bolt(x, y):
    rect((x-1, y-1, x+2, y+2), "k")
    rect((x-1, y-1, x+1, y+1), "l")
    rect((x, y, x+1, y), "s")


def save(name):
    data = list(im.get_flattened_data())
    grid = "\n".join("".join(chr(c) for c in data[y*128:(y+1)*128]) for y in range(128))
    api.draw_set(SPRITE, grid, layer=name, show="none")


layer("legs")
# Pelvis and independently articulated legs.
poly([(43,79),(78,79),(83,88),(77,98),(44,98),(38,89)], "k")
poly([(45,82),(76,82),(79,88),(73,94),(46,94),(42,88)], "s")
rect((50,85,70,89), "d")
for x in (43, 68):
    rect((x,92,x+15,110), "k")
    rect((x+3,93,x+12,108), "s")
    rect((x+4,94,x+6,107), "l")
    for y in (96,100,104):
        rect((x+7,y,x+12,y+1), "d")
    poly([(x-3,101),(x+13,101),(x+16,105),(x+15,115),(x-4,115),(x-5,107)], "k")
    poly([(x-1,103),(x+11,103),(x+13,106),(x+12,112),(x-2,112),(x-3,107)], "r")
    rect((x,103,x+10,105), "y")
    rect((x,106,x+10,110), "o")
    rect((x+2,107,x+8,108), "y")
# Wide, slightly splayed safety boots.
poly([(38,111),(56,111),(60,116),(60,122),(33,122),(33,116)], "k")
poly([(39,113),(53,113),(56,116),(56,118),(36,118),(36,116)], "m")
rect((38,113,51,114), "l")
rect((35,119,58,120), "d")
poly([(69,111),(83,111),(91,116),(91,122),(66,122),(66,116)], "k")
poly([(71,113),(81,113),(87,116),(88,118),(69,118),(69,115)], "m")
line([(72,113),(80,113),(84,115)], "l", 1)
rect((68,119,89,120), "d")
for x in (38,44,50,72,78,84):
    rect((x,119,x+1,121), "s")
save("legs")

layer("rear-arm")
# Right shoulder and bent forearm.
poly([(80,49),(92,49),(100,56),(99,67),(92,73),(82,67)], "k")
poly([(84,52),(91,52),(97,57),(95,64),(87,67),(83,63)], "r")
poly([(84,52),(91,52),(95,56),(86,58),(83,57)], "y")
poly([(88,60),(96,58),(95,64),(88,67)], "o")
ellipse((88,65,101,78), "k")
ellipse((91,68,99,76), "m")
ellipse((94,70,98,74), "d")
poly([(95,73),(101,63),(110,65),(108,79),(102,84),(95,81)], "k")
poly([(99,73),(103,67),(107,68),(105,77),(101,80),(98,78)], "s")
line([(101,71),(104,70),(103,76)], "l", 2)
save("rear-arm")

layer("torso")
# Neck piston, dark side wall, and faceted orange chest.
rect((51,42,72,53), "k")
rect((55,44,68,51), "m")
rect((55,47,68,48), "d")
poly([(42,49),(75,47),(87,55),(88,75),(81,85),(41,85),(35,74),(35,57)], "k")
poly([(75,50),(84,56),(85,73),(79,81),(73,76)], "b")
poly([(42,52),(72,50),(80,56),(79,74),(74,80),(42,80),(38,72),(38,58)], "o")
poly([(42,52),(71,50),(77,54),(44,56),(39,60),(38,58)], "h")
poly([(40,61),(43,57),(74,55),(77,58),(76,67),(40,68)], "y")
poly([(40,71),(76,70),(75,77),(71,80),(43,80)], "r")
line([(42,77),(69,77),(73,75)], "o", 2)
# Cream chest inset with embossed tiny 07 designation.
poly([(46,58),(69,58),(72,61),(72,69),(45,69),(44,62)], "k")
rect((47,60,69,67), "w")
rect((47,66,69,67), "l")
rect((49,61,54,65), "d")
rect((51,62,52,64), "w")
rect((58,61,63,61), "d")
line([(63,61),(60,65)], "d", 1)
# Three louvers and green status lamp.
for x in (48,54,60):
    line([(x,72),(x-1,74)], "k", 2)
rect((68,71,74,75), "k")
rect((69,72,72,73), "c")
rect((69,72,70,72), "i")
bolt(42,59)
bolt(76,59)
# Top-edge paint chips and side fasteners.
rect((59,53,63,53), "w")
rect((61,54,64,54), "b")
line([(40,68),(42,70)], "b")
rect((79,68,81,72), "d")
bolt(81,76)
# Leather utility belt, metal buckle, and hanging pouch.
poly([(39,79),(79,79),(81,83),(78,89),(41,89),(38,85)], "k")
rect((41,81,77,86), "a")
rect((42,81,76,82), "n")
rect((56,80,66,88), "k")
rect((58,81,64,87), "l")
rect((60,83,62,85), "d")
poly([(70,82),(81,82),(82,93),(78,96),(70,93)], "k")
rect((72,84,79,91), "n")
rect((72,84,79,86), "a")
rect((75,85,76,86), "y")
# Two little tools clipped to the belt.
rect((43,79,46,92), "k")
rect((44,80,45,88), "l")
rect((43,88,46,92), "r")
rect((49,81,51,93), "k")
rect((50,82,50,91), "y")
save("torso")

layer("head")
# Antenna with a red service beacon.
line([(70,24),(77,15),(80,15)], "k", 4)
line([(71,22),(77,16),(80,16)], "m", 1)
ellipse((78,9,86,17), "k")
ellipse((80,11,84,15), "e")
rect((81,11,82,12), "h")
# Oversized angular helmet. Side ear modules sit behind the visor.
poly([(40,26),(45,19),(70,17),(79,21),(84,28),(84,43),(76,51),(44,49),(38,42),(37,30)], "k")
poly([(44,25),(48,21),(69,19),(77,23),(79,27),(44,30)], "y")
poly([(48,21),(68,19),(73,21),(47,24)], "h")
poly([(77,25),(81,29),(81,42),(74,48),(70,43),(72,29)], "r")
poly([(41,29),(44,26),(74,25),(78,29),(77,41),(72,46),(45,46),(41,41)], "o")
# Cream crown stripe gives the worker a recognizable silhouette.
poly([(55,21),(61,20),(62,25),(56,26)], "w")
rect((56,26,62,28), "l")
# Recessed, cool glass face.
poly([(44,30),(72,28),(77,31),(77,39),(71,44),(46,43),(42,39),(42,33)], "k")
poly([(46,32),(71,30),(74,32),(74,38),(70,41),(47,40),(45,38),(45,34)], "t")
line([(46,33),(49,32),(68,31)], "u", 1)
poly([(47,34),(54,33),(51,38),(47,38)], "u")
# Two friendly rectangular luminous eyes and a small mouth.
rect((50,34,55,37), "c")
rect((51,34,54,35), "i")
rect((65,33,70,36), "c")
rect((66,33,69,34), "i")
line([(58,39),(61,39),(62,38)], "c", 1)
# Side hinge and cheek plate.
poly([(35,31),(40,29),(44,33),(44,41),(39,44),(35,41)], "k")
rect((37,33,40,40), "m")
rect((37,33,39,34), "w")
rect((39,36,41,39), "s")
rect((79,31,85,41), "k")
rect((80,33,83,39), "s")
rect((81,34,83,35), "l")
line([(46,46),(68,47),(73,45)], "y", 1)
rect((55,46,63,48), "d")
rect((57,46,61,46), "m")
bolt(46,26)
rect((69,22,72,22), "b")
rect((70,21,72,21), "w")
save("head")

layer("left-arm")
# Large near shoulder, outlined round pivot, and diagonal forearm.
poly([(27,51),(37,49),(44,55),(44,66),(37,73),(24,68),(21,60)], "k")
poly([(28,53),(36,52),(41,56),(40,63),(36,68),(26,65),(24,60)], "o")
poly([(28,53),(36,52),(40,55),(28,57),(24,61),(24,58)], "h")
poly([(26,62),(37,64),(37,68),(27,65)], "r")
# Diagonal hazard stripe on the shoulder.
poly([(31,56),(34,55),(40,60),(39,64)], "b")
poly([(27,57),(29,56),(37,64),(34,64)], "b")
bolt(25,60)
ellipse((25,67,40,82), "k")
ellipse((28,70,37,79), "s")
ellipse((30,72,35,77), "m")
rect((31,73,34,76), "d")
poly([(25,77),(35,78),(36,86),(30,94),(19,90),(18,85)], "k")
poly([(25,80),(32,81),(32,86),(28,90),(22,87),(21,84)], "o")
line([(23,82),(25,81),(30,82)], "y", 2)
poly([(29,85),(32,84),(31,88),(28,90),(25,89)], "r")
# An articulated steel gripper, open at its tips.
poly([(20,88),(29,91),(30,99),(26,105),(21,105),(21,100),(24,97),(22,95),(19,98),(19,103),(14,101),(13,96)], "k")
poly([(20,91),(26,93),(27,98),(24,101),(23,100),(25,97),(23,93),(20,93),(17,97),(17,100),(15,99),(15,96)], "m")
line([(19,92),(21,92),(24,94)], "w", 1)
rect((27,94,28,97), "s")
save("left-arm")

layer("wrench")
# Open-ended spanner: dark silhouette, chamfered steel, and cutout jaws.
poly([(103,52),(98,47),(96,42),(97,35),(102,29),(105,28),
      (105,39),(110,42),(114,39),(114,28),(118,32),(122,38),
      (122,44),(117,50),(113,52),(112,84),(108,88),(103,86)], "k")
poly([(101,46),(99,41),(100,36),(102,33),(102,40),(109,46),
      (116,41),(116,33),(119,38),(119,43),(115,48),(110,50),
      (109,83),(107,85),(106,83),(106,50)], "m")
line([(100,40),(100,37),(102,34)], "w", 1)
line([(101,44),(106,48),(108,48)], "l", 2)
line([(117,35),(119,39),(119,42),(115,47),(111,49),(110,66)], "l", 1)
rect((106,53,107,64), "w")
rect((108,72,109,82), "s")
rect((107,81,109,83), "k")
save("wrench")

layer("right-grip")
# Fingers wrap over the wrench handle.
poly([(101,64),(107,62),(113,64),(115,69),(113,76),(103,77),(99,73),(99,68)], "k")
poly([(102,66),(106,65),(106,72),(103,74),(101,71)], "m")
rect((103,66,104,70), "w")
for y in (65,69,73):
    rect((108,y,113,y+2), "s")
    rect((108,y,112,y), "l")
rect((100,71,102,73), "d")
save("right-grip")

api.set_notes(SPRITE, "BOLT, friendly workshop mechanic. 128×128 native pixel art; transparent background. "
              "Warm orange enamel, cream helmet stripe, cyan LED eyes, brushed steel wrench. "
              "Light from upper left; 1–2px dark contour; no antialiasing. Separate limbs, head, tool, and grip for animation.")
api.export_png(SPRITE, ROOT / "mechanic-robot.png")
api.export_png(SPRITE, ROOT / "mechanic-robot-preview.png", scale=6, background="#243342")
print(api.info(SPRITE))
