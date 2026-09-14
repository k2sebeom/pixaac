# Release checks

Run from a checkout with Python 3.12+ and Node.js 22+:

```sh
uv sync --locked
uv run pytest -q
uv build
uv run --isolated --no-project --with dist/pixaac-0.1.0-py3-none-any.whl \
  python -I scripts/smoke_installed.py
uv run python assets/tideglass/build.py
```

Use the current version's wheel path if the package version changes. The smoke
check rejects source-tree imports and verifies that the installed package
contains the preview HTML and JavaScript, can build preview assets in its worker,
serves the query-string URL, and can compose/export/reimport sprites.

The `Checks` workflow runs the suite and installed-wheel smoke check on Python
3.12, 3.13, and 3.14 with Node 22. A locally passing run is not evidence that
the hosted matrix passed; check its results before releasing.

Inspect `assets/tideglass/generated/review.png` and `poses.png`, then run:

```sh
uv run python -m pixaac.preview assets/tideglass/build.py --sprite station
```

In a connected browser:

1. Follow the exact printed URL; verify station selection and a missing-name
   fallback.
2. Play, pause, and step; check the boat's motion and beacon timing through the
   loop boundary. Inspect the smaller sprites at native and enlarged scales.
3. Check cursor coordinates at canvas corners, after scrolling, and after
   switching asset sizes. Verify grid alignment.
4. Compare lighthouse and storm-beacon, and compare poses of the same sprite.
   Test previous/next overlays, opacity, and one-shot boundaries using the
   Moonlit Market reverse-reaction tag.
5. Edit the Python source, confirm visible refresh, introduce an error, verify
   the last successful art remains visible, then correct it and confirm recovery.

These checks exercise actual browser rendering beyond the DOM-adapter tests.
The [2026-09-14 browser-use pass](browser-feedback.md) completed them in Chrome
152, including a narrow-screen layout fix. To repeat the Tideglass UI checks
with browser-use, start its preview on port 8876 and pass the absolute path to
`scripts/verify_preview_browser.js` as `filename` to `browser_run_code_unsafe`.
Source-error recovery and the Moonlit Market walkthrough are documented in the
feedback log. Repeat these checks when the relevant behavior changes.

For delivery to a game, import the PNG plus its JSON frame rectangles together.
Use native-resolution assets with the intended sampler; inspect edges and frame
transitions in that engine. `extrude` duplicates outer texels without trimming
transparent margins. GIF is a review format with binary alpha and 10 ms timing
units; APNG or PNG sheets retain full RGBA fidelity.

Record the result in `IMPROVEMENTS.md` and the current trial feedback log.
Release only after the automated checks and applicable visual checks pass.
