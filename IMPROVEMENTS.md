# PixaaS improvement action items

Based on a hands-on trial creating a 32×32 frog courier, animating a bounce and
blink, generating a palette variant, and exporting and reimporting assets.

The trial confirmed that PNG export, GIF/APNG animation timing, editable snapshot
round trips, and full sprite-sheet pixel round trips worked for this asset.
Preserve those behaviors while improving export correctness and authoring speed.

## P0 — Fix tagged sprite-sheet exports

Two problems were reproduced:

- Exporting a tag covering source frames `1..2` creates a two-frame sheet whose
  JSON tag still references `1..2`. In an Aseprite-style frame array, the exported
  positions are `0..1`.
- Exporting a reverse tag and importing the resulting sheet loses the tag.
  Attempting to export that imported animation raises
  `SpriteError: no tag named 'reverse-reaction'`.

Relevant code: `build_sheet()` and `import_png()` in `src/pixaas/render.py`.

- [x] Define tag ranges against positions in the exported frame array.
- [x] Pack selected frames in source order and express playback order through
  tag direction metadata.
- [x] Keep original source indices as separate metadata if useful; make the
  importer distinguish them from exported array positions.
- [x] Preserve names, durations, direction, and loop behavior through tagged
  sheet export/import.
- [x] Maintain import compatibility with existing PixaaS sheets that use source
  indices for tag endpoints.
- [x] Add focused regression coverage for nonzero-start ranges, forward,
  reverse, pingpong, single-frame, and one-shot tags.

**Acceptance criteria:** Every exported tag addresses valid exported frame
positions. Export → import → animation export preserves the intended frame
sequence and timing. Reverse tags survive the round trip. Existing full-sheet
round trips continue to work.

## P1 — Shorten the visual iteration loop

During the trial, checking proportions required exporting and opening images.
A local preview should keep the Python script as the source of truth.

- [ ] Add a documented watch command that reruns an authoring script and refreshes
  a preview when the script or its local art modules change.
- [ ] Provide nearest-neighbor zoom and a transparency checkerboard.
- [ ] Add play/pause, frame stepping, frame names, and duration display.
- [ ] Show script errors while retaining the last successful preview.
- [ ] Document how scripts expose preview assets and how to select among
  multiple sprites.
- [ ] Keep preview tooling optional so ordinary scripts and build jobs remain
  lightweight.

**Acceptance criteria:** After starting preview once, a user can change a shape,
palette, or frame duration and inspect the result without manually reopening an
image. A script error is visible, and correcting it resumes updates.

## P1 — Expose layer management in the public SDK

The underlying model supports several layer-management operations that the
public `Sprite`/`Frame`/`Layer` API does not expose.

- [ ] Add a public way to list layers in stacking order.
- [ ] Expose layer reordering, renaming, and removal.
- [ ] Define and document how those operations affect every frame.
- [ ] Define how existing `Layer` handles behave after a rename or removal.
- [ ] Offer strict layer lookup alongside get-or-create behavior, so a typo
  during editing can raise an actionable error.
- [ ] Add a README example that moves a foreground accessory behind a character.

**Acceptance criteria:** A script can inspect and change stacking order without
accessing private data or saving and reloading a snapshot. Structural operations
keep frames consistent, and stale handles fail clearly or remain valid according
to the documented contract.

## P2 — Make related parts easier to move together

The frog's bounce required separate shifts for its head, body, and bag. Start
with a small abstraction that works with ordinary Python drawing functions.

- [ ] Design a lightweight way to select named layers and apply a shared shift
  within one frame.
- [ ] Document a common origin convention for reusable drawing functions.
- [ ] Add an example with an accessory that follows a character's movement.
- [ ] Specify clipping and wrapping behavior for grouped shifts.
- [ ] Evaluate a richer component/group API only after the smaller helper has
  been exercised in examples.

**Acceptance criteria:** The example moves the head, body, and accessory together
with one public operation while leaving the feet and other frames unchanged.
Individual layers remain independently editable.

## P2 — Make the README demonstrate the value immediately

- [ ] Place a rendered sprite, an animation, and palette variants near the top.
- [ ] Put a short runnable authoring example beside those results.
- [ ] Explain the practical benefit: edit a shared function or palette and
  regenerate a consistent family of assets.
- [ ] Include a clear path from installation to the first visible output.
- [ ] Add a troubleshooting note for layer order, clipped outlines, and blank
  frames created without `copy_from`.
- [ ] Ensure showcased assets are reproducible from checked-in scripts.

**Acceptance criteria:** A new reader can see what PixaaS produces before reading
the detailed API guide and can reproduce a showcased asset using documented
commands.

## Suggested delivery order

1. Fix tagged exports and add regression coverage.
2. Improve README examples and visual evidence.
3. Expose layer management.
4. Deliver a minimal watching preview, then animation controls.
5. Add grouped movement after validating the API with a complete example.

The hands-on reproduction script and generated outputs are under
`out/pixaas-feedback/` in the trial workspace. That directory is generated output;
move durable regression cases into `tests/` and reusable demonstrations into
`examples/` as the items are implemented.
