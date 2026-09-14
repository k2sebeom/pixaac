"""Text views of a sprite, designed to be read by an AI agent."""

from __future__ import annotations

from .model import TRANSPARENT_KEY, Frame, Layer, Sprite, SpriteError
from .ops import bounding_box, changed_box, histogram


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
    return region_text(layer, (0, 0, layer.width - 1, layer.height - 1), ruler)


def region_text(layer: Layer, box: tuple[int, int, int, int], ruler: bool = True) -> str:
    """Render only the inclusive ``box`` of a layer; rulers show absolute coordinates."""
    x0, y0, x1, y1 = box
    rows = ["".join(r[x0 : x1 + 1]) for r in layer.grid[y0 : y1 + 1]]
    if not ruler:
        return "\n".join(rows)
    pad = len(str(y1))
    xs = range(x0, x1 + 1)
    lines = []
    if x1 >= 10:
        tens = "".join(str((x // 10) % 10) if (x % 10 == 0 or x == x0) else " " for x in xs)
        lines.append(" " * (pad + 1) + tens)
    lines.append(" " * (pad + 1) + "".join(str(x % 10) for x in xs))
    for y, row in zip(range(y0, y1 + 1), rows):
        lines.append(f"{y:>{pad}} {row}")
    return "\n".join(lines)


def palette_text(sprite: Sprite) -> str:
    lines = []
    for k, c in sprite.palette.colors.items():
        lines.append(f"  {k}  {c if c is not None else 'transparent'}")
    return "\n".join(lines)


def layers_text(sprite: Sprite) -> str:
    """One line per layer: index, name, non-transparent pixel count per frame, keys used.

    Lets an agent see at a glance which layer holds what (e.g. ``keys: ow`` is
    the staff layer).
    """
    names = sprite.layer_names()
    name_w = max(len(n) for n in names) if names else 0
    lines = []
    for i, name in enumerate(names):
        counts: list[int] = []
        keys: dict[str, None] = {}
        hidden = False
        for f in sprite.frames:
            layer = next((l for l in f.layers if l.name == name), None)
            if layer is None:
                counts.append(0)
                continue
            hidden = hidden or not layer.visible
            h = histogram(layer)
            counts.append(sum(n for k, n in h.items() if k != TRANSPARENT_KEY))
            for k in h:
                if k != TRANSPARENT_KEY:
                    keys.setdefault(k)
        px = ",".join(str(c) for c in counts)
        used = "".join(sorted(keys)) or "-"
        line = f"  [{i}] {name:<{name_w}}  px: {px}  keys: {used}"
        if hidden:
            line += "  (hidden)"
        lines.append(line)
    return "\n".join(lines)


def info_text(sprite: Sprite) -> str:
    lines = [
        f"sprite: {sprite.name}",
        f"size: {sprite.width}x{sprite.height}",
        f"frames: {len(sprite.frames)}",
        "layers (bottom -> top; px = non-transparent pixels per frame):",
        layers_text(sprite),
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


COMPOSITE = "composite"
"""Layer ref meaning "all visible layers flattened" where a plain layer ref is otherwise expected."""


def frame_text(
    sprite: Sprite,
    frame_ref: str | int = 0,
    layer_ref: str | int | None = None,
    ruler: bool = True,
    legend: bool = True,
    onion: str | int | None = None,
    onion_layer: str | int | None = None,
) -> str:
    """Text grid of one frame.

    With ``onion`` the silhouette of another frame (usually ``"prev"``) is
    drawn underneath: wherever the current frame is transparent but the onion
    frame is not, a ghost marker (``'`` unless that is a palette key) is shown.
    The ghost uses the same layer as the view unless ``onion_layer`` names a
    different one (``"composite"`` for all visible layers of the onion frame).
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
        oframe = sprite.frames[oi]
        if onion_layer is None:
            ghost_ref: str | int | None = layer_ref
        elif isinstance(onion_layer, str) and onion_layer.lower() in (COMPOSITE, "all"):
            ghost_ref = None
        else:
            ghost_ref = onion_layer
        ghost = _view_layer(sprite, oframe, ghost_ref)
        marker = ghost_marker(sprite)
        display = layer.copy()
        n = 0
        only_here: list[tuple[int, int]] = []
        for y in range(sprite.height):
            for x in range(sprite.width):
                here, there = display.grid[y][x] == TRANSPARENT_KEY, ghost.grid[y][x] == TRANSPARENT_KEY
                if here and not there:
                    display.grid[y][x] = marker
                    n += 1
                elif there and not here:
                    only_here.append((x, y))
        ghost_desc = f"frame [{oi}] {oframe.name}"
        if onion_layer is not None:
            ghost_desc += f" ({COMPOSITE})" if ghost_ref is None else f" / layer {ghost.name!r}"
        title += f"  onion: {ghost_desc}"
        onion_line = f"onion: {marker} = {n} pixel(s) only in {ghost_desc}; {len(only_here)} pixel(s) only in this frame"
        if only_here:
            xs, ys = [p[0] for p in only_here], [p[1] for p in only_here]
            onion_line += f" (x={min(xs)}..{max(xs)} y={min(ys)}..{max(ys)})"
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


SHOW_MODES = ("none", "bbox", "full")


def show_mode(show: str | None) -> str:
    """Validate a ``show`` argument and return it lower-cased."""
    mode = (show or "bbox").lower()
    if mode not in SHOW_MODES:
        raise SpriteError(f"show must be one of {', '.join(SHOW_MODES)}, got {show!r}")
    return mode


MASK_BLANK = " "
"""Filler for unchanged cells in the changed-cells mask (a space can never be a palette key)."""


def edit_result_text(
    sprite: Sprite,
    fi: int,
    layer_ref: str | int | None,
    before: list[list[str]],
    after: Layer,
    show: str = "bbox",
) -> str:
    """What a mutating call prints after its summary line.

    ``before`` is a snapshot of the edited layer's grid and ``after`` the layer
    itself. ``show`` is ``"none"`` (nothing), ``"bbox"`` (the box around the
    changed pixels of the edited layer, with absolute rulers; when not every
    cell in that box changed, a second grid beside it shows only the changed
    cells so that e.g. 4 ``g`` pixels set inside a ``g`` area are still
    visible) or ``"full"`` (the whole frame with legend and bbox as
    :func:`frame_text`).

    When every changed cell is now transparent (a clear, a keyed erase) the
    grid shows the *before* state instead, so the keys that were removed are
    visible without a second ``show``.

    The layer is named whenever the frame has more than one, even if the edit
    used the default (layer 0).
    """
    mode = show_mode(show)
    if mode == "none":
        return ""
    if mode == "full":
        return frame_text(sprite, fi, layer_ref)
    box, changed = changed_box(before, after)
    if box is None:
        return "(no pixels changed)"
    frame = sprite.frames[fi]
    x0, y0, x1, y1 = box
    where = f"frame [{fi}] {frame.name}"
    if layer_ref is not None or len(frame.layers) > 1:
        where += f" / layer {after.name!r}"
    cells = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if before[y][x] != after.grid[y][x]]
    erased = all(after.grid[y][x] == TRANSPARENT_KEY for x, y in cells)
    shown = after
    if erased:
        shown = Layer("before", sprite.width, sprite.height, grid=[row[:] for row in before])
        head = f"removed: x={x0}..{x1} y={y0}..{y1} ({changed} pixels) in {where}; grid = the erased pixels (before the edit)"
    else:
        head = f"changed: x={x0}..{x1} y={y0}..{y1} ({changed} pixels) in {where}"
    head += f"; show=\"full\" for the whole {sprite.width}x{sprite.height} frame"
    if changed == (x1 - x0 + 1) * (y1 - y0 + 1):
        return head + "\n" + region_text(shown, box)
    mask = Layer("mask", sprite.width, sprite.height)
    for x, y in cells:
        mask.grid[y][x] = shown.grid[y][x]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if before[y][x] == after.grid[y][x]:
                mask.grid[y][x] = MASK_BLANK
    head += "; right grid = changed cells only"
    return head + "\n" + _side_by_side(region_text(shown, box), region_text(mask, box), len(str(y1)) + 1)


def _side_by_side(left: str, right: str, prefix: int) -> str:
    """Join two ruler-ed region texts row by row; the right one drops its row labels."""
    out = []
    for l, r in zip(left.splitlines(), right.splitlines()):
        out.append(f"{l}   {r[prefix:]}".rstrip())
    return "\n".join(out)


def all_frames_text(sprite: Sprite, layer_ref: str | int | None = None) -> str:
    return "\n\n".join(frame_text(sprite, i, layer_ref, legend=False) for i in range(len(sprite.frames)))


def diff_text(
    sprite: Sprite, a: str | int, b: str | int, layer_ref: str | int | None = None, limit: int = 0
) -> str:
    """Show how frame ``b`` differs from frame ``a``.

    The grid carries the answer: where the frames differ it shows ``b``'s key
    (or the ghost marker where ``b`` is transparent), ``.`` where they agree.
    The per-pixel ``(x,y): a -> b`` list is off by default; ``limit=N`` prints
    at most ``N`` lines, ``limit=-1`` all of them.
    """
    fa, fb = sprite.frame(a), sprite.frame(b)
    ai, bi = sprite.frame_index(a), sprite.frame_index(b)
    la = fa.layer(layer_ref) if layer_ref is not None else flatten_keys(fa, sprite.width, sprite.height)
    lb = fb.layer(layer_ref) if layer_ref is not None else flatten_keys(fb, sprite.width, sprite.height)
    marker = ghost_marker(sprite)
    grid = Layer("diff", sprite.width, sprite.height)
    changes: list[str] = []
    xs: list[int] = []
    ys: list[int] = []
    added = removed = recolored = 0
    for y in range(sprite.height):
        for x in range(sprite.width):
            ka, kb = la.grid[y][x], lb.grid[y][x]
            if ka == kb:
                continue
            changes.append(f"  ({x},{y}): {ka} -> {kb}")
            xs.append(x)
            ys.append(y)
            if ka == TRANSPARENT_KEY:
                added += 1
            elif kb == TRANSPARENT_KEY:
                removed += 1
            else:
                recolored += 1
            grid.grid[y][x] = marker if kb == TRANSPARENT_KEY else kb
    where = "" if layer_ref is None else f" (layer {la.name!r})"
    if not changes:
        return f"frames [{ai}] {fa.name} and [{bi}] {fb.name} are identical{where}"
    lines = [
        f"{len(changes)} pixels differ between frame [{ai}] {fa.name} and [{bi}] {fb.name}{where}: "
        f"{added} added, {removed} removed, {recolored} recolored; bbox x={min(xs)}..{max(xs)} y={min(ys)}..{max(ys)}",
        f"grid: key = [{bi}]'s key where the frames differ, {marker} = transparent in [{bi}], . = identical",
        grid_text(grid),
    ]
    if limit:
        shown = changes if limit < 0 else changes[:limit]
        lines.extend(shown)
        if len(shown) < len(changes):
            lines.append(f"  ... {len(changes) - len(shown)} more (limit=-1 lists all)")
    return "\n".join(lines)


def resize_result_text(sprite: Sprite, show: str = "bbox") -> str:
    """What ``resize`` prints after its summary line: the content box of frame 0 (``bbox``), the frame (``full``) or nothing."""
    mode = show_mode(show)
    if mode == "none":
        return ""
    if mode == "full":
        return frame_text(sprite, 0)
    frame = sprite.frames[0]
    comp = flatten_keys(frame, sprite.width, sprite.height)
    bb = bounding_box(comp)
    if bb is None:
        return f"(frame [0] {frame.name} is empty)"
    head = (
        f"content: x={bb[0]}..{bb[2]} y={bb[1]}..{bb[3]} in frame [0] {frame.name};"
        f" show=\"full\" for the whole {sprite.width}x{sprite.height} frame"
    )
    return head + "\n" + region_text(comp, bb)
