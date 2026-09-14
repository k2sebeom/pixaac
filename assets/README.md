# Artwork

This directory is the single home for PixaaC's art sources, showcase images,
generated exports, compatibility fixture, and browser screenshots.

| Collection | Source | Purpose |
| --- | --- | --- |
| Moonlit Market | [build.py](moonlit_market/build.py) | Fox variants, potions, and an animated apothecary |
| Tideglass | [build.py](tideglass/build.py) | Coastal scene, lighthouses, and cutter |
| Robot | [build.py](robot/build.py) | Additional SDK drawing and animation example |
| Courier | [build.py](courier/build.py) | Independent layers and grouped movement |

From the repository root, with PixaaC installed:

```sh
python assets/moonlit_market/build.py
python -m pixaac.preview assets/moonlit_market/build.py --sprite fox
python assets/tideglass/build.py
python -m assets.build_showcase
```

Each builder writes to its adjacent `generated/` folder by default. An explicit
output-directory argument overrides that location. Generated exports are ignored
by Git and by the preview watcher; regenerate them instead of committing copies.
README snippets write exploratory exports to the shared `assets/generated/`.

`showcase/` contains the small, tracked set of images used by documentation.
`python -m assets.build_showcase` refreshes those images and the full exports for
Moonlit Market and Tideglass. Showcase files are intentionally retained in Git
so documentation displays without running Python.

`screenshots/` contains the two browser verification images linked from the
feedback notes. These require a browser pass to refresh. `fixtures/hero.sprite.json`
is retained for legacy document compatibility tests.

Obsolete mechanic studies, unused snapshots, superseded robot README images,
duplicate output folders, and scratch trial artifacts have been removed.
Historical findings remain in `docs/`; durable regression checks live in `tests/`.
