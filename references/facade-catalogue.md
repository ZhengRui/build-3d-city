# Facade catalogue

Every facade feature and pattern the shared viewer draws, with its settings, the presets and styles that use it, and
where to see it. Start a new city here: pick the nearest viewer preset (§1), list the region's building types, and map
each to the features below; add a library pattern (§4) only for what none of them draws.

How it fits together (`engine/viewer/`): the pipeline's regional preset (`presets/<preset>.toml`) assigns each building
a style name, packed into the tiles (`tiles.json` lists them); the viewer preset of the same name
(`styles/<preset>.json`) says what each style looks like; `styles.js` resolves it for the city (preset, then city.json
`facade.styles`, `facade.acUnits`, `night.homeStyles`); `facade.js` builds the facade shader from only the features the
city's styles list (`facade/core.js`, the core; `facade/patterns.js`, the pattern library; `facade/roofs.js`, roofs).
A test (`engine/pipeline/tests/test_viewer_presets.py`) checks that every style a pipeline preset can assign has viewer
data.

**Seeing a feature.** Text first: every entry names a preset view where the feature is on screen, opened as
`demos/<city>/web/?view=<name>` (or `?at=x,z,distance,elevation,azimuth` for any spot, scene metres and degrees;
`&time=21.5` for night). The view names are the reference project's (their `city.json` files are in `../examples/`);
screenshots are kept out of git. `scripts/facade-ref.sh` takes a reference set (each city's standard views, day and
night, both backends) and `scripts/pixdiff.mjs` diffs a later tree against it.

(The views named under "where to see" are where a style is common by the pipeline's rules; the street views and
the reference set's views were looked at, the rest not each checked by eye.)

**Cost classes.** *const*: a per-style constant (a select chain over the style id, or one constant when all users
agree); *mask*: a few band/stripe terms per wall pixel; *branch*: drawn inside a branch only its walls pay for (the
wall-detail slots, the near detail, a pattern's own `If`).

## 1. The viewer presets

| preset | base | styles (own) | the pipeline preset | city |
|---|---|---|---|---|
| `china-south` | — | glass, residential, village, factory, commercial, civic, plain, fins, bands, lattice, honeycomb, panel | china-south | Shenzhen (the default when city.json names none) |
| `us-northeast` | china-south | brownstone, brick, stone, crowned (extends stone), castiron, signs, spire, piers, floodlit | us-northeast | New York |
| `europe-west` | us-northeast | haussmann, faubourg, house, limestone, brickstone, hbm, postwar, modern, concretepanel, shed, monument | europe-west | Paris |
| `uk-london` | europe-west | georgian, stucco, victorian, mansion, portland, estate, warehouse, modern (London's) | uk-london (base europe-west, styles replaced) | London |
| `de-berlin` | europe-west | altbau, althof, nachkrieg, platte, kma, hansa, neubau, beton, sandstein, klinker, kirche | de-berlin (base europe-west, styles replaced) | Berlin |
| `hk-hongkong` | china-south | estate, apartment, tonglau, composite, industrial, colonial (glass, commercial, village with Hong Kong's palettes) | hk-hongkong (base china-south, osm_style replaced; kinds per building) | Hong Kong |
| `sg-singapore` | china-south | hdb, streamline, carpark, shophouse, granite, colonial, condo, villa, temple, worship (glass, fins, bands palettes changed; facade options: grey-blue factory roofs, coated glass, farFade) | sg-singapore (base china-south, osm_style replaced) | Singapore |
| `jp-tokyo` | china-south | zakkyo, tiled, mansion, granite, depato, wooden, temple, government, signs; civic changed; facade options (shopfront boards with letters) | jp-tokyo (base china-south, styles replaced) | Tokyo |

**Precedence of facade options** (`styles.js` `facadeOptions`, tested by `test_facade_options_precedence`): engine default < viewer
preset (`styles/<preset>.json`, its `facade` options) < city.json `facade`. A key the engine has a default for is
still overridden by the preset (Singapore's `roofs.blueSteel` 0.2 once never applied because the defaults were
merged into city.json's section first). To confirm a value took effect, read the resolved options in the page:
`__viewer.facadeArgs.facadeStyles.facade` (console, or `scripts/cdp.mjs eval`).

A preset's `base` brings every style of the chain (the pipeline's `replace` drops them on its side: only the names in
tiles.json are ever used, so the extras cost nothing). A preset may set facade options under city.json's
(`facade`: `windowF0`, `shopfront`, `roofs`). City changes: `facade.styles` in city.json, key by key
(`{"modern": {"bay": 2.9}}`; `null` or `false` turns a feature off for that style). Details and the format:
`engine/viewer/styles/README.md`.

## 2. Style basics (every style)

| key | default | what | cost |
|---|---|---|---|
| `bay` | 3.0 m | bay width (each building 0.85-1.2 x by its seed; a landmark row's module wins) | const |
| `window` | [0.5, 0.5, 0.5] | the window box [xlo, ylo, yhi] in fractions of a bay and a floor (null: default); 0.5 = no windows | const |
| `shops` | 0 | a share of buildings with a ground-floor shopfront (by the city's `shopSeed`, else the seed's hash), or `"all"`; `shopsBy: "hash"` always by the hash (New York's walk-ups 0.6) | const |
| `ac` | 0 | share of windows with an air conditioner under them (china-south: village 0.45, residential 0.28; city.json `facade.acUnits`) | const |
| `frames` | dark 0.45, light [0.62, 0.62, 0.6] | the share of dark frames and the light ones' colour (London's sashes 0.08, white; warehouses 0.85; Berlin 0.12) | const |
| `masonry` | — | punched windows under a cornice (masonry under 60 m; `cornice.maxHeight` 100 on New York's stone) | mask |
| `cornice` | dark, x1 | `colour` light / mix (London: stone over brick) / dark; `scale` (limestone 1.6, London's terraces 1.45, Berlin's Altbau 1.5); `maxHeight`; `parapet` light / dark and `balustrade` (share) above it (London) | mask |
| `mottle` | — | brick (0.12) or stone (0.05) course mottle close up | mask |
| `balconies` | — | projecting balconies with railings on a third of the columns (residential, postwar, modern, nachkrieg, hansa) | mask |
| `stoneBase` | — | a lighter or darker stone base, 1-2 floors, on 55 % (New York's brick and stone) | mask |
| `windowStrips` | — | windows in vertical strips between piers, dark recessed spandrels, on 60 % (stone) | mask |
| `night` | civic | after dark: `home` (warm two-window flats, the homes' hour), `village`, `mall`, `factory`, `none`; curtain walls are offices | const |
| `zone` | 2 | an office's lit zone in bays (`"office"`: city.json `night.windows.zone` or 7) | const |
| `glazing` | — | window bars: `sash` (six over six, meeting rail), `casement` (two lights under a transom), `kasten` (Kastenfenster: meeting stile and transom, nets and drapes), `stile` (post-war: a stile at two thirds), `office` (stile, no curtains) | branch |
| `reveals` | — | the masonry's depth: a shaded strip inside each opening (London) | branch |
| `roof` | — | `flat` (gravel/bitumen tops, no zinc seams), `dormers: "every"` (a dormer per bay), `metal: "slate"` (slate on the brisis) | const |
| `parapet` | none | rooftops.js parapets: `village`, `block`, `low` (Paris's acrotères), `glass`, `factory` | — |
| `pattern`, `cell` | — | landmark skins: `lattice`, `honeycomb`, `panel`; cell size m | branch |
| `extends` | — | another style's data where this one has none (crowned: stone) | — |
| `fade` | none | the wall-detail slot (§3): none (on the wall), `none` (a branch over the whole wall), `bays` (a branch faded with the bays) | — |
| (`facade.farFade`) | [0.12, 0.35] | a facade option: where the window grid starts and ends fading to its mean (bays or floors a pixel; Singapore [0.03, 0.12]: the HDB and condo grids sparkled at mid distance) | const |

Where: Shenzhen *Xixiang old town* (villages, AC units), *Futian CBD* (glass); New York *Midtown* (stone, window
strips, cornices), *Times Square (street level)*; Paris *Avenue de l'Opéra (street level)* (frames, shops); London
*Ludgate Hill (street level)* (sashes, reveals); Berlin *Oranienstraße (street level)* (Kastenfenster, curtains).

## 3. Core features (`facade/core.js`, keys in the style data)

Each is built only when one of the city's styles lists it; the slot (`fade`) decides where its layer goes: on the wall
itself (Paris's), in the `none` branch (London's) or the `bays` branch (Berlin's), each slot in a fixed order (written
in facade.js). Shares are `{share, hash}` (under the share by the seed's hash k) or `{stripped, hash}` (that share left out).

| key | settings (preset values) | styles | where to see | cost |
|---|---|---|---|---|
| `rustication` | `rows` (2: ground floor and entresol), `groove` m (0.45 Paris, 0.42 London, Berlin), `joint` (0.1, 0.09), `depth` (0.3, 0.22), `notShops`, `on` (`stuccoGround` / `stucco`: only those buildings) | haussmann; georgian, stucco, portland; altbau, sandstein | Paris *Avenue de l'Opéra (street level)*; London *Ludgate Hill (street level)*; Berlin *Oranienstraße (street level)* | mask |
| `balconyRows` | `rows` ([2, 5] Haussmann; [1] London), `share` + `hash` (stucco 0.7, georgian 0.3), `shadow` (0.4 on the row below) | haussmann; stucco, georgian | Paris *Avenue de l'Opéra (street level)* | mask + near |
| `guardRails` | `from` (2: rails across the French windows from the 2nd floor) | haussmann, limestone | Paris *Avenue de l'Opéra (street level)* | mask + near |
| `shutters` | (on 70 %, 30 % over 15 m; 20 % closed; five colours) | faubourg, house | Paris *Marais*, *Latin Quarter* | mask + near |
| `floorBands` | `stone` or `concrete` bands at each floor | brickstone, hbm | Paris *Marais* (Place des Vosges) | mask |
| `surrounds`, `quoins` | stone window surrounds; quoins at the run's ends | brickstone | Paris *Marais* | mask |
| `panelSpandrels` | dark spandrels between piers on 55 % | concretepanel | Paris *Montparnasse* | mask |
| `stuccoGround` | `share`, `hash` (53.1), `paint` (recoloured: georgian 45 %; stucco all) | georgian, stucco | London *Westminster* (Belgravia's terraces off it) | branch |
| `brickCourses` | mortar `colour`, `k` (London [0.36, 0.34, 0.31], 0.45; Berlin [0.42, 0.4, 0.36], 0.4): 75 mm beds, 225 mm heads | georgian, victorian, mansion, estate, warehouse; klinker, kirche | London *Shad Thames (street level)* | branch |
| `shopfront` | the preset's `facade.shopfront`: `box`, `doorEvery` (London 3), `tint` (London: the front a pale pilaster colour; a style's `shopfront.pilasters` mix), `boards` (band, colours per shop of two bays), `letters` (Berlin: names on the boards), `pilasters` (Berlin: light strips between shops), `riser`, `boardTop`, `bars` (transom, mullion), `interior` (`warm` London, `shelves` Berlin), `awnings` (Berlin 0.4) | all London and Berlin styles | London *Ludgate Hill (street level)*; Berlin *Oranienstraße (street level)* | branch |
| `stringCourse` | over the ground floor: `stone` or `self` (the wall a shade lighter) | georgian, victorian, mansion, portland, stucco | London *Ludgate Hill (street level)* | branch |
| `polychrome` | a red band over each row of windows and a pale sill band (share 0.7) | victorian | London *Shad Thames (street level)* surroundings | branch |
| `stoneBands`, `stoneGround` | stone sill and lintel bands; a stone ground floor (share 0.5) | mansion | London *Westminster* | branch |
| `decks` | deck-access balcony fronts on 60 %, concrete floor bands on the rest | estate | London *The City* (the Barbican's estates) | branch |
| `corniceShadow` | `depth` (0.3 m), `k` (0.4); Berlin's is the Gründerzeit profile's (0.45) | London's masonry; gruenderzeit | London *St Paul's Cathedral* | branch |
| `windowBars` (glazing) | `sash` / `casement` (V.sash), `kasten` / `stile` (stile at 0.5 / 0.64, transom); shop windows' `bars` | see `glazing` | London *Ludgate Hill (street level)*; Berlin *Oranienstraße (street level)* | near branch |
| `reveals` | (a strip 0.05 / 0.06 of the opening) | London's masonry | London *Ludgate Hill (street level)* | near branch |
| roofs (`facade/roofs.js`) | city.json `facade.roofs`: `tones`, `blueSteel` (`blueTone`: its colour, linear; Singapore's grey-blue), `zinc`, `tile`, `tileAge`, `flatTops`, `variety`, `slate` (London: slate on every pitched roof, coursed); style `roof` | all | Paris *Roofs of the 9e*; London *The City*; Berlin *Kreuzberg* | const + mask |

## 4. The pattern library (`facade/patterns.js`, named by architecture)

| pattern (key) | what | styles | where to see | cost |
|---|---|---|---|---|
| `gruenderzeitProfile`, `gruenderzeitSurrounds` (`gruenderzeit`, with `stucco`, `stringCourses`) | Gründerzeit stucco: string courses at every floor with their shadow, the cornice's shadow and profile (consoles, soffit, dentils, corona; a plain eave on stripped fronts, 22 %), surrounds, hoods, a pediment over the Beletage, sills | altbau, kma, sandstein | Berlin *Oranienstraße (street level)*, *Kreuzberg* | branch |
| `frenchBalcony` (`frenchBalconies`) | a stucco slab at the French door's foot, middle bay or outer two; its iron railing in the near detail | altbau | Berlin *Oranienstraße (street level)* | branch |
| `pilasterStrips` (`pilasters: {every}`) | pilasters every n bays | sandstein (2), kma (3) | Berlin *Karl-Marx-Allee*, *Unter den Linden (street level)* | branch |
| `frieze` (`frieze`) | a frieze with a running motif under the cornice | kma, sandstein | Berlin *Karl-Marx-Allee* | branch |
| `ceramicTiles` (`ceramicTiles`) | glazed tiles 0.32 x 0.24 m, each its own shade, over a joint grid | kma | Berlin *Karl-Marx-Allee* | branch |
| `plattenbau` (`plattenbau`) | panel joints, loggia columns with coloured fronts, a darker plinth | platte | Berlin *Friedrichshain* | branch |
| `slabEdges` (`slabEdges`) | white slab edges at every floor, coloured balcony panels | hansa | Berlin *City West and the Zoo* (Hansaviertel north of the Tiergarten) | branch |
| `stoneJoints` (`stoneJoints`) | ashlar joints, three slabs a bay, a recessed top floor on 40 % | neubau | Berlin *Mitte* | branch |
| `precastJoints` (`precast`) | lighter spandrel bands, joints at the bays | beton | Berlin *Alexanderplatz* | branch |
| `buttresses` (`buttresses`) | buttresses at each bay's edge | kirche | Berlin *Gendarmenmarkt* (and the churches) | branch |
| `pillaredPorch` (`porch`) | a pale porch with two columns, the door and fanlight, one bay in three | stucco | London *Hyde Park* (Belgravia, Bayswater) | branch |
| `loadingDoors` (`loadingDoors`) | a column of timber doors one bay in three with iron platforms (share 0.85) | warehouse | London *Shad Thames (street level)* | branch |
| `tiledBands` (`tileBands`) | a tiled band facade: 227 x 60 mm tile joints close up, spandrels in a second tile tone on half, a light slab edge at every floor and its shadow | tiled (jp-tokyo) | Tokyo *Ginza Chuo-dori (street level)*, *Akihabara Chuo-dori (street level)* | branch |
| `balconyRails` (`balconyRails`) | apartment balconies on every floor above the ground: frosted-glass, solid or barred railing panels, the slab edge, partition boards every two bays, the shade under the balcony above; the sliding doors are the window box (ylo 0.4) | mansion (jp-tokyo) | Tokyo *Tsukishima and Harumi* | branch |
| `timberFrame` (`timberFrame`) | timber posts at the bays' edges, tie beams under the eaves and over the ground floor, plaster between (vermilion walls keep their colour) | temple (jp-tokyo) | Tokyo *Asakusa and the Skytree* | branch |
| `lapSiding` (`lapSiding`) | siding boards every 0.2 m (or mortar's trowel lines every 0.6 m), a small eave over the ground floor's openings | wooden (jp-tokyo) | Tokyo *Asakusa and the Skytree* | branch |
| `signboardStack` (`signboards`; facade.js lays it over the finished wall) | vertical signboards (袖看板) at one end of a 3-16 m front: a box per floor in its own colour with a column of glyphs, or one tall board; box-filtered (far: a coloured strip), windows behind it hidden, lit after dark | zakkyo (jp-tokyo) | Tokyo *Akihabara Chuo-dori (street level)* | mask |
| `estateAccents` (`estateAccents`) | public housing blocks: a colour accent per block (salmon, teal, orange, blue, green, yellow, lilac, red) on the runs' end bays or every 3-5 bays and a crown band over the top two floors, slab edges, a grey ground floor | estate | Hong Kong *Wong Tai Sin estates* | branch |
| `bayWindows` (`bayWindows`) | tiled towers' projecting bay windows: a lit ledge and its shadow, lit and shaded cheeks, a soffit (on 80 %); 0.3 m tile joints close up | apartment | Hong Kong *Nathan Road (street level)*, *The Peak over Mid-Levels (hillside)* | branch |
| `shophouseBalconies` (`shophouseBalconies`) | tong lau and walk-ups: a balcony at every floor (open with a painted parapet, caged in iron bars, or glazed in), the slab's edge and shadow, soot streaks, first-floor signboards with lines of characters on three in five fronts | tonglau, composite | Hong Kong *Apliu Street, Sham Shui Po (street level)*, *Fa Yuen Street, Mong Kok (street level)* | branch |
| `ribbonSpandrels` (`ribbonSpandrels`) | flatted factories: lighter concrete spandrel bands between ribbon windows, rain streaks, ribbed roller shutters on the ground floor one bay in two | industrial | Hong Kong *Kwun Tong industrial* | branch |
| `verandahArcade` (`verandahArcade`) | colonial verandahs: piers at the bays' edges, the dark verandah under a round arch on the ground floor, a flat lintel on the first | colonial | Hong Kong *Central and Admiralty from the harbour* (the Court of Final Appeal, close up) | branch |
| `tiledWall` (`tiledWall`) | a windowless wall in square ceramic tiles (0.3 m, each its own shade) over a paler joint grid, a darker plinth and a rain-darkened foot | Hong Kong `tiled` (the Cultural Centre's figure) | Hong Kong *Clock Tower and Cultural Centre* | branch |
| lived-in windows (`livedInWindows`, facade.js near detail) | per window: curtains drawn part way, slatted blinds, one sash slid open (dark, no glass), a window air conditioner in the lower part, iron grilles over some flats' windows; a meeting stile down every window | Hong Kong estate, apartment, tonglau, composite | Hong Kong *Apliu Street*, *Nathan Road* (street level) | near branch |
| `paintBands` (`paintBands`) | accent paint over an off-white block: a band over the top floor or two (3 in 5), the ends of runs over 12 m (half), a band every 4-6 floors (a third); nine colours (terracotta, ochre, teal, blue, green, maroon, orange, mauve, sand) | hdb | Singapore *Chinatown and Pinnacle* (Everton Park, Pearl's Hill), *Keppel Bay and HarbourFront* (Telok Blangah) | mask (on the wall) |
| `corridorAccess` (`corridors`) | a corridor-access slab's open corridor face: per floor a parapet with a lit lip, the corridor's shade, the flats' doors and kitchen windows, the slab edge; on runs over 14 m whose normal leans to the block's own direction (about one long side); no windows of its own | hdb | as paintBands | mask (on the wall) |
| `voidDeck` (`voidDeck`) | an open ground floor (blocks over 20 m): columns every two bays and at the run's ends, a beam, the shade between them; no windows | hdb | as paintBands, street level | mask (on the wall) |
| `fiveFootWay` (`fiveFootWay`) | a shophouse row's arcade on the ground floor: piers at the run's ends (the party walls) and every ~4.2 m, lit on one side, the walkway's shade (darkest under the floor above), the shop front at its back (dark, lit, shuttered), the kerb, a signboard on the fascia on 3 in 5; no windows | shophouse | Singapore *Chinatown (street level)*, *Kampong Glam and Bugis*, *Boat Quay (across the river)* | mask (on the wall) |
| `shophouseFront` (`shophouseFront`) | a shophouse's upper floors: paired louvred timber shutters, each leaf half the window wide and the window's height, folded open beside it or closed over it (a third; the core leaves those windows out), each front its own colour; pilasters at the run's ends with their shadow, a sill band at each floor | shophouse | Singapore *Chinatown (street level)*, *Sultan Mosque* (Kampong Glam's rows) | mask (on the wall) |
| `colonnade` (`colonnade`) | columns at every bay's edge through the floors under the cornice, lit on one side, their shadow beside them, the verandah's wall a shade deeper | colonial | Singapore *Civic District* | mask (on the wall) |
| `balconySlabs` (`balconySlabs`) | white slab edges at every floor from the first | condo | Singapore *Singapore River* (Robertson Quay), *Kallang Basin and the Sports Hub* (Tanjong Rhu) | mask (on the wall) |
| fire escapes (`fireEscape`; facade.js) | iron platforms, railings and ladders across two middle bays from the 2nd floor (45 %) | brick | New York *Midtown*, *Lower Manhattan* | mask |
| billboards (`billboards`; billboards.js) | boards in rows from the atlas to 26-58 m, LED screens at night | signs | New York *Times Square (street level)* | mask |
| monument (`monument`; facade.js) | by the landmark row's parameter: arcade, palace, gothic (+ perpendicular), blank (+ peristyle, slots), steel frame | monument (landmark rows) | Paris *Opéra Garnier*, *Notre-Dame*, *Centre Pompidou*; London *Big Ben and Parliament* | branch |
| landmark skins (`pattern`) | steel lattice, honeycomb, metal panels | lattice, honeycomb, panel | Paris *Louvre and Tuileries* (the pyramid); Shenzhen *Spring Cocoon* | branch |
| curtain walls (glass, fins, bands, piers) | mullions, spandrels, refuge floors, coated glass, the city probe's reflection; `facade.glass` | glass, fins, bands, piers | Shenzhen *Ping An Finance Center*; New York *111 West 57th Street (Steinway Tower)* (piers) | branch |

A new pattern: a function in facade/patterns.js taking the branch's copies (V), named by what it draws, a key in the
style data, built in facade.js only when a style lists the key; document it here. A pattern that must read from the air
(Singapore's six) goes on the wall itself instead of a branch: it takes the facade's own nodes, box-filters every edge
(`stripe`) so it averages out far away, and may take the wall's windows away (`noOpen` in facade.js: the corridor face, the
void deck, the five-foot way paint their own openings); it costs every wall of the city a few band terms (mask).

## 5. A new city

1. Pick the pipeline preset and the viewer preset of the same name (or a new pair with `base` on the nearest); set
   city.json `facade.preset`.
2. List the region's building types (`references/porting-checklist.md`, facades) and map each to a style with the
   basics (§2) and the core features (§3); a type none of them draws gets a library pattern (§4).
3. Check: `node scripts/pixdiff.mjs shoot` a view or two, `pytest tests/test_viewer_presets.py`, and the speed test.

## 6. The leaks (styles shared through a preset chain)

A style one city added reaches every city whose preset builds on it, through landmark rows that name it. When the
facade core was split into features, each such leak was listed and decided one by one; the reference project
removed one (Berlin's `house` loses Paris's shutters: de-berlin `"house": {"shutters": false}`) and kept the rest as
intentional (the trim fits St Pancras and the Rotes Rathaus, the panel spandrels fit the slab towers, the limestone
details barely show, London's modern blocks suit Paris's balconies). Do the same review when a new preset builds on
an old one.

Paris's europe-west data reaches London and Berlin through their landmark rows: Berlin's `house` (the Nikolaiviertel)
keeps Paris's shutters; `brickstone` (Rotes Rathaus, St Pancras, Westminster Cathedral's campanile) its floor bands,
surrounds, quoins, slate roofs, dormers and home lighting; `concretepanel` (Haus des Reisens, Centre Point, the Barbican
towers) its dark panel spandrels, Paris's low parapets and home lighting; `limestone` (Neues Museum, Pergamonmuseum, BBC
Broadcasting House) its guard rails, a 1.6 x cornice and dormers.
