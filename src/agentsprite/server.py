"""MCP server exposing agentsprite as tools (``agentsprite server``)."""

from __future__ import annotations

import functools
import threading
from typing import Optional

from mcp.server.mcpserver import Image, MCPServer

from . import api
from .model import SpriteError

GUIDE = """\
agentsprite: pixel-art sprites for AI agents
============================================

A sprite file (*.sprite.json) holds: a palette, a stack of frames, and each
frame a stack of layers. Pixels are a text grid where every character is a
palette KEY. '.' is always transparent.

Workflow
  1. sprite_new(path, width, height)              create the canvas
  2. palette_set(path, {"k": "#000000", "r": "#e04040", ...})
     or palette_preset(path, "pico-8") for a ready-made palette.
  3. draw_set / draw_paste with a grid string, e.g.
        ..kk..
        .krrk.
        ..kk..
     or draw_line / draw_rect / draw_ellipse / draw_fill / draw_pixels
  4. sprite_show(path) to read back the grid (with x/y rulers) after each edit.
     preview(path) returns a PNG if you can see images.
     sprite_show(path, frame="1", onion="prev") ghosts the previous frame
     underneath (') so you can check how an animation frame lines up.
  5. frame_add(path, copy_from=0) then edit the copy; repeat for animation.
     transform_shift / flip / mirror help make variations quickly.
     Pass region=[x0,y0,x1,y1] to shift/flip/clear only part of the layer
     (e.g. bob the torso while the feet stay). draw_copy moves a region
     between frames/layers.
  6. tag_set(path, "walk", 0, 3) to name animation ranges.
  7. export_sheet(path, "out/hero.png", columns=4) -> PNG + .json metadata
     export_gif(path, "out/hero.gif", scale=8) to check the motion
     (export_apng for lossless RGBA animation).

Coordinates: 0-based, x to the right, y down. Ranges are inclusive.
Frame refs: index ("0"), name ("idle1"), or "all". Layer refs: index or name
(default layer 0). Grid strings: rows separated by newlines; spaces inside a
row are ignored; short rows are padded with '.'.

Tips for good pixel art
  - Pick the palette first (4-8 colors). Use a dark outline key ('k').
  - Draw the silhouette filled, then add the outline with draw_outline
    (outer_only=True keeps gaps between limbs open).
  - Use mirror for symmetric characters, then break symmetry for detail.
  - Animate with small shifts (1px bob) and duplicated frames.
"""

mcp = MCPServer(
    "agentsprite",
    version=__import__("agentsprite").__version__,
    instructions="Pixel-art sprite editor. Call guide() once to learn the workflow. "
    "Sprites live in *.sprite.json files given by absolute path.",
)


# Tools return plain text. Without this, mcp 2.x also emits the string as
# structured_content {"result": "..."} which some clients display with escaped
# newlines, mangling the grids.
tool = functools.partial(mcp.tool, structured_output=False)


# mcp runs sync tools on worker threads, and every api call is load -> edit ->
# save. Two concurrent edits of the same file would silently lose one of them,
# so calls are serialised per sprite path.
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(path: object) -> threading.Lock:
    key = str(path)
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _wrap(fn, *args, **kwargs) -> str:
    path = args[0] if args else kwargs.get("path", "")
    try:
        with _lock_for(path):
            return fn(*args, **kwargs)
    except SpriteError as e:
        return f"error: {e}"
    except Exception as e:  # never let a bare exception reach the client without a message
        return f"error: {type(e).__name__}: {e}"


def _layer(layer: Optional[str]):
    return layer if layer not in (None, "") else None


# --------------------------------------------------------------------------- #
# document
# --------------------------------------------------------------------------- #


@tool()
def guide() -> str:
    """Return the agentsprite usage guide (read this first)."""
    return GUIDE


@tool()
def sprite_new(
    path: str,
    width: int,
    height: int,
    name: Optional[str] = None,
    layer: str = "base",
    palette_from: Optional[str] = None,
) -> str:
    """Create a new sprite file at `path` (should end in .sprite.json) with one empty frame.

    `palette_from` copies the palette of an existing sprite file so a set of sprites share keys/colors."""
    return _wrap(api.new, path, width, height, name, layer, _layer(palette_from))


@tool()
def sprite_info(path: str) -> str:
    """Summarize a sprite: size, palette, frames, layers, tags, notes, problems."""
    return _wrap(api.info, path)


@tool()
def sprite_show(
    path: str, frame: str = "0", layer: Optional[str] = None, all_frames: bool = False, onion: Optional[str] = None
) -> str:
    """Show a frame as a text grid with x/y rulers. Omit `layer` for the composite of visible layers.

    `onion` = "prev" | "next" | frame index/name draws that frame's silhouette underneath as
    ghost markers (') wherever this frame is transparent, to check animation alignment."""
    return _wrap(api.show, path, frame, _layer(layer), all_frames, True, _layer(onion))


@tool()
def sprite_diff(path: str, frame_a: str, frame_b: str, layer: Optional[str] = None) -> str:
    """List the pixels that differ between two frames."""
    return _wrap(api.diff, path, frame_a, frame_b, _layer(layer))


@tool()
def sprite_resize(path: str, width: int, height: int, anchor: str = "top-left") -> str:
    """Resize the canvas, cropping or padding with transparent. anchor: top-left|center|bottom|... ."""
    return _wrap(api.resize, path, width, height, anchor)


@tool()
def sprite_notes(path: str, notes: str) -> str:
    """Store free-form notes (design intent, style rules) inside the sprite file."""
    return _wrap(api.set_notes, path, notes)


@tool()
def preview(
    path: str, frame: str = "0", scale: int = 8, layer: Optional[str] = None, checkerboard: bool = True
) -> Image | str:
    """Render one frame to a PNG image (upscaled) so a vision-capable agent can look at it."""
    try:
        return Image(data=api.render_bytes(path, frame, scale, None, checkerboard, _layer(layer)), format="png")
    except Exception as e:
        return f"error: {e}"


@tool()
def preview_sheet(path: str, scale: int = 8, columns: Optional[int] = None) -> Image | str:
    """Render all frames side by side as one PNG image."""
    try:
        return Image(data=api.render_sheet_bytes(path, scale, columns), format="png")
    except Exception as e:
        return f"error: {e}"


# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #


@tool()
def palette_set(path: str, colors: dict[str, str]) -> str:
    """Add/update palette entries. `colors` maps single-character keys to #RRGGBB or #RRGGBBAA."""
    return _wrap(api.palette_set_many, path, colors)


@tool()
def palette_remove(path: str, key: str, replace_with: str = ".") -> str:
    """Remove a palette key; pixels that used it become `replace_with`."""
    return _wrap(api.palette_remove, path, key, replace_with)


@tool()
def palette_preset(path: str, name: str, keys: Optional[str] = None) -> str:
    """Merge a built-in palette preset into the sprite: pico-8, sweetie-16, endesga-32, gameboy, 1bit.

    `keys` optionally gives one key per color in preset order (e.g. "kwrgb...") instead of the
    preset's default keys. Call palette_presets() to see every preset with its colors."""
    return _wrap(api.palette_preset, path, name, _layer(keys))


@tool()
def palette_presets() -> str:
    """List the built-in palette presets with their default keys and colors."""
    return _wrap(api.palette_presets)


# --------------------------------------------------------------------------- #
# frames / layers / tags
# --------------------------------------------------------------------------- #


@tool()
def frame_add(
    path: str,
    name: Optional[str] = None,
    duration_ms: int = 100,
    copy_from: Optional[str] = None,
    at: Optional[int] = None,
) -> str:
    """Append a frame (or insert at `at`). `copy_from` duplicates an existing frame's pixels."""
    return _wrap(api.frame_add, path, name, duration_ms, copy_from, at)


@tool()
def frame_remove(path: str, frame: str) -> str:
    """Delete a frame by index or name."""
    return _wrap(api.frame_remove, path, frame)


@tool()
def frame_move(path: str, frame: str, to: int) -> str:
    """Move a frame to a new index."""
    return _wrap(api.frame_move, path, frame, to)


@tool()
def frame_update(path: str, frame: str, name: Optional[str] = None, duration_ms: Optional[int] = None) -> str:
    """Rename a frame and/or set its duration in milliseconds."""
    return _wrap(api.frame_update, path, frame, name, duration_ms)


@tool()
def layer_add(path: str, name: str, at: Optional[int] = None) -> str:
    """Add a layer to every frame (on top unless `at` is given; 0 = bottom)."""
    return _wrap(api.layer_add, path, name, at)


@tool()
def layer_remove(path: str, layer: str) -> str:
    """Remove a layer from every frame."""
    return _wrap(api.layer_remove, path, layer)


@tool()
def layer_move(path: str, layer: str, to: int) -> str:
    """Reorder a layer (0 = bottom)."""
    return _wrap(api.layer_move, path, layer, to)


@tool()
def layer_rename(path: str, layer: str, new_name: str) -> str:
    """Rename a layer."""
    return _wrap(api.layer_rename, path, layer, new_name)


@tool()
def layer_set_visible(path: str, layer: str, visible: bool) -> str:
    """Show or hide a layer (hidden layers are excluded from renders and composites)."""
    return _wrap(api.layer_visible, path, layer, visible)


@tool()
def tag_set(path: str, name: str, start: int, end: int, direction: str = "forward", loop: bool = True) -> str:
    """Create/update an animation tag over frames start..end (inclusive). direction: forward|reverse|pingpong."""
    return _wrap(api.tag_set, path, name, start, end, direction, loop)


@tool()
def tag_remove(path: str, name: str) -> str:
    """Remove an animation tag."""
    return _wrap(api.tag_remove, path, name)


# --------------------------------------------------------------------------- #
# drawing
# --------------------------------------------------------------------------- #


@tool()
def draw_set(path: str, grid: str, frame: str = "0", layer: Optional[str] = None) -> str:
    """Replace a whole layer with a grid of palette keys (rows separated by newlines; short rows padded with '.')."""
    return _wrap(api.draw_set, path, grid, frame, _layer(layer))


@tool()
def draw_paste(
    path: str,
    grid: str,
    x: int = 0,
    y: int = 0,
    overwrite: bool = False,
    frame: str = "0",
    layer: Optional[str] = None,
) -> str:
    """Stamp a grid of keys with its top-left at (x, y). '.' cells are skipped unless overwrite=True."""
    return _wrap(api.draw_paste, path, grid, x, y, overwrite, frame, _layer(layer))


@tool()
def draw_pixels(path: str, points: list[list[int]], key: str, frame: str = "0", layer: Optional[str] = None) -> str:
    """Set pixels at the given [x, y] points to `key`."""
    pts = [(int(p[0]), int(p[1])) for p in points]
    return _wrap(api.draw_pixels, path, pts, key, frame, _layer(layer))


@tool()
def draw_line(path: str, x0: int, y0: int, x1: int, y1: int, key: str, frame: str = "0", layer: Optional[str] = None) -> str:
    """Draw a 1px line from (x0,y0) to (x1,y1)."""
    return _wrap(api.draw_line, path, x0, y0, x1, y1, key, frame, _layer(layer))


@tool()
def draw_rect(
    path: str, x0: int, y0: int, x1: int, y1: int, key: str, fill: bool = False, frame: str = "0", layer: Optional[str] = None
) -> str:
    """Draw a rectangle with inclusive corners (outline, or filled)."""
    return _wrap(api.draw_rect, path, x0, y0, x1, y1, key, fill, frame, _layer(layer))


@tool()
def draw_ellipse(
    path: str, x0: int, y0: int, x1: int, y1: int, key: str, fill: bool = False, frame: str = "0", layer: Optional[str] = None
) -> str:
    """Draw an ellipse inscribed in the inclusive box (x0,y0)-(x1,y1)."""
    return _wrap(api.draw_ellipse, path, x0, y0, x1, y1, key, fill, frame, _layer(layer))


@tool()
def draw_fill(path: str, x: int, y: int, key: str, diagonal: bool = False, frame: str = "0", layer: Optional[str] = None) -> str:
    """Flood-fill the connected region containing (x, y) with `key`."""
    return _wrap(api.draw_fill, path, x, y, key, diagonal, frame, _layer(layer))


@tool()
def draw_replace(path: str, old: str, new: str, frame: str = "all", layer: Optional[str] = None) -> str:
    """Replace every `old` key with `new` (all frames by default). Useful for recoloring."""
    return _wrap(api.draw_replace, path, old, new, frame, _layer(layer))


@tool()
def draw_outline(
    path: str,
    key: str,
    diagonal: bool = False,
    outer_only: bool = False,
    frame: str = "0",
    layer: Optional[str] = None,
) -> str:
    """Add a 1px outline of `key` around all non-transparent pixels.

    outer_only=True leaves enclosed gaps (holes, space between legs/arms) untouched
    and only outlines pixels reachable from the canvas border."""
    return _wrap(api.draw_outline, path, key, diagonal, frame, _layer(layer), outer_only)


@tool()
def draw_clear(path: str, frame: str = "0", layer: Optional[str] = None, region: Optional[list[int]] = None) -> str:
    """Erase a layer (or only `region` = [x0, y0, x1, y1], inclusive) to transparent."""
    return _wrap(api.draw_clear, path, frame, _layer(layer), region)


@tool()
def draw_copy(
    path: str,
    region: list[int],
    x: int,
    y: int,
    from_frame: str = "0",
    to_frame: str = "0",
    from_layer: Optional[str] = None,
    to_layer: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """Copy `region` = [x0, y0, x1, y1] (inclusive) of from_frame/from_layer so its top-left
    lands at (x, y) on to_frame/to_layer. Same frame is allowed (duplicate a part);
    to_frame may be "all". Transparent pixels are skipped unless overwrite=True."""
    return _wrap(api.draw_copy, path, region, x, y, from_frame, to_frame, _layer(from_layer), _layer(to_layer), overwrite)


# --------------------------------------------------------------------------- #
# transforms
# --------------------------------------------------------------------------- #


@tool()
def transform_flip(
    path: str, axis: str, frame: str = "0", layer: Optional[str] = None, region: Optional[list[int]] = None
) -> str:
    """Flip a layer (or only `region` = [x0, y0, x1, y1]) horizontally ('h') or vertically ('v')."""
    return _wrap(api.flip, path, axis, frame, _layer(layer), region)


@tool()
def transform_rotate(path: str, turns: int = 1, frame: str = "0", layer: Optional[str] = None) -> str:
    """Rotate a square layer by 90° clockwise `turns` times."""
    return _wrap(api.rotate, path, turns, frame, _layer(layer))


@tool()
def transform_shift(
    path: str,
    dx: int,
    dy: int,
    wrap: bool = False,
    frame: str = "0",
    layer: Optional[str] = None,
    region: Optional[list[int]] = None,
) -> str:
    """Translate layer content by (dx, dy). Pixels leaving the canvas are lost unless wrap=True.

    With `region` = [x0, y0, x1, y1] only pixels inside the box move (e.g. shift just the
    torso down by 1 while the feet stay put); they may land outside the box."""
    return _wrap(api.shift, path, dx, dy, wrap, frame, _layer(layer), region)


@tool()
def transform_mirror(path: str, axis: str = "h", source: str = "first", frame: str = "0", layer: Optional[str] = None) -> str:
    """Make a layer symmetric: copy the `source` half ('first' = left/top) onto the other half."""
    return _wrap(api.mirror, path, axis, source, frame, _layer(layer))


# --------------------------------------------------------------------------- #
# export / import
# --------------------------------------------------------------------------- #


@tool()
def export_png(path: str, out: str, frame: str = "0", scale: int = 1, background: Optional[str] = None) -> str:
    """Export one frame to a PNG file (transparent unless `background` color is given)."""
    return _wrap(api.export_png, path, out, frame, scale, background)


@tool()
def export_frames(path: str, out_dir: str, scale: int = 1, background: Optional[str] = None) -> str:
    """Export every frame as a separate PNG in `out_dir`."""
    return _wrap(api.export_frames, path, out_dir, scale, background)


@tool()
def export_sheet(
    path: str,
    out: str,
    columns: Optional[int] = None,
    padding: int = 0,
    scale: int = 1,
    tag: Optional[str] = None,
    metadata: bool = True,
) -> str:
    """Export a sprite sheet PNG plus Aseprite-compatible JSON metadata (frames, durations, frameTags)."""
    return _wrap(api.export_sheet, path, out, columns, padding, scale, tag, metadata)


@tool()
def export_gif(path: str, out: str, scale: int = 1, tag: Optional[str] = None, background: Optional[str] = None) -> str:
    """Export an animated GIF of all frames or one tag."""
    return _wrap(api.export_gif, path, out, scale, tag, background)


@tool()
def export_apng(path: str, out: str, scale: int = 1, tag: Optional[str] = None, background: Optional[str] = None) -> str:
    """Export an animated PNG (APNG) of all frames or one tag: full RGBA, no color quantization."""
    return _wrap(api.export_apng, path, out, scale, tag, background)


@tool()
def import_png(
    png: str,
    out: str,
    name: Optional[str] = None,
    frame_width: Optional[int] = None,
    frame_height: Optional[int] = None,
    max_colors: int = 32,
    palette_from: Optional[str] = None,
) -> str:
    """Import a PNG (or a sheet sliced by frame_width/frame_height) into a new sprite file.

    `palette_from` reuses the keys/colors of an existing sprite file; colors not in that
    palette get new keys."""
    return _wrap(api.import_png, png, out, name, frame_width, frame_height, max_colors, _layer(palette_from))


@mcp.resource("agentsprite://guide")
def guide_resource() -> str:
    """Usage guide for agentsprite."""
    return GUIDE


def run(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8765) -> None:
    if transport not in ("stdio", "sse", "streamable-http"):
        raise SystemExit(f"unknown transport {transport!r}")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=transport, host=host, port=port)  # type: ignore[call-overload]


if __name__ == "__main__":
    run()
