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

agentsprite frame add slime.sprite.json --copy 0 -d 150 -n 3   # 3 duplicates of frame 0
agentsprite transform stretch slime.sprite.json -r 1,2,10,9 --dy -2 -f 1   # squash the body onto its feet
agentsprite transform stretch slime.sprite.json -r 1,2,10,9 --dy 2 -f 3    # stretch it
agentsprite draw replace slime.sprite.json gd wr -f 2                       # recolor two keys at once (hurt flash)
agentsprite tag set slime.sprite.json idle 0 3 --direction pingpong

agentsprite show slime.sprite.json -f 1        # text grid with rulers + legend
agentsprite show slime.sprite.json -f 1 --onion prev   # ghost frame 0 underneath (')
agentsprite diff slime.sprite.json 0 1         # what changed between frames (grid; --limit N lists pixels)

agentsprite export sheet slime.sprite.json out/slime.png -c 2 --padding 1 -s 4
agentsprite export gif   slime.sprite.json out/slime.gif -s 8
agentsprite export png   slime.sprite.json out/slime.png -f 0 -s 8 --bg '#222233'
agentsprite export apng  slime.sprite.json out/slime.png -s 8   # lossless RGBA animation
agentsprite import out/slime.png back.sprite.json               # reads out/slime.json: names, durations, tags, palette

# palettes: built-in presets, or reuse another sprite's palette
agentsprite palette presets                               # pico-8, sweetie-16, endesga-32, gameboy, 1bit
agentsprite palette preset slime.sprite.json pico-8       # keys 0-f
agentsprite new hero.sprite.json --palette-from slime.sprite.json
agentsprite import hero.png hero.sprite.json --palette-from slime.sprite.json
```

Every mutating command prints what changed so an agent can verify the edit
without a second call: by default only the box around the changed pixels
(with absolute rulers), `--show full` for the whole frame, `--show none` for
a one-line result. Counts are *changed* pixels: rewriting a layer with an
identical grid, or rotating a symmetric shape, reports `0 pixels affected`
and `(no pixels changed)`.

```text
filled rect 'k': 12 pixels affected in frame 0
changed: x=12..15 y=3..5 (12 pixels) in frame [0] frame0; show="full" for the whole 32x32 frame
  1
  2345
3 kkkk
4 kkkk
5 kkkk
```

When only some cells inside the box changed, a second grid beside it shows
just those cells, so setting a few `g` pixels inside a `g` area is still
visible:

```text
pixels 'k': 2 pixels affected in frame 0
changed: x=1..4 y=1..4 (2 pixels) in frame [0] frame0; show="full" ...; right grid = changed cells only
  1234   1234
1 kggg   k
2 gggg
3 gggg
4 gggk      k
```

Command groups: `palette` (set, rm, ls, preset, presets), `frame`, `layer`,
`tag`, `draw` (pixel, line, rect, ellipse, fill, replace, clear, copy, cut,
paste, set, outline), `transform` (flip, rotate, shift, stretch, mirror),
`export` (png, frames, sheet, gif, apng), `import`, `resize`, `notes`,
`server`, `guide`.

Selecting what an edit touches:

- `-f/--frame` takes an index, a name, `all`, a range `0..2` or a list `1,3`,
  so one call applies the same bob to several frames.
- `--region x0,y0,x1,y1` on `draw clear`, `draw copy`, `draw cut`,
  `draw replace`, `transform flip` and `transform shift` limits the edit to a
  box (bob the torso, keep the feet; brighten only the orb interior).
- `--keys ow` on `draw clear`, `draw copy`, `draw cut` and `transform shift`
  limits it to pixels with those palette keys ("everything except the staff"
  is a rectangle problem no more).
- `draw cut FILE staff --keys ow -f all` moves the matching pixels onto
  another layer in one call. Put anything that moves independently (weapon,
  staff, cape, shadow) on its own layer before drawing; if you forgot, this
  is the fix.
- `draw outline --outer` leaves enclosed gaps (between legs, inside rings)
  open.
- `draw replace FILE gGl rRw` recolors several keys in one pass (the
  characters pair up; MCP also takes `mapping={"g": "r", ...}`). Pairs apply
  simultaneously, so `gG Gg` swaps two keys.

Animation helpers:

- `transform stretch -r x0,y0,x1,y1 --dy -2` squashes a region onto its
  bottom edge (`--dy 2` stretches it; `--dx` for width; `--anchor top`,
  `center`, ... for which edge stays put). Rows/columns are duplicated or
  dropped nearest-neighbour and the box's edges (the outline) are always
  kept, so a bounce is one call per frame instead of a shift plus a fix-up.
- `transform shift` with `--region` merges the moved pixels into the landing
  area by default (old pixels survive under transparent cells of the moved
  box); `--overwrite` makes the box's footprint replace what it lands on.
- Tags follow their frames through `frame add --at`, `frame mv` and
  `frame rm`: a frame moved out of a tag's block leaves the tag, one dropped
  into the middle of a block joins it.
- `resize --anchor` validates its argument (`botom` is an error, not a silent
  center) and prints the content box afterwards (`--show full|none`).

`show --onion prev` ghosts the previous frame under the current one and
counts both directions (pixels only in the ghost, pixels only in this frame
with their bbox); with `--layer body --onion-layer composite` the ghost is the
previous frame's full composite (staff included) while you look at one layer.
`diff A B` prints a grid with B's key where the frames differ (`'` where B is
transparent) plus added/removed/recolored counts; `--limit N` adds up to N
per-pixel lines, `--limit -1` all of them. `info` lists per-layer pixel counts
and keys per frame so you can see which layer holds what.

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
`palette_preset`, `draw_set`, `draw_paste`, `draw_line`, `draw_cut`,
`frame_add`, `tag_set`, `export_sheet`, `export_gif`, `export_apng`, ...).
Results are plain text (the changed box after every edit, or the whole grid
with `show="full"`), never JSON-wrapped, so newlines survive in the client.
Two extras are only meaningful over MCP:

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

`import` turns a PNG back into this format. When the sheet's JSON sits next to
the image (or `--metadata FILE` points at it) the frame rectangles, names,
durations, tags and palette are restored, so `export sheet` -> `import` is a
lossless round trip; otherwise `--frame-width/--frame-height` slice the image
and the frames are named `frame0, frame1, ...`.

## Development

```bash
uv run pytest
```
