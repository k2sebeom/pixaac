"""In-memory authoring API. Drawing never reads or writes a file."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Mapping, Sequence

from PIL import Image, ImageDraw

from . import model, ops, render, view
from .model import Palette, SpriteError, Tag

Point = tuple[int, int]
Box = tuple[int, int, int, int]


class Layer:
    """A live drawing surface in one frame, backed by palette keys."""

    def __init__(self, sprite: Sprite, frame: model.Frame, name: str):
        self._sprite, self._frame, self.name = sprite, frame, name

    @property
    def _data(self) -> model.Layer:
        return self._frame.layer(self.name)

    @property
    def _palette(self) -> Palette:
        return self._sprite.palette

    @property
    def visible(self) -> bool:
        return self._data.visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._data.visible = value

    def pixel(self, x: int, y: int, key: str) -> int:
        return ops.pixel(self._data, self._palette, x, y, key)

    def pixels(self, points: Sequence[Point], key: str) -> int:
        return ops.pixels(self._data, self._palette, list(points), key)

    def line(self, start: Point, end: Point, key: str) -> int:
        return ops.line(self._data, self._palette, *start, *end, key)

    def rect(self, box: Box, key: str, *, fill: bool = True) -> int:
        return ops.rect(self._data, self._palette, *box, key, fill)

    def ellipse(self, box: Box, key: str, *, fill: bool = True) -> int:
        return ops.ellipse(self._data, self._palette, *box, key, fill)

    def polygon(self, points: Sequence[Point], key: str, *, fill: bool = True) -> int:
        """Rasterize a polygon at native resolution, clipped to this canvas."""
        if not self._palette.has(key):
            raise SpriteError(f"unknown palette key {key!r}")
        if len(points) < 3:
            raise SpriteError("a polygon needs at least three points")
        mask = Image.new("1", (self._data.width, self._data.height))
        draw = ImageDraw.Draw(mask)
        draw.polygon(list(points), fill=1 if fill else None, outline=1)
        return sum(
            self._data.set(x, y, key)
            for y in range(mask.height)
            for x in range(mask.width)
            if mask.getpixel((x, y))
        )

    def fill(self, x: int, y: int, key: str, *, diagonal: bool = False) -> int:
        return ops.flood_fill(self._data, self._palette, x, y, key, diagonal)

    def stamp(self, grid: str, *, x: int = 0, y: int = 0, overwrite: bool = False) -> int:
        """Paste palette-key rows; transparent cells are skipped by default."""
        return ops.paste(self._data, self._palette, grid, x, y, not overwrite)

    def set_grid(self, grid: str) -> int:
        return ops.set_grid(self._data, self._palette, grid)

    def clear(self, *, region: Box | None = None, keys: str | None = None) -> int:
        return ops.clear(self._data, region, keys)

    def replace(self, mapping: Mapping[str, str], *, region: Box | None = None) -> int:
        return ops.replace_map(self._data, self._palette, dict(mapping), region)

    def outline(self, key: str, *, diagonal: bool = False, outer_only: bool = False) -> int:
        return ops.outline(self._data, self._palette, key, diagonal, outer_only)

    def shift(
        self, dx: int, dy: int, *, region: Box | None = None,
        keys: str | None = None, wrap: bool = False, overwrite: bool = False,
    ) -> int:
        return ops.shift(self._data, dx, dy, wrap, region, keys, overwrite)

    def flip(self, axis: str = "h", *, region: Box | None = None) -> int:
        return ops.flip(self._data, axis, region)

    def rotate(self, turns: int = 1) -> int:
        return ops.rotate(self._data, turns)

    def mirror(self, axis: str = "h", *, source: str = "first") -> int:
        return ops.mirror(self._data, axis, source)

    def stretch(
        self, *, region: Box | None = None, dx: int = 0,
        dy: int = 0, anchor: str = "bottom",
    ) -> int:
        return ops.stretch(self._data, region, dx, dy, anchor)

    def rows(self) -> list[str]:
        return self._data.rows()

    def bounds(self) -> Box | None:
        return ops.bounding_box(self._data)

    def histogram(self) -> dict[str, int]:
        return ops.histogram(self._data)


class Frame:
    """A named frame with a duration and the sprite's shared layer stack."""

    def __init__(self, sprite: Sprite, data: model.Frame):
        self._sprite, self._data = sprite, data

    @property
    def name(self) -> str:
        return self._data.name

    @property
    def duration_ms(self) -> int:
        return self._data.duration_ms

    @duration_ms.setter
    def duration_ms(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise SpriteError("duration_ms must be a positive integer")
        self._data.duration_ms = value

    def layer(self, name: str) -> Layer:
        """Get a layer, adding a transparent layer to every frame if new."""
        if name not in self._sprite._data.layer_names():
            self._sprite._data.add_layer(name)
        return Layer(self._sprite, self._data, name)


class Sprite:
    """A mutable pixel-art document; Python code is its source of truth."""

    def __init__(
        self, width: int, height: int, *,
        palette: Mapping[str, str | None] | Palette | None = None,
        name: str = "sprite",
    ):
        self._data = model.Sprite.new(name, width, height)
        colors = palette.colors if isinstance(palette, Palette) else palette
        if colors is not None:
            for key, color in colors.items():
                self._data.palette.set(key, color)

    @classmethod
    def _from_data(cls, data: model.Sprite) -> Sprite:
        sprite = cls.__new__(cls)
        sprite._data = data
        return sprite

    @property
    def name(self) -> str:
        return self._data.name

    @property
    def width(self) -> int:
        return self._data.width

    @property
    def height(self) -> int:
        return self._data.height

    @property
    def palette(self) -> Palette:
        return self._data.palette

    @property
    def frames(self) -> tuple[Frame, ...]:
        return tuple(Frame(self, frame) for frame in self._data.frames)

    def frame(self, ref: int | str = 0) -> Frame:
        return Frame(self, self._data.frame(ref))

    def layer(self, name: str = "base", *, frame: int | str = 0) -> Layer:
        return self.frame(frame).layer(name)

    def add_frame(
        self, name: str | None = None, *,
        copy_from: int | str | None = None, duration_ms: int = 100,
    ) -> Frame:
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            raise SpriteError("duration_ms must be a positive integer")
        return Frame(self, self._data.add_frame(name, duration_ms, copy_from))

    def tag(
        self, name: str, start: int, end: int, *,
        direction: str = "forward", loop: bool = True,
    ) -> Tag:
        return self._data.set_tag(name, start, end, direction, loop)

    def copy(self, *, name: str | None = None) -> Sprite:
        data = deepcopy(self._data)
        if name is not None:
            data.name = name
        return self._from_data(data)

    def resize(self, width: int, height: int, *, anchor: str = "top-left") -> None:
        self._data.resize(width, height, anchor)

    def validate(self) -> list[str]:
        return self._data.validate()

    def inspect(self, *, frame: int | str = 0, layer: str | None = None) -> str:
        return view.frame_text(self._data, frame, layer)

    def render(
        self, *, frame: int | str = 0, scale: int = 1,
        background: str | None = None,
    ) -> Image.Image:
        """Return a Pillow RGBA image. Scaling uses nearest-neighbour pixels."""
        image = render.render_frame(
            self._data.frame(frame), self.palette, self.width, self.height
        )
        return render.with_background(render.upscale(image, scale), background)

    def export_png(
        self, path: str | Path, *, frame: int | str = 0,
        scale: int = 1, background: str | None = None,
    ) -> Path:
        return render.export_png(self._data, path, frame, scale, background)

    def export_frames(
        self, directory: str | Path, *, scale: int = 1, background: str | None = None,
    ) -> list[Path]:
        return render.export_frames(self._data, directory, scale, background)

    def export_sheet(
        self, path: str | Path, *, columns: int | None = None, padding: int = 0,
        scale: int = 1, tag: str | None = None,
    ) -> tuple[Path, Path | None]:
        return render.export_sheet(self._data, path, columns, padding, scale, tag)

    def export_gif(
        self, path: str | Path, *, scale: int = 1,
        tag: str | None = None, background: str | None = None,
    ) -> Path:
        return render.export_gif(self._data, path, scale, tag, background)

    def export_apng(
        self, path: str | Path, *, scale: int = 1,
        tag: str | None = None, background: str | None = None,
    ) -> Path:
        return render.export_apng(self._data, path, scale, tag, background)

    def save(self, path: str | Path) -> Path:
        """Save an optional editable snapshot of the generated document."""
        self._data.save(path)
        return Path(path)

    @classmethod
    def load(cls, path: str | Path) -> Sprite:
        return cls._from_data(model.Sprite.load(path))

    @classmethod
    def from_png(
        cls, path: str | Path, *, palette: Palette | None = None,
        max_colors: int = 32, frame_width: int | None = None,
        frame_height: int | None = None, metadata: str | Path | None = None,
    ) -> Sprite:
        meta = render.load_sheet_metadata(path, metadata)
        # Import can assign keys; never mutate a caller-owned palette.
        data = render.import_png(
            path, palette=deepcopy(palette), max_colors=max_colors,
            frame_width=frame_width, frame_height=frame_height, meta=meta,
        )
        return cls._from_data(data)
