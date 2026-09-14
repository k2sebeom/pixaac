import json
from pathlib import Path
import re
import runpy

from PIL import Image
import pytest

from pixaac import Palette, Sprite, SpriteError
from pixaac import model

ROOT = Path(__file__).resolve().parents[1]


def test_authoring_is_in_memory(monkeypatch):
    def unexpected_io(*args, **kwargs):
        raise AssertionError("drawing must not load or save a document")

    monkeypatch.setattr(model.Sprite, "load", unexpected_io)
    monkeypatch.setattr(model.Sprite, "save", unexpected_io)
    sprite = Sprite(8, 8, palette={"r": "#f00", "k": "#000"})
    layer = sprite.layer("body")
    assert layer.rect((2, 2, 4, 4), "r") == 9
    assert layer.rect((2, 2, 4, 4), "r") == 9
    assert layer.outline("k") == 12
    assert layer.bounds() == (1, 1, 5, 5)
    assert sprite.render().getpixel((2, 2)) == (255, 0, 0, 255)
    assert sprite.render().getpixel((0, 0)) == (0, 0, 0, 0)


def test_frames_layers_and_variants_are_independent():
    palette = Palette()
    palette.set("r", "#f00")
    palette.set("k", "#000")
    sprite = Sprite(8, 8, palette=palette)
    head = sprite.layer("head")
    head.rect((2, 2, 3, 3), "r")
    up = sprite.add_frame("up", copy_from=0, duration_ms=120)
    up.layer("head").shift(0, -1)
    up.layer("tool").pixel(6, 6, "k")
    assert sprite.layer("head").rows()[3][2] == "r"
    assert up.layer("head").rows()[3][2] == "."
    assert sprite.layer("tool").rows()[6][6] == "."
    variant = sprite.copy(name="blue")
    variant.palette.set("r", "#00f")
    variant.layer("head").clear()
    assert sprite.palette.rgba("r") == (255, 0, 0, 255)
    assert palette.rgba("r") == (255, 0, 0, 255)
    assert head.rows()[2][2] == "r"
    assert sprite.validate() == variant.validate() == []


def test_native_geometry_stamps_and_transparency():
    sprite = Sprite(8, 8, palette={"r": "#f00", "k": "#000"})
    layer = sprite.layer()
    layer.polygon([(-2, 1), (4, 1), (4, 4), (-2, 4)], "r")
    assert layer.bounds() == (0, 1, 4, 4)
    assert layer.histogram()["r"] == 20
    layer.stamp(".k", x=1, y=2)
    assert layer.rows()[2][:5] == "rrkrr"
    layer.stamp(".k", x=1, y=2, overwrite=True)
    assert layer.rows()[2][:5] == "r.krr"
    layer.polygon([(0, 0), (7, 0), (7, 7)], "k", fill=False)
    with pytest.raises(SpriteError, match="palette key"):
        layer.polygon([(0, 0), (1, 0), (1, 1)], "z")
    with pytest.raises(SpriteError, match="three points"):
        layer.polygon([(0, 0), (1, 0)], "k")
    with pytest.raises(SpriteError):
        layer.set_grid("z")
    with pytest.raises(SpriteError):
        Sprite(8, 8, palette={".": "#fff"})


def test_layer_visibility_and_handles_survive_resize():
    sprite = Sprite(4, 4, palette={"r": "#f00"})
    layer = sprite.layer("body")
    layer.pixel(1, 1, "r")
    layer.visible = False
    assert sprite.render().getbbox() is None
    layer.visible = True
    sprite.resize(6, 6, anchor="center")
    assert layer.bounds() == (2, 2, 2, 2)
    assert sprite.render(scale=2).getpixel((4, 4)) == (255, 0, 0, 255)


def test_exports_and_import_preserve_pixels_and_timing(tmp_path):
    sprite = Sprite(4, 4, palette={"r": "#f008"}, name="test")
    sprite.layer("body").pixel(1, 1, "r")
    sprite.add_frame("up", copy_from=0, duration_ms=120).layer("body").shift(0, -1)
    sprite.tag("idle", 0, 1, direction="pingpong")
    path = sprite.export_png(tmp_path / "nested/test.png", scale=3)
    with Image.open(path) as image:
        assert image.size == (12, 12)
        assert image.getpixel((3, 3)) == (255, 0, 0, 136)
    sheet, meta = sprite.export_sheet(tmp_path / "sheet.png", columns=2, padding=1)
    assert json.loads(meta.read_text())["meta"]["app"] == "pixaac"
    restored = Sprite.from_png(sheet)
    assert [f.name for f in restored.frames] == ["frame0", "up"]
    assert [f.duration_ms for f in restored.frames] == [100, 120]
    for i in range(2):
        assert restored.render(frame=i).tobytes() == sprite.render(frame=i).tobytes()
    saved = sprite.save(tmp_path / "snapshot.sprite.json")
    assert json.loads(saved.read_text())["format"] == "pixaac"
    assert Sprite.load(saved).layer("body").rows() == sprite.layer("body").rows()
    sprite.export_apng(tmp_path / "idle.png", tag="idle")
    with Image.open(tmp_path / "idle.png") as image:
        assert image.n_frames == 2
        image.seek(1)
        assert image.info["duration"] == 120
    sprite.export_gif(tmp_path / "idle.gif", tag="idle")
    assert len(sprite.export_frames(tmp_path / "frames")) == 2


@pytest.mark.parametrize("format_name", [None, "agentsprite", "pixaas", "pixaac"])
def test_legacy_documents_still_load(tmp_path, format_name):
    data = json.loads((ROOT / "assets/fixtures/hero.sprite.json").read_text())
    data["format"] = format_name
    path = tmp_path / "legacy.sprite.json"
    path.write_text(json.dumps(data))
    sprite = Sprite.load(path)
    assert sprite.validate() == []
    assert sprite.render().size == (sprite.width, sprite.height)


def test_one_shot_animation_playback(tmp_path):
    sprite = Sprite(4, 4, palette={"r": "#f00"})
    sprite.layer().pixel(1, 1, "r")
    sprite.add_frame("next", copy_from=0).layer("base").shift(1, 0)
    sprite.tag("once", 0, 1, loop=False)
    sprite.export_gif(tmp_path / "once.gif", tag="once")
    with Image.open(tmp_path / "once.gif") as image:
        assert image.n_frames == 2
        assert "loop" not in image.info
    sprite.export_apng(tmp_path / "once.png", tag="once")
    with Image.open(tmp_path / "once.png") as image:
        assert image.info["loop"] == 1


@pytest.mark.parametrize("duration", [0, -1, 1.5])
def test_invalid_duration_does_not_append_frame(duration):
    sprite = Sprite(4, 4)
    with pytest.raises(SpriteError, match="positive integer"):
        sprite.add_frame("bad", duration_ms=duration)
    with pytest.raises(SpriteError, match="positive integer"):
        sprite.frame().duration_ms = duration
    assert len(sprite.frames) == 1
    assert sprite.frame().duration_ms == 100


def test_readme_python_examples(tmp_path, monkeypatch):
    """The product contract's Python examples execute together, top to bottom."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(ROOT))
    blocks = re.findall(r"```python\n(.*?)```", (ROOT / "README.md").read_text(), re.S)
    namespace = {}
    for index, code in enumerate(blocks):
        exec(compile(code, f"README.md:python-block-{index + 1}", "exec"), namespace)
    assert namespace["fox"].validate() == []
    assert (tmp_path / "assets/generated/fox.png").exists()
    assert (tmp_path / "assets/generated/fox-sheet.json").exists()


def test_robot_example(tmp_path):
    example = runpy.run_path(str(ROOT / "assets/robot/build.py"))
    example["build"](tmp_path)
    sprite = Sprite.load(tmp_path / "bolt.sprite.json")
    assert (sprite.width, sprite.height) == (32, 32)
    assert len(sprite.frames) == 3
    assert sprite.validate() == []
    assert sprite.render(frame=0).tobytes() != sprite.render(frame="blink").tobytes()


def test_layer_management_across_frames_and_handle_lifetime():
    sprite = Sprite(4, 4, palette={"r": "#f00", "b": "#00f"})
    body = sprite.layer("body")
    body.pixel(1, 1, "r")
    tool = sprite.layer("tool")
    tool.pixel(1, 1, "b")
    pose = sprite.add_frame("pose", copy_from=0)
    pose_tool = pose.get_layer("tool")
    assert sprite.render().getpixel((1, 1)) == (0, 0, 255, 255)
    sprite.move_layer("tool", 1)
    assert sprite.layer_names() == ("base", "tool", "body")
    for i, frame in enumerate(sprite.frames):
        assert tuple(layer.name for layer in frame.layers) == sprite.layer_names()
        assert sprite.render(frame=i).getpixel((1, 1)) == (255, 0, 0, 255)
    sprite.rename_layer("tool", "bag")
    assert tool.name == pose_tool.name == "bag"
    tool.pixel(0, 0, "b")
    assert pose_tool.rows()[0][0] == "."
    with pytest.raises(SpriteError, match="already exists"):
        sprite.rename_layer("bag", "body")
    with pytest.raises(SpriteError, match="nonempty"):
        sprite.rename_layer("bag", "")
    with pytest.raises(SpriteError, match="no layer named.*have"):
        pose.get_layer("bagg")
    assert "bagg" not in sprite.layer_names()
    sprite.remove_layer("bag")
    sprite.layer("bag")  # Reusing a name must never revive a removed handle.
    for handle in (tool, pose_tool):
        with pytest.raises(SpriteError, match="was removed"):
            handle.pixel(0, 0, "r")
    assert sprite.validate() == []
    sprite.remove_layer("base")
    sprite.remove_layer("bag")
    with pytest.raises(SpriteError, match="at least one"):
        sprite.remove_layer("body")
    assert sprite.layer_names() == ("body",)
    assert sprite.validate() == []


@pytest.mark.parametrize("wrap", [False, True])
def test_shift_layers_clipping_wrapping_and_atomic_lookup(wrap):
    sprite = Sprite(4, 4, palette={"r": "#f00"})
    for name in ("head", "body", "bag"):
        sprite.layer(name).pixel(3, 0, "r")
    sprite.layer("feet").pixel(1, 3, "r")
    pose = sprite.add_frame("up", copy_from=0)
    before = pose.get_layer("head").rows()
    with pytest.raises(SpriteError, match="no layer named"):
        pose.shift_layers(["head", "typo"], 1, 0)
    assert pose.get_layer("head").rows() == before
    pose.shift_layers(["head", "body", "bag", "head"], 1, 0, wrap=wrap)
    for name in ("head", "body", "bag"):
        assert pose.get_layer(name).rows()[0] == ("r..." if wrap else "....")
        assert sprite.get_layer(name).rows() == before
    assert pose.get_layer("feet").rows() == sprite.get_layer("feet").rows()
    assert pose.shift_layers([], 1, 0) == 0
    with pytest.raises(SpriteError, match="sequence"):
        pose.shift_layers("head", 1, 0)


def test_courier_example_moves_parts_together(tmp_path):
    example = runpy.run_path(str(ROOT / "assets/courier/build.py"))
    example["build"](tmp_path)
    sprite = Sprite.load(tmp_path / "courier.sprite.json")
    pose = sprite.frame("up")
    assert sprite.validate() == []
    assert pose.get_layer("feet").rows() == sprite.get_layer("feet").rows()
    for name in ("head", "body", "bag"):
        original = sprite.get_layer(name).rows()
        assert pose.get_layer(name).rows() == original[2:] + ["." * 32] * 2
    body = pose.get_layer("body").rows()
    original_bag = sprite.get_layer("bag").rows()
    pose.get_layer("bag").clear()
    assert pose.get_layer("body").rows() == body
    assert sprite.get_layer("bag").rows() == original_bag
    restored = Sprite.from_png(tmp_path / "courier-sheet.png")
    assert restored.render().tobytes() == sprite.render().tobytes()
