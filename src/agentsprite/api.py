"""High-level, file-oriented operations shared by the CLI and the MCP server.

Every function takes a sprite file path, performs one change, saves, and
returns a human/agent-readable string describing the result (usually including
the affected frame grid so the caller can see what happened).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import ops, presets, render, view
from .model import Layer, Palette, Sprite, SpriteError
from .ops import Region

FrameRef = str | int
LayerRef = str | int | None

ALL = "all"


def parse_region(text: str | None) -> Region:
    """Parse ``"x0,y0,x1,y1"`` (CLI form) into a region tuple."""
    if text is None or text == "":
        return None
    parts = [p for p in text.replace(" ", "").split(",") if p]
    if len(parts) != 4:
        raise SpriteError(f"region must be x0,y0,x1,y1, got {text!r}")
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        raise SpriteError(f"region must be integers, got {text!r}") from None


def _region_str(region: Region) -> str:
    return "" if region is None else f" region({','.join(str(v) for v in region)})"


def _target_frames(sprite: Sprite, frame: FrameRef) -> list[int]:
    if isinstance(frame, str) and frame.lower() == ALL:
        return list(range(len(sprite.frames)))
    return [sprite.frame_index(frame)]


def _target_layer(sprite: Sprite, fi: int, layer: LayerRef) -> Layer:
    f = sprite.frames[fi]
    return f.layer(layer if layer is not None else 0)


def _edit(
    path: str | Path,
    frame: FrameRef,
    layer: LayerRef,
    op: Callable[[Layer, Sprite], int],
    what: str,
    show: bool = True,
) -> str:
    """Apply ``op`` to the selected layer(s), save, and describe the result."""
    sprite = Sprite.load(path)
    total = 0
    frames = _target_frames(sprite, frame)
    for fi in frames:
        total += op(_target_layer(sprite, fi, layer), sprite)
    sprite.save(path)
    msg = f"{what}: {total} pixels affected in {len(frames)} frame(s)"
    if show:
        msg += "\n" + view.frame_text(sprite, frames[0], layer)
        if len(frames) > 1:
            msg += f"\n(+{len(frames) - 1} more frame(s) changed; use show to inspect)"
    return msg


# --------------------------------------------------------------------------- #
# document
# --------------------------------------------------------------------------- #


def _palette_from(path: str | Path | None) -> Palette | None:
    """Copy of another sprite file's palette, or None."""
    if path in (None, ""):
        return None
    return Palette(dict(Sprite.load(path).palette.colors))


def new(
    path: str | Path,
    width: int,
    height: int,
    name: str | None = None,
    layer: str = "base",
    palette_from: str | Path | None = None,
) -> str:
    p = Path(path)
    if p.exists():
        raise SpriteError(f"{p} already exists; delete it or choose another path")
    sprite = Sprite.new(name or p.name.split(".")[0], width, height, layer)
    pal = _palette_from(palette_from)
    if pal is not None:
        sprite.palette = pal
    p.parent.mkdir(parents=True, exist_ok=True)
    sprite.save(p)
    return f"created {p}\n" + view.info_text(sprite)


def info(path: str | Path) -> str:
    return view.info_text(Sprite.load(path))


def show(
    path: str | Path,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    all_frames: bool = False,
    ruler: bool = True,
    onion: str | int | None = None,
) -> str:
    sprite = Sprite.load(path)
    if all_frames:
        return view.all_frames_text(sprite, layer)
    return view.frame_text(sprite, frame, layer, ruler=ruler, onion=onion)


def diff(path: str | Path, a: FrameRef, b: FrameRef, layer: LayerRef = None) -> str:
    return view.diff_text(Sprite.load(path), a, b, layer)


def validate(path: str | Path) -> str:
    problems = Sprite.load(path).validate()
    return "ok" if not problems else "\n".join(problems)


def resize(path: str | Path, width: int, height: int, anchor: str = "top-left") -> str:
    sprite = Sprite.load(path)
    sprite.resize(width, height, anchor)
    sprite.save(path)
    return f"resized to {width}x{height} (anchor {anchor})\n" + view.frame_text(sprite, 0)


def set_notes(path: str | Path, notes: str) -> str:
    sprite = Sprite.load(path)
    sprite.notes = notes
    sprite.save(path)
    return "notes updated"


def rename(path: str | Path, name: str) -> str:
    sprite = Sprite.load(path)
    sprite.name = name
    sprite.save(path)
    return f"renamed sprite to {name!r}"


# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #


def palette_set(path: str | Path, key: str, color: str) -> str:
    sprite = Sprite.load(path)
    sprite.palette.set(key, color)
    sprite.save(path)
    return "palette:\n" + view.palette_text(sprite)


def palette_set_many(path: str | Path, colors: dict[str, str]) -> str:
    sprite = Sprite.load(path)
    for k, c in colors.items():
        sprite.palette.set(k, c)
    sprite.save(path)
    return "palette:\n" + view.palette_text(sprite)


def palette_remove(path: str | Path, key: str, replace_with: str = ".") -> str:
    sprite = Sprite.load(path)
    sprite.palette.remove(key)
    n = 0
    for f in sprite.frames:
        for l in f.layers:
            n += ops.replace(l, sprite.palette, key, replace_with)
    sprite.save(path)
    return f"removed {key!r} ({n} pixels replaced with {replace_with!r})\npalette:\n" + view.palette_text(sprite)


def palette_list(path: str | Path) -> str:
    return view.palette_text(Sprite.load(path))


def palette_preset(path: str | Path, name: str, keys: str | None = None) -> str:
    """Merge a built-in preset (pico-8, endesga-32, ...) into the sprite's palette."""
    preset = presets.get(name)
    colors = preset.as_dict(keys)
    sprite = Sprite.load(path)
    for k, c in colors.items():
        sprite.palette.set(k, c)
    sprite.save(path)
    return f"added preset {preset.name} ({len(colors)} colors)\npalette:\n" + view.palette_text(sprite)


def palette_presets() -> str:
    return presets.presets_text()


# --------------------------------------------------------------------------- #
# frames
# --------------------------------------------------------------------------- #


def frame_add(
    path: str | Path,
    name: str | None = None,
    duration_ms: int = 100,
    copy_from: FrameRef | None = None,
    at: int | None = None,
) -> str:
    sprite = Sprite.load(path)
    f = sprite.add_frame(name, duration_ms, copy_from, at)
    sprite.save(path)
    idx = sprite.frames.index(f)
    src = f" (copied from {copy_from})" if copy_from is not None else ""
    return f"added frame [{idx}] {f.name}{src}; now {len(sprite.frames)} frames"


def frame_remove(path: str | Path, frame: FrameRef) -> str:
    sprite = Sprite.load(path)
    name = sprite.frame(frame).name
    sprite.remove_frame(frame)
    sprite.save(path)
    return f"removed frame {name!r}; now {len(sprite.frames)} frames"


def frame_move(path: str | Path, frame: FrameRef, to: int) -> str:
    sprite = Sprite.load(path)
    sprite.move_frame(frame, to)
    sprite.save(path)
    return "frames: " + ", ".join(f"[{i}] {f.name}" for i, f in enumerate(sprite.frames))


def frame_update(
    path: str | Path, frame: FrameRef, name: str | None = None, duration_ms: int | None = None
) -> str:
    sprite = Sprite.load(path)
    f = sprite.frame(frame)
    if name is not None:
        if any(o.name == name for o in sprite.frames if o is not f):
            raise SpriteError(f"frame {name!r} already exists")
        f.name = name
    if duration_ms is not None:
        if duration_ms <= 0:
            raise SpriteError("duration must be positive")
        f.duration_ms = duration_ms
    sprite.save(path)
    return f"frame [{sprite.frames.index(f)}] {f.name} {f.duration_ms}ms"


def frame_list(path: str | Path) -> str:
    sprite = Sprite.load(path)
    return "\n".join(f"[{i}] {f.name}  {f.duration_ms}ms" for i, f in enumerate(sprite.frames))


# --------------------------------------------------------------------------- #
# layers
# --------------------------------------------------------------------------- #


def layer_add(path: str | Path, name: str, at: int | None = None) -> str:
    sprite = Sprite.load(path)
    sprite.add_layer(name, at)
    sprite.save(path)
    return "layers (bottom -> top): " + ", ".join(sprite.layer_names())


def layer_remove(path: str | Path, layer: str | int) -> str:
    sprite = Sprite.load(path)
    sprite.remove_layer(layer)
    sprite.save(path)
    return "layers (bottom -> top): " + ", ".join(sprite.layer_names())


def layer_move(path: str | Path, layer: str | int, to: int) -> str:
    sprite = Sprite.load(path)
    sprite.move_layer(layer, to)
    sprite.save(path)
    return "layers (bottom -> top): " + ", ".join(sprite.layer_names())


def layer_rename(path: str | Path, layer: str | int, new_name: str) -> str:
    sprite = Sprite.load(path)
    if new_name in sprite.layer_names():
        raise SpriteError(f"layer {new_name!r} already exists")
    sprite.rename_layer(layer, new_name)
    sprite.save(path)
    return "layers (bottom -> top): " + ", ".join(sprite.layer_names())


def layer_visible(path: str | Path, layer: str | int, visible: bool) -> str:
    sprite = Sprite.load(path)
    sprite.set_layer_visible(layer, visible)
    sprite.save(path)
    return f"layer {sprite.frames[0].layer(layer).name!r} {'shown' if visible else 'hidden'}"


def layer_list(path: str | Path) -> str:
    sprite = Sprite.load(path)
    f0 = sprite.frames[0]
    return "\n".join(
        f"[{i}] {l.name}" + ("" if l.visible else "  (hidden)") for i, l in enumerate(f0.layers)
    )


# --------------------------------------------------------------------------- #
# tags
# --------------------------------------------------------------------------- #


def tag_set(
    path: str | Path, name: str, start: int, end: int, direction: str = "forward", loop: bool = True
) -> str:
    sprite = Sprite.load(path)
    sprite.set_tag(name, start, end, direction, loop)
    sprite.save(path)
    return "tags:\n" + "\n".join(
        f"  {t.name}: {t.start}..{t.end} {t.direction}{'' if t.loop else ' once'}" for t in sprite.tags
    )


def tag_remove(path: str | Path, name: str) -> str:
    sprite = Sprite.load(path)
    sprite.remove_tag(name)
    sprite.save(path)
    return f"removed tag {name!r}"


def tag_list(path: str | Path) -> str:
    sprite = Sprite.load(path)
    if not sprite.tags:
        return "(no tags)"
    return "\n".join(
        f"{t.name}: frames {t.start}..{t.end} {t.direction}{'' if t.loop else ' once'}" for t in sprite.tags
    )


# --------------------------------------------------------------------------- #
# drawing
# --------------------------------------------------------------------------- #


def draw_pixels(
    path: str | Path, points: list[tuple[int, int]], key: str, frame: FrameRef = 0, layer: LayerRef = None
) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.pixels(l, s.palette, points, key), f"pixels {key!r}")


def draw_line(
    path: str | Path, x0: int, y0: int, x1: int, y1: int, key: str, frame: FrameRef = 0, layer: LayerRef = None
) -> str:
    return _edit(
        path, frame, layer, lambda l, s: ops.line(l, s.palette, x0, y0, x1, y1, key), f"line {key!r}"
    )


def draw_rect(
    path: str | Path,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    key: str,
    fill: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
) -> str:
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.rect(l, s.palette, x0, y0, x1, y1, key, fill),
        f"{'filled ' if fill else ''}rect {key!r}",
    )


def draw_ellipse(
    path: str | Path,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    key: str,
    fill: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
) -> str:
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.ellipse(l, s.palette, x0, y0, x1, y1, key, fill),
        f"{'filled ' if fill else ''}ellipse {key!r}",
    )


def draw_fill(
    path: str | Path, x: int, y: int, key: str, diagonal: bool = False, frame: FrameRef = 0, layer: LayerRef = None
) -> str:
    return _edit(
        path, frame, layer, lambda l, s: ops.flood_fill(l, s.palette, x, y, key, diagonal), f"fill {key!r}"
    )


def draw_replace(path: str | Path, old: str, new: str, frame: FrameRef = ALL, layer: LayerRef = None) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.replace(l, s.palette, old, new), f"replace {old!r}->{new!r}")


def draw_clear(path: str | Path, frame: FrameRef = 0, layer: LayerRef = None, region: Region = None) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.clear(l, region), "clear" + _region_str(region))


def draw_copy(
    path: str | Path,
    region: Region,
    x: int,
    y: int,
    from_frame: FrameRef = 0,
    to_frame: FrameRef = 0,
    from_layer: LayerRef = None,
    to_layer: LayerRef = None,
    overwrite: bool = False,
) -> str:
    """Copy a region of one frame/layer onto (x, y) of another (or the same)."""
    sprite = Sprite.load(path)
    src_fi = sprite.frame_index(from_frame)
    src = _target_layer(sprite, src_fi, from_layer)
    dst_frames = _target_frames(sprite, to_frame)
    total = 0
    for fi in dst_frames:
        dst = _target_layer(sprite, fi, to_layer if to_layer is not None else from_layer)
        total += ops.copy_region(src, dst, region, x, y, overwrite)
    sprite.save(path)
    msg = f"copy{_region_str(region)} from frame {src_fi} -> ({x},{y}): {total} pixels affected in {len(dst_frames)} frame(s)"
    return msg + "\n" + view.frame_text(sprite, dst_frames[0], to_layer if to_layer is not None else from_layer)


def draw_paste(
    path: str | Path,
    grid: str,
    x: int = 0,
    y: int = 0,
    overwrite: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
) -> str:
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.paste(l, s.palette, grid, x, y, skip_transparent=not overwrite),
        f"paste at ({x},{y})",
    )


def draw_set(path: str | Path, grid: str, frame: FrameRef = 0, layer: LayerRef = None) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.set_grid(l, s.palette, grid), "set grid")


def draw_outline(
    path: str | Path,
    key: str,
    diagonal: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    outer_only: bool = False,
) -> str:
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.outline(l, s.palette, key, diagonal, outer_only),
        f"{'outer ' if outer_only else ''}outline {key!r}",
    )


# --------------------------------------------------------------------------- #
# transforms
# --------------------------------------------------------------------------- #


def flip(path: str | Path, axis: str, frame: FrameRef = 0, layer: LayerRef = None, region: Region = None) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.flip(l, axis, region), f"flip {axis}{_region_str(region)}")


def rotate(path: str | Path, turns: int = 1, frame: FrameRef = 0, layer: LayerRef = None) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.rotate(l, turns), f"rotate {turns * 90}°")


def shift(
    path: str | Path,
    dx: int,
    dy: int,
    wrap: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    region: Region = None,
) -> str:
    return _edit(
        path, frame, layer, lambda l, s: ops.shift(l, dx, dy, wrap, region), f"shift ({dx},{dy}){_region_str(region)}"
    )


def mirror(
    path: str | Path, axis: str = "h", source: str = "first", frame: FrameRef = 0, layer: LayerRef = None
) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.mirror(l, axis, source), f"mirror {axis} from {source}")


# --------------------------------------------------------------------------- #
# export / import
# --------------------------------------------------------------------------- #


def export_png(
    path: str | Path,
    out: str | Path,
    frame: FrameRef = 0,
    scale: int = 1,
    background: str | None = None,
    layers: list[str] | None = None,
) -> str:
    sprite = Sprite.load(path)
    p = render.export_png(sprite, out, frame, scale, background, layers)
    return f"wrote {p} ({sprite.width * scale}x{sprite.height * scale})"


def export_frames(path: str | Path, out_dir: str | Path, scale: int = 1, background: str | None = None) -> str:
    sprite = Sprite.load(path)
    paths = render.export_frames(sprite, out_dir, scale, background)
    return f"wrote {len(paths)} frames to {Path(out_dir)}:\n" + "\n".join(f"  {p.name}" for p in paths)


def export_sheet(
    path: str | Path,
    out: str | Path,
    columns: int | None = None,
    padding: int = 0,
    scale: int = 1,
    tag: str | None = None,
    metadata: bool = True,
) -> str:
    sprite = Sprite.load(path)
    p, meta = render.export_sheet(sprite, out, columns, padding, scale, tag, metadata)
    img_w, img_h = render.build_sheet(sprite, columns, padding, scale, tag)[0].size
    msg = f"wrote {p} ({img_w}x{img_h}, frame {sprite.width * scale}x{sprite.height * scale})"
    if meta:
        msg += f"\nwrote {meta}"
    return msg


def export_gif(
    path: str | Path,
    out: str | Path,
    scale: int = 1,
    tag: str | None = None,
    background: str | None = None,
) -> str:
    sprite = Sprite.load(path)
    p = render.export_gif(sprite, out, scale, tag, background)
    n = len(sprite.tag(tag).frame_indices()) if tag else len(sprite.frames)
    return f"wrote {p} ({n} frames)"


def export_apng(
    path: str | Path,
    out: str | Path,
    scale: int = 1,
    tag: str | None = None,
    background: str | None = None,
) -> str:
    sprite = Sprite.load(path)
    p = render.export_apng(sprite, out, scale, tag, background)
    n = len(sprite.tag(tag).frame_indices()) if tag else len(sprite.frames)
    return f"wrote {p} ({n} frames, APNG)"


def import_png(
    png: str | Path,
    out: str | Path,
    name: str | None = None,
    frame_width: int | None = None,
    frame_height: int | None = None,
    max_colors: int = 32,
    palette_from: str | Path | None = None,
) -> str:
    p = Path(out)
    if p.exists():
        raise SpriteError(f"{p} already exists")
    sprite = render.import_png(png, name, _palette_from(palette_from), max_colors, frame_width, frame_height)
    p.parent.mkdir(parents=True, exist_ok=True)
    sprite.save(p)
    return f"imported {png} -> {p}\n" + view.info_text(sprite)


def render_bytes(
    path: str | Path,
    frame: FrameRef = 0,
    scale: int = 8,
    background: str | None = None,
    checker: bool = False,
    layer: LayerRef = None,
) -> bytes:
    """PNG bytes of one frame (for MCP image previews)."""
    import io

    sprite = Sprite.load(path)
    f = sprite.frame(frame)
    layers = [f.layer(layer).name] if layer is not None else None
    img = render.render_frame(f, sprite.palette, sprite.width, sprite.height, layers)
    img = render.upscale(img, scale)
    img = render.checkerboard(img, max(1, scale)) if checker else render.with_background(img, background)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def render_sheet_bytes(path: str | Path, scale: int = 8, columns: int | None = None, padding: int = 1) -> bytes:
    import io

    sprite = Sprite.load(path)
    img, _ = render.build_sheet(sprite, columns, padding * scale, scale)
    img = render.checkerboard(img, scale)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
