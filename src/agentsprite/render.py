"""Rasterisation and export: PNG, sprite sheets (+ JSON metadata), GIF, APNG, and
import of existing PNGs back into the text grid format."""

from __future__ import annotations

import json
import math
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
    if scale < 1:
        raise SpriteError("scale must be >= 1")
    if scale == 1:
        return img
    return img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)


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
) -> tuple[Image.Image, dict]:
    """Pack frames into a grid sheet and return (image, metadata).

    Metadata follows the shape of Aseprite's JSON "array" export so existing
    game-engine importers can consume it.
    """
    indices = sprite.tag(tag).frame_indices() if tag else list(range(len(sprite.frames)))
    # de-duplicate pingpong repeats for packing, keep the order of first appearance
    seen: list[int] = []
    for i in indices:
        if i not in seen:
            seen.append(i)
    n = len(seen)
    cols = columns or n
    cols = max(1, min(cols, n))
    rows = math.ceil(n / cols)
    fw, fh = sprite.width * scale, sprite.height * scale
    sheet_w = cols * fw + (cols + 1) * padding
    sheet_h = rows * fh + (rows + 1) * padding
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    frames_meta = []
    for k, fi in enumerate(seen):
        f = sprite.frames[fi]
        c, r = k % cols, k // cols
        x = padding + c * (fw + padding)
        y = padding + r * (fh + padding)
        img = upscale(render_frame(f, sprite.palette, sprite.width, sprite.height), scale)
        sheet.alpha_composite(img, (x, y))
        frames_meta.append(
            {
                "filename": f"{sprite.name}_{fi}_{f.name}",
                "index": fi,
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
            "app": "agentsprite",
            "version": "0.1",
            "format": "RGBA8888",
            "size": {"w": sheet_w, "h": sheet_h},
            "scale": str(scale),
            "frameSize": {"w": fw, "h": fh},
            "columns": cols,
            "rows": rows,
            "padding": padding,
            "frameTags": [
                {"name": t.name, "from": t.start, "to": t.end, "direction": t.direction, "repeat": "0" if t.loop else "1"}
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
) -> tuple[Path, Path | None]:
    sheet, meta = build_sheet(sprite, columns, padding, scale, tag)
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
    if tag and not sprite.tag(tag).loop:
        loop = 1
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
        loop=loop,
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


def import_png(
    path: str | Path,
    name: str | None = None,
    palette: Palette | None = None,
    max_colors: int = 32,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> Sprite:
    """Load a PNG into a sprite, assigning palette keys to distinct colors.

    If ``frame_width``/``frame_height`` are given the image is treated as a
    sprite sheet and sliced into frames left-to-right, top-to-bottom.
    """
    p = Path(path)
    img = Image.open(p).convert("RGBA")
    fw, fh = frame_width or img.width, frame_height or img.height
    if img.width % fw or img.height % fh:
        raise SpriteError(f"image {img.width}x{img.height} is not a multiple of frame size {fw}x{fh}")

    pal = palette or Palette()
    # count distinct opaque colors, quantize if too many
    colors = [c for _, c in (img.getcolors(img.width * img.height) or []) if c[3] > 0]
    if len(colors) > max_colors:
        q = img.convert("RGB").quantize(colors=max_colors, dither=Image.Dither.NONE).convert("RGBA")
        q.putalpha(img.getchannel("A"))
        img = q

    sprite = Sprite(name=name or p.stem, width=fw, height=fh, palette=pal)
    cols, rows = img.width // fw, img.height // fh
    for r in range(rows):
        for c in range(cols):
            tile = img.crop((c * fw, r * fh, (c + 1) * fw, (r + 1) * fh))
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
            sprite.frames.append(Frame(f"frame{len(sprite.frames)}", layers=[layer]))
    if not sprite.frames:
        sprite.frames.append(Frame("frame0", layers=[Layer("base", fw, fh)]))
    return sprite
