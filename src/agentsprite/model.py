"""Sprite document model.

A sprite is a stack of frames; each frame is a stack of layers; each layer is a
grid of single-character *palette keys*. The palette maps a key to a color
(``#RRGGBB`` / ``#RRGGBBAA``) or to ``None`` for transparent.

Pixels are stored as text rows so that an AI agent can read and write them
directly, e.g.::

    ..##..
    .#rr#.
    ..##..

The reserved key ``.`` is always transparent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

FORMAT_VERSION = 1
TRANSPARENT_KEY = "."

RGBA = tuple[int, int, int, int]

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{8}|[0-9a-fA-F]{3}|[0-9a-fA-F]{4})$")


class SpriteError(Exception):
    """Raised for invalid user input (bad coordinates, unknown keys, ...)."""


# --------------------------------------------------------------------------- #
# colors
# --------------------------------------------------------------------------- #


def parse_color(value: str) -> RGBA:
    """Parse ``#RGB``, ``#RGBA``, ``#RRGGBB`` or ``#RRGGBBAA`` into an RGBA tuple."""
    m = _HEX_RE.match(value.strip())
    if not m:
        raise SpriteError(f"invalid color {value!r}; use #RRGGBB or #RRGGBBAA")
    h = m.group(1)
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return (r, g, b, a)


def format_color(rgba: RGBA) -> str:
    r, g, b, a = rgba
    if a == 255:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"#{r:02x}{g:02x}{b:02x}{a:02x}"


def normalize_color(value: str | None) -> str | None:
    if value is None:
        return None
    return format_color(parse_color(value))


# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #


@dataclass
class Palette:
    """Ordered mapping from single-character key to color string (or None)."""

    colors: dict[str, str | None] = field(default_factory=lambda: {TRANSPARENT_KEY: None})

    def __post_init__(self) -> None:
        self.colors.setdefault(TRANSPARENT_KEY, None)

    def set(self, key: str, color: str | None) -> None:
        _check_key(key)
        if key == TRANSPARENT_KEY and color is not None:
            raise SpriteError(f"palette key {TRANSPARENT_KEY!r} is reserved for transparent")
        self.colors[key] = normalize_color(color)

    def remove(self, key: str) -> None:
        if key == TRANSPARENT_KEY:
            raise SpriteError("cannot remove the transparent key")
        if key not in self.colors:
            raise SpriteError(f"palette has no key {key!r}")
        del self.colors[key]

    def has(self, key: str) -> bool:
        return key in self.colors

    def rgba(self, key: str) -> RGBA | None:
        """Return the RGBA of a key, or None for transparent."""
        try:
            color = self.colors[key]
        except KeyError:
            raise SpriteError(f"unknown palette key {key!r}") from None
        return None if color is None else parse_color(color)

    def is_transparent(self, key: str) -> bool:
        return self.rgba(key) is None or self.rgba(key)[3] == 0  # type: ignore[index]

    def key_for_rgba(self, rgba: RGBA) -> str | None:
        """Reverse lookup: exact color match -> key."""
        if rgba[3] == 0:
            return TRANSPARENT_KEY
        for k, c in self.colors.items():
            if c is not None and parse_color(c) == rgba:
                return k
        return None

    def free_key(self) -> str:
        """Return an unused printable key."""
        for ch in _KEY_CANDIDATES:
            if ch not in self.colors:
                return ch
        raise SpriteError("palette is full")

    def to_json(self) -> dict[str, str | None]:
        return dict(self.colors)

    @classmethod
    def from_json(cls, data: dict[str, str | None]) -> "Palette":
        p = cls({})
        for k, v in data.items():
            if k == TRANSPARENT_KEY:
                continue
            p.set(k, v)
        return p


_KEY_CANDIDATES = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "!@#$%^&*+=-_?/<>~|:;,"
)


def _check_key(key: str) -> None:
    if len(key) != 1 or key.isspace():
        raise SpriteError(f"palette key must be a single non-space character, got {key!r}")


# --------------------------------------------------------------------------- #
# layer / frame / sprite
# --------------------------------------------------------------------------- #


@dataclass
class Layer:
    name: str
    width: int
    height: int
    visible: bool = True
    opacity: float = 1.0
    grid: list[list[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.grid:
            self.grid = [[TRANSPARENT_KEY] * self.width for _ in range(self.height)]

    # -- pixel access ------------------------------------------------------ #

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> str:
        if not self.in_bounds(x, y):
            raise SpriteError(f"({x}, {y}) is outside {self.width}x{self.height}")
        return self.grid[y][x]

    def set(self, x: int, y: int, key: str) -> bool:
        """Set a pixel; silently ignore out of bounds. Returns True if written."""
        if self.in_bounds(x, y):
            self.grid[y][x] = key
            return True
        return False

    def rows(self) -> list[str]:
        return ["".join(r) for r in self.grid]

    def text(self) -> str:
        return "\n".join(self.rows())

    def copy(self) -> "Layer":
        return Layer(
            name=self.name,
            width=self.width,
            height=self.height,
            visible=self.visible,
            opacity=self.opacity,
            grid=[row[:] for row in self.grid],
        )

    def to_json(self) -> dict:
        d: dict = {"name": self.name, "pixels": self.rows()}
        if not self.visible:
            d["visible"] = False
        if self.opacity != 1.0:
            d["opacity"] = self.opacity
        return d

    @classmethod
    def from_json(cls, data: dict, width: int, height: int) -> "Layer":
        rows = data.get("pixels") or []
        grid = parse_grid(rows, width, height) if rows else []
        return cls(
            name=data["name"],
            width=width,
            height=height,
            visible=data.get("visible", True),
            opacity=float(data.get("opacity", 1.0)),
            grid=grid,
        )


@dataclass
class Frame:
    name: str
    duration_ms: int = 100
    layers: list[Layer] = field(default_factory=list)

    def layer(self, ref: str | int) -> Layer:
        return _resolve(self.layers, ref, "layer")

    def layer_index(self, ref: str | int) -> int:
        return self.layers.index(self.layer(ref))

    def copy(self, name: str | None = None) -> "Frame":
        return Frame(
            name=name or self.name,
            duration_ms=self.duration_ms,
            layers=[l.copy() for l in self.layers],
        )

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "layers": [l.to_json() for l in self.layers],
        }

    @classmethod
    def from_json(cls, data: dict, width: int, height: int) -> "Frame":
        return cls(
            name=data["name"],
            duration_ms=int(data.get("duration_ms", 100)),
            layers=[Layer.from_json(l, width, height) for l in data.get("layers", [])],
        )


@dataclass
class Tag:
    """A named animation range over frame indices (inclusive)."""

    name: str
    start: int
    end: int
    direction: str = "forward"  # forward | reverse | pingpong
    loop: bool = True

    def frame_indices(self) -> list[int]:
        seq = list(range(self.start, self.end + 1))
        if self.direction == "reverse":
            return seq[::-1]
        if self.direction == "pingpong":
            return seq + seq[-2:0:-1]
        return seq

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "from": self.start,
            "to": self.end,
            "direction": self.direction,
            "loop": self.loop,
        }

    @classmethod
    def from_json(cls, d: dict) -> "Tag":
        return cls(
            name=d["name"],
            start=int(d["from"]),
            end=int(d["to"]),
            direction=d.get("direction", "forward"),
            loop=bool(d.get("loop", True)),
        )


@dataclass
class Sprite:
    name: str
    width: int
    height: int
    palette: Palette = field(default_factory=Palette)
    frames: list[Frame] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    notes: str = ""

    # -- construction ------------------------------------------------------ #

    @classmethod
    def new(cls, name: str, width: int, height: int, layer_name: str = "base") -> "Sprite":
        if width <= 0 or height <= 0:
            raise SpriteError("width and height must be positive")
        s = cls(name=name, width=width, height=height)
        s.frames.append(Frame(name="frame0", layers=[Layer(layer_name, width, height)]))
        return s

    # -- lookups ----------------------------------------------------------- #

    def frame(self, ref: str | int) -> Frame:
        return _resolve(self.frames, ref, "frame")

    def frame_index(self, ref: str | int) -> int:
        return self.frames.index(self.frame(ref))

    def tag(self, name: str) -> Tag:
        for t in self.tags:
            if t.name == name:
                return t
        raise SpriteError(f"no tag named {name!r}")

    def layer_names(self) -> list[str]:
        names: list[str] = []
        for f in self.frames:
            for l in f.layers:
                if l.name not in names:
                    names.append(l.name)
        return names

    # -- frames ------------------------------------------------------------ #

    def add_frame(
        self,
        name: str | None = None,
        duration_ms: int = 100,
        copy_from: str | int | None = None,
        at: int | None = None,
    ) -> Frame:
        idx = len(self.frames) if at is None else max(0, min(at, len(self.frames)))
        if name is None:
            # name by the index the frame lands on (frame3 for [3]); skip taken names
            name = self._unique_name("frame", [f.name for f in self.frames], start=idx)
        elif any(f.name == name for f in self.frames):
            raise SpriteError(f"frame {name!r} already exists")

        if copy_from is not None:
            frame = self.frame(copy_from).copy(name)
            frame.duration_ms = duration_ms
        else:
            template = self.frames[-1] if self.frames else None
            layer_names = [l.name for l in template.layers] if template else ["base"]
            frame = Frame(
                name=name,
                duration_ms=duration_ms,
                layers=[Layer(ln, self.width, self.height) for ln in layer_names],
            )
        self.frames.insert(idx, frame)
        # tags follow their frames: a tag starting at/after the insertion point
        # shifts; one that spans the insertion point grows to include the new frame
        for t in self.tags:
            if t.start >= idx:
                t.start += 1
            if t.end >= idx:
                t.end += 1
        return frame

    def remove_frame(self, ref: str | int) -> None:
        if len(self.frames) == 1:
            raise SpriteError("a sprite must keep at least one frame")
        idx = self.frame_index(ref)
        del self.frames[idx]
        kept = []
        for t in self.tags:
            if t.start == t.end == idx:
                continue  # the tag's only frame is gone
            if t.start > idx:
                t.start -= 1
            if t.end >= idx:
                t.end -= 1
            kept.append(t)
        self.tags = kept

    def move_frame(self, ref: str | int, to: int) -> None:
        """Move a frame to index ``to``; tags keep pointing at the same frames.

        A tag whose frames stay contiguous simply follows them. If the moved
        frame leaves a tag's block, it drops out of that tag; if it is dropped
        into the middle of a tag's block, that tag grows to include it.
        """
        idx = self.frame_index(ref)
        tagged = [(t, self.frames[t.start : t.end + 1]) for t in self.tags]
        f = self.frames.pop(idx)
        self.frames.insert(max(0, min(to, len(self.frames))), f)
        for t, members in tagged:
            pos = sorted(self.frames.index(m) for m in members)
            if pos[-1] - pos[0] + 1 != len(pos) and f in members:
                pos = sorted(self.frames.index(m) for m in members if m is not f)
            t.start, t.end = pos[0], pos[-1]

    # -- layers (kept in sync across frames) ------------------------------- #

    def add_layer(self, name: str, at: int | None = None) -> None:
        if name in self.layer_names():
            raise SpriteError(f"layer {name!r} already exists")
        for f in self.frames:
            idx = len(f.layers) if at is None else at
            f.layers.insert(idx, Layer(name, self.width, self.height))

    def remove_layer(self, ref: str | int) -> None:
        for f in self.frames:
            if len(f.layers) == 1:
                raise SpriteError("a frame must keep at least one layer")
            del f.layers[f.layer_index(ref)]

    def rename_layer(self, ref: str | int, new_name: str) -> None:
        for f in self.frames:
            f.layer(ref).name = new_name

    def set_layer_visible(self, ref: str | int, visible: bool) -> None:
        for f in self.frames:
            f.layer(ref).visible = visible

    def move_layer(self, ref: str | int, to: int) -> None:
        for f in self.frames:
            idx = f.layer_index(ref)
            l = f.layers.pop(idx)
            f.layers.insert(max(0, min(to, len(f.layers))), l)

    # -- tags -------------------------------------------------------------- #

    def set_tag(
        self, name: str, start: int, end: int, direction: str = "forward", loop: bool = True
    ) -> Tag:
        if direction not in ("forward", "reverse", "pingpong"):
            raise SpriteError("direction must be forward, reverse or pingpong")
        n = len(self.frames)
        if start > end:
            raise SpriteError(f"tag range {start}..{end}: start > end")
        if not (0 <= start and end < n):
            raise SpriteError(f"tag range {start}..{end} out of bounds for {n} frames (0..{n - 1})")
        tag = Tag(name, start, end, direction, loop)
        for i, t in enumerate(self.tags):
            if t.name == name:
                self.tags[i] = tag
                return tag
        self.tags.append(tag)
        return tag

    def remove_tag(self, name: str) -> None:
        self.tags = [t for t in self.tags if t.name != name] if self.tag(name) else self.tags

    # -- canvas ------------------------------------------------------------ #

    def resize(self, width: int, height: int, anchor: str = "top-left") -> None:
        """Resize the canvas (crop or pad with transparent), keeping content."""
        if width <= 0 or height <= 0:
            raise SpriteError("width and height must be positive")
        dx, dy = _anchor_offset(anchor, self.width, self.height, width, height)
        for f in self.frames:
            for l in f.layers:
                new = [[TRANSPARENT_KEY] * width for _ in range(height)]
                for y in range(self.height):
                    ny = y + dy
                    if not 0 <= ny < height:
                        continue
                    for x in range(self.width):
                        nx = x + dx
                        if 0 <= nx < width:
                            new[ny][nx] = l.grid[y][x]
                l.grid, l.width, l.height = new, width, height
        self.width, self.height = width, height

    def validate(self) -> list[str]:
        """Return a list of problems (empty if the sprite is consistent)."""
        problems: list[str] = []
        names = self.layer_names()
        for fi, f in enumerate(self.frames):
            if [l.name for l in f.layers] != names:
                problems.append(f"frame {fi} ({f.name}) layer stack differs: {[l.name for l in f.layers]}")
            for l in f.layers:
                if l.width != self.width or l.height != self.height or len(l.grid) != self.height:
                    problems.append(f"frame {fi} layer {l.name!r} has wrong size")
                for y, row in enumerate(l.grid):
                    if len(row) != self.width:
                        problems.append(f"frame {fi} layer {l.name!r} row {y} has wrong width")
                    for ch in row:
                        if not self.palette.has(ch):
                            problems.append(f"frame {fi} layer {l.name!r} uses unknown key {ch!r}")
                            break
        for t in self.tags:
            if not (0 <= t.start <= t.end < len(self.frames)):
                problems.append(f"tag {t.name!r} range {t.start}..{t.end} is out of bounds")
        return problems

    # -- io ---------------------------------------------------------------- #

    def to_json(self) -> dict:
        return {
            "format": "agentsprite",
            "version": FORMAT_VERSION,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "notes": self.notes,
            "palette": self.palette.to_json(),
            "frames": [f.to_json() for f in self.frames],
            "tags": [t.to_json() for t in self.tags],
        }

    @classmethod
    def from_json(cls, data: dict) -> "Sprite":
        if data.get("format") not in (None, "agentsprite"):
            raise SpriteError("not an agentsprite document")
        w, h = int(data["width"]), int(data["height"])
        s = cls(
            name=data.get("name", "sprite"),
            width=w,
            height=h,
            palette=Palette.from_json(data.get("palette", {})),
            frames=[Frame.from_json(f, w, h) for f in data.get("frames", [])],
            tags=[Tag.from_json(t) for t in data.get("tags", [])],
            notes=data.get("notes", ""),
        )
        if not s.frames:
            s.frames.append(Frame("frame0", layers=[Layer("base", w, h)]))
        return s

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_json(), indent=1) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> "Sprite":
        p = Path(path)
        if not p.exists():
            raise SpriteError(f"no such sprite file: {p}")
        try:
            return cls.from_json(json.loads(p.read_text()))
        except (KeyError, ValueError, TypeError) as e:
            raise SpriteError(f"cannot parse {p}: {e}") from e

    # -- helpers ----------------------------------------------------------- #

    @staticmethod
    def _unique_name(prefix: str, existing: Iterable[str], start: int = 0) -> str:
        taken = set(existing)
        i = start
        while f"{prefix}{i}" in taken:
            i += 1
        return f"{prefix}{i}"


# --------------------------------------------------------------------------- #
# grid text helpers
# --------------------------------------------------------------------------- #


def parse_grid(
    text: str | list[str], width: int | None = None, height: int | None = None
) -> list[list[str]]:
    """Parse grid text into a list of rows of keys.

    Every line is a row: an empty or whitespace-only line is an all-``.`` row,
    so leading blank lines push the drawing down (a grid whose first two lines
    are empty starts at y=2). Only trailing blank lines are dropped. Spaces
    inside a row are ignored so agents may write ``. . # #`` for readability.
    """
    lines = text.splitlines() if isinstance(text, str) else list(text)
    rows = [line.strip().replace(" ", "") for line in lines]
    while rows and not rows[-1]:
        rows.pop()
    if not rows:
        raise SpriteError("grid is empty")
    w = max(len(r) for r in rows)
    if width is not None and w > width:
        raise SpriteError(f"grid is {w} wide but canvas is {width}")
    if height is not None and len(rows) > height:
        raise SpriteError(f"grid has {len(rows)} rows but canvas is {height}")
    target_w = width or w
    grid = [list(r.ljust(target_w, TRANSPARENT_KEY)) for r in rows]
    if height is not None:
        while len(grid) < height:
            grid.append([TRANSPARENT_KEY] * target_w)
    return grid


def _resolve(items: list, ref: str | int, kind: str):
    if isinstance(ref, int) or (isinstance(ref, str) and ref.lstrip("-").isdigit()):
        idx = int(ref)
        if not -len(items) <= idx < len(items):
            raise SpriteError(f"{kind} index {idx} out of range (have {len(items)})")
        return items[idx]
    for it in items:
        if it.name == ref:
            return it
    raise SpriteError(f"no {kind} named {ref!r}; have {[i.name for i in items]}")


ANCHORS = (
    "top-left", "top", "top-right",
    "left", "center", "right",
    "bottom-left", "bottom", "bottom-right",
)
"""Valid anchors for :meth:`Sprite.resize` and region stretching (``middle`` is an alias for ``center``)."""


def normalize_anchor(anchor: str) -> str:
    """Validate an anchor name and return its canonical form (``top-left``, ``bottom``, ...)."""
    a = anchor.strip().lower().replace("_", "-").replace(" ", "-")
    if a == "middle":
        a = "center"
    if a not in ANCHORS:
        raise SpriteError(f"unknown anchor {anchor!r}; use one of: {', '.join(ANCHORS)} (middle = center)")
    return a


def anchor_offset(anchor: str, ow: int, oh: int, nw: int, nh: int) -> tuple[int, int]:
    """Where an ``ow x oh`` box lands inside an ``nw x nh`` box when pinned to ``anchor``."""
    parts = normalize_anchor(anchor).split("-")
    dx = 0 if "left" in parts else (nw - ow if "right" in parts else (nw - ow) // 2)
    dy = 0 if "top" in parts else (nh - oh if "bottom" in parts else (nh - oh) // 2)
    return dx, dy


_anchor_offset = anchor_offset
