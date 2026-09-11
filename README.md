# agentsprite

A pixel-art sprite and sprite-sheet editor built for **AI agents**, not humans.
Think Aseprite, minus the GUI: everything is a CLI command or an MCP tool, and
pixels are expressed as text grids that a language model can read and write
directly.

```text
  0123456789
0 ....kkkk..
1 ..kkggggkk
2 .kggwggwgk
3 .kggeggegk
4 .kggggggkk
```

Every character is a **palette key** (`k` = outline, `g` = body, ...). `.` is
always transparent.

## Install

```bash
uv sync
uv run agentsprite --help
```

## Concepts

| Term    | Meaning                                                               |
| ------- | --------------------------------------------------------------------- |
| sprite  | One `*.sprite.json` file: palette + frames + tags + notes             |
| palette | Map of single-character key -> `#RRGGBB` / `#RRGGBBAA` (or transparent) |
| frame   | One animation frame with a duration in ms                            |
| layer   | A key grid; every frame has the same layer stack (bottom -> top)      |
| tag     | Named frame range (`walk: 0..3`, forward / reverse / pingpong)        |

Coordinates are 0-based, x to the right, y down. All ranges are inclusive.
Frames are referenced by index, name, or `all`. Layers by index or name.

## CLI walkthrough

```bash
agentsprite new slime.sprite.json -w 12 -h 10
agentsprite palette set slime.sprite.json k=#1a1a2e g=#4ade80 d=#16a34a w=#fff e=#000

# rows separated by '/' (or newlines, or pipe a file via stdin)
agentsprite draw set slime.sprite.json \
  "..../..../....gggg..../..gggggggg../.gggggggggg./.ggwggggwgg./.ggeggggegg./.gggggggggg./.dgggggggggd/.dddddddddd."
agentsprite draw outline slime.sprite.json k

agentsprite frame add slime.sprite.json --copy 0 -d 150   # duplicate frame 0
agentsprite transform shift slime.sprite.json 0 1 -f 1     # squash it 1px down
agentsprite tag set slime.sprite.json idle 0 1 --direction pingpong

agentsprite show slime.sprite.json -f 1        # text grid with rulers + legend
agentsprite show slime.sprite.json -f 1 --onion prev   # ghost frame 0 underneath (')
agentsprite diff slime.sprite.json 0 1         # what changed between frames

agentsprite export sheet slime.sprite.json out/slime.png -c 2 --padding 1 -s 4
agentsprite export gif   slime.sprite.json out/slime.gif -s 8
agentsprite export png   slime.sprite.json out/slime.png -f 0 -s 8 --bg '#222233'
agentsprite export apng  slime.sprite.json out/slime.png -s 8   # lossless RGBA animation

# palettes: built-in presets, or reuse another sprite's palette
agentsprite palette presets                               # pico-8, sweetie-16, endesga-32, gameboy, 1bit
agentsprite palette preset slime.sprite.json pico-8       # keys 0-f
agentsprite new hero.sprite.json --palette-from slime.sprite.json
agentsprite import hero.png hero.sprite.json --palette-from slime.sprite.json
```

Every mutating command prints the resulting grid so an agent can verify the
edit without a second call.

Command groups: `palette` (set, rm, ls, preset, presets), `frame`, `layer`,
`tag`, `draw` (pixel, line, rect, ellipse, fill, replace, clear, copy, paste,
set, outline), `transform` (flip, rotate, shift, mirror), `export` (png,
frames, sheet, gif, apng), `import`, `resize`, `notes`, `server`, `guide`.

`draw clear`, `draw copy`, `transform flip` and `transform shift` accept
`--region x0,y0,x1,y1` to touch only part of a layer (bob the torso, keep the
feet). `draw outline --outer-only` leaves enclosed gaps (between legs, inside
rings) open.

## Sprite sheet output

`export sheet` writes a PNG plus a JSON file in the shape of Aseprite's
"array" export, so existing importers (Phaser, Godot plugins, Unity tools)
can consume it:

```json
{
  "frames": [
    {"filename": "slime_0_frame0", "frame": {"x": 1, "y": 1, "w": 48, "h": 40}, "duration": 100, ...}
  ],
  "meta": {
    "app": "agentsprite", "image": "slime.png", "size": {"w": 99, "h": 42},
    "frameTags": [{"name": "idle", "from": 0, "to": 1, "direction": "pingpong"}],
    "palette": {".": null, "k": "#1a1a2e", "g": "#4ade80"}
  }
}
```

## MCP server

```bash
agentsprite server                       # stdio (default)
agentsprite server --transport streamable-http --port 8765
```

Claude Code / Claude Desktop config:

```json
{
  "mcpServers": {
    "agentsprite": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/agentsprite", "agentsprite", "server"]
    }
  }
}
```

The server exposes the same operations as tools (`sprite_new`, `palette_set`,
`palette_preset`, `draw_set`, `draw_paste`, `draw_line`, `frame_add`,
`tag_set`, `export_sheet`, `export_gif`, `export_apng`, ...). Results are plain
text (the grid after every edit), never JSON-wrapped, so newlines survive in
the client. Two extras are only meaningful over MCP:

- `preview(path, frame, scale)` and `preview_sheet(path)` return a rendered
  PNG so vision-capable agents can look at the actual pixels.
- `guide()` (also the `agentsprite://guide` resource) explains the workflow
  and a few pixel-art tips.

## File format

```json
{
  "format": "agentsprite", "version": 1,
  "name": "slime", "width": 12, "height": 10, "notes": "",
  "palette": {".": null, "k": "#1a1a2e", "g": "#4ade80"},
  "frames": [
    {"name": "frame0", "duration_ms": 100,
     "layers": [{"name": "base", "pixels": ["............", "....kkkk....", "..."]}]}
  ],
  "tags": [{"name": "idle", "from": 0, "to": 1, "direction": "pingpong", "loop": true}]
}
```

It is plain JSON with rows as strings, so it diffs well in git and can be
edited by hand or by an agent without the tool.

## Development

```bash
uv run pytest
```
