"""``agentsprite`` command line interface (thin wrapper over :mod:`agentsprite.api`)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer

from . import api
from .model import SpriteError

app = typer.Typer(
    name="agentsprite",
    help="Pixel-art sprite editor for AI agents. Sprites are text grids of palette keys stored in .sprite.json files.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)

FileArg = Annotated[Path, typer.Argument(help="sprite file (.sprite.json)")]
FrameOpt = Annotated[str, typer.Option("--frame", "-f", help="frame index/name, or 'all'")]
LayerOpt = Annotated[Optional[str], typer.Option("--layer", "-l", help="layer index/name (default: 0)")]
KeyArg = Annotated[str, typer.Argument(help="palette key (single character)")]


def _run(fn: Callable[[], str]) -> None:
    try:
        typer.echo(fn())
    except SpriteError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)


def _read_grid(grid: Optional[str], grid_file: Optional[Path]) -> str:
    if grid_file is not None:
        return grid_file.read_text()
    if grid is not None and grid != "-":
        return grid.replace("\\n", "\n").replace("/", "\n")
    if sys.stdin.isatty():
        raise SpriteError("pass GRID as an argument (rows separated by '/' or '\\n'), --file, or pipe via stdin")
    return sys.stdin.read()


# --------------------------------------------------------------------------- #
# document
# --------------------------------------------------------------------------- #


@app.command()
def new(
    file: FileArg,
    width: Annotated[int, typer.Option("--width", "-w")] = 16,
    height: Annotated[int, typer.Option("--height", "-h")] = 16,
    name: Annotated[Optional[str], typer.Option(help="sprite name (default: file stem)")] = None,
    palette_from: Annotated[Optional[Path], typer.Option("--palette-from", help="copy the palette of this sprite file")] = None,
    layer: Annotated[str, typer.Option(help="name of the initial layer")] = "base",
) -> None:
    """Create a new sprite file."""
    _run(lambda: api.new(file, width, height, name, layer, palette_from))


@app.command()
def info(file: FileArg) -> None:
    """Print size, palette, frames, layers, tags and any problems."""
    _run(lambda: api.info(file))


@app.command()
def show(
    file: FileArg,
    frame: FrameOpt = "0",
    layer: LayerOpt = None,
    all_frames: Annotated[bool, typer.Option("--all", "-a", help="show every frame")] = False,
    no_ruler: Annotated[bool, typer.Option("--no-ruler", help="omit coordinate rulers")] = False,
    onion: Annotated[Optional[str], typer.Option("--onion", "-o", help="ghost another frame underneath: 'prev', 'next', index or name")] = None,
) -> None:
    """Print a frame (composite, or a single layer) as a text grid."""
    _run(lambda: api.show(file, frame, layer, all_frames, ruler=not no_ruler, onion=onion))


@app.command()
def diff(file: FileArg, a: str, b: str, layer: LayerOpt = None) -> None:
    """List pixels that differ between two frames."""
    _run(lambda: api.diff(file, a, b, layer))


@app.command()
def validate(file: FileArg) -> None:
    """Check the document for inconsistencies."""
    _run(lambda: api.validate(file))


@app.command()
def resize(
    file: FileArg,
    width: int,
    height: int,
    anchor: Annotated[str, typer.Option(help="top-left, top, top-right, left, center, right, bottom-left, bottom, bottom-right")] = "top-left",
) -> None:
    """Resize the canvas (crop or pad with transparent)."""
    _run(lambda: api.resize(file, width, height, anchor))


@app.command()
def notes(file: FileArg, text: str) -> None:
    """Attach free-form notes (design intent, style guide) to the sprite."""
    _run(lambda: api.set_notes(file, text))


@app.command()
def rename(file: FileArg, name: str) -> None:
    """Rename the sprite."""
    _run(lambda: api.rename(file, name))


# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #

palette_app = typer.Typer(help="Manage the palette (key -> color).", no_args_is_help=True)
app.add_typer(palette_app, name="palette")


@palette_app.command("set")
def palette_set(
    file: FileArg,
    entries: Annotated[list[str], typer.Argument(help="KEY=COLOR pairs, e.g. r=#ff0000 k=#000")],
) -> None:
    """Add or change palette entries."""

    def go() -> str:
        colors: dict[str, str] = {}
        for e in entries:
            if "=" not in e:
                raise SpriteError(f"expected KEY=COLOR, got {e!r}")
            k, c = e.split("=", 1)
            colors[k] = c
        return api.palette_set_many(file, colors)

    _run(go)


@palette_app.command("rm")
def palette_rm(
    file: FileArg,
    key: KeyArg,
    replace_with: Annotated[str, typer.Option(help="key to replace removed pixels with")] = ".",
) -> None:
    """Remove a palette entry (pixels using it become --replace-with)."""
    _run(lambda: api.palette_remove(file, key, replace_with))


@palette_app.command("ls")
def palette_ls(file: FileArg) -> None:
    """List palette entries."""
    _run(lambda: api.palette_list(file))


@palette_app.command("preset")
def palette_preset(
    file: FileArg,
    name: Annotated[str, typer.Argument(help="preset name (see `palette presets`)")],
    keys: Annotated[Optional[str], typer.Option("--keys", "-k", help="one key per color, in preset order (default: preset keys)")] = None,
) -> None:
    """Merge a built-in palette (pico-8, sweetie-16, endesga-32, gameboy, 1bit) into the sprite."""
    _run(lambda: api.palette_preset(file, name, keys))


@palette_app.command("presets")
def palette_presets() -> None:
    """List the built-in palette presets and their colors."""
    _run(api.palette_presets)


# --------------------------------------------------------------------------- #
# frames
# --------------------------------------------------------------------------- #

frame_app = typer.Typer(help="Manage animation frames.", no_args_is_help=True)
app.add_typer(frame_app, name="frame")


@frame_app.command("add")
def frame_add(
    file: FileArg,
    name: Optional[str] = None,
    duration: Annotated[int, typer.Option("--duration", "-d", help="milliseconds")] = 100,
    copy: Annotated[Optional[str], typer.Option("--copy", "-c", help="duplicate this frame")] = None,
    at: Annotated[Optional[int], typer.Option(help="insert position (default: append)")] = None,
) -> None:
    """Append (or insert) a frame, optionally duplicating an existing one."""
    _run(lambda: api.frame_add(file, name, duration, copy, at))


@frame_app.command("rm")
def frame_rm(file: FileArg, frame: str) -> None:
    """Delete a frame."""
    _run(lambda: api.frame_remove(file, frame))


@frame_app.command("mv")
def frame_mv(file: FileArg, frame: str, to: int) -> None:
    """Move a frame to a new index."""
    _run(lambda: api.frame_move(file, frame, to))


@frame_app.command("set")
def frame_set(
    file: FileArg,
    frame: str,
    name: Optional[str] = None,
    duration: Annotated[Optional[int], typer.Option("--duration", "-d")] = None,
) -> None:
    """Rename a frame and/or change its duration."""
    _run(lambda: api.frame_update(file, frame, name, duration))


@frame_app.command("ls")
def frame_ls(file: FileArg) -> None:
    """List frames."""
    _run(lambda: api.frame_list(file))


# --------------------------------------------------------------------------- #
# layers
# --------------------------------------------------------------------------- #

layer_app = typer.Typer(help="Manage layers (shared across all frames).", no_args_is_help=True)
app.add_typer(layer_app, name="layer")


@layer_app.command("add")
def layer_add(file: FileArg, name: str, at: Optional[int] = None) -> None:
    """Add a layer to every frame (on top by default)."""
    _run(lambda: api.layer_add(file, name, at))


@layer_app.command("rm")
def layer_rm(file: FileArg, layer: str) -> None:
    """Remove a layer from every frame."""
    _run(lambda: api.layer_remove(file, layer))


@layer_app.command("mv")
def layer_mv(file: FileArg, layer: str, to: int) -> None:
    """Reorder a layer (0 = bottom)."""
    _run(lambda: api.layer_move(file, layer, to))


@layer_app.command("rename")
def layer_rename(file: FileArg, layer: str, new_name: str) -> None:
    """Rename a layer."""
    _run(lambda: api.layer_rename(file, layer, new_name))


@layer_app.command("hide")
def layer_hide(file: FileArg, layer: str) -> None:
    """Hide a layer (excluded from renders)."""
    _run(lambda: api.layer_visible(file, layer, False))


@layer_app.command("unhide")
def layer_unhide(file: FileArg, layer: str) -> None:
    """Show a hidden layer."""
    _run(lambda: api.layer_visible(file, layer, True))


@layer_app.command("ls")
def layer_ls(file: FileArg) -> None:
    """List layers bottom to top."""
    _run(lambda: api.layer_list(file))


# --------------------------------------------------------------------------- #
# tags
# --------------------------------------------------------------------------- #

tag_app = typer.Typer(help="Manage animation tags (named frame ranges).", no_args_is_help=True)
app.add_typer(tag_app, name="tag")


@tag_app.command("set")
def tag_set(
    file: FileArg,
    name: str,
    start: Annotated[int, typer.Argument(help="first frame index")],
    end: Annotated[int, typer.Argument(help="last frame index (inclusive)")],
    direction: Annotated[str, typer.Option(help="forward | reverse | pingpong")] = "forward",
    once: Annotated[bool, typer.Option("--once", help="play once instead of looping")] = False,
) -> None:
    """Create or update a tag."""
    _run(lambda: api.tag_set(file, name, start, end, direction, not once))


@tag_app.command("rm")
def tag_rm(file: FileArg, name: str) -> None:
    """Remove a tag."""
    _run(lambda: api.tag_remove(file, name))


@tag_app.command("ls")
def tag_ls(file: FileArg) -> None:
    """List tags."""
    _run(lambda: api.tag_list(file))


# --------------------------------------------------------------------------- #
# drawing
# --------------------------------------------------------------------------- #

draw_app = typer.Typer(
    help="Draw on a layer. Coordinates are 0-based, x right, y down; ranges are inclusive.",
    no_args_is_help=True,
)
app.add_typer(draw_app, name="draw")


@draw_app.command("pixel")
def draw_pixel(
    file: FileArg,
    key: KeyArg,
    points: Annotated[list[str], typer.Argument(help="X,Y pairs, e.g. 3,4 5,4")],
    frame: FrameOpt = "0",
    layer: LayerOpt = None,
) -> None:
    """Set individual pixels."""

    def go() -> str:
        pts = []
        for p in points:
            try:
                x, y = (int(v) for v in p.split(","))
            except ValueError:
                raise SpriteError(f"expected X,Y, got {p!r}") from None
            pts.append((x, y))
        return api.draw_pixels(file, pts, key, frame, layer)

    _run(go)


@draw_app.command("line")
def draw_line(file: FileArg, x0: int, y0: int, x1: int, y1: int, key: KeyArg, frame: FrameOpt = "0", layer: LayerOpt = None) -> None:
    """Draw a 1px line between two points."""
    _run(lambda: api.draw_line(file, x0, y0, x1, y1, key, frame, layer))


@draw_app.command("rect")
def draw_rect(
    file: FileArg, x0: int, y0: int, x1: int, y1: int, key: KeyArg,
    fill: Annotated[bool, typer.Option("--fill")] = False,
    frame: FrameOpt = "0", layer: LayerOpt = None,
) -> None:
    """Draw a rectangle (outline, or --fill)."""
    _run(lambda: api.draw_rect(file, x0, y0, x1, y1, key, fill, frame, layer))


@draw_app.command("ellipse")
def draw_ellipse(
    file: FileArg, x0: int, y0: int, x1: int, y1: int, key: KeyArg,
    fill: Annotated[bool, typer.Option("--fill")] = False,
    frame: FrameOpt = "0", layer: LayerOpt = None,
) -> None:
    """Draw an ellipse inside a bounding box (outline, or --fill)."""
    _run(lambda: api.draw_ellipse(file, x0, y0, x1, y1, key, fill, frame, layer))


@draw_app.command("fill")
def draw_fill(
    file: FileArg, x: int, y: int, key: KeyArg,
    diagonal: Annotated[bool, typer.Option("--diagonal", help="8-connected fill")] = False,
    frame: FrameOpt = "0", layer: LayerOpt = None,
) -> None:
    """Flood-fill the region containing (x, y)."""
    _run(lambda: api.draw_fill(file, x, y, key, diagonal, frame, layer))


@draw_app.command("replace")
def draw_replace(file: FileArg, old: str, new: str, frame: FrameOpt = "all", layer: LayerOpt = None) -> None:
    """Replace one key with another (all frames by default)."""
    _run(lambda: api.draw_replace(file, old, new, frame, layer))


RegionOpt = Annotated[Optional[str], typer.Option("--region", "-r", help="x0,y0,x1,y1 (inclusive); default whole layer")]


@draw_app.command("clear")
def draw_clear(file: FileArg, frame: FrameOpt = "0", layer: LayerOpt = None, region: RegionOpt = None) -> None:
    """Erase a layer (or a region of it)."""
    _run(lambda: api.draw_clear(file, frame, layer, api.parse_region(region)))


@draw_app.command("copy")
def draw_copy(
    file: FileArg,
    x0: int, y0: int, x1: int, y1: int,
    to: Annotated[str, typer.Option("--to", help="destination top-left X,Y")],
    from_frame: Annotated[str, typer.Option("--from-frame", "-f", help="source frame")] = "0",
    to_frame: Annotated[str, typer.Option("--to-frame", "-t", help="destination frame (or 'all')")] = "0",
    from_layer: Annotated[Optional[str], typer.Option("--from-layer", "-l")] = None,
    to_layer: Annotated[Optional[str], typer.Option("--to-layer")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="also copy transparent pixels")] = False,
) -> None:
    """Copy a region (inclusive box) onto another position, frame or layer."""

    def go() -> str:
        try:
            tx, ty = (int(v) for v in to.split(","))
        except ValueError:
            raise SpriteError(f"--to expects X,Y, got {to!r}") from None
        return api.draw_copy(file, (x0, y0, x1, y1), tx, ty, from_frame, to_frame, from_layer, to_layer, overwrite)

    _run(go)


@draw_app.command("paste")
def draw_paste(
    file: FileArg,
    grid: Annotated[Optional[str], typer.Argument(help="rows separated by '/' (or '-' for stdin)")] = None,
    x: Annotated[int, typer.Option("-x")] = 0,
    y: Annotated[int, typer.Option("-y")] = 0,
    grid_file: Annotated[Optional[Path], typer.Option("--file", help="read the grid from a text file")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="also paste transparent pixels")] = False,
    frame: FrameOpt = "0",
    layer: LayerOpt = None,
) -> None:
    """Stamp a grid of keys at (x, y). Transparent '.' pixels are skipped unless --overwrite."""
    _run(lambda: api.draw_paste(file, _read_grid(grid, grid_file), x, y, overwrite, frame, layer))


@draw_app.command("set")
def draw_set(
    file: FileArg,
    grid: Annotated[Optional[str], typer.Argument(help="rows separated by '/' (or '-' for stdin)")] = None,
    grid_file: Annotated[Optional[Path], typer.Option("--file")] = None,
    frame: FrameOpt = "0",
    layer: LayerOpt = None,
) -> None:
    """Replace the whole layer with a grid (short rows are padded with '.')."""
    _run(lambda: api.draw_set(file, _read_grid(grid, grid_file), frame, layer))


@draw_app.command("outline")
def draw_outline(
    file: FileArg, key: KeyArg,
    diagonal: Annotated[bool, typer.Option("--diagonal", help="also fill diagonal gaps")] = False,
    outer: Annotated[bool, typer.Option("--outer", help="skip enclosed gaps; outline only the outside")] = False,
    frame: FrameOpt = "0", layer: LayerOpt = None,
) -> None:
    """Add a 1px outline around all non-transparent pixels."""
    _run(lambda: api.draw_outline(file, key, diagonal, frame, layer, outer))


# --------------------------------------------------------------------------- #
# transforms
# --------------------------------------------------------------------------- #

tf_app = typer.Typer(help="Transform a layer.", no_args_is_help=True)
app.add_typer(tf_app, name="transform")


@tf_app.command("flip")
def tf_flip(file: FileArg, axis: Annotated[str, typer.Argument(help="h or v")], frame: FrameOpt = "0", layer: LayerOpt = None, region: RegionOpt = None) -> None:
    """Flip horizontally (h) or vertically (v), optionally only a region."""
    _run(lambda: api.flip(file, axis, frame, layer, api.parse_region(region)))


@tf_app.command("rotate")
def tf_rotate(file: FileArg, turns: Annotated[int, typer.Option(help="90° clockwise steps")] = 1, frame: FrameOpt = "0", layer: LayerOpt = None) -> None:
    """Rotate a square layer by 90° steps."""
    _run(lambda: api.rotate(file, turns, frame, layer))


@tf_app.command("shift")
def tf_shift(file: FileArg, dx: int, dy: int, wrap: Annotated[bool, typer.Option("--wrap")] = False, frame: FrameOpt = "0", layer: LayerOpt = None, region: RegionOpt = None) -> None:
    """Translate content by (dx, dy). With --region only pixels inside the box move."""
    _run(lambda: api.shift(file, dx, dy, wrap, frame, layer, api.parse_region(region)))


@tf_app.command("mirror")
def tf_mirror(
    file: FileArg,
    axis: Annotated[str, typer.Option(help="h (left->right) or v (top->bottom)")] = "h",
    source: Annotated[str, typer.Option(help="which half to keep: first or second")] = "first",
    frame: FrameOpt = "0", layer: LayerOpt = None,
) -> None:
    """Make the layer symmetric by copying one half onto the other."""
    _run(lambda: api.mirror(file, axis, source, frame, layer))


# --------------------------------------------------------------------------- #
# export / import
# --------------------------------------------------------------------------- #

export_app = typer.Typer(help="Export PNG / sprite sheet / GIF / APNG.", no_args_is_help=True)
app.add_typer(export_app, name="export")

ScaleOpt = Annotated[int, typer.Option("--scale", "-s", help="integer upscale factor")]
BgOpt = Annotated[Optional[str], typer.Option("--bg", help="flatten onto this color (default transparent)")]


@export_app.command("png")
def export_png(file: FileArg, out: Path, frame: FrameOpt = "0", scale: ScaleOpt = 1, bg: BgOpt = None,
               layers: Annotated[Optional[list[str]], typer.Option("--layer", "-l", help="only these layers")] = None) -> None:
    """Export a single frame as PNG."""
    _run(lambda: api.export_png(file, out, frame, scale, bg, layers or None))


@export_app.command("frames")
def export_frames(file: FileArg, out_dir: Path, scale: ScaleOpt = 1, bg: BgOpt = None) -> None:
    """Export every frame as a separate PNG."""
    _run(lambda: api.export_frames(file, out_dir, scale, bg))


@export_app.command("sheet")
def export_sheet(
    file: FileArg,
    out: Path,
    columns: Annotated[Optional[int], typer.Option("--columns", "-c", help="frames per row (default: all in one row)")] = None,
    padding: Annotated[int, typer.Option(help="pixels between frames")] = 0,
    scale: ScaleOpt = 1,
    tag: Annotated[Optional[str], typer.Option(help="only frames of this tag")] = None,
    no_meta: Annotated[bool, typer.Option("--no-meta", help="skip the JSON metadata file")] = False,
) -> None:
    """Export a sprite sheet PNG plus Aseprite-style JSON metadata."""
    _run(lambda: api.export_sheet(file, out, columns, padding, scale, tag, not no_meta))


@export_app.command("gif")
def export_gif(file: FileArg, out: Path, scale: ScaleOpt = 1, tag: Optional[str] = None, bg: BgOpt = None) -> None:
    """Export an animated GIF."""
    _run(lambda: api.export_gif(file, out, scale, tag, bg))


@export_app.command("apng")
def export_apng(file: FileArg, out: Path, scale: ScaleOpt = 1, tag: Optional[str] = None, bg: BgOpt = None) -> None:
    """Export an animated PNG (full RGBA, no color quantization)."""
    _run(lambda: api.export_apng(file, out, scale, tag, bg))


@app.command("import")
def import_cmd(
    png: Annotated[Path, typer.Argument(help="PNG image or sprite sheet")],
    out: Annotated[Path, typer.Argument(help="sprite file to create")],
    name: Optional[str] = None,
    frame_width: Annotated[Optional[int], typer.Option(help="slice sheet into frames of this width")] = None,
    frame_height: Annotated[Optional[int], typer.Option(help="slice sheet into frames of this height")] = None,
    max_colors: Annotated[int, typer.Option(help="quantize to at most this many colors")] = 32,
    palette_from: Annotated[Optional[Path], typer.Option("--palette-from", help="reuse the palette (keys and colors) of this sprite file")] = None,
) -> None:
    """Import a PNG (or sheet) into a new sprite file."""
    _run(lambda: api.import_png(png, out, name, frame_width, frame_height, max_colors, palette_from))


# --------------------------------------------------------------------------- #
# mcp server
# --------------------------------------------------------------------------- #


@app.command()
def server(
    transport: Annotated[str, typer.Option(help="stdio | sse | streamable-http")] = "stdio",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Run the MCP server exposing agentsprite as tools."""
    from .server import run

    run(transport, host, port)


@app.command()
def guide() -> None:
    """Print a short usage guide for agents."""
    from .server import GUIDE

    typer.echo(GUIDE)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
