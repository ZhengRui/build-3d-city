# three.js 0.186.1, the files the viewer imports

A copy of the files of the npm package `three@0.186.1` that the viewer loads (`build/three.webgpu.js`,
`build/three.core.js`, `build/three.tsl.js` and the add-ons under `examples/jsm/` that `main.js` imports, with their
own imports), byte for byte as published, fetched on 2 October 2026 from
`https://cdn.jsdelivr.net/npm/three@0.186.1/<path>` (jsDelivr serves the npm package's files). Licence: MIT,
`LICENSE` here (Copyright 2010-2026 three.js authors).

Used instead of the CDN when a city's `city.json` says `"three": "local"`, or for one load with `?three=local`
(`?three=cdn` the other way round); see `index.html`. London M9: from the CDN the modules took 2.6-3 s of a load
at 80 Mbit/s and 8-18 s on a slow evening; from next to the page they come with the city's first files.

When the viewer moves to another three.js version, change the version in `index.html` (both places) and fetch
the same list again into a new folder `vendor/three@<version>/`.
