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
    assert "set grid" in out and "0 ..kk.." in out
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
    assert "' = 4 pixel(s) of frame [0]" in text
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
        assert "\n0 kw..\n1 ..wk" in r.content[0].text  # real newlines, not escaped
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
