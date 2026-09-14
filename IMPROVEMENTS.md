# PixaaC improvement action items

## Asset consolidation — 2026-09-14

All art now lives under [`assets/`](assets/README.md). Each collection keeps its
builder, curated `showcase/` images, and ignored `generated/` exports together.
README imports and commands, documentation images, and test fixtures use the new
paths. Browser screenshots are in `assets/screenshots/`.

Unreferenced mechanic studies, unused legacy snapshots, superseded robot README
images, duplicate builds, and scratch trial artifacts have been removed. The
robot and courier factories and the hero snapshot remain because tests use them.
The preview watcher ignores `generated/` directories, and a single showcase
command regenerates the documented Moonlit Market and Tideglass art.

Verification: all 140 tests pass, all 47 documentation links resolve, and the
11 retained images plus the compatibility fixture are byte-identical to their
previous versions. Both collection exports and the curated showcase regenerate
under `assets/`; the retired `examples/`, `out/`, and `docs/images/` directories
are no longer present.

## Connected browser feedback — 2026-09-14

Browser-use MCP is now connected. See [browser findings](docs/browser-feedback.md).

- [x] Verify printed URL selection, basic playback, comparison, and pixel/grid
  coordinates at every zoom in a real browser.
- [x] Reproduce 40 px document overflow in comparison mode at a 390 px viewport.
- [x] Fix narrow-screen comparison layout and selector overflow.
- [x] Remove the missing-favicon request from a normal preview load.
- [x] Verify one-shot/reverse/pingpong/single-frame overlays, imported-source
  refresh, last-good-image retention on errors, and recovery in the browser.
- [x] Repeat visual checks and record the completed release gates.

The browser-use pass verified Chrome 152 at widths from 320 to 1280 px. All
140 regression tests pass. The repeatable
[browser check](scripts/verify_preview_browser.js) covers the Tideglass UI; the
[feedback log](docs/browser-feedback.md) records the additional Moonlit Market
and source-rebuild checks. Hosted CI and target-engine review remain separate.

## Tideglass feedback loop — 2026-09-14

See [the trial evidence](docs/tideglass-feedback.md) and
[reproducible artwork](assets/tideglass/build.py). This round builds on the existing
uncommitted Moonlit Market and preview work.

- [x] Create and visually inspect a new animated coastal asset set at native and
  enlarged resolution.
- [x] Reproduce palette collisions in grid-based scene composition.
- [x] Add palette-safe `Layer.blit` with explicit remapping, clipping, transparent
  overwrite, and atomic failure behavior.
- [x] Use it in the scene and verify the storm beacon retains its light colors.
- [x] Refine illumination, water clusters, and foreground depth; inspect all poses.
- [x] Reproduce acceptance of negative sheet padding and fractional columns.
- [x] Validate sheet geometry and add opt-in edge extrusion for texture sampling.
- [x] Verify exported content rectangles, gutters, scale, animation metadata,
  transparency, reproducibility, and snapshot/sheet round trips.
- [x] Detect GIF quantization merging nearby colors in a 21-color scene.
- [x] Preserve exact GIF colors whenever the frame fits in its visible palette.
- [x] Build and smoke-test the installed distribution, including preview resources.
- [x] Add continuous checks for Python 3.12–3.14, Node controller tests, and the
  installed wheel. The workflow is added; hosted CI has not yet run.
- [x] Complete visible preview interaction checks in a connected browser.

Production readiness requires passing the checks above and visual acceptance
for the target game's style. A green unit suite alone does not establish either.

Verification: **140 tests passed** on Python 3.12.9 with Node 22.14.0. Source and
wheel distributions built; the isolated wheel passed authoring/export, preview
worker, HTTP, and resource checks. Native and enlarged art, all poses, and an
opaque extrusion fixture were visually inspected. See the
[review board](assets/tideglass/showcase/review.png),
[pose board](assets/tideglass/showcase/poses.png), and
[release procedure](docs/releasing.md). The subsequent browser-use pass above
closed the browser verification gap.

Updated after the [Moonlit Market trial](docs/moonlit-market-feedback.md):
two 40×40 fox variants, three 24×24 potion icons, and a 96×64 animated shop.
The reproducible authoring script is [assets/moonlit_market/build.py](assets/moonlit_market/build.py).

The previous checklist is complete. This next round targets one confirmed
preview bug and the effort required to refine artwork. Coordinate inspection,
onion-skinning, and comparison views are proposed usability improvements;
the trial did not establish them as correctness defects.

Implementation update (2026-09-14): the URL fix, inspection controls, onion
skins, comparison mode, and example refinements are implemented. The full suite
passes, including the Node controller regressions. Native and enlarged artwork
was regenerated and visually inspected. The browser runtime initially reported
no available browsers; the subsequent browser-use pass completed verification. See the
[refinement and verification notes](docs/moonlit-market-refinement.md).

## Preserve the working baseline

The trial verified full sheet and snapshot round trips for all six assets,
including rendered pixels, frame names, and durations. Snapshots retained layer
names and order. Nonzero-start forward, reverse, and pingpong one-shot tags
preserved decoded GIF/APNG pixels, timing, and loop metadata through reimport.
Watcher backend checks confirmed imported-module updates, retention of the last
successful assets on errors, and recovery after correction.

Keep existing export regression coverage, public layer management, grouped
movement, and the optional lightweight preview intact. Python remains the source
of truth; preview overlays must not change sprite pixels or exported files.

Browser interaction was unavailable during the initial trial. The subsequent
browser-use pass verified play/pause, stepping, checkerboard rendering, and
visible refresh/error behavior.

## P0 — Fix the preview URL printed with `--sprite`

The documented command

```sh
python -m pixaac.preview assets/moonlit_market/build.py --sprite fox
```

prints `http://127.0.0.1:8765/?sprite=fox`. Requests with this query-string
format return **404**, while `/` and `/state` return **200**.
`make_server()` compares the complete request target with `/`, including the
query string that the CLI appends.

Relevant code: `make_server()` and `main()` in `src/pixaac/preview.py`;
initial asset selection in `src/pixaac/preview.html`.

- [x] Route requests using the parsed URL path, retaining query parameters for
  client-side sprite selection.
- [x] Add a focused HTTP regression check for the URL format printed by the CLI,
  including an asset name requiring URL encoding.
- [x] Confirm unknown paths still return 404.
- [x] Open the printed URL in a browser and verify the requested asset is
  selected; verify a missing asset name produces the documented fallback.

**Acceptance criteria:** The exact printed URL loads successfully and selects
`fox` without manual URL editing. The README's `--sprite` example works.

## P1 — Add cursor coordinates and an optional pixel grid

Refining the fox's face required inspecting a render and translating the desired
change back into source coordinates. The preview should make that translation
direct.

Relevant code: `src/pixaac/preview.html`.

- [x] Display native pixel `(x, y)` coordinates under the pointer, with `(0, 0)`
  at the top left.
- [x] Keep coordinate mapping correct at every supported zoom and after
  scrolling the preview; clear the readout outside the image.
- [x] Add a toggleable pixel grid that aligns with native pixel boundaries
  without obscuring the artwork.
- [x] Preserve zoom and grid choices across successful rebuilds.
- [x] Document the controls.
- [x] Verify coordinate mapping in the browser at image corners,
  after scrolling, and after switching between differently sized assets.

**Acceptance criteria:** A user can identify a fox eye pixel at multiple zoom
levels, change that coordinate in Python, and see the intended pixel update.
Grid lines stay aligned, and exported PNGs contain no preview overlays.

## P1 — Add onion-skinning for pose refinement

The fox's breathing motion and blink are easy to generate but harder to compare
one frame at a time. Adjacent-pose overlays should reveal alignment and motion.

Relevant code: `src/pixaac/preview.html`; preview serialization in
`src/pixaac/preview.py` only if additional data is needed.

- [x] Add independently toggleable previous/next pose overlays with distinct
  tints and adjustable opacity.
- [x] Define neighbors by the selected tag's playback sequence, including
  reverse and pingpong order.
- [x] Wrap neighbors only for looping playback; omit unavailable neighbors at
  one-shot boundaries and avoid redundant overlays for single-frame assets.
- [x] Keep overlays aligned at every zoom and update them when stepping,
  changing tags, switching assets, or rebuilding.
- [x] Document whether overlays appear during playback (they remain visible).
- [x] Verify overlay rendering and playback behavior in the browser.

**Acceptance criteria:** While stepping through the fox animation, a user can
distinguish the stationary feet from the moving head and lantern. Reverse,
pingpong, one-shot, and single-frame selections show the expected neighbors.
Turning overlays off restores the ordinary preview.

## P2 — Compare variants and poses side by side

Palette variants were the clearest productivity gain in the trial. Comparing
them currently requires switching the selected asset or creating a separate
contact sheet.

- [x] Add an optional second preview pane with independent asset and frame
  selection.
- [x] Use a shared zoom and consistent canvas alignment so differences in color
  and silhouette are easy to judge.
- [x] Label each pane with its asset, frame name, and duration.
- [x] Refresh both panes after a successful rebuild while retaining valid
  selections; handle a removed asset or frame without stale content.
- [x] Keep the single-pane workflow as the default and document comparison mode.

**Acceptance criteria:** A user can compare fox and arctic palettes, then two
poses of the same fox, without exporting a contact sheet. Both panes update
after source changes, including when the selected assets have different sizes
or frame counts.

## P2 — Improve the example's palette roles and visual polish

The art is useful for prototyping, but the scene is geometric and the animation
mostly translates parts by one pixel. These are authoring limitations. The
arctic palette also changes lantern light because fur and light share keys.

Relevant code: `assets/moonlit_market/build.py`.

- [x] Separate fur and lantern-light palette keys so recoloring the character
  can preserve its accessory's lighting.
- [x] Document the distinction between material roles and shared color values
  in the palette example.
- [x] Refine the fox animation with a deliberate pose change beyond a shared
  shift, using ordinary drawing functions and independently editable layers.
- [x] Give the shop a focused detail and lighting pass, checking readability at
  native resolution as well as enlarged.
- [x] Regenerate previews and document the arctic lantern's before/after pixel
  color at `(5, 31)`, with a walkthrough for the new inspection controls.
- [x] Complete that inspection walkthrough in a connected browser.

**Acceptance criteria:** Fox variants retain the intended lantern colors, and
all six assets remain reproducible from the script. A visual review confirms
that the revised motion and scene details read at native size; export and
snapshot round trips continue to preserve the assets.

## Suggested delivery order

1. Fix the printed preview URL and verify the existing controls in a browser.
2. Add coordinate inspection and the pixel grid.
3. Add onion-skinning and exercise it on the fox poses.
4. Add side-by-side comparison for palettes and poses.
5. Refine the example using those controls and record any remaining friction.

For preview changes, verify play/pause, frame stepping, nearest-neighbor zoom,
transparency, imported-module refresh, visible errors, and recovery in a browser.
Keep focused regression cases in `tests/`; scratch trial artifacts were removed
during asset consolidation after their findings were recorded in the notes.

Defer persistent component objects, nested groups, and transform hierarchies
until a concrete example needs them. Ordinary functions and `shift_layers()`
were sufficient for this trial.
