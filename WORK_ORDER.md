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

## Backlog (all done)

- [x] **Quiet/compact edit results.** Every drawing/transform tool (and
      `draw_copy`/`draw_cut`) takes `show="none" | "bbox" | "full"`. Default
      `bbox` prints one summary line plus the box around the pixels that
      actually changed, with absolute rulers (the tens ruler labels the
      first column too). `none` is the summary line only; `full` is the old
      whole-frame view. A no-op edit says `(no pixels changed)`. CLI:
      `--show`.
- [x] **Key-based selection for copy/clear/shift.** `keys="ocC"` on
      `draw_copy`, `draw_clear`, `transform_shift` (combinable with
      `region`). Plus `draw_cut(to_layer, keys=, region=, x=, y=, frame=)`:
      copy + erase in one call, position kept unless `x`/`y` given, works
      per frame with `frame="all"`. Moving the staff to its own layer is now
      `draw_cut(path, to_layer="staff", keys="ow", frame="all")`.
- [x] **Guide: props on their own layer.** New step 3 in the guide says to
      plan layers before drawing and points at `draw_cut` as the fix.
- [x] **Frame lists.** Every `frame` argument accepts `"1,3"`, ranges
      `"0..2"`, names, `all`, and mixes (`"0..2,idle4"`). Order kept,
      duplicates dropped. `draw_copy(to_frame=...)` too.
- [x] **`region` on `draw_replace`.** `region=[x0,y0,x1,y1]` (CLI
      `--region`), still all frames by default.
- [x] `frame_add(copy_from=..., count=3)` (CLI `-n`). With a `name` the
      copies are `name0, name1, ...`; `at` inserts them in order.
- [x] `sprite_show(onion_layer=...)`: a layer ref, or `"composite"`/`"all"`
      for the onion frame's flattened visible layers. Default stays "same
      layer as `layer`". Title and onion line say which was used.
- [x] `sprite_info` (and `layer ls`) print per-layer stats:
      `[1] staff  px: 55,55,58,55  keys: Cckosy  (hidden)` (one pixel count
      per frame).

## Dogfooding session 3 (24x24 slime, 4-frame bounce + 2-frame hurt flash, `examples/slime.sprite.json`)

Exercised the paths the knight/wizard rounds skipped: `draw_ellipse`,
vertical `region` shifts for squash-and-stretch, `draw_copy` within a frame
to fill the stretch gap, `draw_replace` per frame for the hurt recolor,
tags with `loop=False`, per-frame durations, `sprite_notes`, `sprite_diff`,
`export_sheet` -> `import_png(palette_from=)` round trip, `sprite_resize`,
`transform_rotate`, `frame_move`, hidden layers, and three deliberate errors.

What worked: `draw_ellipse` past the canvas edge clips silently. A batch of
8 parallel edits (4 renames + 4 shifts on two frames) landed with nothing
lost. Frame names work everywhere a frame ref is taken (`frame="hurt0"` on
`draw_replace`, `copy_from="rest"`, `onion="rest"`). Error messages list the
valid choices (`unknown palette key 'z' ... (palette keys: .kgGlwdrR)`,
`no layer named 'eyez'; have [...]`). Sheet export + re-import was
pixel-exact, including the `#0f0f1a80` semi-transparent shadow mapped back
to its key. Hidden layers stay out of `preview`. Sheet JSON carries names,
durations, tags, layers and the palette.

- [x] **Tags follow `frame_move`.** `Sprite.move_frame` now re-derives
      each tag from the frames it covered: a contiguous block simply
      follows its frames; a frame moved out of a block leaves the tag; one
      dropped into the middle of a block joins it. Consistent with
      `frame_add(at=)` and `frame_remove` (which already adjusted tags).
      `frame_move` prints the frame order and the tags afterwards.
- [x] **Changed-only "pixels affected" counts.** `set_grid`, `rotate`,
      `flip` and `mirror` now count cells whose key actually changed, so an
      identical grid or a symmetric rotate reports `0 pixels affected` and
      `(no pixels changed)`, matching the `changed:` bbox line.
- [x] **Region shift: merge vs overwrite.** Default merge behaviour is now
      documented on `transform_shift`; `overwrite=True` (CLI `--overwrite`)
      moves the box's transparent pixels too so its footprint replaces what
      it lands on (no more double outline).
- [x] **`sprite_diff` grid carries the keys.** Where the frames differ the
      grid shows frame B's key (ghost marker where B is transparent) plus
      added/removed/recolored counts and a bbox. The per-pixel list is
      opt-in: `limit=N` (CLI `--limit`), `-1` for all.
- [x] **Onion counts both directions.** The onion line now also counts the
      pixels of this frame that are transparent in the onion frame, with
      their bbox (`8 pixel(s) only in this frame (x=1..4 y=0..1)`).
- [x] **Multi-key `draw_replace`.** `old`/`new` may be several characters
      that pair up (`"gGl"` -> `"rRw"`) or MCP `mapping={"g":"r",...}`;
      all pairs apply in one pass so `gG` -> `Gg` swaps.
- [x] **`import_png` reads the sibling sheet JSON.** `<png>.json` (or
      `metadata=` / `--metadata`) restores frame rectangles (padding and
      columns honoured, scale undone), names, durations, tags and the
      palette; `palette_from` still wins over the sheet palette. A sibling
      JSON that is not sheet metadata is ignored; an explicit one errors.
- [x] **Resize anchor validated.** `normalize_anchor` accepts exactly the
      nine documented anchors (case/`_`/space tolerant, `middle` = `center`)
      and lists them in the error; used by `resize` and `stretch`.
- [x] `sprite_resize` takes `show=` (`bbox` default: the content box of
      frame 0 after the resize; `full`; `none`).
- [x] **Squash/stretch primitive.** `transform_stretch(region, dx, dy,
      anchor="bottom")` (CLI `transform stretch -r ... --dy -2`) resamples
      the box nearest-neighbour, always keeping its first/last row and
      column (the outline) and pinning the anchor edge. A bounce is one
      call per frame.
- [x] Bbox echo marks changed cells: when only some cells inside the
      changed box differ, a second grid beside it shows just those cells;
      a no-op still says `(no pixels changed)`.

## Dogfooding session 4 (18x24 side-view hero, 4-frame walk + flipped left-facing set, `examples/hero.sprite.json`)

Four layers planned up front (cape below body, legs, sword), a contact/pass
walk cycle, then frames 4..7 as the horizontal flip of 0..3. Exports in
`examples/out/hero_*`. Also exercised: `layer_add(at=0)`, `frame_update`,
`palette_remove`, `layer_set_visible`, `frame_move`, `export_frames`,
`export_png(background=)`, `export_sheet(metadata=False)` ->
`import_png(frame_width=, frame_height=, palette_from=)`, and five
deliberate errors. 13 tool calls in one parallel batch (exports + probes)
all landed.

Process note: the MCP server had been started before the session-3 edits
(no `transform_stretch`, single-key `draw_replace` only, old "pixels
affected" counts, no `limit=` on diff). Nothing in any result says which
build is running, so it took a failed multi-key replace to notice. The
stretch / diff-limit / sidecar-import checks below were done through the
CLI instead. Every finding marked *(current code)* was re-verified against
the working tree.

What worked: layer planning paid off exactly as the guide promises: the
1px bob in the pass frames was one `transform_shift` per moving layer
with `frame="1,3"`, spreading the legs was two region shifts with
`frame="0,2"`, and the second contact pose was a single
`transform_flip(layer="legs")` because the legs are symmetric about the
canvas centre. Making the back leg a darker key (`P`/`W`) is what makes
the cycle readable. `draw_copy(from_frame="pass_a", to_frame="0,2")`
rebuilt a botched layer from a good frame. `sprite_resize(anchor="center")`
gave the cape room after it hit the edge. Sheet without metadata ->
`import_png` sliced by frame size was pixel-exact over 8 frames; the
sidecar-JSON import (CLI) restored names, durations and both tags.
`export_frames` names (`hero_000_contact_a.png`) are engine-friendly.
`transform_stretch(region, dx=2, anchor="center")` widened each leg by one
column symmetrically and the changed-cells grid made that obvious at a
glance. Error messages that list the valid names saved a lookup every
time.

Bugs / gotchas

- [ ] **Blank lines in grid strings are dropped** *(current code)*.
      `draw_set` with two leading empty lines put the head at y=0 instead
      of y=2 (a legs grid that used `.` placeholder rows landed right).
      An empty line should be an all-`.` row; only strip the trailing
      newline. Same for whitespace-only lines.
- [ ] **`draw_outline` is not idempotent** *(current code)*. After a
      shift lost the cape's left outline at the canvas edge and a resize
      made room, re-running `draw_outline` outlined the existing outline
      (33 new `k` pixels, 2px border). Pixels already equal to `key`
      should not count as shape, so "re-outline after an edit" becomes a
      safe normal step. Recovering took clear + copy-from-frame + re-shift.
- [ ] **Default layer is index 0, whatever that is.** After
      `layer_add("cape", at=0)` a `draw_pixels` without `layer` silently
      drew on the cape, and the echo (`in frame [0] contact_a`) did not
      say which layer it hit. At minimum always name the layer in the
      echo when there is more than one; better, default to the top layer
      or remember an active layer per file.
- [ ] **Auto frame names disagree with indices** *(current code)*. With
      frame 0 renamed `contact_a`, `frame_add(copy_from=0, count=3)`
      produced `[1] frame0, [2] frame1, [3] frame2`. Name by index
      (`frame1..3`), skipping taken names.
- [ ] **Misleading errors** *(current code)*: `sprite_show(frame="0..9")`
      -> `no frame named '0..9'` (show takes a single frame; say so, or
      accept lists and print each). `tag_set(start=5, end=2)` ->
      `out of bounds for 8 frames` although both are in bounds; say
      `start > end`.
- [ ] **`draw_copy` echo repeats the source**: `from frames 1,1 -> (0,1)
      frames 0,2` (once per target frame).
- [ ] **Clear echo is all dots.** The bbox grid after `draw_clear` shows
      only `.`; show the keys that were removed (before-state) so a
      wrong region is visible without a second `sprite_show`.
- [ ] **Silent edge loss.** A region shift that pushes pixels off the
      canvas drops them without a word (documented, but I only noticed
      because the outline vanished). Echo `(N pixels dropped at the
      canvas edge)`.

Workflow requests

- [ ] **Composite-aware outline.** Outlining each layer separately gave a
      double outline where cape meets body and a legs-outline row that
      covered the tunic hem (fixed by hand with two region clears, and a
      third clear on the body layer in the pass frames). Wanted:
      `draw_outline(layer=..., against="composite")` that places `key`
      only where the composite is transparent.
- [ ] **Multi-layer / all-layer transforms.** Flipping the four
      left-facing frames took one `transform_flip` per layer (4 calls);
      the bob took 3 shifts. `layer="all"` or `layer="body,cape,sword"`
      on shift/flip/clear/rotate.
- [ ] **Copy a frame range.** The left-facing set needed four sequential
      `frame_add(copy_from=...)` calls (in parallel the order would be
      random). `frame_add(copy_from="0..3")` appending in order, with an
      optional name prefix (`name="l_"` -> `l_contact_a`, ...).
- [ ] **Undo / backup.** No way back from a bad edit except git or
      rebuilding by hand. Files are tiny: keep `<file>.bak` (or N deep)
      on every save and add `sprite_undo(path)`.
- [ ] **Cross-file diff.** Verifying the sheet round trip needed a Python
      script because `sprite_diff` only compares frames inside one file.
      `sprite_diff(path, frame_a, frame_b, other_path=...)`.
- [ ] **Report the running build.** Print the package version (and the
      source mtime or git short hash when run from a checkout) in
      `guide()` and `sprite_info`, so a stale server is obvious.
