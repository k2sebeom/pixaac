import json

from PIL import Image
import pytest

from pixaas import Sprite


def animation(path):
    with Image.open(path) as image:
        loop = image.info.get("loop")
        frames = []
        for i in range(image.n_frames):
            image.seek(i)
            frames.append((image.convert("RGBA").tobytes(), image.info.get("duration")))
        return loop, frames


@pytest.mark.parametrize("direction", ["forward", "reverse", "pingpong"])
@pytest.mark.parametrize("end", [1, 3])
@pytest.mark.parametrize("loop", [False, True])
def test_tagged_sheet_round_trip(tmp_path, direction, end, loop):
    sprite = Sprite(4, 4, palette={"r": "#f00"})
    for i in range(4):
        frame = sprite.frame() if i == 0 else sprite.add_frame(f"pose{i}")
        frame.duration_ms = 100 + i * 40
        frame.layer("base").pixel(i, 1, "r")
    tag = sprite.tag("reaction", 1, end, direction=direction, loop=loop)
    sheet, metadata = sprite.export_sheet(tmp_path / "sheet.png", tag=tag.name, scale=2, padding=1)
    data = json.loads(metadata.read_text())
    exported_tag = data["meta"]["frameTags"][0]
    assert (exported_tag["from"], exported_tag["to"]) == (0, end - 1)
    assert [f["sourceIndex"] for f in data["frames"]] == list(range(1, end + 1))
    restored = Sprite.from_png(sheet)
    assert [(f.name, f.duration_ms) for f in restored.frames] == [
        (f.name, f.duration_ms) for f in sprite.frames[1:end + 1]
    ]
    for fmt in ("gif", "apng"):
        before = getattr(sprite, f"export_{fmt}")(tmp_path / f"before.{fmt}", tag=tag.name)
        after = getattr(restored, f"export_{fmt}")(tmp_path / f"after.{fmt}", tag=tag.name)
        assert animation(before) == animation(after)


@pytest.mark.parametrize("direction", ["forward", "reverse", "pingpong"])
def test_legacy_source_index_sheets(tmp_path, direction):
    sprite = Sprite(4, 4, palette={"r": "#f00"})
    for i in range(1, 4):
        sprite.add_frame(f"pose{i}", duration_ms=i * 100).layer("base").pixel(i, 0, "r")
    sprite.tag("old", 1, 3, direction=direction, loop=False)
    sheet, metadata = sprite.export_sheet(tmp_path / "legacy.png", tag="old")
    data = json.loads(metadata.read_text())
    data["meta"].pop("tagIndexSpace")
    data["meta"]["version"] = "0.1"
    for frame in data["frames"]:
        frame["index"] = frame.pop("sourceIndex")
    data["meta"]["frameTags"][0].update({"from": 1, "to": 3})
    if direction == "reverse":
        data["frames"].reverse()
    metadata.write_text(json.dumps(data))
    restored = Sprite.from_png(sheet)
    assert [f.name for f in restored.frames] == ["pose1", "pose2", "pose3"]
    assert animation(sprite.export_apng(tmp_path / "before.png", tag="old")) == animation(
        restored.export_apng(tmp_path / "after.png", tag="old"))
