# Work Order

Findings from the first dogfooding session: an agent used agentsprite over MCP
to draw a 16x16 knight and a 2-frame idle animation (`examples/knight.sprite.json`).

## Done

- [x] Empty error when `sprite_new` targets a missing directory.
      Non-`SpriteError` exceptions were swallowed by the MCP wrapper and
      `save()` did not create parent directories. Both fixed.
- [x] **Region operations** (item 1). Moving only the torso required a
      whole-layer shift followed by re-pasting the feet. Added:
      - `region` (`x0,y0,x1,y1`, inclusive) on `shift`, `flip`, `clear`.
      - `draw_copy`: copy a region from one frame/layer to a position in
        another frame/layer (same file), optional `overwrite`.
- [x] **Outer-only outline** (item 2). `outline` filled every transparent
      pixel touching the shape, including gaps between arm/body and between
      the legs. Added `outer_only` option: only transparent pixels reachable
      from the canvas border are outlined.
- [x] **Onion skin text view.** `show --onion prev|next|<frame>` (MCP
      `sprite_show(onion=...)`) draws the other frame's silhouette as `'`
      wherever the current frame is transparent; legend/bbox still describe
      the real frame. The marker falls back to `` ` ``, `"`, `°` if `'` is a
      palette key.
- [x] **Plain-text tool results.** All MCP tools are registered with
      `structured_output=False`, so mcp 2.x emits only the text block (no
      `{"result": "..."}` copy with escaped newlines).
- [x] **Palette presets.** `palette preset FILE NAME [--keys ...]` and
      `palette presets` (MCP `palette_preset` / `palette_presets`):
      pico-8, sweetie-16, endesga-32, gameboy, 1bit. Presets merge into the
      existing palette; `--keys` remaps the keys in preset order.
- [x] **Reuse an existing sprite's palette.** `--palette-from FILE` on
      `import` and on `new` (MCP `palette_from=`). Import maps matching
      colors to the existing keys and only allocates keys for new colors.
- [x] **APNG export.** `export apng` / `export_apng`: full RGBA per frame
      (semi-transparent colors survive, unlike GIF), honours durations, tags
      and `--bg`.
- [x] Fixed a wrong test: a U shape open at the canvas edge is *not*
      enclosed, so `outer_only` correctly outlines its interior. Replaced it
      with a genuinely closed gap-between-legs case plus the open-cup case.

## Dogfooding session 2 (32x32 wizard, 4-frame idle, `examples/wizard.sprite.json`)

What worked: `draw_set` with a hand-written 32x32 grid was fine (short rows
padded, no counting of trailing dots). `draw_paste` with a sparse grid is a
good way to batch unrelated pixel edits into one call. `draw_copy` +
`overwrite` pastes moved the staff onto its own layer after the fact.
Onion skin made the 1px bob obvious. `preview_sheet` gave a one-shot check of
all frames. Presets listing was useful as a reference but a hand-picked
palette with mnemonic keys (p robe, s skin, o wood) was easier to draw with
than index keys.

- [x] **Lost writes on concurrent tool calls.** mcp 2.x runs sync tools on
      worker threads and every api call is load -> edit -> save. 64 parallel
      `draw_pixels` on one file kept 7 pixels. Fixed with a per-path lock in
      the server wrapper; regression test added.

## Backlog

- [ ] **Quiet/compact edit results.** Every edit echoes the full grid: at
      32x32 that is ~1.2 KB per call, most of it unchanged. Add
      `show="none" | "bbox" | "full"` (default bbox of the changed pixels,
      with rulers) or a `quiet` flag on the drawing tools.
- [ ] **Key-based selection for copy/clear/shift.** A rectangle could not
      express "everything except the staff column". Options: `keys="ocC"` on
      `draw_copy`/`draw_clear`/`transform_shift` to restrict to those keys, or
      a `layer_split(keys)` / `draw_cut` that moves matching pixels to another
      layer in one call. Moving the staff to its own layer took 3 calls and
      hand-written cleanup grids.
- [ ] **Guide: props on their own layer.** Say up front: put anything that
      moves independently (weapon, staff, cape, shadow) on its own layer
      before drawing; bobbing the body is then a one-call `transform_shift`.
- [ ] **`transform_shift` with `frame="1,3"`.** Applying the same bob to two
      non-adjacent frames took two identical calls; accept a frame list.
- [ ] **`region` on `draw_replace`.** "Make the orb interior brighter" is a
      recolor of a few pixels; flood fill worked but a region-limited replace
      is the natural tool and does not depend on connectivity.
- [ ] `frame_add(copy_from=..., count=3)` to make N duplicates at once.
- [ ] `sprite_show(layer=...)` for the onion view uses the same layer for the
      ghost; add `onion_layer` so the body can be checked against the
      composite (staff layer visible) of the previous frame.
- [ ] Notes mention the layer plan; `sprite_info` could print per-layer
      pixel counts so an agent can see at a glance which layer holds what.
