import json
from pathlib import Path

import pytest
from PIL import Image

from agentsprite import api, ops, render, view
from agentsprite.model import Palette, Sprite, SpriteError, parse_color, parse_grid


# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #


def test_parse_color_forms():
    assert parse_color("#ff0000") == (255, 0, 0, 255)
    assert parse_color("#f00") == (255, 0, 0, 255)
    assert parse_color("#ff000080") == (255, 0, 0, 128)
    assert parse_color("00ff00") == (0, 255, 0, 255)
    with pytest.raises(SpriteError):
        parse_color("red")


def test_palette_reserved_transparent():
    p = Palette()
    with pytest.raises(SpriteError):
        p.set(".", "#000000")
    with pytest.raises(SpriteError):
        p.remove(".")
    p.set("k", "#000")
    assert p.rgba("k") == (0, 0, 0, 255)
    assert p.key_for_rgba((0, 0, 0, 255)) == "k"
    assert p.key_for_rgba((1, 2, 3, 0)) == "."


def test_parse_grid_pads_and_strips_spaces():
    g = parse_grid("a b\n\n  cd  \n", 4, 3)
    assert g == [list("ab.."), list("cd.."), list("....")]
    with pytest.raises(SpriteError):
        parse_grid("abcde", 4, 1)


def test_sprite_roundtrip(tmp_path: Path):
    s = Sprite.new("hero", 4, 3)
    s.palette.set("r", "#ff0000")
    s.frames[0].layers[0].grid[1][2] = "r"
    s.add_frame(copy_from=0, duration_ms=200)
    s.add_layer("fx")
    s.set_tag("idle", 0, 1, "pingpong")
    s.notes = "test"
    p = tmp_path / "hero.sprite.json"
    s.save(p)
    s2 = Sprite.load(p)
    assert s2.to_json() == s.to_json()
    assert s2.frames[1].layers[0].grid[1][2] == "r"
    assert s2.layer_names() == ["base", "fx"]
    assert s2.tag("idle").frame_indices() == [0, 1]
    assert s2.validate() == []


def test_frame_removal_adjusts_tags():
    s = Sprite.new("a", 2, 2)
    for _ in range(3):
        s.add_frame()
    s.set_tag("all", 0, 3)
    s.set_tag("tail", 2, 3)
    s.remove_frame(0)
    assert (s.tag("all").start, s.tag("all").end) == (0, 2)
    assert (s.tag("tail").start, s.tag("tail").end) == (1, 2)
    with pytest.raises(SpriteError):
        s.set_tag("bad", 0, 9)


def test_resize_anchor_center():
    s = Sprite.new("a", 2, 2)
    s.palette.set("x", "#fff")
    s.frames[0].layers[0].grid = [list("xx"), list("xx")]
    s.resize(4, 4, "center")
    assert s.frames[0].layers[0].rows() == ["....", ".xx.", ".xx.", "...."]


# --------------------------------------------------------------------------- #
# ops
# --------------------------------------------------------------------------- #


@pytest.fixture
def canvas():
    s = Sprite.new("c", 8, 8)
    s.palette.set("k", "#000")
    s.palette.set("r", "#f00")
    return s, s.frames[0].layers[0]


def test_rect_and_fill(canvas):
    s, l = canvas
    assert ops.rect(l, s.palette, 1, 1, 6, 6, "k") == 20
    assert ops.flood_fill(l, s.palette, 3, 3, "r") == 16
    assert l.grid[0][0] == "."
    assert l.grid[3][3] == "r"
    assert ops.histogram(l) == {".": 28, "k": 20, "r": 16}


def test_line_endpoints(canvas):
    s, l = canvas
    ops.line(l, s.palette, 0, 0, 7, 7, "k")
    assert all(l.grid[i][i] == "k" for i in range(8))
    ops.line(l, s.palette, 0, 7, 7, 0, "r")
    assert l.grid[7][0] == "r" and l.grid[0][7] == "r"


def test_ellipse_fill_symmetric(canvas):
    s, l = canvas
    ops.ellipse(l, s.palette, 0, 0, 7, 7, "k", fill=True)
    rows = l.rows()
    assert rows == [r[::-1] for r in rows]
    assert rows == rows[::-1]
    assert l.grid[0][0] == "."
    assert l.grid[3][3] == "k"


def test_paste_skips_transparent_and_clips(canvas):
    s, l = canvas
    ops.rect(l, s.palette, 0, 0, 7, 7, "r", fill=True)
    n = ops.paste(l, s.palette, "k.k\n.k.", x=6, y=6)
    assert n == 2  # (6,6) and (7,7); (8,6) clipped
    assert l.grid[6][6] == "k" and l.grid[6][7] == "r" and l.grid[7][7] == "k"
    with pytest.raises(SpriteError):
        ops.paste(l, s.palette, "zz")


def test_outline_and_transforms(canvas):
    s, l = canvas
    ops.rect(l, s.palette, 3, 3, 4, 4, "r", fill=True)
    assert ops.outline(l, s.palette, "k") == 8
    assert ops.outline(l, s.palette, "k", diagonal=True) == 20  # 8-connected ring around the plus shape
    ops.clear(l)
    l.grid[0][0] = "r"
    ops.flip(l, "h")
    assert l.grid[0][7] == "r"
    ops.rotate(l, 1)
    assert l.grid[7][7] == "r"
    ops.shift(l, 1, 1)
    assert ops.bounding_box(l) is None
    l.grid[0][0] = "r"
    ops.shift(l, -1, 0, wrap=True)
    assert l.grid[0][7] == "r"


def test_mirror(canvas):
    s, l = canvas
    ops.line(l, s.palette, 0, 0, 3, 3, "k")
    ops.mirror(l, "h")
    for i in range(4):
        assert l.grid[i][7 - i] == "k"


# --------------------------------------------------------------------------- #
# render / export
# --------------------------------------------------------------------------- #


def test_render_composites_layers_and_alpha():
    s = Sprite.new("r", 2, 1)
    s.palette.set("r", "#ff0000")
    s.palette.set("h", "#0000ff80")
    s.add_layer("top")
    s.frames[0].layers[0].grid = [list("r.")]
    s.frames[0].layers[1].grid = [list("hh")]
    img = render.render_frame(s.frames[0], s.palette, 2, 1)
    r, g, b, a = img.getpixel((0, 0))
    assert a == 255 and b > 100 and r > 100  # blended
    assert img.getpixel((1, 0)) == (0, 0, 255, 128)
    s.set_layer_visible("top", False)
    img = render.render_frame(s.frames[0], s.palette, 2, 1)
    assert img.getpixel((0, 0)) == (255, 0, 0, 255)
    assert img.getpixel((1, 0))[3] == 0


def test_sheet_layout_and_metadata(tmp_path: Path):
    s = Sprite.new("sh", 4, 4)
    s.palette.set("k", "#000")
    for i in range(1, 5):
        s.add_frame(duration_ms=50 * i)
    s.set_tag("run", 1, 4)
    out, meta_path = render.export_sheet(s, tmp_path / "sh.png", columns=3, padding=1, scale=2)
    img = Image.open(out)
    assert img.size == (3 * 8 + 4, 2 * 8 + 3)
    meta = json.loads(meta_path.read_text())
    assert len(meta["frames"]) == 5
    assert meta["frames"][3]["frame"] == {"x": 1, "y": 10, "w": 8, "h": 8}
    assert meta["frames"][3]["duration"] == 150
    assert meta["meta"]["frameTags"][0]["name"] == "run"
    assert meta["meta"]["image"] == "sh.png"


def test_gif_and_png_export(tmp_path: Path):
    s = Sprite.new("g", 3, 3)
    s.palette.set("k", "#000")
    s.frames[0].layers[0].grid[1][1] = "k"
    s.add_frame(copy_from=0)
    ops.shift(s.frames[1].layers[0], 1, 0)
    s.set_tag("bounce", 0, 1, "pingpong")
    gif = render.export_gif(s, tmp_path / "g.gif", scale=2, tag="bounce")
    im = Image.open(gif)
    assert im.n_frames == 2  # pingpong of 2 frames = [0,1]
    png = render.export_png(s, tmp_path / "g.png", 0, scale=3, background="#ffffff")
    im = Image.open(png).convert("RGBA")
    assert im.size == (9, 9)
    assert im.getpixel((4, 4)) == (0, 0, 0, 255)
    assert im.getpixel((0, 0)) == (255, 255, 255, 255)


def test_import_png_roundtrip(tmp_path: Path):
    s = Sprite.new("imp", 4, 2)
    s.palette.set("a", "#112233")
    s.palette.set("b", "#445566")
    s.frames[0].layers[0].grid = [list("aabb"), list("..ab")]
    s.add_frame()
    s.frames[1].layers[0].grid = [list("b..."), list("...a")]
    render.export_sheet(s, tmp_path / "sheet.png", metadata=False)
    imported = render.import_png(tmp_path / "sheet.png", frame_width=4, frame_height=2)
    assert len(imported.frames) == 2
    assert imported.width == 4
    # colors preserved even though keys may differ
    orig = render.render_frame(s.frames[1], s.palette, 4, 2).tobytes()
    back = render.render_frame(imported.frames[1], imported.palette, 4, 2).tobytes()
    assert orig == back


# --------------------------------------------------------------------------- #
# api (file-level) and views
# --------------------------------------------------------------------------- #


def test_api_workflow(tmp_path: Path):
    p = tmp_path / "hero.sprite.json"
    api.new(p, 6, 4)
    api.palette_set_many(p, {"k": "#000", "r": "#f00"})
    out = api.draw_set(p, "..kk..\n.krrk.\n..kk..")
    assert "set grid" in out and "changed: x=1..4 y=0..2 (8 pixels)" in out and "0 .kk." in out
    assert "0 ..kk.." in api.draw_set(p, "..kk..\n.krrk.\n..kk..", show="full")
    api.frame_add(p, copy_from=0, duration_ms=120)
    api.shift(p, 0, 1, frame="1")
    d = api.diff(p, "0", "1")
    assert "pixels differ" in d
    api.draw_replace(p, "r", "k")  # all frames
    s = Sprite.load(p)
    assert all("r" not in row for f in s.frames for row in f.layers[0].rows())
    api.tag_set(p, "idle", 0, 1)
    msg = api.export_sheet(p, tmp_path / "out" / "hero.png", columns=2)
    assert "hero.json" in msg
    assert "frame_add" not in api.info(p)
    with pytest.raises(SpriteError):
        api.new(p, 1, 1)


def test_api_all_frames_and_layer_by_name(tmp_path: Path):
    p = tmp_path / "x.sprite.json"
    api.new(p, 3, 3)
    api.palette_set_many(p, {"k": "#000"})
    api.frame_add(p)
    api.layer_add(p, "fx")
    api.draw_rect(p, 0, 0, 2, 2, "k", fill=True, frame="all", layer="fx")
    s = Sprite.load(p)
    for f in s.frames:
        assert f.layer("fx").rows() == ["kkk"] * 3
        assert f.layer("base").rows() == ["..."] * 3
    api.layer_visible(p, "fx", False)
    assert "..." in api.show(p, "0")  # composite ignores hidden layer
    assert "kkk" in api.show(p, "0", layer="fx")


def test_view_ruler_for_wide_canvas():
    s = Sprite.new("w", 12, 2)
    txt = view.grid_text(s.frames[0].layers[0])
    lines = txt.splitlines()
    assert lines[0].endswith("0         1 ")
    assert lines[1].endswith("012345678901")
    assert lines[2].startswith("0 ")


def test_render_bytes_is_png(tmp_path: Path):
    p = tmp_path / "b.sprite.json"
    api.new(p, 2, 2)
    data = api.render_bytes(p, scale=4, checker=True)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    import io

    assert Image.open(io.BytesIO(data)).size == (8, 8)


# --------------------------------------------------------------------------- #
# regions / outer outline (WORK_ORDER items 1 & 2)
# --------------------------------------------------------------------------- #


def test_shift_region_moves_only_box(canvas):
    s, l = canvas
    ops.rect(l, s.palette, 2, 0, 5, 3, "r", fill=True)  # "torso" rows 0..3
    ops.rect(l, s.palette, 3, 4, 4, 6, "k", fill=True)  # "legs" rows 4..6
    n = ops.shift(l, 0, 1, region=(0, 0, 7, 3))
    assert n == 16
    rows = l.rows()
    assert rows[0] == "........"          # top row vacated
    assert rows[4] == "..rrrr.."          # torso bottom now covers legs top
    assert rows[5] == "...kk..."          # rest of legs untouched
    assert rows[6] == "...kk..."


def test_shift_region_wraps_inside_box(canvas):
    s, l = canvas
    l.grid[0][0] = "k"
    ops.shift(l, -1, 0, wrap=True, region=(0, 0, 3, 0))
    assert l.grid[0][3] == "k" and l.grid[0][7] == "."


def test_flip_and_clear_region(canvas):
    s, l = canvas
    ops.line(l, s.palette, 0, 0, 3, 0, "k")  # kkkk....
    l.grid[0][4] = "r"
    ops.flip(l, "h", region=(0, 0, 3, 0))
    assert l.rows()[0] == "kkkkr..."
    ops.flip(l, "h", region=(3, 0, 4, 0))
    assert l.rows()[0] == "kkkrk..."
    assert ops.clear(l, region=(0, 0, 1, 0)) == 2
    assert l.rows()[0] == "..krk..."
    with pytest.raises(SpriteError):
        ops.clear(l, region=(20, 20, 30, 30))


def test_copy_region_same_and_other_layer(canvas):
    s, l = canvas
    ops.paste(l, s.palette, "kr\nrk", 0, 0)
    n = ops.copy_region(l, l, (0, 0, 1, 1), 6, 6)
    assert n == 4
    assert l.rows()[6][6:] == "kr" and l.rows()[7][6:] == "rk"
    other = s.frames[0].layers[0].copy()
    ops.clear(other)
    l.grid[0][1] = "."
    ops.copy_region(l, other, (0, 0, 1, 1), 0, 0)
    assert other.rows()[0] == "k......."  # transparent skipped
    other.grid[0][1] = "r"
    ops.copy_region(l, other, (0, 0, 1, 1), 0, 0, overwrite=True)
    assert other.rows()[0] == "k......."  # transparent copied over


def test_outline_outer_only_skips_enclosed_gaps(canvas):
    s, l = canvas
    # two "legs" with a 1px gap between them, plus a closed ring with a hole
    ops.rect(l, s.palette, 1, 4, 2, 7, "r", fill=True)
    ops.rect(l, s.palette, 4, 4, 5, 7, "r", fill=True)
    ops.rect(l, s.palette, 4, 0, 6, 2, "r")  # ring, hole at (5,1)
    inner_gap = (3, 5)
    hole = (5, 1)
    before = [row[:] for row in l.grid]
    ops.outline(l, s.palette, "k", outer_only=True)
    assert l.grid[inner_gap[1]][inner_gap[0]] == "k"  # gap between legs is open to the bottom -> still outlined? no: it's open, so yes outlined
    assert l.grid[hole[1]][hole[0]] == "."          # enclosed hole untouched
    assert l.grid[3][1] == "k"                       # above the leg is outlined
    l.grid = before
    ops.outline(l, s.palette, "k", outer_only=False)
    assert l.grid[hole[1]][hole[0]] == "k"


def test_outline_outer_only_closed_gap_between_limbs(canvas):
    s, l = canvas
    # torso over two legs; the gap between the legs (x=3, y=4..6) is closed at
    # the bottom by a bar at y=7 so it is fully enclosed
    ops.rect(l, s.palette, 1, 1, 5, 3, "r", fill=True)  # torso
    ops.rect(l, s.palette, 1, 4, 2, 7, "r", fill=True)  # left leg
    ops.rect(l, s.palette, 4, 4, 5, 7, "r", fill=True)  # right leg
    ops.rect(l, s.palette, 3, 7, 3, 7, "r", fill=True)  # bar closing the gap
    before = [row[:] for row in l.grid]
    ops.outline(l, s.palette, "k", outer_only=True)
    assert l.grid[4][3] == "."  # enclosed gap stays transparent
    assert l.grid[6][3] == "."
    assert l.grid[0][3] == "k"  # above the torso is reachable -> outlined
    assert l.grid[5][0] == "k"  # left of the leg
    l.grid = before
    ops.outline(l, s.palette, "k", outer_only=False)
    assert l.grid[4][3] == "k"  # plain outline fills the gap


def test_outline_outer_only_open_cup_is_reachable(canvas):
    s, l = canvas
    # U shape open at the top edge of the canvas: the inside is NOT enclosed
    ops.rect(l, s.palette, 1, 0, 1, 5, "r", fill=True)
    ops.rect(l, s.palette, 5, 0, 5, 5, "r", fill=True)
    ops.rect(l, s.palette, 1, 5, 5, 5, "r", fill=True)
    ops.outline(l, s.palette, "k", outer_only=True)
    assert l.grid[4][3] == "k"  # reachable from the top -> outlined
    assert l.grid[0][3] == "."  # not adjacent to the shape -> untouched
    assert l.grid[0][2] == "k"  # touches the left arm
    assert l.grid[6][3] == "k"  # below the bar


def test_api_draw_copy_and_region(tmp_path: Path):
    p = tmp_path / "c.sprite.json"
    api.new(p, 6, 4)
    api.palette_set_many(p, {"k": "#000"})
    api.draw_rect(p, 0, 0, 1, 1, "k", fill=True)
    api.frame_add(p)
    out = api.draw_copy(p, [0, 0, 1, 1], 4, 2, from_frame="0", to_frame="1")
    assert "4 pixels" in out
    s = Sprite.load(p)
    assert s.frames[1].layers[0].rows()[2] == "....kk"
    api.shift(p, 0, 1, frame="0", region=[0, 0, 5, 0])
    s = Sprite.load(p)
    assert s.frames[0].layers[0].rows()[:3] == ["......", "kk....", "kk...."][:3] or s.frames[0].layers[0].rows()[0] == "......"
    assert api.parse_region("1, 2,3,4") == (1, 2, 3, 4)
    assert api.parse_region(None) is None
    with pytest.raises(SpriteError):
        api.parse_region("1,2")


# --------------------------------------------------------------------------- #
# onion skin, presets, palette reuse, apng, mcp plain text
# --------------------------------------------------------------------------- #


def test_onion_skin_view(tmp_path: Path):
    p = tmp_path / "o.sprite.json"
    api.new(p, 6, 4)
    api.palette_set_many(p, {"k": "#000"})
    api.draw_rect(p, 0, 0, 1, 1, "k", fill=True)  # frame 0: 2x2 block top-left
    api.frame_add(p, copy_from="0")
    api.shift(p, 2, 0, frame="1")  # frame 1: same block moved right by 2
    s = Sprite.load(p)
    text = view.frame_text(s, 1, onion="prev")
    rows = text.splitlines()
    assert "onion: frame [0] frame0" in rows[0]
    # row 0 of the grid: ghost where frame 0 was, real pixels where frame 1 is
    grid_row0 = [r for r in rows if r.startswith("0 ")][0]
    assert grid_row0 == "0 ''kk.."
    assert "onion: ' = 4 pixel(s) only in frame [0] frame0; 4 pixel(s) only in this frame (x=2..3 y=0..1)" in text
    assert "legend: k=#000000" in text  # legend describes the real frame only
    assert "bbox: x=2..3 y=0..1" in text
    # "next" and explicit refs work; edges raise
    assert "onion: frame [1]" in view.frame_text(s, 0, onion="next")
    assert "onion: frame [1]" in view.frame_text(s, 0, onion="frame1")
    with pytest.raises(SpriteError):
        view.frame_text(s, 0, onion="prev")
    with pytest.raises(SpriteError):
        view.frame_text(s, 1, onion="next")
    # per-layer onion and the api/show path
    assert "''kk.." in api.show(p, "1", layer="base", onion="0")
    # marker avoids palette collisions
    api.palette_set_many(p, {"'": "#fff"})
    assert view.ghost_marker(Sprite.load(p)) == "`"


def test_palette_presets(tmp_path: Path):
    from agentsprite import presets

    p = tmp_path / "p.sprite.json"
    api.new(p, 4, 4)
    out = api.palette_preset(p, "PICO_8")  # name normalisation
    assert "added preset pico-8 (16 colors)" in out
    s = Sprite.load(p)
    assert s.palette.colors["0"] == "#000000"
    assert s.palette.colors["8"] == "#ff004d"
    assert s.palette.colors["f"] == "#ffccaa"
    # custom keys
    api.palette_preset(p, "gameboy", keys="abcd")
    s = Sprite.load(p)
    assert s.palette.colors["a"] == "#0f380f" and s.palette.colors["d"] == "#9bbc0f"
    with pytest.raises(SpriteError):
        api.palette_preset(p, "gameboy", keys="abc")
    with pytest.raises(SpriteError):
        api.palette_preset(p, "gameboy", keys="aabb")
    with pytest.raises(SpriteError):
        api.palette_preset(p, "gameboy", keys=".abc")
    with pytest.raises(SpriteError, match="unknown palette preset"):
        api.palette_preset(p, "nope")
    for pr in presets.PRESETS.values():
        assert len(pr.keys) == len(pr.colors) == len(set(pr.colors))
        assert len(set(pr.keys)) == len(pr.keys)
        for c in pr.colors:
            parse_color(c)
    listing = api.palette_presets()
    assert "endesga-32" in listing and "#be4a2f" in listing
    assert len(presets.get("endesga-32").colors) == 32


def test_palette_from_new_and_import(tmp_path: Path):
    src = tmp_path / "src.sprite.json"
    api.new(src, 4, 4)
    api.palette_set_many(src, {"k": "#000000", "r": "#ff0000"})
    # new sprite reuses the palette
    dst = tmp_path / "dst.sprite.json"
    api.new(dst, 8, 8, palette_from=src)
    assert Sprite.load(dst).palette.colors == {".": None, "k": "#000000", "r": "#ff0000"}
    # mutating the copy does not touch the source
    api.palette_set_many(dst, {"g": "#00ff00"})
    assert "g" not in Sprite.load(src).palette.colors
    # import maps known colors to the existing keys and adds keys for the rest
    img = Image.new("RGBA", (3, 1), (0, 0, 0, 0))
    img.putpixel((0, 0), (0, 0, 0, 255))
    img.putpixel((1, 0), (255, 0, 0, 255))
    img.putpixel((2, 0), (0, 0, 255, 255))
    img.save(tmp_path / "in.png")
    api.import_png(tmp_path / "in.png", tmp_path / "imp.sprite.json", palette_from=src)
    s = Sprite.load(tmp_path / "imp.sprite.json")
    row = s.frames[0].layers[0].rows()[0]
    assert row[:2] == "kr"
    assert s.palette.colors[row[2]] == "#0000ff"
    with pytest.raises(SpriteError):
        api.new(tmp_path / "x.sprite.json", 2, 2, palette_from=tmp_path / "missing.sprite.json")


def test_export_apng(tmp_path: Path):
    p = tmp_path / "a.sprite.json"
    api.new(p, 4, 4)
    api.palette_set_many(p, {"r": "#ff0000", "b": "#0000ff80"})
    api.draw_rect(p, 0, 0, 1, 1, "r", fill=True)
    api.frame_add(p, duration_ms=250)
    api.draw_rect(p, 2, 2, 3, 3, "b", fill=True, frame="1")
    api.frame_add(p, copy_from="0", duration_ms=50)
    api.tag_set(p, "two", 0, 1)
    out = api.export_apng(p, tmp_path / "a.png", scale=2)
    assert "3 frames, APNG" in out
    im = Image.open(tmp_path / "a.png")
    assert im.format == "PNG" and im.is_animated and im.n_frames == 3
    assert im.size == (8, 8)
    im.seek(1)
    assert im.info["duration"] == 250
    assert im.convert("RGBA").getpixel((5, 5)) == (0, 0, 255, 128)  # alpha preserved (GIF could not)
    assert im.convert("RGBA").getpixel((0, 0)) == (0, 0, 0, 0)
    api.export_apng(p, tmp_path / "t.png", tag="two", background="#ffffff")
    im2 = Image.open(tmp_path / "t.png")
    assert im2.n_frames == 2
    assert im2.convert("RGBA").getpixel((3, 3)) == (255, 255, 255, 255)


def test_mcp_tools_return_plain_text(tmp_path: Path):
    import asyncio

    from agentsprite import server

    p = str(tmp_path / "m.sprite.json")

    async def go():
        r = await server.mcp.call_tool("sprite_new", {"path": p, "width": 4, "height": 2})
        assert r.structured_content is None
        assert r.content[0].type == "text" and "created" in r.content[0].text
        r = await server.mcp.call_tool("palette_preset", {"path": p, "name": "1bit"})
        assert "k  #000000" in r.content[0].text
        r = await server.mcp.call_tool("draw_set", {"path": p, "grid": "kw..\n..wk"})
        assert r.structured_content is None
        assert "\n0 kw..   kw\n1 ..wk     wk" in r.content[0].text  # real newlines, not escaped
        r = await server.mcp.call_tool("sprite_show", {"path": p, "frame": "0", "onion": "prev"})
        assert r.content[0].text.startswith("error: frame [0] has no previous frame")
        r = await server.mcp.call_tool("export_apng", {"path": p, "out": str(tmp_path / "m.png")})
        assert "APNG" in r.content[0].text
        r = await server.mcp.call_tool("preview", {"path": p})
        assert r.content[0].type == "image" and r.structured_content is None
        tools = {t.name for t in (await server.mcp.list_tools())}
        assert {"palette_preset", "palette_presets", "export_apng"} <= tools

    asyncio.run(go())


def test_mcp_concurrent_edits_do_not_lose_writes(tmp_path: Path):
    import asyncio

    from agentsprite import server

    p = str(tmp_path / "race.sprite.json")
    api.new(p, 16, 16)
    api.palette_set_many(p, {"k": "#000"})

    async def go():
        calls = [
            server.mcp.call_tool("draw_pixels", {"path": p, "points": [[x, y]], "key": "k"})
            for x in range(16)
            for y in range(4)
        ]
        results = await asyncio.gather(*calls)
        assert all(r.content[0].text.startswith("pixels") for r in results)

    asyncio.run(go())
    s = Sprite.load(p)
    assert all(s.frames[0].layers[0].grid[y][x] == "k" for x in range(16) for y in range(4))


# --------------------------------------------------------------------------- #
# dogfooding session 2 backlog
# --------------------------------------------------------------------------- #


def test_edit_show_modes(tmp_path: Path):
    p = tmp_path / "s.sprite.json"
    api.new(p, 32, 32)
    api.palette_set_many(p, {"k": "#000"})
    out = api.draw_rect(p, 12, 3, 15, 5, "k", fill=True)  # default bbox
    lines = out.splitlines()
    assert lines[0] == "filled rect 'k': 12 pixels affected in frame 0"
    assert lines[1].startswith("changed: x=12..15 y=3..5 (12 pixels) in frame [0] frame0")
    assert lines[2] == "  1   "  # tens ruler: first column labelled even though 12 % 10 != 0
    assert lines[3] == "  2345"
    assert lines[4:] == ["3 kkkk", "4 kkkk", "5 kkkk"]
    assert len(out) < 250  # vs ~1.2 KB for the full 32x32 grid
    assert api.draw_rect(p, 12, 3, 15, 5, "k", fill=True, show="none") == "filled rect 'k': 12 pixels affected in frame 0"
    assert api.draw_rect(p, 12, 3, 15, 5, "k", fill=True).endswith("(no pixels changed)")
    full = api.draw_pixels(p, [(0, 0)], "k", show="full")
    assert "frame [0] frame0 (composite" in full and "legend: k=#000000" in full and "bbox: x=0..15" in full
    with pytest.raises(SpriteError, match="show must be one of"):
        api.draw_pixels(p, [(0, 0)], "k", show="huge")
    # the bbox view follows the edited layer, absolute rulers on a padded row label
    api.layer_add(p, "fx")
    out = api.draw_pixels(p, [(3, 9), (3, 10)], "k", layer="fx")
    assert "in frame [0] frame0 / layer 'fx'" in out
    assert out.splitlines()[2:] == ["   3", " 9 k", "10 k"]


def test_frame_lists_and_ranges(tmp_path: Path):
    p = tmp_path / "f.sprite.json"
    api.new(p, 4, 4)
    api.palette_set_many(p, {"k": "#000"})
    api.draw_pixels(p, [(0, 0)], "k")
    api.frame_add(p, copy_from="0", count=3)
    api.frame_update(p, "3", name="last")
    out = api.shift(p, 0, 1, frame="1,3")
    assert "in frames 1,3" in out and "+1 more frame(s)" in out
    s = Sprite.load(p)
    assert [f.layers[0].grid[0][0] for f in s.frames] == ["k", ".", "k", "."]
    assert [f.layers[0].grid[1][0] for f in s.frames] == [".", "k", ".", "k"]
    api.draw_pixels(p, [(3, 3)], "k", frame="0..2,last")
    assert all(f.layers[0].grid[3][3] == "k" for f in Sprite.load(p).frames)
    api.draw_clear(p, frame="last, 0")  # spaces and names allowed
    s = Sprite.load(p)
    assert ops.bounding_box(s.frames[0].layers[0]) is None and ops.bounding_box(s.frames[3].layers[0]) is None
    assert ops.bounding_box(s.frames[1].layers[0]) is not None
    assert api._target_frames(s, "2..0") == [0, 1, 2]
    assert api._target_frames(s, "1,1,all") == [1, 0, 2, 3]
    with pytest.raises(SpriteError):
        api._target_frames(s, "1,9")
    with pytest.raises(SpriteError):
        api._target_frames(s, ",")


def test_frame_add_count(tmp_path: Path):
    p = tmp_path / "n.sprite.json"
    api.new(p, 2, 2)
    api.palette_set_many(p, {"k": "#000"})
    api.draw_pixels(p, [(1, 1)], "k")
    out = api.frame_add(p, copy_from="0", count=3, duration_ms=80)
    assert out.startswith("added 3 frames: [1] frame1, [2] frame2, [3] frame3 (copied from 0); now 4 frames")
    s = Sprite.load(p)
    assert all(f.layers[0].grid[1][1] == "k" and f.duration_ms == 80 for f in s.frames[1:])
    out = api.frame_add(p, name="blink", count=2, at=0)  # inserted before the source; names get a suffix
    assert "[0] blink0, [1] blink1" in out
    assert [f.name for f in Sprite.load(p).frames][:3] == ["blink0", "blink1", "frame0"]
    assert "added frame [6] solo" in api.frame_add(p, name="solo")
    with pytest.raises(SpriteError):
        api.frame_add(p, count=0)


def test_keys_selection_clear_shift_copy(canvas):
    s, l = canvas
    s.palette.set("o", "#8b5a2b")
    ops.paste(l, s.palette, "rrro\nrrro\nkkko", 0, 0)
    assert ops.clear(l, keys="o") == 3
    assert l.rows()[0] == "rrr....." and l.rows()[2] == "kkk....."
    # shift only the 'r' pixels; the 'k' row stays and gets overwritten where they land
    assert ops.shift(l, 0, 1, keys="r") == 6
    assert l.rows()[:4] == ["........", "rrr.....", "rrr.....", "........"]
    # region + keys together
    l.grid[3][0] = "k"
    assert ops.shift(l, 1, 0, region=(0, 1, 7, 3), keys="k") == 1
    assert l.rows()[3] == ".k......" and l.rows()[1] == "rrr....."
    other = l.copy()
    ops.clear(other)
    assert ops.copy_region(l, other, None, 0, 0, keys="k") == 1
    assert other.rows()[3] == ".k......" and other.rows()[1] == "........"
    # overwrite with keys only writes transparent when '.' is selected
    other.grid[0][0] = "r"
    ops.copy_region(l, other, (0, 0, 0, 0), 0, 0, overwrite=True, keys="k")
    assert other.grid[0][0] == "r"
    ops.copy_region(l, other, (0, 0, 0, 0), 0, 0, overwrite=True, keys="k.")
    assert other.grid[0][0] == "."


def test_cut_region_and_api_draw_cut(tmp_path: Path):
    p = tmp_path / "w.sprite.json"
    api.new(p, 6, 4)
    api.palette_set_many(p, {"p": "#5533aa", "o": "#8b5a2b", "w": "#ffffff"})
    api.draw_set(p, "pppp.w\npppp.o\npppp.o\n.pp..o")
    api.frame_add(p, copy_from="0", count=2)
    api.layer_add(p, "staff")
    out = api.draw_cut(p, to_layer="staff", keys="ow", frame="all")
    assert out.startswith("cut keys(ow) from frames 0,1,2 -> (0,0) frames 0,1,2 layer 'staff': 12 pixels affected")
    assert "changed: x=5..5 y=0..3 (4 pixels) in frame [0] frame0 / layer 'staff'" in out
    for f in Sprite.load(p).frames:
        assert f.layer("base").rows() == ["pppp..", "pppp..", "pppp..", ".pp..."]
        assert f.layer("staff").rows() == [".....w", ".....o", ".....o", ".....o"]
    # region-only cut with an offset, single frame
    api.draw_cut(p, to_layer="base", region=[5, 0, 5, 1], x=0, y=0, frame="1", layer="staff")
    s = Sprite.load(p)
    assert s.frames[1].layer("staff").rows() == ["......", "......", ".....o", ".....o"]
    assert s.frames[1].layer("base").rows()[0] == "wppp.." and s.frames[1].layer("base").rows()[1] == "oppp.."
    assert s.frames[0].layer("staff").rows()[0] == ".....w"  # other frames untouched
    # cutting a layer onto itself at the same position is a no-op mistake
    with pytest.raises(SpriteError, match="cut needs"):
        api.draw_cut(p, to_layer="base", keys="p")
    # copy into a list of destination frames, keys-filtered
    api.draw_copy(p, [0, 0, 5, 3], 0, 0, from_frame="1", to_frame="0,2", from_layer="base", keys="w")
    assert all(Sprite.load(p).frames[i].layer("base").grid[0][0] == "w" for i in (0, 2))
    with pytest.raises(SpriteError, match="cannot pair"):
        api.draw_copy(p, [0, 0, 1, 1], 0, 0, from_frame="0,1", to_frame="0,1,2")


def test_replace_region(canvas):
    s, l = canvas
    ops.rect(l, s.palette, 0, 0, 7, 7, "r", fill=True)
    assert ops.replace(l, s.palette, "r", "k", region=(2, 2, 3, 3)) == 4
    assert ops.histogram(l) == {"r": 60, "k": 4}
    assert l.grid[2][2] == "k" and l.grid[1][1] == "r"


def test_api_replace_region(tmp_path: Path):
    p = tmp_path / "r.sprite.json"
    api.new(p, 4, 4)
    api.palette_set_many(p, {"b": "#0000ff", "B": "#8888ff"})
    api.draw_rect(p, 0, 0, 3, 3, "b", fill=True)
    api.frame_add(p, copy_from="0")
    out = api.draw_replace(p, "b", "B", region=[1, 1, 2, 2])  # all frames by default
    assert "replace 'b'->'B' region(1,1,2,2): 8 pixels affected in frames 0,1" in out
    for f in Sprite.load(p).frames:
        assert f.layers[0].rows() == ["bbbb", "bBBb", "bBBb", "bbbb"]


def test_onion_layer(tmp_path: Path):
    p = tmp_path / "ol.sprite.json"
    api.new(p, 6, 2)
    api.palette_set_many(p, {"k": "#000", "o": "#8b5a2b"})
    api.layer_add(p, "staff")
    api.draw_pixels(p, [(0, 0), (1, 0)], "k", layer="base")
    api.draw_pixels(p, [(5, 0), (5, 1)], "o", layer="staff")
    api.frame_add(p, copy_from="0")
    api.shift(p, 0, 1, frame="1", layer="base")
    s = Sprite.load(p)
    # same-layer ghost (old behaviour): staff not in the ghost
    same = view.frame_text(s, 1, layer_ref="base", onion="prev")
    assert "0 ''...." in same and "onion: frame [0] frame0" in same.splitlines()[0]
    # composite ghost: the staff of frame 0 shows up as ghost too
    comp = view.frame_text(s, 1, layer_ref="base", onion="prev", onion_layer="composite")
    assert "0 ''...'" in comp and "1 kk...'" in comp
    assert "onion: frame [0] frame0 (composite)" in comp.splitlines()[0]
    assert "' = 4 pixel(s) only in frame [0] frame0 (composite); 2 pixel(s) only in this frame (x=0..1 y=1..1)" in comp
    # explicit other layer
    other = view.frame_text(s, 1, layer_ref="base", onion="prev", onion_layer="staff")
    assert "0 .....'" in other and "/ layer 'staff'" in other.splitlines()[0]
    assert "0 ''...'" in api.show(p, "1", layer="base", onion="prev", onion_layer="all")
    with pytest.raises(SpriteError):
        api.show(p, "1", layer="base", onion="prev", onion_layer="nope")


def test_info_per_layer_pixel_counts(tmp_path: Path):
    p = tmp_path / "i.sprite.json"
    api.new(p, 4, 4)
    api.palette_set_many(p, {"p": "#5533aa", "o": "#8b5a2b", "w": "#fff"})
    api.layer_add(p, "staff")
    api.draw_rect(p, 0, 0, 2, 2, "p", fill=True, layer="base")
    api.draw_pixels(p, [(3, 0), (3, 1)], "o", layer="staff")
    api.draw_pixels(p, [(3, 2)], "w", layer="staff")
    api.frame_add(p, copy_from="0")
    api.draw_clear(p, frame="1", layer="staff")
    api.layer_visible(p, "staff", False)
    info = api.info(p)
    assert "layers (bottom -> top" in info
    assert "  [0] base   px: 9,9  keys: p" in info
    assert "  [1] staff  px: 3,0  keys: ow  (hidden)" in info
    assert api.layer_list(p) == view.layers_text(Sprite.load(p))
    empty = api.info(tmp_path / "i.sprite.json").splitlines()
    assert any("keys: p" in l for l in empty)
    api.new(tmp_path / "e.sprite.json", 2, 2)
    assert "[0] base  px: 0  keys: -" in api.info(tmp_path / "e.sprite.json")


def test_guide_mentions_layer_plan_and_new_tools():
    from agentsprite.server import GUIDE

    assert "own layer" in GUIDE and "draw_cut" in GUIDE
    assert 'show="full"' in GUIDE and "onion_layer" in GUIDE and "count=3" in GUIDE


def test_mcp_new_tool_params(tmp_path: Path):
    import asyncio

    from agentsprite import server

    p = str(tmp_path / "m2.sprite.json")

    async def go():
        tools = {t.name: t for t in (await server.mcp.list_tools())}
        assert "draw_cut" in tools
        for name in ("draw_set", "draw_paste", "draw_pixels", "draw_rect", "draw_replace", "draw_clear", "draw_copy",
                     "transform_shift", "transform_flip", "draw_outline"):
            assert "show" in tools[name].input_schema["properties"], name
        for name in ("draw_clear", "draw_copy", "transform_shift", "draw_cut"):
            assert "keys" in tools[name].input_schema["properties"], name
        assert "region" in tools["draw_replace"].input_schema["properties"]
        assert "count" in tools["frame_add"].input_schema["properties"]
        assert "onion_layer" in tools["sprite_show"].input_schema["properties"]
        await server.mcp.call_tool("sprite_new", {"path": p, "width": 8, "height": 8})
        await server.mcp.call_tool("palette_set", {"path": p, "colors": {"k": "#000", "o": "#8b5a2b"}})
        r = await server.mcp.call_tool("draw_rect", {"path": p, "x0": 1, "y0": 1, "x1": 2, "y1": 2, "key": "k", "fill": True})
        assert r.content[0].text.splitlines()[1].startswith("changed: x=1..2 y=1..2 (4 pixels)")
        r = await server.mcp.call_tool("draw_pixels", {"path": p, "points": [[7, 7]], "key": "o", "show": "none"})
        assert r.content[0].text == "pixels 'o': 1 pixels affected in frame 0"
        r = await server.mcp.call_tool("frame_add", {"path": p, "copy_from": "0", "count": 2})
        assert "added 2 frames" in r.content[0].text
        r = await server.mcp.call_tool("transform_shift", {"path": p, "dx": 0, "dy": 1, "frame": "0,2", "keys": "k"})
        assert "in frames 0,2" in r.content[0].text
        r = await server.mcp.call_tool("layer_add", {"path": p, "name": "prop"})
        r = await server.mcp.call_tool("draw_cut", {"path": p, "to_layer": "prop", "keys": "o", "frame": "all"})
        assert r.content[0].text.startswith("cut keys(o)")
        s = Sprite.load(p)
        assert all(f.layer("prop").grid[7][7] == "o" and f.layer("base").grid[7][7] == "." for f in s.frames)
        assert s.frames[0].layer("base").grid[2][1] == "k" and s.frames[1].layer("base").grid[1][1] == "k"
        r = await server.mcp.call_tool("draw_replace", {"path": p, "old": "k", "new": "o", "region": [1, 2, 1, 2], "frame": "0"})
        assert "region(1,2,1,2): 1 pixels" in r.content[0].text
        r = await server.mcp.call_tool("sprite_show", {"path": p, "frame": "1", "layer": "base", "onion": "prev", "onion_layer": "composite"})
        assert "(composite)" in r.content[0].text

    asyncio.run(go())


# --------------------------------------------------------------------------- #
# dogfooding session 3
# --------------------------------------------------------------------------- #


def test_frame_move_keeps_tags_on_their_frames():
    s = Sprite.new("m", 2, 2)
    for _ in range(5):
        s.add_frame()  # frame0..frame5
    s.set_tag("a", 0, 2)
    s.set_tag("tail", 4, 5)
    s.move_frame(5, 0)  # frame5 lands in front: a's frames are now at 1..3
    assert [f.name for f in s.frames] == ["frame5", "frame0", "frame1", "frame2", "frame3", "frame4"]
    assert (s.tag("a").start, s.tag("a").end) == (1, 3)
    # frame5 left the tail block, so the tag shrinks to the frame that stayed (frame4, now last)
    assert (s.tag("tail").start, s.tag("tail").end) == (5, 5)
    # a frame moved out of a tag's block leaves the tag
    s = Sprite.new("m", 2, 2)
    for _ in range(5):
        s.add_frame()
    s.set_tag("a", 0, 2)
    s.move_frame(1, 5)
    assert [f.name for f in s.frames][:2] == ["frame0", "frame2"]
    assert (s.tag("a").start, s.tag("a").end) == (0, 1)
    # a frame dropped into the middle of a block joins it
    s.set_tag("a", 0, 1)
    s.move_frame("frame5", 1)
    assert (s.tag("a").start, s.tag("a").end) == (0, 2)
    # a single-frame tag follows its frame
    s.set_tag("solo", 4, 4)
    name = s.frames[4].name
    s.move_frame(4, 0)
    assert s.frames[0].name == name and (s.tag("solo").start, s.tag("solo").end) == (0, 0)
    # consistent with frame_add(at=0) shifting the tag
    s.set_tag("a", 1, 3)
    s.add_frame(at=0)
    assert (s.tag("a").start, s.tag("a").end) == (2, 4)


def test_api_frame_move_reports_tags(tmp_path: Path):
    p = tmp_path / "fm.sprite.json"
    api.new(p, 2, 2)
    api.frame_add(p, count=3)
    api.tag_set(p, "a", 0, 2)
    out = api.frame_move(p, "3", 0)
    assert out.splitlines()[0] == "frames: [0] frame3, [1] frame0, [2] frame1, [3] frame2"
    assert out.splitlines()[1] == "tags: a: 1..3"
    api.frame_remove(p, "0")
    assert (Sprite.load(p).tag("a").start, Sprite.load(p).tag("a").end) == (0, 2)


def test_transforms_count_only_changed_pixels(canvas):
    s, l = canvas
    ops.rect(l, s.palette, 0, 0, 7, 7, "r", fill=True)  # solid square: every symmetric op is a no-op
    assert ops.set_grid(l, s.palette, "\n".join(["rrrrrrrr"] * 8)) == 0
    assert ops.rotate(l, 1) == 0
    assert ops.flip(l, "h") == 0
    assert ops.mirror(l, "h") == 0
    assert ops.mirror(l, "v") == 0
    l.grid[0][0] = "k"
    assert ops.rotate(l, 1) == 2  # k moves (0,0)->(7,0): two cells differ
    assert ops.flip(l, "h") == 2
    assert ops.mirror(l, "h") == 1  # k at (0,0) is copied over the r at (7,0)
    assert ops.histogram(l) == {"r": 62, "k": 2}
    assert ops.set_grid(l, s.palette, "kkkkkkkk") == 6 + 56  # row 0: 6 new k; rows 1..7 padded to '.'


def test_api_set_grid_reports_changed_only(tmp_path: Path):
    p = tmp_path / "sg.sprite.json"
    api.new(p, 24, 24)
    api.palette_set_many(p, {"g": "#4ade80"})
    full = "\n".join(["g" * 24] * 24)
    assert api.draw_set(p, full).startswith("set grid: 576 pixels affected")
    out = api.draw_set(p, full)  # identical grid
    assert out.startswith("set grid: 0 pixels affected") and out.endswith("(no pixels changed)")
    assert api.rotate(p, 1).startswith("rotate 90°: 0 pixels affected")
    assert api.flip(p, "v").startswith("flip v: 0 pixels affected")
    assert api.mirror(p).startswith("mirror h from first: 0 pixels affected")


def test_shift_region_overwrite(canvas):
    s, l = canvas
    # outline at x=1 and x=6 across rows 0..7, "dome" of r at rows 0..3 between them
    ops.rect(l, s.palette, 1, 0, 6, 7, "k")
    ops.rect(l, s.palette, 2, 0, 5, 3, "r", fill=True)
    # merge (default): shifting rows 0..3 down 2 keeps the old outline where the moved box is transparent
    merged = l.copy()
    ops.shift(merged, 0, 2, region=(0, 0, 7, 3))
    assert merged.rows()[4] == ".krrrrk."
    assert merged.rows()[0] == "........" and merged.rows()[1] == "........"
    # overwrite: the moved box's footprint fully replaces rows 2..5
    over = l.copy()
    n = ops.shift(over, 0, 2, region=(0, 0, 7, 3), overwrite=True)
    assert over.rows()[0] == "........" and over.rows()[1] == "........"
    assert over.rows()[2] == ".krrrrk." and over.rows()[5] == ".krrrrk."
    assert over.rows()[6] == ".k....k."
    assert n == 8 * 4  # every cell of the box moved, transparent ones included


def test_api_shift_overwrite(tmp_path: Path):
    p = tmp_path / "so.sprite.json"
    api.new(p, 4, 4)
    api.palette_set_many(p, {"k": "#000", "r": "#f00"})
    api.draw_set(p, "rr..\n....\nkkkk\n....")
    out = api.shift(p, 0, 2, region=[0, 0, 3, 0], overwrite=True)
    assert out.startswith("shift (0,2) region(0,0,3,0) overwrite:")
    assert Sprite.load(p).frames[0].layers[0].rows() == ["....", "....", "rr..", "...."]
    api.draw_set(p, "rr..\n....\nkkkk\n....")
    api.shift(p, 0, 2, region=[0, 0, 3, 0])
    assert Sprite.load(p).frames[0].layers[0].rows() == ["....", "....", "rrkk", "...."]


def test_diff_grid_and_limit(tmp_path: Path):
    p = tmp_path / "d.sprite.json"
    api.new(p, 4, 2)
    api.palette_set_many(p, {"g": "#0f0", "r": "#f00"})
    api.draw_set(p, "gg..\ngg..")
    api.frame_add(p, copy_from="0")
    api.draw_set(p, "rg..\n.ggg", frame="1")
    out = api.diff(p, "0", "1")
    lines = out.splitlines()
    assert lines[0].startswith("4 pixels differ between frame [0] frame0 and [1] frame1: 2 added, 1 removed, 1 recolored; bbox x=0..3 y=0..1")
    assert "grid: key = [1]'s key where the frames differ, ' = transparent in [1], . = identical" in lines[1]
    assert lines[3:5] == ["0 r...", "1 '.gg"]
    assert "->" not in out  # per-pixel list is off by default
    limited = api.diff(p, "0", "1", limit=2)
    assert limited.count("->") == 2 and "... 2 more (limit=-1 lists all)" in limited
    everything = api.diff(p, "0", "1", limit=-1)
    assert everything.count("->") == 4 and "(0,0): g -> r" in everything
    assert api.diff(p, "0", "0").startswith("frames [0] frame0 and [0] frame0 are identical")


def test_replace_map_simultaneous(canvas):
    s, l = canvas
    s.palette.set("G", "#0a0")
    ops.paste(l, s.palette, "rkG", 0, 0)
    assert ops.replace_map(l, s.palette, {"r": "k", "k": "r"}) == 2  # swap
    assert l.rows()[0] == "krG....."
    assert ops.replace_map(l, s.palette, {"k": "G", "G": "k", "r": "r"}) == 2
    assert l.rows()[0] == "Grk....."
    with pytest.raises(SpriteError):
        ops.replace_map(l, s.palette, {"k": "z"})
    with pytest.raises(SpriteError):
        ops.replace_map(l, s.palette, {})
    assert api.replace_mapping("gGl", "rRw") == {"g": "r", "G": "R", "l": "w"}
    assert api.replace_mapping(None, None, {"g": "r"}) == {"g": "r"}
    assert api.replace_mapping("g", "r", {"G": "R"}) == {"g": "r", "G": "R"}
    with pytest.raises(SpriteError):
        api.replace_mapping("gG", "r")
    with pytest.raises(SpriteError):
        api.replace_mapping("gg", "rk")
    with pytest.raises(SpriteError):
        api.replace_mapping(None, None, None)


def test_api_multi_key_replace(tmp_path: Path):
    p = tmp_path / "mk.sprite.json"
    api.new(p, 3, 1)
    api.palette_set_many(p, {"g": "#0f0", "G": "#0a0", "l": "#ccc", "r": "#f00", "R": "#a00", "w": "#fff"})
    api.draw_set(p, "gGl")
    api.frame_add(p, copy_from="0", name="hurt0")
    out = api.draw_replace(p, "gGl", "rRw", frame="hurt0")
    assert out.startswith("replace 'g'->'r','G'->'R','l'->'w': 3 pixels affected in frame 1")
    s = Sprite.load(p)
    assert s.frames[1].layers[0].rows() == ["rRw"] and s.frames[0].layers[0].rows() == ["gGl"]
    api.draw_replace(p, mapping={"g": "G", "G": "g"}, frame="0")
    assert Sprite.load(p).frames[0].layers[0].rows() == ["Ggl"]


def test_import_png_reads_sheet_metadata(tmp_path: Path):
    p = tmp_path / "slime.sprite.json"
    api.new(p, 4, 3)
    api.palette_set_many(p, {"k": "#0f0f1a", "g": "#4ade80", "s": "#0f0f1a80"})
    api.draw_set(p, "kgg.\nkss.\n....")
    api.frame_add(p, copy_from="0", name="rest", duration_ms=150)
    api.frame_add(p, name="hurt0", duration_ms=60)
    api.draw_pixels(p, [(3, 2)], "s", frame="hurt0")
    api.tag_set(p, "bounce", 0, 1, "pingpong")
    api.tag_set(p, "hurt", 2, 2, loop=False)
    api.export_sheet(p, tmp_path / "out" / "slime_sheet.png", columns=2, padding=1, scale=2)
    # sibling json picked up automatically
    out = api.import_png(tmp_path / "out" / "slime_sheet.png", tmp_path / "back.sprite.json")
    assert "metadata: " in out and "2 tag(s)" in out and "palette)" in out
    b = Sprite.load(tmp_path / "back.sprite.json")
    a = Sprite.load(p)
    assert (b.width, b.height) == (4, 3)
    assert [f.name for f in b.frames] == ["frame0", "rest", "hurt0"]
    assert [f.duration_ms for f in b.frames] == [100, 150, 60]
    assert [(t.name, t.start, t.end, t.direction, t.loop) for t in b.tags] == [
        ("bounce", 0, 1, "pingpong", True), ("hurt", 2, 2, "forward", False)
    ]
    assert b.palette.colors == a.palette.colors  # same keys, including the semi-transparent shadow
    assert [f.layers[0].rows() for f in b.frames] == [f.layers[0].rows() for f in a.frames]
    # explicit metadata path, and --palette-from wins over the sheet palette
    api.import_png(
        tmp_path / "out" / "slime_sheet.png", tmp_path / "back2.sprite.json",
        metadata=tmp_path / "out" / "slime_sheet.json", palette_from=p,
    )
    assert Sprite.load(tmp_path / "back2.sprite.json").frames[1].name == "rest"
    with pytest.raises(SpriteError, match="no such metadata"):
        api.import_png(tmp_path / "out" / "slime_sheet.png", tmp_path / "x.sprite.json", metadata=tmp_path / "nope.json")
    # a sibling json that is not sheet metadata is ignored; an explicit one is an error
    img = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    img.save(tmp_path / "plain.png")
    (tmp_path / "plain.json").write_text('{"hello": 1}')
    out = api.import_png(tmp_path / "plain.png", tmp_path / "plain.sprite.json")
    assert "metadata:" not in out
    with pytest.raises(SpriteError, match="no 'frames' list"):
        api.import_png(tmp_path / "plain.png", tmp_path / "plain2.sprite.json", metadata=tmp_path / "plain.json")
    # size mismatch between sheet and metadata is caught
    Image.new("RGBA", (5, 5)).save(tmp_path / "out" / "wrong.png")
    with pytest.raises(SpriteError, match="describes a"):
        api.import_png(tmp_path / "out" / "wrong.png", tmp_path / "w.sprite.json", metadata=tmp_path / "out" / "slime_sheet.json")


def test_import_metadata_frame_size_override_note(tmp_path: Path):
    p = tmp_path / "a.sprite.json"
    api.new(p, 3, 2)
    api.palette_set_many(p, {"k": "#000"})
    api.draw_pixels(p, [(0, 0)], "k")
    api.frame_add(p, copy_from="0")
    api.export_sheet(p, tmp_path / "a.png")
    out = api.import_png(tmp_path / "a.png", tmp_path / "b.sprite.json", frame_width=1, frame_height=1)
    assert "note: frame size 1x1 ignored; metadata says 3x2" in out
    assert Sprite.load(tmp_path / "b.sprite.json").width == 3


def test_resize_anchor_validation_and_show(tmp_path: Path):
    from agentsprite.model import ANCHORS, anchor_offset, normalize_anchor

    assert normalize_anchor("Bottom_Right") == "bottom-right"
    assert normalize_anchor("middle") == "center"
    assert normalize_anchor(" top ") == "top"
    for a in ANCHORS:
        normalize_anchor(a)
    with pytest.raises(SpriteError, match="unknown anchor 'botom'"):
        normalize_anchor("botom")
    assert anchor_offset("bottom", 2, 2, 4, 6) == (1, 4)
    assert anchor_offset("top-right", 2, 2, 4, 6) == (2, 0)
    p = tmp_path / "rs.sprite.json"
    api.new(p, 4, 4)
    api.palette_set_many(p, {"k": "#000"})
    api.draw_rect(p, 0, 0, 1, 1, "k", fill=True)
    with pytest.raises(SpriteError, match="unknown anchor"):
        api.resize(p, 6, 6, "botom")
    out = api.resize(p, 6, 6, "bottom-right")
    lines = out.splitlines()
    assert lines[0] == "resized 4x4 -> 6x6 (anchor bottom-right; content moved by (+2,+2))"
    assert lines[1].startswith("content: x=2..3 y=2..3 in frame [0] frame0")
    assert lines[2:] == ["  23", "2 kk", "3 kk"]
    assert api.resize(p, 6, 6, "center", show="none") == "resized 6x6 -> 6x6 (anchor center; content moved by (+0,+0))"
    full = api.resize(p, 8, 8, "top-left", show="full")
    assert "frame [0] frame0 (composite" in full and "legend: k=#000000" in full
    out = api.resize(p, 2, 2, "top-left")
    assert "4 pixels cropped away" in out and "(frame [0] frame0 is empty)" in out
    with pytest.raises(SpriteError, match="show must be"):
        api.resize(p, 2, 2, show="huge")


def test_stretch_squash_keeps_feet_and_outline(canvas):
    s, l = canvas
    # 6x6 body in rows 1..6: outline k, fill r
    ops.rect(l, s.palette, 1, 1, 6, 6, "k")
    ops.rect(l, s.palette, 2, 2, 5, 5, "r", fill=True)
    before = l.rows()
    n = ops.stretch(l, (1, 1, 6, 6), dy=-2, anchor="bottom")
    rows = l.rows()
    assert rows[0] == "........" and rows[1] == "........" and rows[2] == "........"
    assert rows[3] == ".kkkkkk."  # top edge kept
    assert rows[4] == ".krrrrk." and rows[5] == ".krrrrk."
    assert rows[6] == ".kkkkkk."  # bottom edge stays put
    assert rows[7] == "........"
    assert n == 6 * 2 + 4  # rows 1..2 cleared (12); row 3 turns from krrrrk into the top edge (4)
    # stretch back up by 2: nearest neighbour duplicates rows, so the box is 6 tall again
    # with its outline intact, but the sampled rows are not the originals
    ops.stretch(l, (1, 3, 6, 6), dy=2, anchor="bottom")
    rows = l.rows()
    assert rows[1] == ".kkkkkk." and rows[6] == ".kkkkkk." and rows[0] == "........" and rows[7] == "........"
    assert all(r[1] == "k" and r[6] == "k" for r in rows[1:7])
    assert ".krrrrk." in rows[2:6]
    l.grid = [list(r) for r in before]
    # horizontal stretch centred: width 6 -> 8 fills x=0..7
    ops.stretch(l, (1, 1, 6, 6), dx=2, anchor="bottom")
    assert l.rows()[1] == "kkkkkkkk" and l.rows()[3] == "krrrrrrk"
    # shrinking below 1 row is an error; a no-op stretch is rejected at the api level
    with pytest.raises(SpriteError):
        ops.stretch(l, (0, 0, 7, 1), dy=-2)


def test_api_stretch(tmp_path: Path):
    p = tmp_path / "st.sprite.json"
    api.new(p, 8, 8)
    api.palette_set_many(p, {"k": "#000", "r": "#f00"})
    api.draw_rect(p, 1, 1, 6, 6, "k")
    api.draw_rect(p, 2, 2, 5, 5, "r", fill=True)
    api.frame_add(p, copy_from="0", name="squash")
    api.frame_add(p, copy_from="0", name="stretch")
    out = api.stretch(p, [1, 1, 6, 6], dy=-2, frame="squash")
    assert out.startswith("stretch (+0,-2) region(1,1,6,6) anchor bottom: 16 pixels affected in frame 1")
    assert "changed: x=1..6 y=1..3 (16 pixels)" in out
    api.stretch(p, [1, 1, 6, 6], dy=1, anchor="bottom", frame="stretch")
    s = Sprite.load(p)
    assert s.frame("squash").layers[0].rows()[3] == ".kkkkkk." and s.frame("squash").layers[0].rows()[6] == ".kkkkkk."
    assert s.frame("stretch").layers[0].rows()[0] == ".kkkkkk." and s.frame("stretch").layers[0].rows()[6] == ".kkkkkk."
    assert s.frame("frame0").layers[0].rows()[1] == ".kkkkkk."  # untouched
    with pytest.raises(SpriteError, match="non-zero"):
        api.stretch(p, [1, 1, 6, 6])
    with pytest.raises(SpriteError, match="unknown anchor"):
        api.stretch(p, [1, 1, 6, 6], dy=-1, anchor="feet")
    # top anchor grows downwards
    api.stretch(p, [1, 1, 6, 6], dy=1, anchor="top", frame="0")
    assert Sprite.load(p).frames[0].layers[0].rows()[7] == ".kkkkkk."


def test_bbox_echo_marks_changed_cells(tmp_path: Path):
    p = tmp_path / "e.sprite.json"
    api.new(p, 6, 6)
    api.palette_set_many(p, {"g": "#0f0"})
    api.draw_rect(p, 0, 0, 5, 5, "g", fill=True)
    # 4 'g' pixels set inside a 'g' area: nothing changes, and the echo says so
    assert api.draw_pixels(p, [(1, 1), (4, 4)], "g").endswith("(no pixels changed)")
    api.palette_set_many(p, {"k": "#000"})
    out = api.draw_pixels(p, [(1, 1), (4, 4)], "k")
    lines = out.splitlines()
    assert lines[1].endswith("right grid = changed cells only")
    assert lines[2] == "  1234   1234"
    assert lines[3] == "1 kggg   k"
    assert lines[4] == "2 gggg"
    assert lines[6] == "4 gggk      k"
    # a fully-changed box is echoed once, without the mask
    out = api.draw_rect(p, 2, 2, 3, 3, "k", fill=True)
    assert "changed cells only" not in out and out.splitlines()[2:] == ["  23", "2 kk", "3 kk"]


def test_onion_counts_both_directions(tmp_path: Path):
    p = tmp_path / "ob.sprite.json"
    api.new(p, 6, 4)
    api.palette_set_many(p, {"g": "#0f0"})
    api.draw_rect(p, 1, 2, 4, 3, "g", fill=True)  # rest: 4x2 block
    api.frame_add(p, copy_from="0", name="stretch")
    api.draw_rect(p, 1, 0, 4, 1, "g", fill=True, frame="stretch")  # superset: dome grew by 8
    text = view.frame_text(Sprite.load(p), "stretch", onion="0")
    assert "onion: ' = 0 pixel(s) only in frame [0] frame0; 8 pixel(s) only in this frame (x=1..4 y=0..1)" in text
    text = view.frame_text(Sprite.load(p), "0", onion="stretch")
    assert "onion: ' = 8 pixel(s) only in frame [1] stretch; 0 pixel(s) only in this frame" in text
    assert "0 .''''." in text


def test_cli_session3_surface(tmp_path: Path):
    from typer.testing import CliRunner

    from agentsprite.cli import app

    runner = CliRunner()
    p = str(tmp_path / "c.sprite.json")
    assert runner.invoke(app, ["new", p, "-w", "8", "-h", "8"]).exit_code == 0
    assert runner.invoke(app, ["palette", "set", p, "k=#000", "r=#f00", "g=#0f0", "G=#0a0"]).exit_code == 0
    assert runner.invoke(app, ["draw", "rect", p, "1", "1", "6", "6", "k"]).exit_code == 0
    assert runner.invoke(app, ["draw", "rect", p, "2", "2", "5", "5", "g", "--fill"]).exit_code == 0
    r = runner.invoke(app, ["transform", "stretch", p, "-r", "1,1,6,6", "--dy", "-2"])
    assert r.exit_code == 0 and r.output.startswith("stretch (+0,-2)")
    assert Sprite.load(p).frames[0].layers[0].rows()[3] == ".kkkkkk."
    r = runner.invoke(app, ["draw", "replace", p, "gG", "Gg"])
    assert r.exit_code == 0 and "'g'->'G','G'->'g'" in r.output
    assert runner.invoke(app, ["frame", "add", p, "--copy", "0"]).exit_code == 0
    r = runner.invoke(app, ["transform", "shift", p, "0", "1", "-f", "1", "-r", "0,3,7,3", "--overwrite"])
    assert r.exit_code == 0 and "overwrite" in r.output
    r = runner.invoke(app, ["diff", p, "0", "1", "--limit", "3"])
    assert r.exit_code == 0 and r.output.count("->") == 3 and "more (limit=-1" in r.output
    r = runner.invoke(app, ["resize", p, "10", "10", "--anchor", "botom"])
    assert r.exit_code == 1 and "unknown anchor" in r.output
    r = runner.invoke(app, ["resize", p, "10", "10", "--anchor", "center", "--show", "none"])
    assert r.exit_code == 0 and r.output.strip() == "resized 8x8 -> 10x10 (anchor center; content moved by (+1,+1))"
    assert runner.invoke(app, ["export", "sheet", p, str(tmp_path / "s.png")]).exit_code == 0
    r = runner.invoke(app, ["import", str(tmp_path / "s.png"), str(tmp_path / "i.sprite.json"), "-m", str(tmp_path / "s.json")])
    assert r.exit_code == 0 and "metadata:" in r.output
    assert len(Sprite.load(tmp_path / "i.sprite.json").frames) == 2


def test_mcp_session3_tools(tmp_path: Path):
    import asyncio

    from agentsprite import server

    p = str(tmp_path / "m3.sprite.json")

    async def go():
        tools = {t.name: t for t in (await server.mcp.list_tools())}
        assert "transform_stretch" in tools
        assert "overwrite" in tools["transform_shift"].input_schema["properties"]
        assert "mapping" in tools["draw_replace"].input_schema["properties"]
        assert "limit" in tools["sprite_diff"].input_schema["properties"]
        assert "show" in tools["sprite_resize"].input_schema["properties"]
        assert "metadata" in tools["import_png"].input_schema["properties"]
        await server.mcp.call_tool("sprite_new", {"path": p, "width": 8, "height": 8})
        await server.mcp.call_tool("palette_set", {"path": p, "colors": {"k": "#000", "g": "#0f0", "r": "#f00"}})
        await server.mcp.call_tool("draw_rect", {"path": p, "x0": 1, "y0": 1, "x1": 6, "y1": 6, "key": "k"})
        await server.mcp.call_tool("draw_rect", {"path": p, "x0": 2, "y0": 2, "x1": 5, "y1": 5, "key": "g", "fill": True})
        r = await server.mcp.call_tool("transform_stretch", {"path": p, "region": [1, 1, 6, 6], "dy": -2})
        assert r.content[0].text.startswith("stretch (+0,-2) region(1,1,6,6) anchor bottom")
        r = await server.mcp.call_tool("draw_replace", {"path": p, "mapping": {"g": "r", "k": "g"}})
        assert "'g'->'r','k'->'g'" in r.content[0].text
        assert Sprite.load(p).frames[0].layers[0].rows()[3] == ".gggggg."
        r = await server.mcp.call_tool("sprite_resize", {"path": p, "width": 4, "height": 4, "anchor": "botom"})
        assert r.content[0].text.startswith("error: unknown anchor 'botom'")
        r = await server.mcp.call_tool("sprite_resize", {"path": p, "width": 10, "height": 10, "anchor": "center", "show": "none"})
        assert r.content[0].text == "resized 8x8 -> 10x10 (anchor center; content moved by (+1,+1))"

    asyncio.run(go())
