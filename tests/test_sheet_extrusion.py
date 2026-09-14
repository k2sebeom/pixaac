import json

from PIL import Image
import pytest

from pixaac import Sprite, SpriteError


@pytest.mark.parametrize("scale,extrude,padding", [(1, 1, 0), (2, 3, 1), (3, 0, 2)])
def test_extrusion_clamps_texels_and_preserves_content(tmp_path, scale, extrude, padding):
    sprite = Sprite(2, 2, palette={"r": "#f00", "g": "#0f08", "b": "#00f"})
    sprite.layer().set_grid("rg\nb.")
    sprite.add_frame("second", copy_from=0, duration_ms=180).layer("base").flip()
    sprite.add_frame("third", copy_from=0, duration_ms=220)
    sprite.tag("reverse", 1, 2, direction="reverse", loop=False)
    path, metadata = sprite.export_sheet(
        tmp_path / "sheet.png", columns=2, scale=scale, padding=padding, extrude=extrude)
    info = json.loads(metadata.read_text())
    occupied = set()
    with Image.open(path) as sheet:
        for index, frame in enumerate(info["frames"]):
            rect = frame["frame"]
            x, y, w, h = (rect[key] for key in ("x", "y", "w", "h"))
            native = sprite.render(frame=index, scale=scale)
            assert sheet.crop((x, y, x + w, y + h)).tobytes() == native.tobytes()
            # Independent oracle: every extruded texel is the nearest edge pixel.
            for dy in range(-extrude, h + extrude):
                for dx in range(-extrude, w + extrude):
                    expected = native.getpixel((min(max(dx, 0), w - 1), min(max(dy, 0), h - 1)))
                    assert sheet.getpixel((x + dx, y + dy)) == expected
                    occupied.add((x + dx, y + dy))
        for y in range(sheet.height):
            for x in range(sheet.width):
                if (x, y) not in occupied:
                    assert sheet.getpixel((x, y)) == (0, 0, 0, 0)
    restored = Sprite.from_png(path)
    assert restored.width == sprite.width
    assert restored.height == sprite.height
    for index in range(3):
        assert restored.render(frame=index).tobytes() == sprite.render(frame=index).tobytes()
    tag = info["meta"]["frameTags"][0]
    assert (tag["from"], tag["to"], tag["direction"], tag["repeat"]) == (1, 2, "reverse", "1")


def test_extruded_nonzero_tag_keeps_rebased_frame_indices(tmp_path):
    sprite = Sprite(1, 1, palette={"a": "#fff"})
    sprite.layer().pixel(0, 0, "a")
    for name in ("start", "end"):
        sprite.add_frame(name, copy_from=0)
    sprite.tag("reaction", 1, 2, direction="pingpong", loop=False)
    path, metadata = sprite.export_sheet(tmp_path / "tag.png", tag="reaction", extrude=2)
    info = json.loads(metadata.read_text())
    assert [frame["sourceIndex"] for frame in info["frames"]] == [1, 2]
    restored = Sprite.from_png(path)
    assert [frame.name for frame in restored.frames] == ["start", "end"]
    assert restored._data.tag("reaction").frame_indices() == [0, 1]
    assert restored._data.tag("reaction").loop is False


@pytest.mark.parametrize("option,bad", [
    ("scale", 0), ("scale", 1.5), ("scale", True),
    ("padding", -1), ("padding", 0.5), ("padding", False),
    ("extrude", -1), ("extrude", 0.5), ("extrude", True),
    ("columns", 0), ("columns", -1), ("columns", 1.5), ("columns", True),
])
def test_invalid_sheet_geometry_preserves_files(tmp_path, option, bad):
    sprite = Sprite(2, 2)
    path, meta = tmp_path / "sheet.png", tmp_path / "sheet.json"
    path.write_bytes(b"existing image")
    meta.write_bytes(b"existing metadata")
    with pytest.raises(SpriteError, match=option):
        sprite.export_sheet(path, **{option: bad})
    assert path.read_bytes() == b"existing image"
    assert meta.read_bytes() == b"existing metadata"
