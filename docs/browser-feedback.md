# Browser-use verification — 2026-09-14

Resumed the Tideglass feedback loop using the browser-use MCP browser, as
requested. The local preview is served on port 8876. This supersedes the
earlier browser-unavailable limitation.

## Findings before fixes

- The printed query-string URL selects `station`. Stepping, play/pause,
  comparison pose retention during playback, and both onion overlays work.
- Native `(0, 0)` and `(159, 95)` coordinates are correct at 1×, 2×, 4×, 8×,
  12×, and 16×, including after scrolling. Switching to the 32×24 cutter
  correctly reports `(31, 23)`. Leaving the stage clears the readout.
- Computed grid spacing matches every zoom; 1× suppresses interior lines.
- **Confirmed layout bug:** at a 390 px viewport, comparison controls expand
  the document to 430 px. Two narrow panes leave little room for artwork and
  the comparison selector overflows its pane. Stack comparison panes on narrow
  screens and allow selectors to shrink inside their labels.
- **Console noise:** the browser requests `/favicon.ico`, which returns 404.
  Supply an inline icon so a clean preview does not begin with a failed request.

The initial screenshot is `out/browser-checks/mobile-before.png`.
Rebuild/error recovery, animation boundary cases, and post-fix screenshots are
checked in the next pass.

## Fixes and completed verification

`preview.html` now stacks comparison panes at viewport widths up to 650 px,
allows selectors to shrink inside their labels, and supplies an inline favicon.
At 390 px, document width is now exactly 390 px. The repeatable browser check
also passes at 320, 650, 651, and 1280 px, with desktop panes aligned at the top.
See the [corrected mobile layout](images/preview-mobile.png) and
[desktop onion/comparison view](images/preview-onions.png).

Browser: Chrome 152, through browser-use MCP. Completed:

- All four canvas corners at every zoom (1×–16×), after horizontal/vertical
  scrolling; asset-size changes; pointer exit; native grid suppression;
  nearest-neighbor image rendering.
- Play/pause, stepping, comparison holding its pose during primary playback,
  visible pink/cyan onion filters, and adjustable opacity.
- Reverse one-shot start/middle/end, disabled boundary buttons, restart after
  completion, automatic stopping, pingpong looping, and no redundant skins
  for single-frame potion assets.
- The Moonlit Market inspection walkthrough: both fox lanterns at `(5, 31)`
  read `#ffd28a`, cores at `(6, 31)` read `#fff0c9`, and fur colors differ.
  Pointer readouts match at 8× and 16×. Editing eye pixel `(13, 15)` in the
  temporary source changed that exact displayed pixel while retaining grid
  and coordinates.
- Imported-module palette edits update the visible image. A deliberate syntax
  error displays its traceback while both panes retain their exact last-good
  images. Correction hides the error and resumes updates.
- Rebuilds retain zoom, grid, onion settings, comparison frames, and the second
  occurrence of a middle pose in a three-frame pingpong sequence. Removing a
  selected frame falls back to frame zero in both panes; removing the selected
  asset falls back in both panes with a notice.
- URL-encoded asset names containing spaces and `/` select correctly; initial
  missing-name URLs show the documented fallback. A fresh normal page load
  has **zero console errors or warnings**.

The temporary fixture is under `out/browser-checks/`; original artwork scripts
were not changed. Screenshots were visually inspected for sharp pixels,
checkerboard transparency, aligned overlays, and usable controls.

All **140 regression tests pass** after the fixes. The reusable browser-use
check is [scripts/verify_preview_browser.js](../scripts/verify_preview_browser.js);
pass its absolute path to `browser_run_code_unsafe` as `filename` while the
Tideglass server runs on port 8876. It expects the browser-use-provided Playwright
page and needs no added project dependencies.

This closes the browser verification gate for the tested Chrome environment.
Hosted CI results, other browser engines, and integration into a target game
are not established by this pass.
