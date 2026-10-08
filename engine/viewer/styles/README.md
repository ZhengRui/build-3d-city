# Viewer style presets

What each facade style looks like, per region: one JSON file per preset, the same names as the pipeline's regional
presets (`engine/pipeline/src/city3d/presets/<preset>.toml`, which assign the styles). Read by `../styles.js`; drawn by
`../facade.js` with `../facade/core.js` (core features), `../facade/patterns.js` (the pattern library) and
`../facade/roofs.js`. Every key, its settings, the styles that use it and where to see it:
`references/facade-catalogue.md` in the skill.

## Base chain

```
china-south  (root: glass, residential, village, factory, commercial, civic, plain, fins, bands, lattice, honeycomb, panel)
├─ us-northeast  (+ brownstone, brick, stone, crowned, castiron, signs, spire, piers, floodlit)
│  └─ europe-west  (+ haussmann, faubourg, house, limestone, brickstone, hbm, postwar, modern, concretepanel, shed, monument)
│     ├─ uk-london  (+ georgian, stucco, victorian, mansion, portland, estate, warehouse; modern changed; facade options)
│     └─ de-berlin  (+ altbau, althof, nachkrieg, platte, kma, hansa, neubau, beton, sandstein, klinker, kirche; options)
└─ hk-hongkong  (+ estate, apartment, tonglau, composite, industrial, colonial; shop signboards; options)
├─ sg-singapore  (+ hdb, streamline, carpark, shophouse, granite, colonial, condo, villa, temple, worship; facade options: tile roofs, roofs, glass, farFade)
└─ us-northeast  (+ brownstone, brick, stone, crowned, castiron, signs, spire, piers, floodlit)
   └─ europe-west  (+ haussmann, faubourg, house, limestone, brickstone, hbm, postwar, modern, concretepanel, shed, monument)
      ├─ uk-london  (+ georgian, stucco, victorian, mansion, portland, estate, warehouse; modern changed; facade options)
      └─ de-berlin  (+ altbau, althof, nachkrieg, platte, kma, hansa, neubau, beton, sandstein, klinker, kirche; options)
├─ hk-hongkong  (+ estate, apartment, tonglau, composite, industrial, colonial; shop signboards; options)
└─ jp-tokyo  (+ zakkyo, tiled, mansion, granite, depato, wooden, temple, government, signs; civic changed; options)
```

`engine/pipeline/tests/test_viewer_presets.py` checks that each viewer preset describes every style its pipeline preset
can assign, and that every `extends` resolves.

## Format

```json
{
  "notes": "what the region's styles are; the leaks kept from the base",
  "base": "europe-west",
  "replace": [],
  "facade": { "windowF0": 0.08, "shopfront": { ... }, "roofs": { "slate": true } },
  "styles": { "georgian": { "bay": 2.0, "window": [0.25, 0.14, 0.8], "rustication": { ... }, ... } }
}
```

- `base`: the preset this one builds on; its styles merge under these key by key (objects all the way down, arrays and
  plain values replace). `replace`: top-level keys taken whole from this file instead.
- `facade`: facade options under city.json's `facade` (city.json wins): `windowF0` (plain windows' reflectance head on,
  0.05), `shopfront` (the ground floor's shops: `box`, `doorEvery`, `tint`, `boards`, `letters`, `pilasters`, `riser`,
  `boardTop`, `bars`, `interior`, `awnings`), `roofs` (`slate` and city.json's `tones`, `zinc`, `tile`...), `bayFade`
  (`[from, to]`: the `fade: "bays"` detail branch fades out as a bay shrinks from `from` to `to` (the bay's
  fwidth measure) (default `[0.12, 0.35]`; jp-tokyo `[0.08, 0.24]`: the branch's cost off more walls), `billboardBranch` (true: the
  `billboards` boards built in a branch only the signs walls pay for; default false, every wall computes them: jp-tokyo).
- `styles`: per style name, the keys of the catalogue (§2-4): basics (`bay`, `window`, `shops`, `ac`, `frames`,
  `masonry`, `cornice`, `mottle`, `night`, `zone`, `glazing`, `roof`, `parapet`, `extends`, `fade`...), core features
  (`rustication`, `balconyRows`, `brickCourses`, `shopfront`, `corniceShadow`...) and patterns (`gruenderzeit`,
  `plattenbau`, `ceramicTiles`...). A key left out is not used; a number left out takes facade.js's default.

A city picks its preset in city.json (`facade.preset`, default `china-south`) and changes any style without a re-pack
(`facade.styles`: `{"modern": {"bay": 2.9}}`; `null` or `false` turns a feature off). The older city.json keys are still
read: `facade.acUnits` (a style's `ac`), `night.homeStyles` (`night: "home"`). `?facadelog=1` prints the resolved
preset chain and each feature's users.
