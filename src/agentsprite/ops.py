"""Drawing and transformation operations on a :class:`Layer`.

Every operation mutates the layer in place and returns the number of pixels
written, so callers can report what happened back to the agent.
"""

from __future__ import annotations

from collections import deque

from PIL import Image, ImageDraw

from .model import TRANSPARENT_KEY, Layer, Palette, SpriteError, parse_grid


Region = tuple[int, int, int, int] | list[int] | None
"""Inclusive ``(x0, y0, x1, y1)`` box, or ``None`` for the whole layer."""


def _check_key(palette: Palette, key: str) -> None:
    if not palette.has(key):
        raise SpriteError(
            f"unknown palette key {key!r}; add it first (palette keys: {''.join(palette.colors)})"
        )


def _box(layer: Layer, region: Region) -> tuple[int, int, int, int]:
    """Normalise a region to an in-bounds inclusive box."""
    if region is None:
        return 0, 0, layer.width - 1, layer.height - 1
    if len(region) != 4:
        raise SpriteError("region must be x0,y0,x1,y1")
    x0, y0, x1, y1 = (int(v) for v in region)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(layer.width - 1, x1), min(layer.height - 1, y1)
    if x0 > x1 or y0 > y1:
        raise SpriteError(f"region {tuple(region)} is outside {layer.width}x{layer.height}")
    return x0, y0, x1, y1


def _extract(layer: Layer, box: tuple[int, int, int, int]) -> list[list[str]]:
    x0, y0, x1, y1 = box
    return [row[x0 : x1 + 1] for row in layer.grid[y0 : y1 + 1]]


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #


def pixel(layer: Layer, palette: Palette, x: int, y: int, key: str) -> int:
    _check_key(palette, key)
    if not layer.in_bounds(x, y):
        raise SpriteError(f"({x}, {y}) is outside {layer.width}x{layer.height}")
    layer.set(x, y, key)
    return 1


def pixels(layer: Layer, palette: Palette, points: list[tuple[int, int]], key: str) -> int:
    _check_key(palette, key)
    return sum(1 for x, y in points if layer.set(x, y, key))


def line(layer: Layer, palette: Palette, x0: int, y0: int, x1: int, y1: int, key: str) -> int:
    """Bresenham line, inclusive of both endpoints."""
    _check_key(palette, key)
    n = 0
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        n += layer.set(x, y, key)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return n


def rect(
    layer: Layer,
    palette: Palette,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    key: str,
    fill: bool = False,
) -> int:
    """Rectangle with inclusive corners. Outline unless ``fill``."""
    _check_key(palette, key)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    n = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if fill or x in (x0, x1) or y in (y0, y1):
                n += layer.set(x, y, key)
    return n


def ellipse(
    layer: Layer,
    palette: Palette,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    key: str,
    fill: bool = False,
) -> int:
    """Ellipse inscribed in the inclusive bounding box (x0,y0)-(x1,y1)."""
    _check_key(palette, key)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    w, h = x1 - x0 + 1, y1 - y0 + 1
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    if fill:
        d.ellipse([0, 0, w - 1, h - 1], fill=255)
    else:
        d.ellipse([0, 0, w - 1, h - 1], outline=255, width=1)
    n = 0
    px = mask.load()
    for yy in range(h):
        for xx in range(w):
            if px[xx, yy]:
                n += layer.set(x0 + xx, y0 + yy, key)
    return n


def flood_fill(layer: Layer, palette: Palette, x: int, y: int, key: str, diagonal: bool = False) -> int:
    """Fill the 4-connected (or 8-connected) region containing (x, y)."""
    _check_key(palette, key)
    if not layer.in_bounds(x, y):
        raise SpriteError(f"({x}, {y}) is outside {layer.width}x{layer.height}")
    target = layer.grid[y][x]
    if target == key:
        return 0
    q: deque[tuple[int, int]] = deque([(x, y)])
    seen = {(x, y)}
    n = 0
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diagonal:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    while q:
        cx, cy = q.popleft()
        layer.grid[cy][cx] = key
        n += 1
        for dx, dy in steps:
            nx, ny = cx + dx, cy + dy
            if (nx, ny) not in seen and layer.in_bounds(nx, ny) and layer.grid[ny][nx] == target:
                seen.add((nx, ny))
                q.append((nx, ny))
    return n


def replace(layer: Layer, palette: Palette, old: str, new: str) -> int:
    """Replace every pixel with key ``old`` by ``new``."""
    _check_key(palette, new)
    n = 0
    for row in layer.grid:
        for i, ch in enumerate(row):
            if ch == old:
                row[i] = new
                n += 1
    return n


def clear(layer: Layer, region: Region = None) -> int:
    """Erase the layer (or just ``region``) to transparent."""
    x0, y0, x1, y1 = _box(layer, region)
    n = 0
    for y in range(y0, y1 + 1):
        row = layer.grid[y]
        for x in range(x0, x1 + 1):
            if row[x] != TRANSPARENT_KEY:
                n += 1
                row[x] = TRANSPARENT_KEY
    return n


def copy_region(
    src: Layer,
    dst: Layer,
    region: Region,
    x: int,
    y: int,
    overwrite: bool = False,
) -> int:
    """Copy ``region`` of ``src`` so its top-left lands at (x, y) on ``dst``.

    ``src`` and ``dst`` may be the same layer. Transparent source pixels are
    skipped unless ``overwrite``.
    """
    sub = [row[:] for row in _extract(src, _box(src, region))]
    n = 0
    for dy, row in enumerate(sub):
        for dx, ch in enumerate(row):
            if ch == TRANSPARENT_KEY and not overwrite:
                continue
            n += dst.set(x + dx, y + dy, ch)
    return n


# --------------------------------------------------------------------------- #
# grid paste
# --------------------------------------------------------------------------- #


def paste(
    layer: Layer,
    palette: Palette,
    text: str,
    x: int = 0,
    y: int = 0,
    skip_transparent: bool = True,
) -> int:
    """Paste a grid of keys at (x, y).

    Transparent keys in the pasted grid are skipped by default so the paste acts
    like a stamp; pass ``skip_transparent=False`` to overwrite with transparent.
    """
    grid = parse_grid(text)
    for row in grid:
        for ch in row:
            _check_key(palette, ch)
    n = 0
    for dy, row in enumerate(grid):
        for dx, ch in enumerate(row):
            if skip_transparent and ch == TRANSPARENT_KEY:
                continue
            n += layer.set(x + dx, y + dy, ch)
    return n


def set_grid(layer: Layer, palette: Palette, text: str) -> int:
    """Replace the whole layer with the given grid (must fit the canvas)."""
    grid = parse_grid(text, layer.width, layer.height)
    for row in grid:
        for ch in row:
            _check_key(palette, ch)
    layer.grid = grid
    return layer.width * layer.height


# --------------------------------------------------------------------------- #
# transforms
# --------------------------------------------------------------------------- #


def flip(layer: Layer, axis: str, region: Region = None) -> int:
    """Flip the layer (or just ``region``) horizontally or vertically."""
    x0, y0, x1, y1 = _box(layer, region)
    sub = _extract(layer, (x0, y0, x1, y1))
    if axis in ("h", "horizontal", "x"):
        sub = [row[::-1] for row in sub]
    elif axis in ("v", "vertical", "y"):
        sub = sub[::-1]
    else:
        raise SpriteError("axis must be 'h' or 'v'")
    for dy, row in enumerate(sub):
        layer.grid[y0 + dy][x0 : x1 + 1] = row
    return (x1 - x0 + 1) * (y1 - y0 + 1)


def rotate(layer: Layer, turns: int = 1) -> int:
    """Rotate by 90° clockwise ``turns`` times. Requires a square canvas."""
    if layer.width != layer.height:
        raise SpriteError("rotate requires a square canvas (use resize first)")
    for _ in range(turns % 4):
        layer.grid = [list(r) for r in zip(*layer.grid[::-1])]
    return layer.width * layer.height


def shift(layer: Layer, dx: int, dy: int, wrap: bool = False, region: Region = None) -> int:
    """Translate the layer content by (dx, dy).

    With ``region`` only the pixels inside the box move; they may land outside
    the box (overwriting what is there) but are clipped to the canvas. With
    ``wrap`` pixels wrap around the box (or the canvas when no region).
    """
    x0, y0, x1, y1 = _box(layer, region)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    sub = [row[:] for row in _extract(layer, (x0, y0, x1, y1))]
    clear(layer, (x0, y0, x1, y1))
    n = 0
    for sy, row in enumerate(sub):
        for sx, ch in enumerate(row):
            if ch == TRANSPARENT_KEY:
                continue
            nx, ny = sx + dx, sy + dy
            if wrap:
                nx, ny = nx % bw, ny % bh
            n += layer.set(x0 + nx, y0 + ny, ch)
    return n


def mirror(layer: Layer, axis: str = "h", source: str = "first") -> int:
    """Make the layer symmetric by copying one half onto the other.

    ``axis='h'`` mirrors left<->right, ``'v'`` top<->bottom. ``source`` is which
    half is kept: ``'first'`` (left/top) or ``'second'`` (right/bottom).
    """
    w, h = layer.width, layer.height
    n = 0
    if axis in ("h", "horizontal", "x"):
        for y in range(h):
            for x in range(w // 2):
                mx = w - 1 - x
                if source == "first":
                    layer.grid[y][mx] = layer.grid[y][x]
                else:
                    layer.grid[y][x] = layer.grid[y][mx]
                n += 1
    elif axis in ("v", "vertical", "y"):
        for y in range(h // 2):
            my = h - 1 - y
            if source == "first":
                layer.grid[my] = layer.grid[y][:]
            else:
                layer.grid[y] = layer.grid[my][:]
            n += w
    else:
        raise SpriteError("axis must be 'h' or 'v'")
    return n


def outside_mask(layer: Layer) -> set[tuple[int, int]]:
    """Transparent pixels 4-connected to the canvas border (i.e. not enclosed)."""
    w, h = layer.width, layer.height
    seen: set[tuple[int, int]] = set()
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if layer.grid[y][x] == TRANSPARENT_KEY and (x, y) not in seen:
                seen.add((x, y))
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if layer.grid[y][x] == TRANSPARENT_KEY and (x, y) not in seen:
                seen.add((x, y))
                q.append((x, y))
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if (nx, ny) not in seen and layer.in_bounds(nx, ny) and layer.grid[ny][nx] == TRANSPARENT_KEY:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def outline(
    layer: Layer, palette: Palette, key: str, diagonal: bool = False, outer_only: bool = False
) -> int:
    """Draw ``key`` on every transparent pixel adjacent to a non-transparent one.

    With ``outer_only`` enclosed gaps (holes, the space between legs) are left
    alone; only transparent pixels reachable from the canvas border are drawn.
    """
    _check_key(palette, key)
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diagonal:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    outside = outside_mask(layer) if outer_only else None
    targets: list[tuple[int, int]] = []
    for y in range(layer.height):
        for x in range(layer.width):
            if layer.grid[y][x] != TRANSPARENT_KEY:
                continue
            if outside is not None and (x, y) not in outside:
                continue
            for dx, dy in steps:
                nx, ny = x + dx, y + dy
                if layer.in_bounds(nx, ny) and layer.grid[ny][nx] != TRANSPARENT_KEY:
                    targets.append((x, y))
                    break
    for x, y in targets:
        layer.grid[y][x] = key
    return len(targets)


def scale(layer: Layer, factor: int) -> Layer:
    """Return a new layer scaled up by an integer factor (nearest neighbour)."""
    if factor < 1:
        raise SpriteError("scale factor must be >= 1")
    grid = []
    for row in layer.grid:
        big = [ch for ch in row for _ in range(factor)]
        grid.extend([big[:] for _ in range(factor)])
    return Layer(layer.name, layer.width * factor, layer.height * factor, layer.visible, layer.opacity, grid)


# --------------------------------------------------------------------------- #
# inspection
# --------------------------------------------------------------------------- #


def bounding_box(layer: Layer) -> tuple[int, int, int, int] | None:
    """Inclusive (x0, y0, x1, y1) of non-transparent pixels, or None if empty."""
    xs = [x for y in range(layer.height) for x in range(layer.width) if layer.grid[y][x] != TRANSPARENT_KEY]
    if not xs:
        return None
    ys = [y for y in range(layer.height) for x in range(layer.width) if layer.grid[y][x] != TRANSPARENT_KEY]
    return min(xs), min(ys), max(xs), max(ys)


def histogram(layer: Layer) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in layer.grid:
        for ch in row:
            counts[ch] = counts.get(ch, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
