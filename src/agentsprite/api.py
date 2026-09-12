"""High-level, file-oriented operations shared by the CLI and the MCP server.

Every function takes a sprite file path, performs one change, saves, and
returns a human/agent-readable string describing the result (usually including
the affected frame grid so the caller can see what happened).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import ops, presets, render, view
from .model import TRANSPARENT_KEY, Layer, Palette, Sprite, SpriteError, anchor_offset, normalize_anchor
from .ops import Keys, Region

FrameRef = str | int
"""Frame index, name, ``"all"``, or a comma-separated list of those (``"1,3"``, ``"0..2,5"``)."""
LayerRef = str | int | None

ALL = "all"
SHOW_DEFAULT = "bbox"


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
    """Resolve a frame ref to a list of frame indices.

    Accepts an index, a name, ``"all"``, an inclusive range ``"a..b"`` and
    comma-separated combinations (``"1,3"``, ``"0..2,idle4"``). Order is kept,
    duplicates dropped.
    """
    if isinstance(frame, int):
        return [sprite.frame_index(frame)]
    text = str(frame).strip()
    if text.lower() == ALL:
        return list(range(len(sprite.frames)))
    if any(f.name == text for f in sprite.frames):
        return [sprite.frame_index(text)]
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if part.lower() == ALL:
            idxs = list(range(len(sprite.frames)))
        elif ".." in part and not any(f.name == part for f in sprite.frames):
            a, b = part.split("..", 1)
            ia, ib = sprite.frame_index(a.strip()), sprite.frame_index(b.strip())
            idxs = list(range(min(ia, ib), max(ia, ib) + 1))
        else:
            idxs = [sprite.frame_index(part)]
        for i in idxs:
            if i not in out:
                out.append(i)
    if not out:
        raise SpriteError(f"no frames selected by {frame!r}")
    return out


def _target_layer(sprite: Sprite, fi: int, layer: LayerRef) -> Layer:
    f = sprite.frames[fi]
    return f.layer(layer if layer is not None else 0)


def _frames_str(frames: list[int]) -> str:
    return f"frame {frames[0]}" if len(frames) == 1 else f"frames {','.join(str(i) for i in frames)}"


def _layer_str(sprite: Sprite, fi: int, layer: LayerRef, target: Layer) -> str:
    """`` / layer 'name'`` when it matters: the layer was given, or the frame has several.

    An edit without ``layer`` lands on layer 0, whatever that currently is
    (after ``layer_add(at=0)`` it is the new bottom layer), so the echo always
    says which layer it hit once there is a choice.
    """
    if layer is None and len(sprite.frames[fi].layers) == 1:
        return ""
    note = " (default: layer 0)" if layer is None else ""
    return f" / layer {target.name!r}{note}"


def _unique(items: list[int]) -> list[int]:
    return list(dict.fromkeys(items))


def _edit(
    path: str | Path,
    frame: FrameRef,
    layer: LayerRef,
    op: Callable[[Layer, Sprite], int],
    what: str,
    show: str = SHOW_DEFAULT,
) -> str:
    """Apply ``op`` to the selected layer(s), save, and describe the result.

    ``show`` controls what is echoed after the summary line: ``"none"``,
    ``"bbox"`` (box around the changed pixels of the first target frame, with
    absolute rulers) or ``"full"`` (the whole frame).
    """
    mode = view.show_mode(show)
    sprite = Sprite.load(path)
    total = 0
    frames = _target_frames(sprite, frame)
    first = _target_layer(sprite, frames[0], layer)
    before = [row[:] for row in first.grid]
    for fi in frames:
        total += op(_target_layer(sprite, fi, layer), sprite)
    sprite.save(path)
    msg = f"{what}: {total} pixels affected in {_frames_str(frames)}{_layer_str(sprite, frames[0], layer, first)}"
    body = view.edit_result_text(sprite, frames[0], layer, before, first, mode)
    if body:
        msg += "\n" + body
    if len(frames) > 1 and mode != "none":
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
    onion_layer: str | int | None = None,
) -> str:
    """Text view of one frame, or of several: ``frame`` takes the usual lists
    (``"0..3"``, ``"1,3"``, ``"all"``) and prints each selected frame."""
    sprite = Sprite.load(path)
    if all_frames:
        return view.all_frames_text(sprite, layer)
    frames = _target_frames(sprite, frame)
    return "\n\n".join(
        view.frame_text(sprite, fi, layer, ruler=ruler, onion=onion, onion_layer=onion_layer) for fi in frames
    )


def diff(path: str | Path, a: FrameRef, b: FrameRef, layer: LayerRef = None, limit: int = 0) -> str:
    """How frame ``b`` differs from ``a``; ``limit`` caps the per-pixel list (0 = grid only, -1 = all)."""
    return view.diff_text(Sprite.load(path), a, b, layer, limit)


def validate(path: str | Path) -> str:
    problems = Sprite.load(path).validate()
    return "ok" if not problems else "\n".join(problems)


def _pixel_count(sprite: Sprite) -> int:
    return sum(
        1 for f in sprite.frames for l in f.layers for row in l.grid for ch in row if ch != TRANSPARENT_KEY
    )


def resize(path: str | Path, width: int, height: int, anchor: str = "top-left", show: str = SHOW_DEFAULT) -> str:
    """Resize the canvas. ``show`` = none | bbox (content box of frame 0, default) | full."""
    mode = view.show_mode(show)
    sprite = Sprite.load(path)
    anchor = normalize_anchor(anchor)
    ow, oh = sprite.width, sprite.height
    dx, dy = anchor_offset(anchor, ow, oh, width, height)
    was = _pixel_count(sprite)
    sprite.resize(width, height, anchor)
    sprite.save(path)
    msg = f"resized {ow}x{oh} -> {width}x{height} (anchor {anchor}; content moved by ({dx:+d},{dy:+d}))"
    lost = was - _pixel_count(sprite)
    if lost:
        msg += f"; {lost} pixels cropped away"
    body = view.resize_result_text(sprite, mode)
    return msg + ("\n" + body if body else "")


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
    count: int = 1,
) -> str:
    """Add ``count`` frames (default 1). With a ``name`` and ``count > 1`` the
    frames are named ``name0, name1, ...``."""
    if count < 1:
        raise SpriteError("count must be at least 1")
    sprite = Sprite.load(path)
    # resolve the source by name so inserting before it does not shift the reference
    src_name = sprite.frame(copy_from).name if copy_from is not None else None
    added = []
    for i in range(count):
        n = name if (name is None or count == 1) else f"{name}{i}"
        pos = None if at is None else at + i
        added.append(sprite.add_frame(n, duration_ms, src_name, pos))
    sprite.save(path)
    src = f" (copied from {copy_from})" if copy_from is not None else ""
    listing = ", ".join(f"[{sprite.frames.index(f)}] {f.name}" for f in added)
    if count == 1:
        return f"added frame {listing}{src}; now {len(sprite.frames)} frames"
    return f"added {count} frames: {listing}{src}; now {len(sprite.frames)} frames"


def frame_remove(path: str | Path, frame: FrameRef) -> str:
    sprite = Sprite.load(path)
    name = sprite.frame(frame).name
    sprite.remove_frame(frame)
    sprite.save(path)
    return f"removed frame {name!r}; now {len(sprite.frames)} frames"


def frame_move(path: str | Path, frame: FrameRef, to: int) -> str:
    """Move a frame to a new index. Tags keep pointing at the same frames (see :meth:`Sprite.move_frame`)."""
    sprite = Sprite.load(path)
    sprite.move_frame(frame, to)
    sprite.save(path)
    msg = "frames: " + ", ".join(f"[{i}] {f.name}" for i, f in enumerate(sprite.frames))
    if sprite.tags:
        msg += "\ntags: " + ", ".join(f"{t.name}: {t.start}..{t.end}" for t in sprite.tags)
    return msg


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
    return view.layers_text(Sprite.load(path))


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
#
# Every drawing/transform function takes ``show`` = "none" | "bbox" | "full"
# (default "bbox": only the box around the changed pixels is echoed back).


def _keys_str(keys: Keys) -> str:
    return "" if keys is None else f" keys({keys})"


def draw_pixels(
    path: str | Path,
    points: list[tuple[int, int]],
    key: str,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.pixels(l, s.palette, points, key), f"pixels {key!r}", show)


def draw_line(
    path: str | Path,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    key: str,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(
        path, frame, layer, lambda l, s: ops.line(l, s.palette, x0, y0, x1, y1, key), f"line {key!r}", show
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
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.rect(l, s.palette, x0, y0, x1, y1, key, fill),
        f"{'filled ' if fill else ''}rect {key!r}",
        show,
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
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.ellipse(l, s.palette, x0, y0, x1, y1, key, fill),
        f"{'filled ' if fill else ''}ellipse {key!r}",
        show,
    )


def draw_fill(
    path: str | Path,
    x: int,
    y: int,
    key: str,
    diagonal: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(
        path, frame, layer, lambda l, s: ops.flood_fill(l, s.palette, x, y, key, diagonal), f"fill {key!r}", show
    )


def replace_mapping(old: str | None, new: str | None, mapping: dict[str, str] | None = None) -> dict[str, str]:
    """Build the key mapping for :func:`draw_replace`.

    Either ``mapping`` (``{"g": "r", "G": "R"}``) or ``old``/``new`` strings of
    equal length whose characters pair up (``"gGl"`` -> ``"rRw"``).
    """
    out: dict[str, str] = {}
    if old or new:
        old, new = old or "", new or ""
        if len(old) != len(new) or not old:
            raise SpriteError(f"old and new must be non-empty and the same length ({old!r} vs {new!r})")
        for o, n in zip(old, new):
            if o in out and out[o] != n:
                raise SpriteError(f"key {o!r} is mapped twice ({out[o]!r} and {n!r})")
            out[o] = n
    for o, n in (mapping or {}).items():
        if o in out and out[o] != n:
            raise SpriteError(f"key {o!r} is mapped twice ({out[o]!r} and {n!r})")
        out[o] = n
    if not out:
        raise SpriteError("replace needs old/new keys or a mapping")
    return out


def draw_replace(
    path: str | Path,
    old: str | None = None,
    new: str | None = None,
    frame: FrameRef = ALL,
    layer: LayerRef = None,
    region: Region = None,
    show: str = SHOW_DEFAULT,
    mapping: dict[str, str] | None = None,
) -> str:
    """Recolor: replace keys in one pass. ``old``/``new`` may be several
    characters each (``"gGl"`` -> ``"rRw"``) or use ``mapping``; all pairs are
    applied simultaneously so ``g<->G`` swaps work."""
    m = replace_mapping(old, new, mapping)
    desc = ",".join(f"{o!r}->{n!r}" for o, n in m.items())
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.replace_map(l, s.palette, m, region),
        f"replace {desc}{_region_str(region)}",
        show,
    )


def draw_clear(
    path: str | Path,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    region: Region = None,
    keys: Keys = None,
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(
        path, frame, layer, lambda l, s: ops.clear(l, region, keys), "clear" + _region_str(region) + _keys_str(keys), show
    )


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
    keys: Keys = None,
    show: str = SHOW_DEFAULT,
) -> str:
    """Copy a region of one frame/layer onto (x, y) of another (or the same)."""
    return _move_region(
        path, region, x, y, from_frame, to_frame, from_layer, to_layer, overwrite, keys, show, cut=False
    )


def draw_cut(
    path: str | Path,
    to_layer: LayerRef,
    keys: Keys = None,
    region: Region = None,
    x: int | None = None,
    y: int | None = None,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    to_frame: FrameRef | None = None,
    overwrite: bool = False,
    show: str = SHOW_DEFAULT,
) -> str:
    """Move pixels (all, or only those with ``keys``, or only inside ``region``)
    from ``layer`` to ``to_layer`` in one call; the source pixels are erased.

    Without ``x``/``y`` the pixels keep their position, which is how you split
    a prop (staff, weapon, shadow) off onto its own layer after the fact.
    ``frame`` may be a list or "all"; the cut then happens within each frame
    unless ``to_frame`` names a single destination frame.
    """
    return _move_region(
        path, region, x, y, frame, to_frame, layer, to_layer, overwrite, keys, show, cut=True
    )


def _move_region(
    path: str | Path,
    region: Region,
    x: int | None,
    y: int | None,
    from_frame: FrameRef,
    to_frame: FrameRef | None,
    from_layer: LayerRef,
    to_layer: LayerRef,
    overwrite: bool,
    keys: Keys,
    show: str,
    cut: bool,
) -> str:
    mode = view.show_mode(show)
    sprite = Sprite.load(path)
    src_frames = _target_frames(sprite, from_frame)
    dst_layer_ref = to_layer if to_layer is not None else from_layer
    if x is None or y is None:
        # default: same position as the region's top-left
        bx, by, _, _ = ops._box(_target_layer(sprite, src_frames[0], from_layer), region)
        x = bx if x is None else x
        y = by if y is None else y
    pairs: list[tuple[int, int]]
    if to_frame is None:
        pairs = [(fi, fi) for fi in src_frames]  # within each frame
    else:
        dst_frames = _target_frames(sprite, to_frame)
        if len(src_frames) == 1:
            pairs = [(src_frames[0], fi) for fi in dst_frames]  # one source -> many destinations
        elif len(dst_frames) == 1:
            pairs = [(fi, dst_frames[0]) for fi in src_frames]  # many sources -> one destination
        elif len(src_frames) == len(dst_frames):
            pairs = list(zip(src_frames, dst_frames))
        else:
            raise SpriteError(
                f"cannot pair {len(src_frames)} source frames with {len(dst_frames)} destination frames"
            )
    view_fi = pairs[0][1]
    first_dst = _target_layer(sprite, view_fi, dst_layer_ref)
    before = [row[:] for row in first_dst.grid]
    total = 0
    for sf, df in pairs:
        src = _target_layer(sprite, sf, from_layer)
        dst = _target_layer(sprite, df, dst_layer_ref)
        if cut:
            if src is dst and (x, y) == ops._box(src, region)[:2]:
                raise SpriteError("cut needs a different layer/frame or an offset (x, y); use draw_copy otherwise")
            total += ops.cut_region(src, dst, region, x, y, overwrite, keys)
        else:
            total += ops.copy_region(src, dst, region, x, y, overwrite, keys)
    sprite.save(path)
    what = "cut" if cut else "copy"
    dst_desc = _frames_str([df for _, df in pairs])
    if to_layer is not None and to_layer != from_layer:
        dst_desc += f" layer {first_dst.name!r}"
    msg = (
        f"{what}{_region_str(region)}{_keys_str(keys)} from {_frames_str(_unique([sf for sf, _ in pairs]))}"
        f" -> ({x},{y}) {dst_desc}: {total} pixels affected"
    )
    body = view.edit_result_text(sprite, view_fi, dst_layer_ref, before, first_dst, mode)
    if body:
        msg += "\n" + body
    if len(pairs) > 1 and mode != "none":
        msg += f"\n(+{len(pairs) - 1} more frame(s) changed; use show to inspect)"
    return msg


def draw_paste(
    path: str | Path,
    grid: str,
    x: int = 0,
    y: int = 0,
    overwrite: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.paste(l, s.palette, grid, x, y, skip_transparent=not overwrite),
        f"paste at ({x},{y})",
        show,
    )


def draw_set(
    path: str | Path, grid: str, frame: FrameRef = 0, layer: LayerRef = None, show: str = SHOW_DEFAULT
) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.set_grid(l, s.palette, grid), "set grid", show)


def draw_outline(
    path: str | Path,
    key: str,
    diagonal: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    outer_only: bool = False,
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.outline(l, s.palette, key, diagonal, outer_only),
        f"{'outer ' if outer_only else ''}outline {key!r}",
        show,
    )


# --------------------------------------------------------------------------- #
# transforms
# --------------------------------------------------------------------------- #


def flip(
    path: str | Path,
    axis: str,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    region: Region = None,
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(
        path, frame, layer, lambda l, s: ops.flip(l, axis, region), f"flip {axis}{_region_str(region)}", show
    )


def rotate(
    path: str | Path, turns: int = 1, frame: FrameRef = 0, layer: LayerRef = None, show: str = SHOW_DEFAULT
) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.rotate(l, turns), f"rotate {turns * 90}°", show)


def shift(
    path: str | Path,
    dx: int,
    dy: int,
    wrap: bool = False,
    frame: FrameRef = 0,
    layer: LayerRef = None,
    region: Region = None,
    keys: Keys = None,
    show: str = SHOW_DEFAULT,
    overwrite: bool = False,
) -> str:
    """Translate content. Moved pixels merge into the landing area unless
    ``overwrite`` (then the box's transparent pixels move too and replace
    what they land on). Pixels pushed off the canvas are lost and the summary
    line says how many (``(N pixels dropped at the canvas edge)``)."""
    stats: dict[str, int] = {}
    msg = _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.shift(l, dx, dy, wrap, region, keys, overwrite, stats),
        f"shift ({dx},{dy}){_region_str(region)}{_keys_str(keys)}{' overwrite' if overwrite else ''}",
        show,
    )
    if stats.get("dropped"):
        head, _, rest = msg.partition("\n")
        msg = f"{head} ({stats['dropped']} pixels dropped at the canvas edge)" + (f"\n{rest}" if rest else "")
    return msg


def stretch(
    path: str | Path,
    region: Region = None,
    dx: int = 0,
    dy: int = 0,
    anchor: str = "bottom",
    frame: FrameRef = 0,
    layer: LayerRef = None,
    show: str = SHOW_DEFAULT,
) -> str:
    """Squash/stretch a region by ``dx`` columns and ``dy`` rows (nearest
    neighbour), keeping the ``anchor`` edge in place (default ``bottom``: feet
    planted, centred horizontally). See :func:`ops.stretch`."""
    anchor = normalize_anchor(anchor)
    if dx == 0 and dy == 0:
        raise SpriteError("stretch needs a non-zero dx and/or dy")
    return _edit(
        path,
        frame,
        layer,
        lambda l, s: ops.stretch(l, region, dx, dy, anchor),
        f"stretch ({dx:+d},{dy:+d}){_region_str(region)} anchor {anchor}",
        show,
    )


def mirror(
    path: str | Path,
    axis: str = "h",
    source: str = "first",
    frame: FrameRef = 0,
    layer: LayerRef = None,
    show: str = SHOW_DEFAULT,
) -> str:
    return _edit(path, frame, layer, lambda l, s: ops.mirror(l, axis, source), f"mirror {axis} from {source}", show)


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
    metadata: str | Path | None = None,
) -> str:
    """Import a PNG (or sheet) into a new sprite file.

    Sheet metadata (the ``.json`` written by ``export_sheet``) restores frame
    names, durations, tags and the palette. It is read from ``metadata`` if
    given, otherwise from ``<png>.json`` next to the image when that exists.
    """
    p = Path(out)
    if p.exists():
        raise SpriteError(f"{p} already exists")
    meta = render.load_sheet_metadata(png, metadata)
    sprite = render.import_png(
        png, name, _palette_from(palette_from), max_colors, frame_width, frame_height, meta
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    sprite.save(p)
    msg = f"imported {png} -> {p}"
    if meta is not None:
        msg += f"\nmetadata: {meta.path} (frame names, durations, {len(sprite.tags)} tag(s)"
        msg += ", palette)" if meta.palette and palette_from in (None, "") else ")"
        if meta.notes:
            msg += "\n" + "\n".join(f"  note: {n}" for n in meta.notes)
    return msg + "\n" + view.info_text(sprite)


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
