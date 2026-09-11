"""Text views of a sprite, designed to be read by an AI agent."""

from __future__ import annotations

from .model import TRANSPARENT_KEY, Frame, Layer, Sprite, SpriteError
from .ops import bounding_box, histogram


def flatten_keys(frame: Frame, width: int, height: int, include_hidden: bool = False) -> Layer:
    """Collapse the layer stack into one key grid (top-most opaque key wins)."""
    out = Layer("composite", width, height)
    for layer in frame.layers:
        if not layer.visible and not include_hidden:
            continue
        for y in range(height):
            src, dst = layer.grid[y], out.grid[y]
            for x in range(width):
                if src[x] != TRANSPARENT_KEY:
                    dst[x] = src[x]
    return out


def grid_text(layer: Layer, ruler: bool = True) -> str:
    """Render a layer's key grid with optional coordinate rulers."""
    rows = layer.rows()
    if not ruler:
        return "\n".join(rows)
    w = layer.width
    pad = len(str(layer.height - 1))
    lines = []
    if w > 10:
        tens = "".join(str((x // 10) % 10) if x % 10 == 0 else " " for x in range(w))
        lines.append(" " * (pad + 1) + tens)
    lines.append(" " * (pad + 1) + "".join(str(x % 10) for x in range(w)))
    for y, row in enumerate(rows):
        lines.append(f"{y:>{pad}} {row}")
    return "\n".join(lines)


def palette_text(sprite: Sprite) -> str:
    lines = []
    for k, c in sprite.palette.colors.items():
        lines.append(f"  {k}  {c if c is not None else 'transparent'}")
    return "\n".join(lines)


def info_text(sprite: Sprite) -> str:
    lines = [
        f"sprite: {sprite.name}",
        f"size: {sprite.width}x{sprite.height}",
        f"frames: {len(sprite.frames)}",
        f"layers: {', '.join(sprite.layer_names())}",
        "palette:",
        palette_text(sprite),
        "frames:",
    ]
    for i, f in enumerate(sprite.frames):
        hidden = [l.name for l in f.layers if not l.visible]
        extra = f"  hidden={hidden}" if hidden else ""
        lines.append(f"  [{i}] {f.name}  {f.duration_ms}ms{extra}")
    if sprite.tags:
        lines.append("tags:")
        for t in sprite.tags:
            loop = "" if t.loop else "  once"
            lines.append(f"  {t.name}: frames {t.start}..{t.end}  {t.direction}{loop}")
    if sprite.notes:
        lines.append("notes:")
        lines.append("  " + sprite.notes.replace("\n", "\n  "))
    problems = sprite.validate()
    if problems:
        lines.append("PROBLEMS:")
        lines.extend(f"  - {p}" for p in problems)
    return "\n".join(lines)


GHOST_MARKERS = "'`\"\u00b0"


def ghost_marker(sprite: Sprite) -> str:
    """A display-only character for onion-skin pixels that is not a palette key."""
    for ch in GHOST_MARKERS:
        if not sprite.palette.has(ch):
            return ch
    return GHOST_MARKERS[-1]


def resolve_onion(sprite: Sprite, fi: int, onion: str | int) -> int:
    """Turn an onion reference ('prev', 'next', index or name) into a frame index."""
    if isinstance(onion, str) and onion.lower() in ("prev", "previous", "before"):
        if fi == 0:
            raise SpriteError(f"frame [{fi}] has no previous frame")
        return fi - 1
    if isinstance(onion, str) and onion.lower() in ("next", "after"):
        if fi >= len(sprite.frames) - 1:
            raise SpriteError(f"frame [{fi}] has no next frame")
        return fi + 1
    return sprite.frame_index(onion)


def _view_layer(sprite: Sprite, frame: Frame, layer_ref: str | int | None) -> Layer:
    if layer_ref is None:
        return flatten_keys(frame, sprite.width, sprite.height)
    return frame.layer(layer_ref)


def frame_text(
    sprite: Sprite,
    frame_ref: str | int = 0,
    layer_ref: str | int | None = None,
    ruler: bool = True,
    legend: bool = True,
    onion: str | int | None = None,
) -> str:
    """Text grid of one frame.

    With ``onion`` the silhouette of another frame (usually ``"prev"``) is
    drawn underneath: wherever the current frame is transparent but the onion
    frame is not, a ghost marker (``'`` unless that is a palette key) is shown.
    """
    frame = sprite.frame(frame_ref)
    fi = sprite.frame_index(frame_ref)
    layer = _view_layer(sprite, frame, layer_ref)
    if layer_ref is None:
        title = f"frame [{fi}] {frame.name} (composite of {len([l for l in frame.layers if l.visible])} visible layers)"
    else:
        title = f"frame [{fi}] {frame.name} / layer {layer.name!r}" + ("" if layer.visible else " (hidden)")
    display = layer
    onion_line = None
    if onion is not None:
        oi = resolve_onion(sprite, fi, onion)
        ghost = _view_layer(sprite, sprite.frames[oi], layer_ref)
        marker = ghost_marker(sprite)
        display = layer.copy()
        n = 0
        for y in range(sprite.height):
            for x in range(sprite.width):
                if display.grid[y][x] == TRANSPARENT_KEY and ghost.grid[y][x] != TRANSPARENT_KEY:
                    display.grid[y][x] = marker
                    n += 1
        title += f"  onion: frame [{oi}] {sprite.frames[oi].name}"
        onion_line = f"onion: {marker} = {n} pixel(s) of frame [{oi}] {sprite.frames[oi].name} not covered by this frame"
    parts = [title, grid_text(display, ruler)]
    if onion_line:
        parts.append(onion_line)
    if legend:
        used = histogram(layer)
        legend_items = [
            f"{k}={sprite.palette.colors.get(k, '?') or 'transparent'}" for k in used if k != TRANSPARENT_KEY
        ]
        parts.append("legend: " + (", ".join(legend_items) if legend_items else "(empty)"))
        bb = bounding_box(layer)
        if bb:
            parts.append(f"bbox: x={bb[0]}..{bb[2]} y={bb[1]}..{bb[3]}")
    return "\n".join(parts)


def all_frames_text(sprite: Sprite, layer_ref: str | int | None = None) -> str:
    return "\n\n".join(frame_text(sprite, i, layer_ref, legend=False) for i in range(len(sprite.frames)))


def diff_text(sprite: Sprite, a: str | int, b: str | int, layer_ref: str | int | None = None) -> str:
    """Show pixels that differ between two frames (``x,y: a -> b``)."""
    fa, fb = sprite.frame(a), sprite.frame(b)
    la = fa.layer(layer_ref) if layer_ref is not None else flatten_keys(fa, sprite.width, sprite.height)
    lb = fb.layer(layer_ref) if layer_ref is not None else flatten_keys(fb, sprite.width, sprite.height)
    changes = []
    marker = Layer("diff", sprite.width, sprite.height)
    for y in range(sprite.height):
        for x in range(sprite.width):
            if la.grid[y][x] != lb.grid[y][x]:
                changes.append(f"  ({x},{y}): {la.grid[y][x]} -> {lb.grid[y][x]}")
                marker.grid[y][x] = "X"
    if not changes:
        return f"frames {a} and {b} are identical"
    return "\n".join([f"{len(changes)} pixels differ (X marks changed):", grid_text(marker), *changes])
