# Buildings and landmarks

How building footprints, heights and facades were made trustworthy (first in Shenzhen, then in seven more
cities: the examples in `../examples/`), and how landmarks were researched and modelled. The code is `04_buildings.py` (table), `06_tiles.py` (`facade_styles`, `landmark_facades`,
`extrude`), `data/landmarks*.csv`, `data/landmark_facades.csv` and `data/landmark_facades.md`. For the pipeline
mechanics see `data-pipeline.md`.

## 1. Footprint and height quality: lessons

| Symptom seen in the viewer | Cause | Fix that worked |
|---|---|---|
| Urban-village blocks extruded as continuous walls ("these buildings are interconnected") | GBA footprints come from 3 m imagery, which can't see 1-2 m alleys | 0.5 m East Asia footprints for villages. Keep a compact GBA footprint only if it holds ≤ 3 East Asia pieces and isn't a blob of many small (< 150 m² median) pieces |
| Single buildings cut into 2-4 blocks of different heights ("it used to be perfect") | 0.5 m data over-splits multi-roof buildings, and each piece took its own CNBH/GBA height | OSM footprints first. OSM heights reach pieces by containment (≥ 50 % inside). Compact GBA before East Asia |
| Thin lower "lips" or skirts beside real buildings | East Asia is 4-8 m offset, and its duplicates were clipped rather than dropped | Align East Asia per 2 km cell (median offset against OSM). Drop a piece whole at ≥ 5 % overlap with a chosen footprint |
| Needles: tiny footprints at tower height | A tall GBA height transferred to kiosk-sized pieces next to a tower | Needle guard: GBA h ≥ 40 m only onto footprints ≥ 250 m² or covering ≥ 40 % of the GBA polygon |
| Towers missing or truncated over metro stations | OSM metro stations are `building=train_station` + `location=underground` / `layer<0`. They took GBA heights of 70-150 m and displaced the towers above them (826 buildings, 169 stations) | Drop underground and `layer<0` buildings on load |
| Airport terminal and stadium in fragments | The estate-outline rule (OSM polygons > 5,000 m² are compounds) caught them | Big OSM polygons count as one building when tagged terminal/stadium/hall/... or named |
| Buildings standing on carriageways, piercing viaducts | ML segmentation outlines toll booths, lorries and interchange decks | Road-clearance culling of non-OSM footprints (30 % major core, 60 % minor, 50 % under a deck, 55 % all roads combined) |
| Fixes only checked in 3 views; regressions elsewhere | Tuning by eye | `04b_quality.py` checks the whole city after every rebuild, with the worst 2 km cells listed. Tell the user which views you checked |
| Skyline wrong even though the average error looked fine | ML heights don't rank towers (GBA r = −0.03 for ≥ 60 m; CNBH saturates at about 40 m) | Hand-checked landmark height list overrides everything |

Other rules:

- **Choose the footprint source per building, never one dataset everywhere.** Each source is best somewhere.
- **Heights by band.** Measure every height source against OSM tags in 0-15, 15-30, 30-60 and 60+ m bands, and
  use each where it wins (CNBH blend only at 15-30 m).
- Keep `h_src` and `source` columns. Every odd building can then be traced ("which rule gave this height?").
- OSM `building:levels` × 3.2 m is a good height; Shenzhen floor-to-floor averages about 3.0-3.2 m residential and
  4.2-4.5 m office. A roof or `height` tag beats levels.
- Heights floored at 3.5 m; 3-storey default when nothing is known.
- Check for a coordinate offset between any non-OSM source and OSM (China's GCJ-02 would be 300-500 m).
- Large OSM polygons with no building-like tag are usually estates or compounds: don't extrude them.

- **A lidar-maximum height source (London's Carbon & Place) needs more than an OSM cross-check** (London M2 fix
  round, critic round 1): the top of a polygon whose mean is far under it is a steeple, floodlights, a crane or a
  neighbour's edge even with no OSM height to compare (`[buildings.spikes] alone_ratio`; churches get their mean
  × 1.2 for the nave and their spires back from the landmark pass); a large footprint over 2× its mean is a block
  of several heights, split along the source's polygons (`podium`); stadium stands are capped without a height tag.
- **Check that every OSM outline ends up in the table** (coverage ≥ 50 % by its own outline or its parts):
  London lost the National Gallery, Smithfield's market and 100 Bishopsgate's site because an untagged outline
  over `osm_max_area`, or one holding other OSM buildings, was dropped while its building:parts had no host left
  (`part_outlines`), and an estate outline's inner buildings went with it as its "duplicates" (`container_inner`).
- **`layer < 0` is not "underground"**: Victoria Station is `layer=-2 location=surface`; drop only
  `location=underground`, or untagged ones no lidar polygon covers (`surface_layers`).
- **Fill polygons over a river** (a lidar plot over a station on a bridge) extrude from the water: lift what lies
  over water to the deck (`water`), and clip pieces drawn twice in the same volume (`volume_dedupe`).
- **A CityGML LoD2 as the primary source (Berlin M2)** is more than buildings: ALKIS structures (canopies 51009_1610,
  memorials 51009_1750, stands, chimneys, towers) are solids too, and so are building roofs at the ground
  (underground garages at 0.5 m). Decide by function, height and area (`[buildings] rules`): canopies under 20 m²
  (balcony roofs) go, bigger ones are drawn as their roof (raised from under their eave: the Hauptbahnhof's hall
  23-31 m), flat structures under 2.5 m (terraces, pitches) go, a memorial's stelae keep their own 0.5-4.7 m (and must survive 06_tiles' 4 m² footprint cull: `[tiles] small_exact`; Berlin's 2,600 stelae of 2.4 m² were kept in the table and silently not drawn until the M10 critic asked for the memorial), the
  listed Stadtbahn viaduct (51009_1750 at 7-9 m) stays; what the rules drop must not come back from a 2D copy of the
  same footprints (the Umweltatlas) or OSM. Its parts (73,600 in Berlin) tile their building side by side from the
  ground: 15,000 under 12 m² and 24,000 under 3 m wide, which min_piece and the strip rule would drop, leaving gaps
  (`keep`). A few solids are wrong in shape, not only in height: the Fernsehturm is a 763 m² prism from the ground
  to 229 m round its shaft, a roofType 9999 solid is a whole complex at one generalised height (the Atrium Tower 55
  for 106): use OSM's parts for those few only (`parts_in`), never wholesale (OSM parts by levels are worse than the
  laser). Trust the LoD2's laser heights over the landmark list on completed buildings; the list sets only towers
  built since the scan (EDGE East Side, the Berlinian, Upbeat: `keep` them over the LoD2) and names the rest.

## 2. Facade style assignment

The facade shader switches on a style id; the order is `STYLES` in `06_tiles.py`, the same order as in
`web/facade.js`.

- **Generic styles** (nominal floor height, one wall colour per building picked from the palette by seed):
  - `glass` 4.2 m
  - `residential` 3.0 m
  - `village` 3.0 m
  - `factory` 5.0 m
  - `commercial` 4.8 m
  - `civic` 3.9 m
  - `plain` (plant rooms, no windows)
- **Landmark-only styles**:
  - `fins`: glass between stainless piers or fins
  - `bands`: glass with spandrel bands
  - `lattice`: diagonal steel lattice
  - `honeycomb`
  - `panel`: metal cladding, for halls
- The shader makes the height a whole number of floors: `floor = h / max(1, round(h / nominal))`.
- **A style made from another** takes the parent's data through `extends` in its viewer preset (styles.js,
  `engine/viewer/styles/<preset>.json`; New York: `crowned`, the stone towers with floodlit crowns, `"extends":
  "stone"`). Without it a style no preset describes takes every default: `crowned` had windows of no height, and the Empire State, Chrysler
  and 30 Rockefeller Plaza showed smooth beige walls by day and dark ones at night.

`facade_styles(b)` applies these rules in order; later rules win:

1. Default `residential`. By kind: podium → commercial, civic → civic, factory → factory, village or house →
   village, tower with h ≥ 150 → glass.
2. **Land use** decides what geometry can't. The use is taken at the building's representative point, the
   smallest containing polygon winning.
   - `commercial`: tall (≥ 40 m) → glass; lower non-village → commercial.
   - `industrial`: tall → glass (R&D towers in industrial parks); lower → factory.
   - `civic` and low → civic.
   - `residential` with kind tower, slab or midrise → residential.
3. An **explicit OSM tag** beats everything (`OSM_STYLE`):
   - office, hotel → glass
   - apartments, residential, dormitory → residential
   - house, terrace → village
   - industrial, warehouse, shed, hangar → factory
   - commercial, retail, mall → commercial
   - school, hospital, station, government, temple, church, stadium, museum → civic
4. Cleanups: commercial and ≥ 40 m → glass; village and ≥ 40 m → residential; a landmark with h ≥ 60 → glass.

**Why land use matters:** most footprints are satellite-derived and untagged, and most tall towers in Shenzhen
are apartments. Without land use every tower was glass or every tower was residential.

**A region's sub-preset** (London M4): a preset can name a `base` preset and `replace` whole tables of it
(`uk-london`: `base = "europe-west"`, `replace = ["facade.styles", "facade.osm_style"]`), so a second city of a
region gets its own styles without touching the first's (Paris's resolved config stays identical). With no
construction dates (London), style rules read the OSM tag, height, conservation-area names mapped to a
character, listed-building points and hand-drawn areas; offices and colleges inside Georgian areas keep the
terrace's style (Bedford Square's houses are offices). Berlin (`de-berlin`, M4) is the second: with a cadastre's
LoD2 and the Umweltatlas it has what London lacked, and the style comes from data more than from areas: the block
structure type (Realnutzung `typ_klar`: "Geschlossene Blockbebauung, Hinterhof (1870er - 1918)", "Großsiedlung und
Punkthochhäuser", "Lückenschluss nach 1945"...), then the building itself over its block: the **storey height**
(LoD2 eave over the Umweltatlas storeys: a Gründerzeit house 3.6-4.2 m a storey, post-war infill and slabs 2.8-3.2)
and the roof type tell a surviving Altbau from the infill beside it; a piece whose inside point lies within 12 m of
a street's kerb line (centre line less half the width and 4 m of pavement) is a front house, the rest courtyard
wings (plainer); hand-drawn areas only for what no field says (Karl-Marx-Allee's tiled blocks, the Hansaviertel,
the glass clusters, the government quarter). Roofs from the LoD2 roof type with the rise from its eaves
(`[tiles] roof_eave`), the Altbau's mixed and mono-pitch roofs as the Berliner Dach.

**Porting:** the engine's default categories are Shenzhen's (urban village, handshake buildings, R&D towers in
industrial parks); every other region preset defines its own (Paris's Haussmann blocks, Berlin's Altbau, Tokyo's
雑居ビル). Define the local vernacular and the rules that pick it (see `porting-checklist.md`). Wall palettes are sRGB hex,
converted to linear for glTF vertex colours (`srgb()`).

## 3. Landmark research workflow

Two hand-made data files per area. Keep the research notes next to them.

### 3a. Landmark height list: `data/landmarks*.csv`

Columns: `name_zh, name_en, height_m, height_type, floors, status, year, lat, lon, source, notes, feature,
use_height[, district]`.

- **Scope:** every completed or topped-out building ≥ about 150 m in the area, plus key landmarks regardless of
  height (stadiums, terminals, convention centres, civic buildings). Shenzhen: 49 rows (Bao'an) + 123 (Nanshan
  and Futian). 142 heights applied.
- **Sources:**
  - CTBUH Skyscraper Center
  - EN and local-language Wikipedia lists (zh "深圳摩天大楼列表"; a guessed list title 404'd)
  - local skyscraper forums (gaoloumi)
  - developer and leasing pages, news
  - OSM tags
- **Position must be on the tower's own footprint**, not a site centroid. `apply_landmarks` gives the height to
  the footprint under the point, or the nearest within 40 m. A site centroid lands on a podium or the wrong
  tower.
  - Get positions from OSM: the Overpass footprint centroid by name, or the tallest `building:part`.
  - Name unlabelled OSM towers from the named land plot around them.
- **`use_height=True`** only when all of these hold:
  - `feature=building`;
  - the height is known;
  - the point is verified on the footprint.
- **`feature=structure`** for ferris wheels, bridges and masts: they must not set a building height.
- **A landmark height sets the whole footprint under its point.** A tower standing on a larger building takes
  all of it to the tower's tip: Hoboken Terminal's 68.6 m clock tower, which has no footprint of its own, turned
  the station and its train shed into a 20-storey box. Give such a row `use_height=False` (or a footprint of its
  own). `04_buildings` prints "… share one footprint; the first sets its height" when two rows land on one.
- Rows with an unverified position are kept with `use_height=False` and a note, so they are not lost.
- Note conflicts in `notes`, and state `height_type` (architectural, roof, tip, OSM tag, floors × 3.2 m
  ESTIMATED). Examples: 230 m vs 210.6 m, 150 m for 52 floors.
- Flag rows within about 800 m of a district boundary as BORDERLINE and test them against the boundary polygon.
- Include under-construction towers only if topped out; say so in `status`.
- After `04_buildings.py`, `checks/buildings.md` lists the tallest 8 with their `h_src`. All should be
  `landmark`.

### 3b. Photo-referenced facade table: `data/landmark_facades.csv` + `.md`

Columns: `name, facade, tint, module, variant, profile, notes`. `name` must equal the building's name in the table
(set from `landmarks*.csv` `name_zh`). Otherwise 06_tiles prints "landmark facade: no building named X".

- `facade`: a style name (`fins`, `bands`, `lattice`, `honeycomb`, `panel`, `glass`).
- `tint`: sRGB hex **sampled from daylight photos** of the glass or cladding. It replaces the palette colour.
  **On the glass-wall styles (`glass`, `fins`, `piers`, `bands`) it is the glass's colour**; the fins, piers and
  frames have their own. New York's 99 Hudson Street, limestone piers between dark glass, had its limestone
  colour as the tint and `variant` 0.9 (piers 72 % of each 1.5 m bay): glass and piers one beige, a smooth slab
  from any distance. Tint the glass (`#3e4854`), 3 m bays, variant 0.4: stripes that read from afar.
- `module`: window bay or fin width in metres, or `bays:N` to spread exactly N bays around the footprint
  perimeter (China Resources' 56 columns). Stored in `COLOR_0.a` as module / 12 m.
- `variant`: a 0-1 style parameter that replaces the random seed (fin depth or band pattern, per the shader).
- `profile`: massing, lofted by `extrude`.

  | Profile | Meaning | Example |
  |---|---|---|
  | `0:1 0.12:1 0.93:0.8 1:0.3` | height fraction : scale about the centroid | Ping An taper and truncated crown |
  | `0:1 0.7:1 0.8:0.93 0.88:0.76 0.94:0.52 0.98:0.26 1:0.02` | vertical, then an ogive to a point | China Resources "bullet tip" |
  | `0:1 0.3:1 0.3:0.96 0.55:0.96 ...` | repeated fractions give flat **setbacks** | Changfu Jinmao stepping in at mechanical bands |
  | `dome:f` | vertical to f, then a quarter-ellipse scale-in | domes |
  | `shell:f:d` | vertical to f, then the **outline moves inward** up to d m on a quarter ellipse | Spring Cocoon `shell:0.15:55`, airport T3 `shell:0.3:24`, exhibition halls `shell:0.55:9` |
  | `long:f:sl:sw ...` | scale sl **along the footprint's long axis**, sw across it | Tour Triangle `long:0:1:1 1:0.1:0.6` (a trapezoid face, a slim end); a gable `long:0:1:1 1:1:0.02` |

- **Landmarks made of parts** take `;`-separated directives in the same cell (New York and Paris; the engine
  README has the full table): `crown@m[-top]:<profile>[:#hex]` cuts a body at m and lofts the rest as a
  coloured crown (`-top` picks every part that tall: the Invalides' dome under its lantern, the Sacré-Cœur's four
  small domes, Notre-Dame's nave roof pieces already lifted to 33 m); `tops@m:<p>|<p>` stacks the tallest spire
  parts from m; `h@a=b` corrects a part's height (the Arc's attic 47 → 49.5); `lid@m` makes a hollow block's
  stacked lid slices one thick lid (Grande Arche `lid@93`); `wing@m:<osm id>` cuts a roof-plan footprint to the
  tower's OSM outline and leaves the rest as a lower wing (Duo 1); `slot@w:e` splits twin towers on one footprint
  (The Link); `base@a=b` and `fill@m` rebuild an attic over vaults from pieces OSM maps with gaps (the Arc de
  Triomphe read as an "H" with sky through its top until `fill@29.2`). **No part may float**: 06_tiles'
  `grounded()` lets a part down onto the host below it or drops it with a `FLOATING` line; read those lines
  after every build (London's Gherkin vanished: `whole=true` merged its six stacked prisms into the first row,
  the 70-180 m top piece, keeping its 70 m underside; the merge now takes the body's lowest underside). Columns `take` (m: unnamed pieces near the
  landmark join it, e.g. Notre-Dame's towers mapped under other outlines, which otherwise got apartment windows)
  and `roof` (spire and crown colour; crowns' roofs keep that colour in the viewer, not the roof palette).
- **Monuments get the `monument` style, never a housing grid** (Paris M4 critic: the Opéra, Notre-Dame and the
  Louvre with apartment windows read as housing). Its variant picks the kind by fifths: 0.1 arcade (round-arched
  bays, paired columns, a gilt band: the Opéra), 0.3 palace (arched windows between pilasters, slate mansards via
  [facade.zones] `variant`: the Louvre's wings), 0.5 gothic (lancets, buttresses, portals and a rose window on
  short fronts, a louvred belfry in the top third of a tower over 55 m; 0.54-0.59 Perpendicular instead: wide
  mullioned windows, the wall between panelled in thin vertical ribs, no rose, portal or belfry: the Palace of
  Westminster, whose 0.5 read as "a uniform khaki box with invented rose windows" and a hollow Victoria Tower), 0.7 blank ashlar with an entablature (the
  Arc; 0.6-0.69 the same with a peristyle: one free-standing column per bay on a podium, the shaded cella wall
  between, no windows: the Madeleine, `module` 5.6 m), 0.9 a steel frame over glass with coloured ducts on the east face and an escalator on the west (the Centre
  Pompidou); `module` is the bay.
- **Glass domes, glazed halls and tents are see-through** (Berlin M4 fix round: the Reichstag's dome as an opaque grey-blue
  ball, the Hauptbahnhof's 321 m hall missing, the Sony Center's tent an opaque white cone): a figure's `glazing` sheets
  (a grid of points in the figure's frame, the members' spacing as `period`) go into the tile's lattice mesh and draw as
  light members over panes that let most of the light through (`kind` "fabric": a translucent membrane on thin
  cables); keep the ribs, rings and arches that make the outline as solid tubes (they cast the shadow). A barrel vault
  over an outline: cross-sections every few metres along its long axis spanning the outline there, the crown lower
  where it narrows (scripts/m4h_structures.py `vault`).
- **A landmark row's name can land on the wrong building** when the landmark itself is a figure and its outline is
  excluded: the nearest piece takes the name (Berlin: the Brandenburg Gate's peristyle on Haus Liebermann, read as an
  outsized Torhaus). Give that row the neighbour's own facade, or drop it.
- **Columns and obelisks** (Paris M10b: the Bastille, the Place Vendôme, the Luxor obelisk) are needles 04_buildings
  drops: build them as `[[structures]]` `figure`s at OSM's centroid: round shafts as `sections` (one loft, the
  figure's colour), square pedestals and an obelisk's taper as stacked `prisms` (each its own colour; a loft of
  four sides would shade round), statues as a few `tubes`, gilt where gilt. About 1-2k triangles each.
  **Where the figures live:** hand-written ones stay in city.toml; figures a script generates (Berlin's and London's
  `scripts/*_structures.py`) are written to `generated/structures-<name>.toml` and listed in city.toml's top-level
  `include = [...]` (engine README, "Generated settings"): re-running the script then changes that file only, not
  the 100s of KB of city.toml every reader pulls again. Never write generated blocks between markers in city.toml.
- **Sloped and curved tops** (Hong Kong M4): a figure's `wedges` are prisms with their own top height at each outline
  point, flat-shaded per triangle: the Bank of China Tower's four triangular prisms under 45-degree glass roofs, the
  Cultural Centre's roof plane; a curved roof as strips cut along its ridge, each a wedge (the HKCEC's wing roof). A
  survey row that is a whole lot or one box for a complex (Central Plaza's lot, the CGO's "open door", a stadium) is
  excluded by its id (`[buildings] exclude` takes any source column, **lower-cased**: `buildingcsuid`, not the file's
  `BuildingCSUID`, which silently matched nothing) or capped with `fix_h` and the landmark drawn as a figure on it, its
  0 set from the row's base (Terrain.bases + height) so it sits on the roof. A preset without a `spire` style can't
  take `crown@`: draw the crown as a figure.
- Monuments with no windows that are not stone (a metal-clad concert hall, glass sails) read better as the
  `floodlit` style (their own colour) with a `shell:` profile than as any windowed style: a box with a window
  grid is the worst outcome for a landmark chip.
- Pick a crown colour from the photos like a tint: gilt `#c4a45c` (the Invalides reads darker than its gold leaf
  from afar), lead `#80868c`-`#8a8e95`, copper verdigris `#8fa396`, travertine white `#dcd6ca`, slate `#4f5966`.

- Tall glass landmarks skip the plant room and rooftop clutter.
- The landmark's height comes from the landmark list.
- Not modelled, so noted in `notes`: twists (OCT Tower), leans (Tours Duo), sliced or sloped tops (Hanking),
  detached cores, wing roofs (Civic Center). For true icons the next level is a hand-built mesh from photos.

The `.md` (Shenzhen: 25 landmarks, about 350 lines) has one section per landmark:

- facade system: unitized curtain wall, fins, diagrid, exoskeleton, stone; module and floor-to-floor if published
  (the only published module found was Upperhills, 3.0 × 3.5 m panes);
- colours, **each marked (sampled) with the photo and conditions, (est.) or unverified**: overcast vs blue-sky
  glass differ hugely (Ping An #625a56 overcast, #31507b blue sky), so give both and choose in between;
- massing visible from afar: taper, chamfers, setbacks, crown or spire (built vs planned: Ping An's 60 m spire was
  never built);
- night lighting notes (used by night mode);
- 1-3 reference photo URLs (Commons file pages preferred);
- corrections to the brief (Ping An's piers are stainless steel, not granite as KPF's text implies);
- confusions to avoid (a Commons search for "China Merchants Bank headquarters" finds the *old* Futian tower).

Also:

- a general section: **palettes by building type** for the city (residential towers, urban villages, factories,
  offices by district generation), with floor heights, window grids and rooftop clutter. This fed the generic
  styles and `06c_rooftops.py`.
- an **Open gaps** list: what could not be verified (no daylight photo, under construction, text only).

### 3c. How to find reference images and sample colours

What worked (all scripted, no browser needed):

1. **Wikimedia Commons API search**, namespace 6 (files), with thumbnails:
   `https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=<q>&gsrnamespace=6&gsrlimit=12&prop=imageinfo&iiprop=url|size&iiurlwidth=330&format=json`.
   - Send a descriptive `User-Agent`. Retry 429 with backoff (5 s × attempt).
   - Try English, local and alternative names (e.g. "Dabaihui Plaza", "Shenzhen Center", "Riverfront Times
     Square").
2. **Contact sheets**: download about 12 thumbnails, tile them 4 wide with PIL and an index label, and look at
   the sheet (one image read instead of 12). Pick real photos, not renders; daylight, facade clearly visible.
3. **Sample boxes**: fetch the chosen file at `iiurlwidth=1000` and give boxes as image fractions
   `x0,y0,x1,y1`. Print the mean and median hex per box (`ImageStat`). Save a copy with the boxes drawn and look
   at it to confirm each box is on the facade (glass field, not sky, not a fin).
   - Sample mid-shaft, away from the sky-reflecting edges and from shadow.
   - Record the file, the conditions (overcast, blue sky, hazy, sunset) and the value.
4. When Commons has nothing current: architect pages (KPF, SOM, Foster, Gensler, Morphosis), ArchDaily, Dezeen,
   gooood.cn, CTBUH, local news. Image URLs can be scraped from page HTML (e.g. ArchDaily
   `images.adsttc.com/.../large_jpg/...`) and put on the same contact sheet.
5. Text sources (curtain-wall suppliers, CTBUH papers) for module sizes and materials.
6. Be honest: an estimate is marked (est.), and nothing is invented as "sampled".

A general-purpose subagent can do this well from a brief like:

> Research these landmarks (name, height, lat/lon list) from real photos. For each: facade system and module,
> daylight colours as hex with how they were obtained, massing, night lighting, 1-3 photo URLs. Also a general
> section on the city's facade palettes by building type. Write markdown to <scratch path>; don't edit the repo;
> say what you couldn't verify.

Then turn the report into the CSV yourself, and keep the `.md` in `data/`.

### Tint caveats (from the viewer side)

- Sampled glass colours include sky reflections. The viewer adds reflections of its own, so a sampled blue-sky
  tint rendered with strong reflections looks "weird light blue" or "too glassy".
- Prefer tints between the overcast and blue-sky samples. The viewer caps grazing reflectance and shows the
  glass's own body tint. The user settled on a reflection strength of 50 %.

### 3d. Open lattice structures (the Eiffel Tower)

A lattice tower is not a building: its OSM/cadastre outlines are stacked solid prisms (Paris: ten OSM parts, eight
APUR and four BD TOPO outlines), which read as a rocket. Exclude them all and build it as a `[[structures]]`
`lattice_tower` (`stages/structures.py`):
- **Plan from the data, heights from the operator, the rest from photos.** The piers' OSM parts gave the frame
  (their mean = the centre, their bearing = `facing`) and the half-widths at the base and each deck; the SETE's
  deck heights; the legs' inner edges, the arches and the top's proportions were read off a face-on photo.
- **Solid where it makes the outline, cut-out between.** The legs' edges (chords), the arches' ribs, the decks'
  belts and slabs are bars and boxes in the buildings mesh (they cast the shadow, take the floodlit style);
  the braced faces are flat panels in the tile's `lattice` mesh, drawn by `viewer/lattice.js` with a box-filtered
  bar pattern: near, St Andrew's crosses with sky between; far, a brown veil of the pattern's mean density.
  A solid loft reads as a rocket; instanced bars (thousands) cost more and alias to noise at 3 km.
- **Density:** a single set of thin crosses reads as a wireframe model; the real lattice is dense (members are
  latticed themselves): three bar families (the crosses, a quarter-period lacing, a twelfth-period mesh) with
  about 60 % coverage per face made the legs read as brown iron with sky showing through.
- Budget (Paris): about 11k triangles in the buildings mesh and 2k in the lattice mesh, one extra draw call.

## 4. Pitfalls checklist

- [ ] Underground or `layer<0` OSM buildings dropped (metro stations, underground malls).
- [ ] Big named or tagged OSM buildings (terminal, stadium, hall) kept whole; untagged estate outlines dropped.
- [ ] No satellite footprints on carriageways or under decks (`checks/road_clearance.md`).
- [ ] No needles (small footprints with tower heights).
- [ ] No lips or slivers beside OSM buildings (duplicate threshold 5 %, dropped, not clipped).
- [ ] Villages separate, single buildings whole (compare against a well-known neighbourhood; in Shenzhen, Wutong
      Island, a place reconstructed before).
- [ ] Tallest 8 all `h_src = landmark`, heights match the list.
- [ ] Every landmark in `LANDMARKS` (camera views) and `landmark_facades.csv` found by name.
- [ ] Shell and inset profiles don't fold in narrow necks (the T3 transport-centre neck folded until the 40 %
      inset cap).
- [ ] Structures (wheels, masts, bridges) have `use_height=False`.
- [ ] GBA blobs merging urban-village blocks: count footprints per km² in village areas against a 0.5 m source,
      or eyeball the Xixiang-type view.
- [ ] Buildings on steep slopes: base = lowest ground; check a few hillside ones aren't buried roof-deep.
- [ ] (HK/SG/Tokyo, Oct 2026) Untagged `building=train_station|transportation` outlines over an underground
      metro are boxes, often fed to height estimates (Singapore: 40–115 m "towers"): `[osm] underground_drop`,
      `[buildings] station_untagged`; `underground=yes` on `layer=1` exists (HarbourFront MRT).
- [ ] Unbuilt projects: fast-building cities map towers before completion, with levels but no construction tag
      (Singapore: 19 public-housing towers due 2029–31). Review recent OSM ids (> ~1.2e9) at ≥ 40 m against completion
      dates; the reverse also happens (towers completed this year missing from both OSM and the survey: Tokyo 2026).
- [ ] Official surveys photograph sites mid-construction (PLATEAU stubs of 2024–26 towers; LandsD rows over 2020 LiDAR
      excavation pits): compare survey height with storeys and the DEM under the row; take the completed height from
      the list or a newer source.
- [ ] Raised pieces: sky bridges, decks and stadium roof rings with `min_height` extruded from the ground become walls
      (Pinnacle@Duxton, the National Stadium): `[osm] min_height = "decks"`, `[buildings] lift_parts = "gaps"`;
      enclosed `part_rest` shafts: `parts_fill_shafts`.
- [ ] Survey heights that contradict storey counts (LandsD: ~80 rows under 2.2 m a storey; sister estate blocks a third
      of each other's height): check height ÷ storeys per row, fix by storeys only for residential/office names, never
      for podiums carrying the whole building's storeys.
- [ ] Two independent critics per milestone each sampling their own 30+ buildings found new classes of error every
      time: let the second critic choose its own sample, not the first's.

## 5. Landmark figures and structures checklist

Landmarks drawn as `[[structures]]` figures (towers, statues, bridge arches, pagodas: usually written by a city
script into `generated/structures-*.toml`) failed the same few ways in every city. The user notices each of these
at once, and a critic who checks the figure "centred on the outline" from above does not. Before calling a
landmark done:

- [ ] **Coordinates with at least 7 decimals** (about 1 cm). Three decimals (~100 m grid) put figures 10–60 m off
      their footprint (Tokyo M4); four is still ~10 m. Take them from the OSM outline's centroid or the surveyed
      point, not from a rounded Wikipedia infobox.
- [ ] **Seated on the piece it stands on.** A figure's foot is the ground (or the roof of its base building) under it
      plus `base`; compute it, then check it: a script that compares each figure's lowest point with the terrain and
      the tops of the building pieces under it (more than 1.5 m over everything: floating; more than 3 m inside a
      piece: sunk) caught every floating tower (Tokyo's `examples/tokyo/scripts/m4f_seat_check.py`).
- [ ] **Look at every building within ~50 m of the figure**, from the ground and from four sides. The building table
      has its own idea of what stands there: Tokyo Tower first stood on a windowed office block (its base,
      FootTown, drawn with an office facade); its leg pedestals came out as small windowed "house" boxes. Fix with
      a `landmark_facades.csv` row for the base (kind, colour, no windows where there are none) and the `near`
      column ("lon lat m|...") to pull unnamed nearby pieces into the landmark, or drop them.
- [ ] **Bridge figures on the deck the viewer draws.** Arches, towers and cables go on the elevated road ways the
      roads stage builds (`05b_roads` decks: their height and ends), not on OSM's `man_made=bridge` outline, which
      is often wider, shorter or offset: Tokyo's Eitai arch hung off its deck, Kachidoki's arches stood over the
      water beside it. Read the deck geometry back from the built roads and place the figure on it.
- [ ] **Deck ends meet the ground.** A lidar terrain has no abutments; a deck can end in mid-air over a quay wall or
      dive into an embankment. `[terrain] deck_ends` raises the ground under a deck's end to the roads it meets
      (Tokyo's Sumida bridges: approaches dropped from the deck's end to the levelled river bank until it was on;
      `{ level = "high", reach = 20.0 }` takes the highest dry ground within 20 m along the roads, past a quay
      wall's foot). `[cars] deck_ends = true` keeps cars at the deck's height where a lane meets it.
- [ ] **Glows and floodlights on the footprint's centroid**, not on a label point or an entrance node: Hong Kong's
      Central Plaza glow sat 29 m off and lit only one face. Look at every lit landmark at night **from four sides**.
- [ ] **Re-run the structure scripts after a roads or terrain rebuild.** Scripts that read deck heights or ground
      levels bake them into `generated/`; a later change to `[roads]` or `[terrain]` leaves the figures at the old
      heights (floating or sunk) until the script runs again. Put the script in the rebuild order.
- [ ] **The user's own camera.** When the user reported a landmark, re-shoot it at their camera (and a four-side
      orbit) after the fix; "fixed" from another view is not evidence.
