# PixaaC hands-on review: Moonlit Market

Trial date: 2026-09-13.

Follow-up: the URL fix and preview improvements are now implemented, along with
an art refinement pass. See [the refinement notes](moonlit-market-refinement.md)
for current behavior, regenerated artwork, and remaining browser verification.
The observations below record the original trial.

**Verdict:** PixaaC is useful for small, reproducible game assets, especially
families of icons and recolored characters. The SDK stayed out of the way during
this trial. Visual refinement is still the expensive part: code makes repeating
an established design cheap, but does not make discovering a good design cheap.

## What I made

Run `.venv/bin/python examples/moonlit_market.py` from this checkout, or use
`python` after installing PixaaC in your environment.

- A 40×40 lantern fox, with four breathing/blinking poses.
- An arctic fox made by copying the same sprite and changing five palette keys.
- Three 24×24 potion icons from one factory and palette swaps.
- A 96×64 apothecary at night, with four frames of moving fireflies.

All artwork uses the public PixaaC SDK. Pillow only lays out the contact sheet.
The script exposes all six assets through `preview_assets()`.

Generated files are in `out/moonlit-market/`: `contact-sheet.png`, native and
enlarged PNGs, GIF/APNG animations, sheets with JSON, and editable snapshots.
The output folder is ignored by Git; rerun the example to regenerate the art.

## What worked

- **Variants are the clearest value.** Once the potion geometry existed,
  producing two more coherent icons required only palette changes.
- **Grouped movement is enough for this character.** One call moved the body,
  head, face, scarf, arm, and lantern while the feet and shadow stayed planted.
  A scene graph would have added little value here.
- **Layers are understandable.** Named surfaces made it easy to isolate the
  blink and put the tail behind the body. The public rename operation worked
  without reaching into the model.
- **The earlier export fixes held up on new art.** All six assets retained
  rendered pixels, frame names, and durations through full sheet and snapshot
  round trips. Snapshots also preserved layer names and order.
- **Tagged exports held up.** Source frames 1–3 exported with tag positions
  0–2. Forward, reverse, and pingpong one-shot tags retained decoded animation
  pixels, durations, and loop metadata through sheet import and subsequent GIF
  and APNG export.
- **Watcher recovery worked at the backend.** Editing an imported local module
  changed preview images. A syntax error retained the previous assets, and
  fixing it resumed updates.

## Confirmed bug: the advertised asset-selection URL returns 404

The documented invocation

```sh
python -m pixaac.preview examples/moonlit_market.py --sprite fox
```

prints `http://127.0.0.1:8765/?sprite=fox`.

An HTTP trial against the actual server returned:

| Request | Status |
| --- | --- |
| `/` | 200 |
| `/?sprite=probe` | 404 |
| `/state` | 200 |

`make_server()` compares `self.path` directly with `/`, but that value includes
the query string. The CLI explicitly appends that query string for `--sprite`.
See `src/pixaac/preview.py:140` and `src/pixaac/preview.py:188`.

**Next fix:** route on the parsed URL path and add a regression check for the
exact URL format printed by the CLI. Meanwhile, open `/` and select the sprite
from the dropdown. This matters because the README's first preview command
uses `--sprite`.

## Honest assessment of the art and authoring experience

The fox has a clear silhouette, the potions form a consistent icon family, and
the shop has a readable warm/cool palette. These are useful prototype assets.
The scene is still visibly built from simple geometry, and the animation is
mostly a one-pixel translation plus a blink. I would give the poses and lighting
another art pass before presenting this as a polished game asset pack.

Those visual limitations are mostly my drawing choices, not rendering defects.
For example, reusing the same palette keys for fur and lantern light also
recolors the lantern in the arctic variant. Separate material roles would avoid
that coupling; it does not require a new engine feature.

I had to inspect an image, reason back to coordinates, change the script, and
render again. That is workable but laborious for small facial adjustments.
The preview implementation exposes zoom and frame controls, but no coordinate
readout, pixel grid, or onion-skin view.

After fixing the URL, my next priorities would be:

1. Cursor pixel coordinates and an optional grid for precise edits.
2. Onion-skinning for comparing adjacent poses and spotting unwanted jumps.
3. Side-by-side palette/pose comparison for the asset-family workflow.

I would defer a richer component hierarchy until a concrete example needs it.
The small grouped-shift helper already solved the immediate animation problem.

## Scope of verification

The trial's scratch reproduction script and machine-readable results are
`out/moonlit-market/check_trial.py` and `checks.json`. The script checks export
round trips, watcher recovery, and HTTP responses. It is trial evidence rather
than a new permanent test suite.

I visually inspected the contact sheet and all four fox poses. No browser was
available through the browser runtime, so I did not verify interactive
play/pause, stepping, checkerboard rendering, or refresh behavior in a browser.
Animation comparisons used decoded image frames and metadata. I did not rerun
the repository's full test suite or modify the SDK.
