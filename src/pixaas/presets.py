"""Built-in palette presets (well-known pixel-art palettes)."""

from __future__ import annotations

from dataclasses import dataclass

from .model import TRANSPARENT_KEY, SpriteError

_HEX = "0123456789abcdef"
_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    colors: tuple[str, ...]
    keys: str  # default key per color, same length as ``colors``

    def as_dict(self, keys: str | None = None) -> dict[str, str]:
        ks = keys if keys is not None else self.keys
        ks = ks.replace(" ", "")
        if len(ks) != len(self.colors):
            raise SpriteError(f"preset {self.name!r} has {len(self.colors)} colors but {len(ks)} keys were given")
        if len(set(ks)) != len(ks):
            raise SpriteError("keys must be unique")
        if TRANSPARENT_KEY in ks:
            raise SpriteError(f"{TRANSPARENT_KEY!r} is reserved for transparent")
        return dict(zip(ks, self.colors))


PRESETS: dict[str, Preset] = {}


def _add(name: str, description: str, colors: list[str], keys: str) -> None:
    PRESETS[name] = Preset(name, description, tuple(colors), keys)


_add(
    "pico-8",
    "PICO-8 fantasy console (16 colors; keys 0-f match PICO-8 indices)",
    [
        "#000000", "#1d2b53", "#7e2553", "#008751", "#ab5236", "#5f574f", "#c2c3c7", "#fff1e8",
        "#ff004d", "#ffa300", "#ffec27", "#00e436", "#29adff", "#83769c", "#ff77a8", "#ffccaa",
    ],
    _HEX,
)
_add(
    "sweetie-16",
    "Sweetie 16 by GrafxKid (16 colors, dark to light per hue)",
    [
        "#1a1c2c", "#5d275d", "#b13e53", "#ef7d57", "#ffcd75", "#a7f070", "#38b764", "#257179",
        "#29366f", "#3b5dc9", "#41a6f6", "#73eff7", "#f4f4f4", "#94b0c2", "#566c86", "#333c57",
    ],
    _HEX,
)
_add(
    "endesga-32",
    "Endesga 32 by Endesga (32 colors; keys a-z then A-F)",
    [
        "#be4a2f", "#d77643", "#ead4aa", "#e4a672", "#b86f50", "#733e39", "#3e2731", "#a22633",
        "#e43b44", "#f77622", "#feae34", "#fee761", "#63c74d", "#3e8948", "#265c42", "#193c3e",
        "#124e89", "#0099db", "#2ce8f5", "#ffffff", "#c0cbdc", "#8b9bb4", "#5a6988", "#3a4466",
        "#262b44", "#181425", "#ff0044", "#68386c", "#b55088", "#f6757a", "#e8b796", "#c28569",
    ],
    _ALPHA[:32],
)
_add(
    "gameboy",
    "Game Boy DMG greens (4 colors; 0 = darkest, 3 = lightest)",
    ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"],
    "0123",
)
_add(
    "1bit",
    "Black and white (k = black, w = white)",
    ["#000000", "#ffffff"],
    "kw",
)


def normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", "-").replace(" ", "-")


def get(name: str) -> Preset:
    key = normalize_name(name)
    if key not in PRESETS:
        raise SpriteError(f"unknown palette preset {name!r}; available: {', '.join(PRESETS)}")
    return PRESETS[key]


def presets_text() -> str:
    lines = []
    for p in PRESETS.values():
        lines.append(f"{p.name}: {p.description}")
        lines.append("  " + " ".join(f"{k}={c}" for k, c in zip(p.keys, p.colors)))
    return "\n".join(lines)
