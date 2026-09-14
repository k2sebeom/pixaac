"""Rasterisation and export: PNG, sprite sheets (+ JSON metadata), GIF, APNG, and
import of existing PNGs back into the text grid format."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, PngImagePlugin

from .model import RGBA, TRANSPARENT_KEY, Frame, Layer, Palette, Sprite, SpriteError

# --------------------------------------------------------------------------- #
# compositing
# --------------------------------------------------------------------------- #


def render_layer(layer: Layer, palette: Palette) -> Image.Image:
    img = Image.new("RGBA", (layer.width, layer.height), (0, 0, 0, 0))
    px = img.load()
    cache: dict[str, RGBA | None] = {}
    for y, row in enumerate(layer.grid):
        for x, ch in enumerate(row):
            if ch not in cache:
                cache[ch] = palette.rgba(ch)
            c = cache[ch]
            if c is None:
                continue
            if layer.opacity < 1.0:
                c = (c[0], c[1], c[2], int(round(c[3] * layer.opacity)))
            px[x, y] = c
    return img


def render_frame(
    frame: Frame,
    palette: Palette,
    width: int,
    height: int,
    layers: list[str] | None = None,
    include_hidden: bool = False,
) -> Image.Image:
    """Composite the visible layers of a frame bottom-up into one RGBA image."""
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for layer in frame.layers:
        if layers is not None and layer.name not in layers:
            continue
        if not layer.visible and not include_hidden:
            continue
        out.alpha_composite(render_layer(layer, palette))
    return out


def upscale(img: Image.Image, scale: int) -> Image.Image:
    _integer_option("scale", scale, minimum=1)
    if scale == 1:
        return img
    return img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)


def _integer_option(name: str, value: int, *, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise SpriteError(f"{name} must be an integer >= {minimum}")


def _extruded(img: Image.Image, border: int) -> Image.Image:
    """Duplicate outer texels, including corners; preserve RGBA bytes exactly."""
    if not border:
        return img
    w, h = img.size
    out = Image.new("RGBA", (w + 2 * border, h + 2 * border))
    out.paste(img, (border, border))
    # Nine patches avoid a full-image Python pixel loop.
    for left, top, right, bottom, box in (
        (0, 0, w, 1, (border, 0, border + w, border)),
        (0, h - 1, w, h, (border, border + h, border + w, h + 2 * border)),
        (0, 0, 1, h, (0, border, border, border + h)),
        (w - 1, 0, w, h, (border + w, border, w + 2 * border, border + h)),
        (0, 0, 1, 1, (0, 0, border, border)),
        (w - 1, 0, w, 1, (w + border, 0, w + 2 * border, border)),
        (0, h - 1, 1, h, (0, h + border, border, h + 2 * border)),
        (w - 1, h - 1, w, h,
         (w + border, h + border, w + 2 * border, h + 2 * border)),
    ):
        patch = img.crop((left, top, right, bottom))
        out.paste(patch.resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.NEAREST), box)
    return out


def with_background(img: Image.Image, color: str | None) -> Image.Image:
    """Flatten onto a solid background (``None`` keeps transparency)."""
    if color is None:
        return img
    from .model import parse_color

    bg = Image.new("RGBA", img.size, parse_color(color))
    bg.alpha_composite(img)
    return bg


def checkerboard(img: Image.Image, cell: int = 1) -> Image.Image:
    """Flatten onto a light/dark checkerboard (handy for previews)."""
    bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
    px = bg.load()
    for y in range(img.height):
        for x in range(img.width):
            px[x, y] = (200, 200, 200, 255) if ((x // cell) + (y // cell)) % 2 == 0 else (140, 140, 140, 255)
    bg.alpha_composite(img)
    return bg


# --------------------------------------------------------------------------- #
# exports
# --------------------------------------------------------------------------- #


def export_png(
    sprite: Sprite,
    path: str | Path,
    frame: str | int = 0,
    scale: int = 1,
    background: str | None = None,
    layers: list[str] | None = None,
) -> Path:
    img = render_frame(sprite.frame(frame), sprite.palette, sprite.width, sprite.height, layers)
    img = with_background(upscale(img, scale), background)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p, "PNG")
    return p


def export_frames(
    sprite: Sprite, directory: str | Path, scale: int = 1, background: str | None = None
) -> list[Path]:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for i, f in enumerate(sprite.frames):
        out.append(export_png(sprite, d / f"{sprite.name}_{i:03d}_{f.name}.png", i, scale, background))
    return out


def build_sheet(
    sprite: Sprite,
    columns: int | None = None,
    padding: int = 0,
    scale: int = 1,
    tag: str | None = None,
    extrude: int = 0,
) -> tuple[Image.Image, dict]:
    """Pack frames into a grid sheet and return (image, metadata).

    Metadata follows the shape of Aseprite's JSON "array" export so existing
    game-engine importers can consume it.
    """
    _integer_option("scale", scale, minimum=1)
    _integer_option("padding", padding)
    _integer_option("extrude", extrude)
    if columns is not None:
        _integer_option("columns", columns, minimum=1)
    indices = sprite.tag(tag).frame_indices() if tag else list(range(len(sprite.frames)))
    # Packing is always in source order; tags describe playback separately.
    seen = sorted(set(indices))
    positions = {source: position for position, source in enumerate(seen)}
    n = len(seen)
    cols = columns or n
    cols = max(1, min(cols, n))
    rows = math.ceil(n / cols)
    fw, fh = sprite.width * scale, sprite.height * scale
    cell_w, cell_h = fw + 2 * extrude, fh + 2 * extrude
    sheet_w = cols * cell_w + (cols + 1) * padding
    sheet_h = rows * cell_h + (rows + 1) * padding
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    frames_meta = []
    for k, fi in enumerate(seen):
        f = sprite.frames[fi]
        c, r = k % cols, k // cols
        x = padding + c * (cell_w + padding) + extrude
        y = padding + r * (cell_h + padding) + extrude
        img = upscale(render_frame(f, sprite.palette, sprite.width, sprite.height), scale)
        sheet.paste(_extruded(img, extrude), (x - extrude, y - extrude))
        frames_meta.append(
            {
                "filename": f"{sprite.name}_{fi}_{f.name}",
                "name": f.name,
                "index": k,
                "sourceIndex": fi,
                "frame": {"x": x, "y": y, "w": fw, "h": fh},
                "rotated": False,
                "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": fw, "h": fh},
                "sourceSize": {"w": fw, "h": fh},
                "duration": f.duration_ms,
            }
        )

    meta = {
        "frames": frames_meta,
        "meta": {
            "app": "pixaac",
            "version": "0.2",
            "tagIndexSpace": "exported",
            "name": sprite.name,
            "format": "RGBA8888",
            "size": {"w": sheet_w, "h": sheet_h},
            "scale": str(scale),
            "frameSize": {"w": fw, "h": fh},
            "columns": cols,
            "rows": rows,
            "padding": padding,
            "extrude": extrude,
            "frameTags": [
                {"name": t.name, "from": positions[t.start], "to": positions[t.end], "direction": t.direction, "repeat": "0" if t.loop else "1"}
                for t in sprite.tags
                if tag is None or t.name == tag
            ],
            "layers": [{"name": ln, "opacity": 255, "blendMode": "normal"} for ln in sprite.layer_names()],
            "palette": sprite.palette.to_json(),
        },
    }
    return sheet, meta


def export_sheet(
    sprite: Sprite,
    path: str | Path,
    columns: int | None = None,
    padding: int = 0,
    scale: int = 1,
    tag: str | None = None,
    metadata: bool = True,
    extrude: int = 0,
) -> tuple[Path, Path | None]:
    sheet, meta = build_sheet(sprite, columns, padding, scale, tag, extrude)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(p, "PNG")
    meta_path = None
    if metadata:
        meta["meta"]["image"] = p.name
        meta_path = p.with_suffix(".json")
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return p, meta_path


def export_gif(
    sprite: Sprite,
    path: str | Path,
    scale: int = 1,
    tag: str | None = None,
    background: str | None = None,
    loop: int = 0,
) -> Path:
    """Animated GIF of all frames or a tag. Transparent by default."""
    indices = sprite.tag(tag).frame_indices() if tag else list(range(len(sprite.frames)))
    # GIF's loop count is the number of repeats after the first play.
    # Omit the extension for a one-shot tag (loop=1 would play twice).
    loop_options = {} if tag and not sprite.tag(tag).loop else {"loop": loop}
    imgs, durations = [], []
    for i in indices:
        f = sprite.frames[i]
        img = with_background(
            upscale(render_frame(f, sprite.palette, sprite.width, sprite.height), scale), background
        )
        imgs.append(_to_gif_frame(img))
        durations.append(max(20, f.duration_ms))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    first, rest = imgs[0], imgs[1:]
    first.save(
        p,
        "GIF",
        save_all=True,
        append_images=rest,
        duration=durations,
        **loop_options,
        disposal=2,
        transparency=first.info.get("transparency", 0),
        optimize=False,
    )
    return p


def export_apng(
    sprite: Sprite,
    path: str | Path,
    scale: int = 1,
    tag: str | None = None,
    background: str | None = None,
    loop: int = 0,
) -> Path:
    """Animated PNG (APNG) of all frames or a tag: full RGBA, no quantization."""
    indices = sprite.tag(tag).frame_indices() if tag else list(range(len(sprite.frames)))
    if tag and not sprite.tag(tag).loop:
        loop = 1
    imgs, durations = [], []
    for i in indices:
        f = sprite.frames[i]
        img = with_background(
            upscale(render_frame(f, sprite.palette, sprite.width, sprite.height), scale), background
        )
        imgs.append(img)
        durations.append(max(1, f.duration_ms))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(
        p,
        "PNG",
        save_all=True,
        append_images=imgs[1:],
        duration=durations,
        loop=loop,
        disposal=PngImagePlugin.Disposal.OP_BACKGROUND,
        blend=PngImagePlugin.Blend.OP_SOURCE,
    )
    return p


def _to_gif_frame(img: Image.Image) -> Image.Image:
    """Convert RGBA -> P with index 0 reserved for fully transparent pixels."""
    # Quantizers may merge close colors even below the color limit. Pixel art
    # with a small palette must bypass them to retain every deliberate shade.
    colors: dict[tuple[int, int, int], int] = {}
    indices = bytearray()
    for r, g, b, a in img.get_flattened_data():
        if a < 128:
            indices.append(0)
            continue
        color = (r, g, b)
        if color not in colors:
            if len(colors) == 255:
                break
            colors[color] = len(colors) + 1
        indices.append(colors[color])
    else:
        exact = Image.frombytes("P", img.size, bytes(indices))
        palette = [0, 0, 0] + [channel for color in colors for channel in color]
        exact.putpalette(palette + [0] * (768 - len(palette)))
        exact.info["transparency"] = 0
        return exact
    alpha = img.getchannel("A")
    rgb = img.convert("RGB")
    pal = rgb.quantize(colors=255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    # shift indices up by one so 0 is free for transparency
    pal_data = pal.getpalette()[: 255 * 3] or []
    shifted = pal.point(lambda i: i + 1)
    shifted.putpalette([0, 0, 0] + pal_data)
    mask = alpha.point(lambda a: 255 if a < 128 else 0)
    shifted.paste(0, mask=mask)
    shifted.info["transparency"] = 0
    return shifted


# --------------------------------------------------------------------------- #
# import
# --------------------------------------------------------------------------- #


@dataclass
class SheetMeta:
    """The parts of an ``export_sheet`` JSON file that an import can use."""

    path: Path
    name: str | None
    frames: list[dict]  # {"rect": (x, y, w, h), "name": str, "duration": int, "index": int}
    tags: list[dict]  # {"name", "from", "to", "direction", "loop"}
    palette: dict[str, str | None] | None
    size: tuple[int, int] | None
    scale: int = 1
    notes: list[str] = field(default_factory=list)
    tag_index_space: str = "exported"


def load_sheet_metadata(png: str | Path, metadata: str | Path | None = None) -> SheetMeta | None:
    """Read sheet metadata for ``png``.

    With ``metadata`` given the file must exist and parse. Otherwise the
    sibling ``<png>.json`` is used when it exists and looks like sheet
    metadata (has a ``frames`` list); anything else is ignored.
    """
    explicit = metadata not in (None, "")
    mp = Path(metadata) if explicit else Path(png).with_suffix(".json")
    if not mp.exists():
        if explicit:
            raise SpriteError(f"no such metadata file: {mp}")
        return None
    try:
        data = json.loads(mp.read_text())
    except ValueError as e:
        if explicit:
            raise SpriteError(f"cannot parse {mp}: {e}") from e
        return None
    frames = data.get("frames") if isinstance(data, dict) else None
    if isinstance(frames, dict):  # Aseprite "hash" layout: {filename: {...}}
        frames = [{"filename": k, **v} for k, v in frames.items()]
    if not isinstance(frames, list) or not frames:
        if explicit:
            raise SpriteError(f"{mp} has no 'frames' list; not sprite sheet metadata")
        return None
    meta = data.get("meta") or {}
    sprite_name = meta.get("name")
    out_frames = []
    for k, fr in enumerate(frames):
        try:
            r = fr["frame"]
            rect = (int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"]))
        except (KeyError, TypeError, ValueError):
            raise SpriteError(f"{mp}: frame {k} has no usable 'frame' rectangle") from None
        index = int(fr.get("index", k))
        fname = fr.get("name")
        if not fname:
            fname = _frame_name_from_filename(str(fr.get("filename", "")), sprite_name, index) or f"frame{k}"
        out_frames.append({"rect": rect, "name": fname, "duration": int(fr.get("duration", 100)), "index": index})
    # Old PixaaS sheets used source indices and packed reverse tags backwards.
    # Normalize their frames to source order before resolving tag endpoints.
    legacy = (meta.get("app") == "pixaas" and "tagIndexSpace" not in meta
              and all("index" in fr for fr in frames))
    if legacy:
        out_frames.sort(key=lambda fr: fr["index"])
    tags = []
    for t in meta.get("frameTags") or []:
        try:
            tags.append(
                {
                    "name": str(t["name"]),
                    "from": int(t["from"]),
                    "to": int(t["to"]),
                    "direction": t.get("direction", "forward"),
                    "loop": str(t.get("repeat", "0")) in ("0", "None", ""),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    size = meta.get("size") or {}
    try:
        scale = int(float(meta.get("scale", 1)))
    except (TypeError, ValueError):
        scale = 1
    return SheetMeta(
        path=mp,
        name=sprite_name,
        frames=out_frames,
        tags=tags,
        palette=meta.get("palette") if isinstance(meta.get("palette"), dict) else None,
        size=(int(size["w"]), int(size["h"])) if "w" in size and "h" in size else None,
        scale=max(1, scale),
        tag_index_space="source" if legacy else "exported",
    )


def _frame_name_from_filename(filename: str, sprite_name: str | None, index: int) -> str | None:
    """Recover ``f.name`` from ``"{sprite}_{index}_{f.name}"`` (best effort for old exports)."""
    if not filename:
        return None
    if sprite_name and filename.startswith(f"{sprite_name}_{index}_"):
        return filename[len(f"{sprite_name}_{index}_") :] or None
    parts = filename.split(f"_{index}_", 1)
    return parts[1] if len(parts) == 2 and parts[1] else None


def import_png(
    path: str | Path,
    name: str | None = None,
    palette: Palette | None = None,
    max_colors: int = 32,
    frame_width: int | None = None,
    frame_height: int | None = None,
    meta: SheetMeta | None = None,
) -> Sprite:
    """Load a PNG into a sprite, assigning palette keys to distinct colors.

    If ``frame_width``/``frame_height`` are given the image is treated as a
    sprite sheet and sliced into frames left-to-right, top-to-bottom. With
    ``meta`` (see :func:`load_sheet_metadata`) the frames are cut from the
    recorded rectangles instead (so padding and columns are honoured) and
    frame names, durations, tags and the palette are restored.
    """
    p = Path(path)
    img = Image.open(p).convert("RGBA")

    tiles: list[tuple[tuple[int, int, int, int], str, int]] = []  # (crop box in image px, frame name, duration)
    s = 1  # upscale factor of the sheet; each tile is shrunk back by it
    if meta is not None:
        if meta.size is not None and meta.size != img.size:
            raise SpriteError(
                f"{meta.path} describes a {meta.size[0]}x{meta.size[1]} sheet but {p.name} is {img.width}x{img.height}"
            )
        s = meta.scale
        # padding is not scaled on export, so only the frame rectangles (not the
        # whole sheet) are guaranteed to be multiples of the scale
        for f in meta.frames:
            if f["rect"][2] % s or f["rect"][3] % s:
                raise SpriteError(
                    f"{meta.path} says scale {s} but frame {f['name']!r} is {f['rect'][2]}x{f['rect'][3]}, not divisible by it"
                )
        sizes = {(r[2] // s, r[3] // s) for r in (f["rect"] for f in meta.frames)}
        if len(sizes) != 1:
            raise SpriteError(f"{meta.path}: frames have different sizes {sorted(sizes)}; cannot import as one sprite")
        fw, fh = next(iter(sizes))
        if (frame_width or fw) != fw or (frame_height or fh) != fh:
            meta.notes.append(f"frame size {frame_width}x{frame_height} ignored; metadata says {fw}x{fh}")
        for f in meta.frames:
            x, y, w, h = f["rect"]
            if x + w > img.width or y + h > img.height:
                raise SpriteError(f"{meta.path}: frame {f['name']!r} rectangle lies outside the image")
            tiles.append(((x, y, x + w, y + h), f["name"], f["duration"]))
        if palette is None and meta.palette:
            palette = Palette.from_json(meta.palette)
        name = name or meta.name
    else:
        fw, fh = frame_width or img.width, frame_height or img.height
        if img.width % fw or img.height % fh:
            raise SpriteError(f"image {img.width}x{img.height} is not a multiple of frame size {fw}x{fh}")
        for r in range(img.height // fh):
            for c in range(img.width // fw):
                tiles.append(((c * fw, r * fh, (c + 1) * fw, (r + 1) * fh), f"frame{len(tiles)}", 100))

    pal = palette or Palette()
    # count distinct opaque colors, quantize if too many
    colors = [c for _, c in (img.getcolors(img.width * img.height) or []) if c[3] > 0]
    if len(colors) > max_colors:
        q = img.convert("RGB").quantize(colors=max_colors, dither=Image.Dither.NONE).convert("RGBA")
        q.putalpha(img.getchannel("A"))
        img = q

    sprite = Sprite(name=name or p.stem, width=fw, height=fh, palette=pal)
    used_names: set[str] = set()
    for box, fname, duration in tiles:
        tile = img.crop(box)
        if s > 1:
            tile = tile.resize((fw, fh), Image.Resampling.NEAREST)
        layer = Layer("base", fw, fh)
        px = tile.load()
        for y in range(fh):
            for x in range(fw):
                rgba = px[x, y]
                if rgba[3] == 0:
                    continue
                key = pal.key_for_rgba(rgba)
                if key is None:
                    key = pal.free_key()
                    from .model import format_color

                    pal.set(key, format_color(rgba))
                layer.grid[y][x] = key
        if fname in used_names:
            fname = Sprite._unique_name(fname, used_names)
        used_names.add(fname)
        sprite.frames.append(Frame(fname, duration_ms=max(1, duration), layers=[layer]))
    if not sprite.frames:
        sprite.frames.append(Frame("frame0", layers=[Layer("base", fw, fh)]))

    if meta is not None:
        pos = {(f["index"] if meta.tag_index_space == "source" else k): k
               for k, f in enumerate(meta.frames)}
        for t in meta.tags:
            a, b = pos.get(t["from"]), pos.get(t["to"])
            if a is None or b is None or a > b:
                meta.notes.append(f"tag {t['name']!r} ({t['from']}..{t['to']}) does not map onto the imported frames; skipped")
                continue
            try:
                sprite.set_tag(t["name"], a, b, t["direction"], t["loop"])
            except SpriteError as e:
                meta.notes.append(f"tag {t['name']!r} skipped: {e}")
    return sprite
