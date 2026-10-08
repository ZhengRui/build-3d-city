# Data pipeline (as built for Shenzhen, extended per city)

Code: the engine `engine/pipeline/` (package `city3d`; a stage per module, named as the scripts were, e.g.
`06_tiles` = `stages/tiles.py`). Settings: the city's `demos/<city>/city.toml` over its region preset over the
engine defaults (the first city, Shenzhen, used almost only the `china-south` preset; seven later cities'
`city.toml` files are in `../examples/`). Data: `demos/data/<city>/` (git-ignored); raw downloads live in `raw/`.
The sections below follow Shenzhen's build and name the later cities where they added or changed a step. Run from the city folder with
`uv run city3d <stage>` or `uv run city3d all` (deps in the engine's `pyproject.toml`: geopandas, pyogrio,
shapely 2, pyproj, rasterio, scipy, ijson, remotezip, mapbox-earcut, meshoptimizer ≥ 0.2.30a0). Every stage is
re-runnable; each writes one product and, where useful, a report in `checks/`. Script names below
(`05a_terrain.py`, `common.UTM`...) are now the stages and their settings (`05a_terrain`, `utm_epsg`).

## Conventions

- **CRS**: `common.UTM = "EPSG:32650"` (UTM 50N, metres). Everything is computed in UTM and stored in WGS84 or UTM
  gpkg.
- **Scene frame**: metres from `origin` = centre of the districts' bounding box (UTM). x = east, y = up,
  **z = south** (three.js), so `z = -(N - origin_N)`. See `06_tiles.to_scene`. Every output's index JSON carries
  `origin: {utm_epsg, easting, northing}`.
- **Tiles**: 1 km squares keyed `(tx, ty) = floor((E - oE)/1000), floor((N - oN)/1000)`. A building goes to the
  tile of its centroid, a road piece or lane to the tile of its midpoint. The same keys are used by the tiles,
  markings, trees, cars and rooftops.
- **Ground**: `common.Terrain` (the TIN from `05a_terrain.py`) is *the* ground. Everything that stands on it reads
  it there (`height`, `height_utm`, `bases`, `drape`, `drape_triangles`), so nothing floats or sinks.
- **Areas**:
  - districts: `common.boundary()`, the union of the `DISTRICTS` relations;
  - ground area: the districts' bounding box + 4 km (`05_ground.MARGIN`);
  - roads: districts + 1 km (`05b_roads.MARGIN`); bridges are kept whole;
  - backdrop: ground area + 36 km.
- **Plausible, not mapped**: trees, cars and rooftop clutter are invented where they would be. Real data decides
  where; seeded RNG (`default_rng(fixed seed)`) keeps runs reproducible.

## Run order and runtimes (8-core laptop, about 0.66k km² of land, 0.2 M buildings)

| # | Script | Needs | Runtime | Peak RAM |
|---|---|---|---|---|
| 1 | `01_osm.py` | Overpass | minutes (server-bound) | small |
| 2 | `02_gba.py` | GBA tile in `raw/` | ~5-10 min (3.7 GB geojson bbox read + ijson) | ~2 GB |
| 3 | `02b_eastasia.py` | network (range requests) | ~1 min | small |
| 4 | `03_compare.py` | 01, 02, CNBH | ~1-2 min | |
| 5 | `04_buildings.py` | 01, 02, 02b, CNBH, `data/landmarks*.csv` | several minutes (overlays) | |
| 6 | `04b_quality.py` | 04 | ~1 min | |
| 7 | `05_ground.py` | Overpass | ~1 min | |
| 8 | `05c_landuse.py` | Overpass | < 1 min | |
| 9 | `08_trees.py` first run (caches `raw/osm_green.json`, used by 05a) | 05_ground | 1.5 min | 4 GB |
| 10 | `05a_terrain.py` | DEM tiles, buildings, ground, green cache | **3.2-3.5 min** | **2.4 GB** |
| 11 | `05b_roads.py` | 05a, Overpass (cached) | 12 s | 1.1 GB |
| 12 | `06_tiles.py` | 04, 05, 05a, 05b, 05c | **4.5 min** | 1.4 GB |
| 13 | `07_pack.py` | 06 | 1-2 s (8 processes) | |
| 14 | `06b_markings.py` | 05a, 05b (+ its cache) | 1.4 min | 1.2 GB |
| 15 | `05e_shores.py` | 05, 05a | 33 s | 1.1 GB |
| 16 | `08_trees.py` (again, after the terrain) | 05a, 05b, 04 | 1.5 min | 4 GB |
| 17 | `06d_cars.py` | 05a, 05b, 04, 05c | 1.2 min | 1.4 GB |
| 18 | `06c_rooftops.py` | 04, 05a, 05b, 05c (imports 06_tiles steps) | 1.3 min | 1.4 GB |
| 19 | `07b_blocks.py` | 07, 06b | seconds | |

- Rerun `07b_blocks.py` after `07_pack.py` or `06b_markings.py`.
- `06_tiles.py --views-only` (7 s) refreshes only the camera presets in `tiles.json` (raw and packed).
- Dependency gotcha: `05a` reads `08_trees.fetch_green` (cached OSM green areas) for the canopy, and `08` lays
  its carpet on the terrain. So on a fresh city, run `08_trees.py` once before `05a` to fill the cache (or call
  `fetch_green` alone), and again after `05a`.

Final sizes (Shenzhen): 885 building/road tiles, 279 MB raw → 64 MB meshopt; blocks 91 files, 42 MB gzipped
(tiles and markings); plus trees 7.9 MB, cars 4.6 MB, rooftops 7.8 MB, shores 7.3 MB; about 100 MB in total.
Triangles: buildings 3.7 M, roads 0.56 M, bridges 0.32 M, ground 0.93 M + 0.09 M backdrop, markings 0.98 M,
tree carpet 0.62 M.

---

## 01_osm: boundaries and OSM buildings

- For each `DISTRICTS` relation id:
  - `rel(id); out geom;` → polygonize the outer ways → `boundary.gpkg` (name, osm_id).
  - Buildings in `area(3600000000+id)` → `osm_buildings.gpkg` with `osm_id` (w/r prefix), `building`, `name`,
    `height`, `levels`, **`layer`, `location`**, `district`; `buffer(0)`; `drop_duplicates("osm_id")` across
    districts.
  - A district may be only the part of its relation inside a clip (`{ relation = id, clip = ... }`): a ring
    `[[lon, lat], ...]` inline, or `clip = "data/districts.geojson"`, a path (relative to the city folder, or
    absolute) to a GeoJSON FeatureCollection whose Feature with `properties.name` = the district's key is the clip
    (Polygon or MultiPolygon). Use the file for anything generated (Singapore's subzone unions): it keeps city.toml
    small. The clip is intersected with the boundary, and its bounding box limits the Overpass query.
- Opt-ins for cities with underground malls and stations, sky bridges and decks (`[osm]`, off by default; the gpkg
  columns are exactly as before when off): `underground_drop = true` also keeps `underground` and `level`, and
  `load_osm` (and `use_parts`, for building:parts) then drops outlines with `underground=yes`,
  `location=underground|indoor` or a `level` entirely under 0, besides `layer<0`; `min_height = true` also keeps
  `min_height` / `building:min_level` on buildings (`load_osm` adds `min_h_tag`, metres).
- Admin boundaries can include sea: Bao'an's is 552 km², against about 400 km² of land. That is harmless; the
  land comes from the coastline.
- `common.load_osm()` does the loading for everything downstream:
  - drops `location=underground` and `layer<0`;
  - parses `height` (first number);
  - `h_levels = levels × LEVEL_H` (3.2 m);
  - `h = height or h_levels`;
  - `make_valid`.

## 02_gba / 02b_eastasia / 03_compare: building sources and the data check

- `02_gba`:
  - clip both polygon files (`GBA.LoD1/Polygon` and `GBA.ODbLPolygon`) to the scene bbox and polygon in EPSG:3857;
  - key = `source+id+region`;
  - stream the LoD1 heights with `ijson.kvitems` for the wanted keys;
  - `height < 0` → None;
  - output `gba_buildings.gpkg`.
- `02b_eastasia`: `RemoteZip(url)` → extract `China/Guangdong/Shenzhen.*` → read with a bbox → clip →
  `eastasia_buildings.gpkg`.
- `02_<name>` with `adapter = "citygml"` (`sources/citygml.py`): CityGML LoD2 tiles (Berlin's CityGML 1.0,
  PLATEAU's 2.0) → `<name>_buildings.gpkg`, a row per solid (a Building, or each BuildingPart):
  - one tile at a time, `ET.iterparse` with start/end events, each CityModel member cleared and removed from the
    root once read; inside an `app:appearanceMember` every element is dropped as it ends (PLATEAU files open with a
    50-60 MB texture/material block: a 166 MB mesh peaked at 0.41 GB without this, 0.13 GB with);
  - `.zip` members and `.gml.gz` are read in place, never unpacked to disk;
  - footprint = 2D union of the GroundSurfaces (else of the RoofSurfaces); `ground_z`, `roof_top_z`, `eave_z`,
    `roof_area` (sloped, Newell) from the surfaces' z;
  - `flavour = "plateau"` (opt-in): lat/lon/h posLists projected per solid with pyproj from EPSG:6668 in its
    authority axis order (lat first) straight to UTM, one transform call per solid; only `lod2MultiSurface`
    geometry (LoD3 buildings carry `lod3MultiSurface` twins); LOD1-only solids from `lod0FootPrint` /
    `lod0RoofEdge` / the `lod1Solid`'s bottom faces, their z from the `lod1Solid` (`lod` = 1); uro: attributes
    and English codelist names; -9999 / 9999 → NaN; rows deduped by `gml_id` across the source's files.
    Tokyo samples (FY2025, 4 meshes of 16-166 MB raw, 1-21 MB gzip): 980-2,143 solids, 0.6-5.0 s and
    +10-42 MB each.
  - `roof_split = {}` (opt-in, Tokyo M2): a LoD2 solid whose roof stands at several levels becomes a row per level
    (gml_id `<id>#r<k>`, parent_id the Building, `roof_level` k from the top, `roof_top_z` / `eave_z` its own):
    PLATEAU draws a tower and its podium as one Building (Roppongi Hills: 22,800 m² from one 235 m top; Tokyo
    Midtown 15,500 m² at 224.6), so without it every podium stands at its tower's height. Roof polygons (each at
    its highest z) join the level above while within max(`tol` 3 m, `rel_tol` 0.08 x its height); levels under
    `min_part` 40 m² (plant rooms, crown tips, gaps) and slivers under `min_width` 2 m go to the neighbour with the
    longest shared edge; only footprints of `min_area` 300 m² or more, roofs covering `cover` 0.8 of them, at most
    `max_parts` 12 levels. The level's height is `roof_top_z - ground_z` (measuredHeight stays the building's).
- `03_compare`: alignment, coverage and height statistics plus figures → `checks/report.md`
  (see `data-sources.md` §checks). Run it for every new city **before** designing the building table.

## 04_buildings: the building table

Output `buildings.gpkg` (WGS84) with columns: `source` (osm / gba_<sub> / eastasia), `h`, `h_src`, `floors`,
`kind`, `name`, `osm_id`, `osm_building`, `h_gba`, `h_cnbh`, `h_osm_tag`, `h_osm_levels`, and shape stats
(`area`, `aspect`). Report: `checks/buildings.md`. Shenzhen: 207k buildings (eastasia 107k, GBA 57k, OSM 42k),
89 km² footprint.

Opt-ins from Singapore's M2 (all off by default): with `[osm] min_height = true` a matched OSM building with a
`min_height` / `building:min_level` is a raised piece from there to its height (`min_h`, as a part's overhang; column
`osm_deck`: kept out of the estate and duplicate rules, and `dedupe` / `volume_dedupe` leave it and its towers whole:
the MBS SkyPark at 193-207 m, sky bridges); `[buildings] station_untagged = "drop"` or `"<metres>"`: untagged (no
height, no levels, no parts) `train_station` / `transportation` outlines of 150 m² or more are left out like
`osm_skip`'s (no fill source builds there) or stand that high (`h_src` station) after every estimate, never fed to
one (underground station boxes, entrance sheds).

Raised pieces, Singapore M2's engine wishes (all off by default; measured on Singapore, below):
- `[osm] min_height = "decks"`: only deck-like outlines keep their `min_height` (`deck_rule`): `building=bridge`, a
  name with bridge / deck / sky park, or half or more of it over two or more other OSM buildings that reach its
  underside (less 3 m); any other (a tower with `building:min_level` over the hole of its podium ring, upper storeys
  drawn inside one tower's outline) stands on the ground as with the setting off. With either `true` or `"decks"` a
  deck is set aside by the estate and duplicate rules (`drop_osm_containers(aside=)`: it took the SkyPark as an
  estate outline and MBS's three towers as its smaller duplicates), never nests anything on its roof (`nested`), and
  is no landmark row's building (the towers' points lie under the SkyPark). Singapore: 3 of 80 buildings with a
  min_height are decks (the SkyPark 193-207 m, OUE Link, Canninghill Piers' skybridge).
- `[buildings] lift_parts = "gaps"` (`true` is Paris's rule, unchanged): a raised part inside its building floats
  only over a real gap in a low building: thin (no thicker than the gap), not on mapped parts meeting its underside,
  no part of the building on the ground under it nor up to its underside anywhere (a tower whose crown, sky gardens
  or core segments are mapped from a min_height: OCBC Centre, South Beach, ION), the building's own height known
  (not `default`) and, with its OSM height / levels tags, below the underside, and under half the building's
  footprint (not its top: Pinnacle@Duxton's roof parts). The building's body stays under it at the rest's height
  (the National Stadium's 20 m seating bowl under its roof rings). `true` lifted 168 pieces over nothing in
  Singapore; `"gaps"` lifts 2 skybridges and 18 roof rings, none over nothing.
- `[buildings] parts_fill_shafts = 5.0` (a ratio): a `part_rest` piece closed (90 % of its outline within 1 m) by
  its building's parts standing on the ground, all taller, the lowest of them ratio x its width (√area) or more, is a
  shaft (a tower's core), filled to that lowest part; slivers (< 100 m², < 6 m wide) are left alone. Asia Square
  Tower 2's 393 m² core at 3.5 m in its 173-222 m parts; at 3.0 a 129 m² light well (17.5 m among 56 m parts)
  would be filled too.

Ground opt-ins from Tokyo's M2 (off by default): `[buildings] split_ground = true`: the roof levels of one building
(the citygml adapter's `roof_split`) each lose the DEM's rise from the building's lowest cell to the lowest under their
own outline, since 06_tiles stands each on its own lowest ground (Tokyo: 1,247 of 9,150 levels, median 1.1 m, max
18.4 m); `[buildings.landmarks] ground = "point"`: a listed height counts from the DEM at the row's point and the
table's from the lowest ground under the outline, so the difference is added (the Metropolitan Government Building
+6.3 m over Nishi-Shinjuku's sunken streets). Both sample `[sources] dem` (`dem_low()`).

Hong Kong M2 fix round (off by default): `[buildings] kind_map = {village = "midrise"}` renames a preset kind after every
other kind rule (china-south's urban village, 12-40 m on a small plot, is tong lau and pencil towers in Hong Kong: 11.5k
pieces, 94 % in the urban districts; its real villages are under 12 m, kind `house`); `[buildings] valid_out = true`
make_valid's the table as written (the WGS84 reprojection folded 25 clipped pieces).

### Footprint source, per building (`choose_footprints`)

1. **OSM** polygons of `area ≤ OSM_MAX_AREA` (5,000 m²), plus larger ones **tagged or named as one building**:
   - tags in `BIG_BUILDING_TAGS` (terminal, transportation, train_station, stadium, sports_hall, hangar,
     industrial, warehouse, commercial, retail, office, civic, public, hospital, school, university, hotel,
     exhibition/conference centre, ...), or any polygon with a `name`;
   - without this rule the airport terminal and the stadium broke into fragments;
   - bigger untagged polygons are estate outlines.
   - `drop_osm_containers` then removes:
     - estate outlines: a polygon holding ≥ 2 other OSM buildings (each ≥ 80 % inside);
     - duplicate parts: of two polygons overlapping by more than half of the smaller, the smaller goes.
2. **Compact GBA** footprints that satisfy all of:
   - overlap the chosen OSM by less than `DUP_SHARE` (5 %);
   - solidity (area / convex hull) ≥ 0.75;
   - hold **≤ 3 East Asia pieces** (each ≥ 50 % inside);
   - are not a "village blob" (≥ 2 pieces with median piece area < 150 m²).

   The 0.5 m data would only over-split these, so the building stays whole with one height. They are then
   clipped by OSM (`overlay difference`), and pieces under 12 m² are dropped.
3. **East Asia** pieces, first **aligned to OSM per 2 km cell** (`align_eastasia`):
   - pairs: nearest centroids of buildings over 150 m², less than 25 m apart;
   - offset: the median dx, dy per cell with ≥ 30 pairs, else the district-wide median;
   - Shenzhen: typical shift 4.6 m, up to 8 m.

   Then a piece is **dropped whole** if the summed overlap with chosen footprints is ≥ 5 % of it (it is the same
   building drawn a few metres off). Clipping it instead leaves a lower "lip" or skirt beside the real building.
   Survivors are clipped by the chosen footprints; pieces under 12 m² are dropped.
4. `cleanup`: `make_valid`, keep Polygon/MultiPolygon, drop non-OSM strips < 3 m wide (min rotated rectangle).

History worth knowing:

- GBA alone gave village blobs.
- East Asia alone gave over-split buildings plus slivers beside offset OSM buildings.
- The duplicate threshold went 20 % → 5 % after lips were seen on Wutong Island.
- Tuning was done on 3 views until the user asked "you only fix certain area?". From then on `04b_quality.py`
  checks the whole district after every rebuild.

### Attaching OSM attributes and GBA heights

- Name, `osm_building` and `osm_id` come from the best-overlapping OSM building with IoU ≥ 0.5.
- OSM heights come by **containment**: from the OSM building (≤ 5,000 m², with a height) that holds ≥ 50 % of the
  footprint. An OSM tower drawn as one polygon then gives its height to every piece the 0.5 m data split it into.
- `gba_height`: from the GBA polygon covering ≥ 30 % of the footprint. **Needle guard**: a GBA height ≥ 40 m
  does not transfer to a footprint < 250 m² that covers < 40 % of the GBA polygon. Otherwise kiosks and
  podium bits next to towers become needles.

### Height, first rule that applies (`h_src`)

Implemented as successive overrides, lowest priority first:

1. `landmark`: the hand-checked lists `data/landmarks*.csv`, rows with `use_height=True` and a position. The
   footprint under the point wins, else the nearest within 40 m; the name is set from `name_zh`.
2. `osm_height`: OSM `height` tag (via containment).
3. `osm_levels`: `building:levels` × 3.2 m.
4. `blend`: where mean(GBA, CNBH) is 15-30 m and both exist: `0.35·GBA + 0.65·CNBH` (CNBH is better in that
   band).
5. `gba`: the GBA estimate.
6. `cnbh`: OSM-only footprints without a tag get CNBH.
7. `default`: 3 × 3.2 m.

Then floor at `MIN_H` 3.5 m, round to 0.1 m, `floors = round(h / 3.2)`. Shenzhen counts: gba 85k, blend 53k,
cnbh 42k, default 18k, osm_levels 8.1k, osm_height 0.9k, landmark 142.

### Kind (`classify`), which drives facades and roofs later

In order: `tower` h ≥ 60; `slab` h ≥ 24 and aspect ≥ 2.5; `factory` h < 24 and area ≥ 3,000; `house` h < 12 and
area < 250; `village` 12 ≤ h < 40 and area < 450; `podium` h < 24 and area ≥ 1,200; else `midrise`. The OSM tag
(`OSM_KIND`: industrial/warehouse → factory, house/villa → house, school/hospital/station/stadium/... → civic)
wins unless the kind is tower.

## 04b_quality: district-wide checks → `checks/quality.md`

| Check | Shenzhen result |
|---|---|
| non-OSM strips < 3 m wide | 14 |
| pairs overlapping > 10 % of the smaller | 124 |
| touching pairs with height ratio > 1.5× | 1,486 (many are real: podium beside tower) |
| invalid geometries | 7 |

Also lists the worst 2 km cells (≥ 300 buildings) with lat, lon to inspect. Look there, not at random views.

## 05_ground: ground layers → `ground.gpkg` (UTM)

One Overpass bbox query over the ground area (districts bbox + 4 km), with the coastline, water, green, aeroway
and mud tags. Layers:

- **land**: `land_from_coastline`.
  1. Polygonize the coastline lines clipped to the area together with the area outline.
  2. Every 5th segment votes: probe points 2 m left (land, +1) and right (−1) of the line.
  3. Faces with a positive vote are land.
  4. This relies on OSM's rule that land is on the **left** of `natural=coastline`.
  5. An inland city has no coastline. The single face then gets no votes and **no land is returned**:
     special-case it so land = the whole area.
- **water**: `natural=water`, `waterway=riverbank`, `landuse=reservoir` polygons.
- **green**: park, garden, golf, nature_reserve, forest, grass, meadow, farmland, orchard, recreation ground,
  cemetery, wood, scrub, grassland, wetland, heath. **Clipped to the land**, except mangroves
  (`wetland=mangrove`), which grow in the tide. Futian's nature reserve polygon reached 4 km² out over the bay
  and was painted as lawn.
- **mud**: `natural=mud` and `wetland=tidalflat`, minus the land and the mangroves (12.4 km²).
- **aeroway**: runway and taxiway lines buffered by `width` (defaults 60 and 23 m), aprons as polygons.
- **area**: the ground area rectangle.

## 06e_masses: the town beyond the districts as block masses (optional)

`[ground] masses = true`: OSM buildings over the ground margin and `masses_reach` m into the backdrop (Overpass in
~5 km chunks; cached as `town_buildings.gpkg`), outside the districts and not over a modelled building. Heights:
`height`, else `building:levels` x level_h + 1 m, else by kind (houses 7.5, sheds 3.5, apartments 17...), else
(building=yes) by the built cover within ~120 m (5-6 storeys in continuous blocks, houses where sparse).
Beyond the ground area only buildings of 9 m and more, thinned towards the reach, masses under 150 m² left out and
outlines simplified 4 m; over the reach's last 1.5 km (`masses_fade`) they sink to 30 % of their height (the M7 critic: the edge
broke into confetti). Blocks merged per **12 km** cell into one mesh (`m_L<I>_<J>.glb`, tile size 12000: Paris 8
meshes; in 4 km cells, 48 cells x 2 meshes, they were 209 draws at the overview), houses per 4 km cell
(`m_h<i>_<j>.glb`, mesh `masses_small`, drawn within 6 km only); both by height class (houses one class, closed
over 6 m garden gaps; 4 m steps to 40 m, then 10 m), simplified 3-4 m, small ones as oriented rectangles; closed
shells sharing roof and wall vertices (no normals: the viewer shades them flat; wall colour in RGB, roof kind in
alpha); 16-bit positions (18 cm steps over 12 km). 07b_blocks puts them in blocks of their own
(`b_m<I>_<J>.bin`, `"late": true`) that the viewer loads after the first usable frame. Careful: the markings'
tiles are also named `m_<i>_<j>.glb` — filter masses by kind `tiles` as well as the prefix (`?masses=0` dropped
the markings with them until Paris M7's fix, which made the masses look 60 ms and 209 draws dearer than they are).
Paris: 1.14 M OSM buildings fetched, 408 k kept, 2.77 M triangles, 8.1 MB gzipped in 8 late blocks, 3 min.
`[terrain] backdrop_cover = "worldcover"` (the same stage; `--cover-only`): ESA WorldCover 2021 read from its
public COGs (AWS, no account), classes to colours, averaged onto two JPEG maps: `cover.jpg` at 50 m over the
whole backdrop (Paris 1948 x 1792, 1.1 MB) and `cover_inner.jpg` at 20 m over the masses' zone (1702 x 1280,
0.7 MB, read at the native 10 m), which the backdrop and the town layer sample. A 200 m backdrop TIN has its
vertices kilometres apart on the flats, and colouring it by height made Paris's plateaus (40-180 m) one forest;
the map shows the real forests, fields and towns. The first version, one 100 m PNG, read as "blurred camouflage"
and the Seine past the masses as a smudge: at 20-50 m a pixel the rivers (10 m classes) stay sharp ribbons.
Water is coloured as the city's own river seen from above (olive-dark), not a generic blue-grey.
`[terrain] cover_lines = { cell, rail, yard }` (Berlin M7 fix round): a lossless line map over the inner map
(`cover_lines.png`, 10 m: R the cover_roads' share, G the rail beds' (OSM railway ways off tunnels, `rail` m each;
landuse=railway at `yard`), B the nearest track's direction within 3 pixels). The 20 m colour map smeared the
Ringbahn's and the A100's corridors into a mottled grey-brown band 200-400 m wide; the town layer now draws asphalt,
ballast and track lines from it (`ground.coverLines`). Berlin 2264 x 1692, 1.1 MB, 5,730 track ways, 522 yards;
`06e_masses --lines-only` writes only it.
`[terrain] cover_roofs = { rgb = [[r, g, b], ...], gaps = [r, g, b] }` with `cover_buildings` (Tokyo far-field fix,
critic 2): the footprints painted into the inner map as roofs, each in one colour of `rgb` by a hash of its centre (list
one twice to weight it), and WorldCover's built-up share that no footprint or road covers in `gaps`, instead of all of
it in the town colour, so the map is pale roofs over darker alleys and streets as aerials show (the flat town colour
read from 2-8 km as a dark bare plain with no footprints). `cover_inner_cell` (default 20) sets the inner map's metres a
pixel: at 20 m Tokyo's 40-80 m blocks and 4-8 m streets averaged into one grey, at 10 m they show (2002 x 1874,
1.7 MB JPEG against 0.24 MB). The viewer's `ground.townMapNear` draws that map in the town layer near the camera too. `[ground] masses_skip { field: [values] }` leaves towers and masts out
of the masses (the Umweltatlas's "Sende-, Funkturm, Fernmeldeturm" and "Mast": the Funkturm stood as a fat
windowed block); draw them as city.json `masts` lattices instead.
`[ground] masses_within = "<file>.geojson"` (WGS84 Polygons / MultiPolygons, path from the city folder; off by default) keeps
only the masses inside the union, for a city whose town should stand in a band or in gaps, not all round (Singapore: 500 m
on the land side; Tokyo: the gaps between its core and two islands). A building is kept or dropped whole by a point inside
it (a clipped one would end in a cut-off slab, and an L's centroid can lie outside it), after its height is known; OSM is
fetched only over the 5 km chunks that touch the clip, and a stamp beside `town_buildings.gpkg` fetches again when the clip
changes; `cover_buildings` then paints only footprints inside it. A missing file or no polygon stops the stage at once.
`[ground] masses_thin = false` (Singapore M7; default true) stands every mass inside the clip at its height however far
out it lies (no thinning towards `masses_reach`, no sinking over `masses_fade`): a far town as an island of masses well
inside the reach, Johor Bahru's towers 15-17 km beyond Singapore's ground area across the strait (masses_reach 18 km,
the clip the 500 m band plus a polygon north of the Causeway). `[terrain] cover_inner_reach` (m, default masses_reach)
keeps the inner cover map, and the roads and footprints painted into it, at its own reach (0: the ground area + 1 km).
`[ground] masses_tall_within = { file, min_h }` (Singapore M7; with masses_within): a second clip where only the masses
of `min_h` m and more stand (fetched with the first): Singapore's HDB towns, 11,839 blocks of 30 m and more over the
island beyond the band, where the heartlands had been a flat painted plain to the horizon (405k triangles in 19 cells,
+1 MB of late blocks; their low-rise stays the cover map's roofscape).
`masses_tall_within.tagged = true` (Tokyo M7) fetches the tall clip on its own with an Overpass tag filter (`height` >=
min_h or `building:levels` >= (min_h - 1) / level_h), in `chunk`-degree boxes (0.2), cached as
`town_buildings_tall.gpkg`: Tokyo's clip is the Kanto plain within ~32 km, millions of buildings of which 1,135 are tagged
60 m or more (one fetch of 20 boxes from the local Overpass, seconds). They take their tagged heights and skip
`masses_tall` (which would hold a tower on a podium outline under min_h and drop it). Watch the local extract's bounds:
Tokyo's ends at 35.56-35.78 N, so Minato Mirai and Makuhari came back empty.

## 05c_landuse → `landuse.gpkg`

Maps `landuse` residential / commercial / retail / industrial / education and `amenity` school / university /
college / kindergarten / hospital to `use` ∈ residential, commercial, industrial, civic. Needed because
satellite footprints carry no tags: without it a Futian office tower and a Bao'an apartment tower look the same.

## 05a_terrain: bare earth, TIN, backdrop → `terrain.npz` (+ `checks/terrain.md`, `terrain.png`)

On a `WORK` = 10 m grid over the ground area, aligned so `TIN_CELL` = 20 m nodes are every other work node:

1. **DSM**: GLO-30 tiles merged and reprojected bilinear onto the grid.
   Memory: `dem_on` merges each CRS's run of tiles at its finest resolution before warping, by default over the
   whole run. A fine DTM listed with a coarse one of the same CRS covering far more (Hong Kong: the 2 m LiDAR
   mosaic, then the territory's 5 m DTM) is merged 64 x 48 km at 2 m: 3 GB a copy, 02_dem peaked at 10.2 GB.
   The whole merge also sits on the union's corner: the 5 m DTM's (…7.5 m) put the 2 m LiDAR half a pixel off,
   ±0.3-0.5 m on slopes (up to 12 m on cliffs) at the 10 m work grid. `[terrain] dem_window = true` merges each
   run only over the grid it fills, on the first tile's pixel grid, into a temporary tiled GeoTIFF in the data
   folder, and GDAL warps it from there in chunks: Hong Kong's 02_dem 10.2 GB / 51 s -> 1.8 GB / 18 s,
   05a_terrain 1.9 GB / 65 s; inside the LiDAR the 10 m grid is the LiDAR's own warp. For a datum offset, use
   `[sources.geotiff]` entries `{path, shift}` rather than a prepared copy.
2. **Mask buildings**: footprints buffered by `BUILDING_PAD` 12 m (the DEM's 30 m pixels smear roofs) are set to
   +inf.
3. **Morphological opening**: a grey min filter then a max filter over `OPEN` = 50 m. This removes remaining
   unmapped buildings and single trees. Masked blocks are filled from openings over `OPEN_FILL` = 150, 350, 750
   and 1,500 m windows in turn.
4. **Canopy subtraction**: `CANOPY` metres per OSM green class (forest 5, park 3, orchard 3, scrub 1), burned,
   Gaussian-blurred 40 m and subtracted. Keep it modest: the DEM's summits carry scrub, not forest. The viewer's
   trees stand on top again.
5. **Smoothing**: Gaussian σ 45 m on open ground, 120 m where built up. The blend weight comes from the local
   footprint cover: `clip((cover_200m − 0.08)/0.25)`.
6. **Sea-level knee**: the scene's sea plane is at 0, but reclaimed land sits a few metres up.
   `sea_drop(h)`:
   - x = h − `SEA_DROP` (3 m);
   - 0 if x ≤ 0;
   - x²/(4k) if x < 2k, with `SEA_KNEE` k = 2 m;
   - else x − k.

   That is about 5 m off the top, continuous in value and slope. The result is multiplied by `coast_ramp`: 0
   within `COAST_FLAT` 40 m of the sea, smoothstep to 1 over `COAST_RAMP` 160 m. Everything off the land is 0.
7. **Inland water levelled** (`inland_water`), per merged water body over 200 m²:
   - if the 10th-90th percentile spread of the ground under it is ≤ `FLAT_SPREAD` 4 m, it is flat at its median;
   - the ground within `WATER_FLAT` 25 m of its banks is flat too, rising back to its own height by
     `WATER_RAMP` 90 m;
   - the ground never drops away from the water faster than `BANK_SLOPE` 0.35, so dams become embankments;
   - water on a slope (hill streams) keeps its ground.

   Shenzhen: 3,088 bodies levelled, 475 left on their slope.

   Paris (inland, a lidar DTM at 5 m): the Seine is one OSM body across three dams, so `[ground] pools` cuts the
   water at OSM's dams, weirs and lock gates first and each pool is levelled alone (3.55 m through Paris, 0.47
   below Suresnes; the Canal Saint-Martin lock by lock). The flat band and ramp above are for a 30 m DEM: on a
   lidar they erase the quays (lower quays 2.5 m over the water, walls to the upper quays 6-8 m), so Paris sets
   `water_flat` 0, `water_ramp` 5, `water_all_touched` false (the cell by the wall is the quay's, or the quay road
   drops to the water) and `tin_error_bank` 0.5 within 40 m of the water.

   Even so, a 5 m TIN draws a vertical quay wall as a 5-10 m slope, faceted, grassed where a park polygon reaches
   the edge, and its waterline follows the grid in a sawtooth (the M3 critic: "sloping embankments, not stone
   walls"). `quay_walls = true` (off by default) makes the step one cell: the first ring of land cells along a
   levelled body takes the highest height of the next ring inland (the quay's, not the smeared wall's) where it
   stands `quay_min` 1 m over the water, and the water cells along it drop `quay_depth` 6 m under the level, so the
   TIN crosses the water's surface within a metre or so of the land node. 05e_shores' `quay_walls` then covers
   that cell with a vertical wall at the water's outline and a flat apron (below). A TIN on a grid cannot hold a
   breakline; the wall mesh is what makes it vertical.
   `deck_ends` (off: `{}`; EXPERIMENTAL, only Tokyo uses it (`level` "high"): it removes the steps but leaves artefacts, below): bridge abutments. A lidar DTM has no bridges, so under a road
   deck's end it reads the water, the quay wall's foot or the hollow under the first arch, and the ground road
   meeting the deck dipped metres into that notch right where it ran onto the deck (Oct 2026: a step over 0.3 m at
   140 of Berlin's 291 road deck ends, 389 of Paris's 714, 233 of London's 468; Admiralbrücke's north end 6.5 m
   over −0.7 m). Where a road deck meets a ground-level road (05b_roads' pins, read from its OSM cache: run 05b
   once before) the ground is raised to that road's level: per road leaving the node, the line through its dry
   ground 8-20 m on (past the notch; its grade capped at 15 %) carried back to the node (the median of 4 m to
   `reach` 12 m where the road is shorter), the median over the roads; over the grid square round the node and the
   deck's width up to 5.5 m into the bridge, and along each road (its half width, 2.5-6 m) easing to its own line at
   `ramp` 20 m. A first cut took the median of all roads' ground 4-12 m on, and lifted ends where a road climbs
   away (an embankment up to a bridge over the tracks) up to 3 m over their own road. Only ever
   raised, and only dry cells (raised water cells, 6 m under the pool by a quay wall, stood as brown earth wedges in
   the river under and beside the deck's end: Admiralbrücke, Roßstraßenbrücke), except the grid square round the
   node (left low, the TIN sank the deck's end towards the river with it: Lohmühlenbrücke to −2.9 m); round a corner
   raised in the water the water cells two or more cells inside the water sink `sink` 24 m more, so its facet falls under the
   opaque water within a fraction of a metre, a dark vertical abutment face instead of a ~2 m earth wedge (a cell by
   the bank sunk too showed as a pit in the grass beside the Mehringbrücke, cells one inside opened dark holes by the
   Pont d'Arcole), the raised cells and the ring round them TIN vertices (a one-cell ramp at their edge). 05b_roads then
   ends the deck on the ground at the node instead of the highest ground within 12 m (which put the Pont Neuf's
   ends on the Île 1.2-1.4 m over the road leaving them). `landings`: footbridges whose free ends meet no road
   fetched (footways up to an avenue) take the highest dry ground within 10 m (the Passerelle Debilly's end on the
   Avenue de New York, 2 m over the lower ground under it). `level` "high" (Tokyo, Oct 2026, the first city to use
   deck_ends): the deck's end at the highest dry ground within `reach` m along the roads, not their fitted line, and
   with `tin_cell` over `work` (20 m over 10 m) the TIN's whole square round the node held at it: the Sumida's bridges
   end on the quay's edge, and the 10 m grid square's cells were not TIN vertices, so the node read the quay wall's
   −6 m foot 20 m off (Kachidoki's west deck ends at −1.4 and 0.4 m under a 3 m street; Tokyo `reach` 20).
   `dalles` (off: `[]`): polygons ([[lon, lat], ...]) each held on the robust plane through the ground under it
   (fitted, points over a metre off dropped, refitted) and kept to the edge tolerance in the TIN: a slab over
   roads (La Défense's dalle, whose lidar has lumps and holes filled from the 5 m RGE ALTI); 05b_roads cuts
   ground-level ways out of them (they run under the slab).
   `patches` (off: `[]`): polygons whose cells are re-filled linearly from the ground just outside them: a pit
   in the lidar ground on a slope (Paris: a 10 m hole halfway down the Square Louise-Michel under the
   Sacré-Cœur, drawn as a dark "building" in a torn hole with triangular flaps).
   `tin_steps` (off: 0): every node whose ground drops that much (Paris 3 m) to a neighbouring node is a TIN vertex
   from the start. The greedy TIN otherwise meets an upper-to-lower quay step with sparse vertices on its top and
   bottom edges, and its long slivers between them read as rows of light spikes (Quai Branly, Quai de Conti, La
   Défense's Boulevard circulaire): all nodes make the step a regular one-cell ramp.
8. **TIN by greedy Delaunay insertion** (`greedy_tin`), on the 20 m subgrid:
   - start from a sparse grid: every 50th node inside, every 25th along the edge, plus the corners;
   - each round, add the node furthest from its triangle's plane (relative to its tolerance) in every triangle
     that is off;
   - stop when none is off, or after round 12 with fewer than 50 off;
   - tolerance per node: `TIN_ERROR` 4 m in the districts (+1.5 km), growing to `TIN_ERROR_FAR` 12 m over 4 km
     beyond, and **`TIN_ERROR_EDGE` 0.5 m** where the ground is held level (coast strip, lakes), so those stay
     flat;
   - result: 114k vertices, 222k triangles in about 13 rounds;
   - **Delaunay, not a mesh simplifier**: edge collapses fold triangles over each other on flat ground; Delaunay
     keeps a proper height field;
   - triangles oriented counter-clockwise seen from above; vertices stored as uint16 grid indices plus float
     heights.
   `gap_fill` (off: `{}`): a lidar DTM's tiles rarely cover the whole ground rectangle (Berlin's DGM1: 8 % of the
   grid in its four corners); the nearest-cell fill draws the gap as stretched columns (streaks in the hillshade and
   ribbed ground in the ring). Filled from the backdrop DEM instead: opened `open` 150 m and smoothed (GLO-30 is a
   surface model), offset by the two DEMs' difference along the gap's edge, easing over `blend` 600 m into their
   median difference (Berlin −2.34 m), so neither a step nor a slope shows at the coverage edge.
   `cuttings` (off: `{}`): past the roads' margin no track or carriageway is drawn, so a rail or motorway cutting in
   a lidar DTM is only a trench under the town layer, which its relief shading draws as a smeared soft band across
   an overview (Berlin's Ringbahn and A100, M3 critic). Dry hollows `grow` 2 m under the closing over `window` 150 m
   within `near` 30 m of OSM rail and motorway ways, more than `beyond` 1 km outside the districts, are filled to
   grade from their outlines (Berlin: 504, 549 ha, up to 14.5 m). With 06e_masses, `cover_buildings` paints the
   town's footprints into the inner cover map in the town colour (no back-yard tree green under the masses).
9. **Backdrop**: the DEM averaged onto a `FAR_CELL` 200 m grid out to `FAR_REACH` 36 km beyond the ground area
   (limited by the DEM tiles fetched). Where the backdrop DEM ends short of it, list a coarser one after it (London
   M7: Carbon & Place's z11 mosaic ended 25-29 km out; OS Terrain 50 read from its zip archive carries on, same datum,
   -0.14 m median in the overlap): `dem_on` lets an earlier source win and fills only its gaps. From an overview
   high up the haze is thin and any backdrop edge shows: fade it out (viewer `haze.edge`).
   A hill view needs its summit inside the ground area: the backdrop's 200 m TIN carries no trees or cover detail,
   and a camera on a backdrop summit looks down a bare dark cone (Berlin M7: the Teufelsberg 240 m outside the
   area, the Müggelberge 10 km out; the view went to the Drachenberg beside the Teufelsberg, the Müggelberge's was
   dropped). Pinning `back_peaks` keeps their heights right as seen from the city.
   - Sea is where the DEM is about 0 (mean and nearest); it goes to `SEA_Y` −3 so the coast is where the surface
     crosses the viewer's sea plane.
   - Lakes are where min = max (dead level).
   - Same `sea_drop`, then a greedy TIN with error 6 → 30 m with distance.
   - The **inner edge takes the ground TIN's exact heights** at the points where its edges cross the ground area
     outline (`edge_breaks`), so the two meet without cracks.
   - Triangles over the ground area or wholly on the sea are dropped.
   - Vertex colours: forest on steep (> about 20°) or high (> 25-85 m) ground, else town or field at random,
     lakes dark.
   - Result: 91k triangles over 123 × 106 km.
   Far sectors (Tokyo M7, all off by default): `far_reach_sides = [w, s, e, n]` reaches one way only (Mount Fuji 98 km
   west-south-west; the backdrop 163 x 137 km, 191k triangles with `back_error` [6, 35]); list every DEM tile of the
   box or the missing squares read 0 and vanish as sea. `curvature = { from, k }` drops the backdrop past `from` m by
   D = (r - from)^2 / (2 R / (1 - k)), applied as y^2 / (y + D) so no land sinks under the sea plane (Fuji 3,776 ->
   3,325 m as seen from the city; without it 24 % too tall); it also stores `back_h`, the heights before it, which
   06e_masses' `snow = { from, full, rgb, patchy }` paints into the outer cover map (Fuji's cap). `back_sea = "void"`:
   with a bare-earth backdrop (GSI) the old rule took all land at or under 0.2 m for sea, and the zero-metre polders
   behind Tokyo's levees (-1 to -3 m) dropped under the sea plane, which showed through as blue blob "lakes"; now the
   sea is only where the bare file is void. `cover_cell` sets the outer map's pixel (60 m: 2,724 x 2,281, 1.7 MB).
   With a far sector, thin the far haze over high ground (city.json `haze.thinHeight`, Tokyo 250) or a 100 km peak
   stays 75 % haze.
   `[terrain] summits = { radius }` (Singapore M7; off by default): the named `[terrain.peaks]` inside the ground area
   that the canopy cut and the smoothing left under their surveyed height (less the sea drop: the scene's plain lies
   that much under the DEM's) are lifted back to it: the hill within `radius` m of its own top scaled up over its foot
   (the 5th percentile there), in full within a third of the radius, easing out to none at it; levelled water keeps
   its level. Singapore's small steep hills: Mount Faber 91 -> 101 m, Telok Blangah 79 -> 89, Serapong 80 -> 85, Imbiah 54 -> 57 (radius 500).
10. **Checks**: `PEAKS` (named summits with surveyed heights). The max within 1 km in the DEM and in the scene
    ground goes to `checks/terrain.md`, plus a hillshade PNG with the district outlines.
    - Expect the scene to sit 10-35 m below survey (the knee plus smoothing); the DEM matches survey within a
      few metres.
    - If the DEM is far off, the tile or the datum is wrong.

`common.Terrain` loads the npz:
- builds a matplotlib `LinearTriInterpolator`, area-weighted vertex normals and a shapely STRtree of the
  triangles;
- `level[t]` holds the height of each dead-level triangle;
- `bases(geoms)` returns the lowest ground along each outline, sampled every 4 m;
- `drape(poly)` cuts a polygon along the TIN except where the triangles below are all at the same level (the
  plain at 0, a lake), where it stays whole;
- `drape_triangles(xz, tri, tol)` cuts only where a plane through a triangle's corners misses the ground by more
  than `tol` at its edge midpoints and centre, and returns barycentrics so callers can carry their own
  attributes;
- `weld` merges equal vertices again (mm positions).

## 05b_roads: roads, widths, bridge decks → `roads.gpkg` layer `ways`

- One bbox query (ground area) for:
  - `highway` motorway..tertiary (+ `_link`), residential, unclassified, living_street, road, service,
    pedestrian;
  - `railway` rail, light_rail, subway, narrow_gauge, monorail, tram.

  Cached to `raw/osm_roads.json`.
- `kind` = major (motorway, trunk, primary, secondary), minor, service (not parking_aisle, driveway or
  drive-through), or rail.
- **Tunnels dropped**: `tunnel`, `covered` or `layer < 0`. That includes most of the metro.
- **Width**: the `width` tag (2-60 m); else `lanes × 3.5` (+2 m on motorway/trunk); rail 3.2 m × tracks; else
  `DEFAULT_W[highway]` as (two-way, one-way) widths, e.g. motorway (24, 12), primary (18, 10.5), residential
  (7, 5), service (4.5, 4).
- **Deck heights** for `bridge=*` ways:
  1. **Target clearance**: `LAYER_H` 7.5 m × max(1, layer). A bridge without a layer counts as layer 1.
  2. **Pins**: nodes shared with ground-level ways are 0 (the deck meets the road).
  3. **Ramps**: the lower envelope `h(n) = min_m init(m) + GRADE·dist(n, m)` along the elevated graph (Dijkstra),
     with `GRADE` 0.05. Ramps rise gradually, short river bridges stay low, long viaducts reach full height.
  4. **Grade line** under the decks: harmonic along the elevated network between the pinned nodes (ground height
     there), solving `min Σ w(Bi−Bj)² + PULL Σ (Bi−Ti)²` with w = 1/length and `PULL` 1e-5/m (sparse `spsolve`).
     Viaducts **span valleys** instead of dipping into them.
  5. **Top** = max(grade line, ground) + h.
  6. **Crests**: `deck_line` adds points every `DECK_STEP` 20 m where the ground rises closer than the clearance,
     so a ridge doesn't poke through. Only raised segments keep their extra points.
- Paris's lessons (all options, off by default): a deck's end pinned to a ground road takes the highest ground
  within 12 m along the roads it meets (with `[terrain] deck_ends`: the ground at the node, which 05a raised to the road's level) (a lidar DTM has no bridges: under an abutment it reads the lower quay or
  the water); `decks_ref = "water"` counts a named deck from the lowest ground under its span (level across an
  island); `{deck, water}` gives a viaduct its own height over the river (Métro 6 on top of a road bridge),
  `{deck, reach}` holds a viaduct level over a cutting; `footbridges` fetches footways on bridges (not pavements
  along road bridges, nor `area=yes` outlines); ways tagged `area=yes` (squares) are never drawn as roads.
- Deck heights after the outlines followed their roads (Paris, London, Oct 2026): with `decks_ref = "water"` alone
  a named deck counted from the lowest ground under its span, and with `[terrain] quay_walls` the water cells by
  the walls lie 6 m under the pool: every bridge with a node there stood 6 m low mid-river (the Pont de Sully 6.2 m
  between quays at 11.5, 17 of Paris's 38 decks, 10 of London's 14, Tower Bridge on the water) and climbed 20-60 %
  to its ends; `decks_level = true` (Berlin's already) counts from the pool's level. Check every deck with a profile
  of its ways over the outline (z at the ends vs. inside, the steepest segment) after any terrain change. Two more
  opt-ins: `decks_ease` (a span climbing at `grade` to a bank's road higher than its value: the Pont de Puteaux over
  the Île de Puteaux) and `bridge_ways` (ways that are bridges though not tagged so: Tower Bridge's roadway through its towers is a building_passage).
- **Bridge outlines** (`bridge_outlines = true`, off by default): the ways alone can draw a wide bridge as strips
  over open water (Paris's Pont d'Iéna since 2024: two 3.2 m `highway=service` bus lanes, its pavements dropped as
  "along a road bridge", on a 35 m deck). OSM's `man_made=bridge` outlines (cached `raw/osm_bridge_outlines.json`)
  are matched to the `decks` span with the most road-way length inside (railways left out) and written as layer
  `outlines` with that span's median deck height; 06_tiles draws each as a slab just under the ways' decks (its
  `DeckField`: at each point the lowest of the elevated ways' decks over the outline, each rising 0.15 m/m beyond
  its edge and never above the nearest way's, 0.1 m under their tops; footways only on a footbridge and where
  they run along it (a road bridge's footways sank London Bridge's slab 6.5 m; not the ground roads continuing them over the outline's ends: at a quay wall's foot the ground can read
  metres under the deck's pinned end, and the slab sank 6 m over half of the Pont Marie); cut into 2 m cells where it varies across the deck, a typed bridge's elevation, parapets and arcade
  following its lowest across the deck). Lesson (Paris, London, Berlin, Oct 2026): a flat slab at the span's
  median deck covered every way that sloped below it (a humped bridge's ends, ramps, a carriageway of another
  name, slip roads): a plain grey deck without asphalt, lane lines or crossings, the cars sunk into it; at least
  5 % of the ways' length over the outline was covered on 28 of Paris's 41 outlines, 18 of Berlin's 29 and 8 of
  London's 17 (22 %, 26 % and 18 % of all; now 0.1-0.3 %: stairs down to the quays, walks under the ends). Its
  fascia and piers from `[roads] piers = {span: [spans, fascia m]}` (spans − 1 piers evenly along the outline's
  long axis, those in the water kept, across the whole deck with pointed cutwaters, from a metre under the bed to
  the slab). `checks/bridges.md` lists each outline's share covered by its ways' decks (FAIL under 60 % when the
  outlines are not drawn). Named decks get no pillars in the water from `deck()` (`dry`), which is why
  `[tiles] pillars_in_water` did nothing for them: their piers come from this table.
- **Bridge types** (a third entry, or a table: `{spans, fascia, type, rise, ...}`; M4 critic in Paris: "every
  bridge a thin flat slab on box piers"): the outline is drawn as its *elevation* instead, a rectangle along the
  outline's axis from under the water to the pavement less one opening per span (arcade over the water's extent
  along the axis + `reach` 6 m over the lower quays' walls), triangulated for both faces and extruded across the
  deck's width, the width and centre line being the median cross-section of the outline at 20-80 % of its length
  (the bounding rectangle of an outline fanning out over its abutments put the old piers 25 % beyond the deck).
  `BRIDGE_TYPES` in 06_tiles: `stone` (basket-handle arches, `arch = "segment"` for low circular ones, rise capped so
  the arch springs `spring` m over the water), `iron` (low segmental arches in dark green-grey on stone piers),
  `concrete`, `girder` (flat soffit). Cutwaters (`point`/`round`) at every pier in the water up to part of the
  rise; `bastions = true` takes them to the pavement with a parapet round them (the Pont Neuf's demi-lunes);
  parapets along both sides; `pylons = [h, side, colour, top h, top colour]` at the arcade's ends (Alexandre III);
  `upper = "<decks span>"` puts columns (`columns = [step, radius, colour]`) from the pavement up to that span's
  ways over the outline (Bir-Hakeim's and Bercy's Métro 6). `spans` may be a list, one per outline of the span,
  longest outline first (the Pont Neuf: 7 and 5). Paris: 33 outlines typed, ~16k triangles for all of them,
  merged into the tiles' bridge mesh (no extra draw calls).
- Geometry is 3D (z = deck height in the scene). Ground roads are clipped to the districts + `MARGIN` 1 km;
  elevated ways are kept whole if they touch it (cutting loses deck heights).
- Lesson: context roads over the whole ground bbox added 1,268 road-only tiles (2,021 in total). Cutting at
  district + 1 km brought it to about 900.
- **Suspension bridges** (New York): a `[[structures]]` suspension bridge's `roadways = { centre, width }` moves
  its carriageways to ± centre of the towers' line between the anchorages, fading back to OSM's line over 80 m
  beyond. OSM's needn't be symmetric about the towers the trusses and cables are built on (the Brooklyn
  Bridge's lay at −7.7 and +9.0 m, its promenade over one of them).

## 06_tiles: road clearance, buildings, roads, ground → `tiles_raw/`

### Road clearance (`road_clearance`) → `checks/road_clearance.md`

Satellite segmentation outlines toll booths, parked lorries and whole interchange decks as "buildings". **Only
non-OSM footprints** are candidates (people drew OSM ones; elevated stations do span roads). A footprint is
dropped if, as a share of its area:

| Rule | Threshold | Road polygon | Dropped |
|---|---|---|---|
| major road core | ≥ 30 % | buffered to 0.4 × width (the middle 80 %) | 1,023 |
| minor or service road core | ≥ 60 % (lenient: village alleys are mapped narrower than the default widths) | 0.4 × width | 1,261 |
| under an elevated deck | ≥ 50 % | 0.5 × width | 337 new |
| all roads and decks combined | ≥ 55 % | full width, dissolved per building | 1,363 new |

- The combined rule caught pieces straddling a ramp, a slip road and a viaduct that stayed under each single
  threshold (e.g. 49 % minor, 27 % major, 41 % deck).
- Total: 3,984 of 207k.
- Big buildings with one road running into them survive.

### Buildings

- Footprints are simplified 0.5 m after `make_valid`; parts under 4 m² are skipped.
- `facade_styles` and landmark facades: see `buildings-and-landmarks.md`. Seed per building
  `default_rng(7).random()`.
- **Base** = `terrain.bases(geom)`, the lowest ground under the outline. Walls reach `SKIRT` 1 m further down so
  no gap opens on a slope; uphill the ground covers them.
  - Downside: about 0.1 % of buildings on slopes over 10 m sink deep into the hill uphill.
  - A terraced pad would fix it, at the cost of TIN detail.
- `extrude(poly, h, ...)` builds the walls and a flat earcut roof.
  - **Wall runs** restart at corners sharper than `CORNER_DEG` 30°. UV = (distance along the run, run length) in
    metres, so the shader fits whole window bays per run. Exterior rings are counter-clockwise, holes clockwise.
  - **Profiles** loft the footprint through levels:
    - `f:scale` pairs such as `0:1 0.9:1 1:0.8` scale about the centroid (tapers, setbacks);
    - `dome:f` is vertical to f, then a quarter ellipse scaled in;
    - `shell:f:d` moves the outline **inward** by up to d m along mitred normals (curved roofs following the
      building's own outline: airport terminal, stadium, halls).

    Walls get their true tilted normals; UVs stay those of the base ring, so bays narrow with a taper.
  - **Shell-roof fold fix** (`inset_room`): each vertex moves in at most 40 % of the distance to the far side
    along its inset direction. Narrow necks otherwise crossed and folded the roof. The final inset outline goes
    through `make_valid`.
- **Plant room** on roofs with h ≥ 24 m and area ≥ 250 m², not factories, not landmarks with a researched tint:
  the footprint scaled 0.35 about a representative point ∩ (footprint − 2 m), ≥ 12 m², 3.6 m high, style
  `plain`.
- Vertex attributes (read by the facade shader):
  - `COLOR_0` RGBA8: palette or tint colour (linear); alpha = bay module / 12 m.
  - `TEXCOORD_0` (u along run, run length), unorm16 over 4,096 m.
  - `TEXCOORD_1` (style id + 0.999·seed, height), unorm16 over (16, 1,024).
  - `TEXCOORD_2` (base, 0), unorm16 over 1,024 m.

  `tiles.json.uvRange` passes these ranges to the viewer. Wall runs over 4 km or buildings over 1 km would be
  clipped: enlarge the ranges for a city with bigger values.

### Structures (`[[structures]]`, `stages/structures.py`)

- Parametric figures the building table can't make (landmark towers, wheels, domes, bridges), read from the
  resolved settings by 06_tiles (and, for the named bridge decks, 05b_roads). Hand-written ones live in city.toml;
  those a script generates (`demos/<city>/scripts/*_structures.py`) go to `generated/structures-<name>.toml`, which
  city.toml's top-level `include = [...]` lays under its own settings (arrays of tables appended in list order,
  then the city's own). Never write them into city.toml between markers: each run would rewrite (and commit) a
  file of hundreds of KB. `city3d stale` flags `tiles_raw` older than an included file.

### Roads and bridges

- Ground roads are buffered to width/2 (resolution 3) and merged **per tile and kind**. Earlier kinds win
  overlaps (major > minor > service > rail). Simplified 0.2 m, draped `ROAD_Y` 1.5 m over the terrain.
- Bridges:
  - a deck per segment, `DECK_T` 1.4 m thick, with a top, soffit and sides, mitred offsets (capped 2×);
  - **pillars** every `PILLAR_STEP` 32 m where the soffit is ≥ `PILLAR_MIN_H` 4.5 m above the ground: 2.2 m ×
    min(0.45·width, 7) m boxes from the ground (with skirt);
  - each deck segment goes to the tile of its midpoint.
- Colours (linear): major 0.10, minor 0.13, service 0.16 grey, rail brownish, concrete 0.42.

### Ground

- `ground.glb`:
  - land, mud, green, water and aeroway, each one mesh: polygons > 50 m² unioned (overlaps drawn and cut once),
    simplified 0.5 m, draped at 0 and **welded**, so pieces of one river are connected again (the water shader
    finds rivers and ponds as connected pieces);
  - positions on **one 16-bit lattice** over the ground area (the 14-bit version gave 4.6 m steps over
    kilometres);
  - normals are the TIN's smooth normals;
  - plus the **backdrop** (float positions, vertex colours); its outline vertices are snapped onto the same
    lattice so the seam is exact.
- `terrain.glb`: the TIN itself (grid indices × 20 m, heights in `TERRAIN_Q` 2 cm steps) for the viewer's
  height lookups.

### glb writer (`write_glb`)

- Every mesh is first reordered with `meshoptimizer.optimize_vertex_cache`, then its vertices by first use. That
  gives better GPU locality and better compression.
- **KHR_mesh_quantization** (in `extensionsRequired`):
  - positions uint16, 14 bits per tile (about 6 cm over 1 km), with the node's translation and scale undoing it;
    padded to 8 bytes per vertex;
  - normals int8, padded to 4 bytes, **stored multiplied by the node's step and renormalized** (three.js scales
    normals by the inverse of a non-uniform node scale);
  - colours RGBA8, normalized;
  - facade texcoords unorm16 of fixed ranges.

  Attributes must be 4-byte aligned.
- The viewer picks each material by **mesh name** (`buildings`, `road`, `bridge`, `land`, `water`, ...), with one
  node per mesh.

### Camera views (`camera_views`) → `tiles.json.views`

- **Areas** (`AREAS`: name → lon, lat, distance m, elevation °): the target is the ground height there.
- **Landmarks** (`LANDMARKS`: menu label → building `name` in the table):
  - target = footprint centroid at base + h/3 if tall (h > √area), else the base;
  - distance = max(350, 2.4 × max(h, √area));
  - elevation 12° if tall, else 30°;
  - "view: no building named X" means the landmark list and the table disagree.

`tiles.json` also holds `origin`, `tileSize`, `extent`, `styles`, `uvRange`, `floor` (the styles' nominal floor
heights), `moduleMax` and `tiles` (file, x, z, size, buildings, triangles, maxHeight).

## 07_pack: meshopt → `tiles/`

- Per buffer view:
  - `EXT_meshopt_compression`;
  - vertex views with `encode_vertex_buffer` (count, stride);
  - index views with `encode_index_buffer`;
  - `encode_vertex_version(1)` and `encode_index_version(1)`, which is about 20 % smaller and read by three's
    `MeshoptDecoder`.
- The original layout becomes a fallback buffer (`EXT_meshopt_compression: {fallback: true}`, no data). The
  compressed bytes live in buffer 0.
- **Round-trip check on every view**: decode and compare, raising on any mismatch. The Python bindings are young
  and have two workarounds:
  - decode indices as **32-bit** even for 16-bit data (the stream is the same; 16-bit output comes back
    mis-shaped);
  - compare triangles **rotated to start at their smallest index**, since the codec may rotate a triangle's
    corners (same winding).
- `ProcessPoolExecutor(8)`; about 4× smaller (279 → 64 MB). Also packs `ground.glb` and `terrain.glb`, and copies
  `tiles.json`.
- The first version used `gltfpack` through `npx`: 2.5 s per call, against 0.05 s for `node cli.js`. It was
  dropped because it discards custom attributes, mesh names and unused texcoords' scale.

## 06b_markings: road surface overlays → `markings/` (+ `markings.json`)

- Tags (lanes, oneway, sidewalk) are re-read from the cached `raw/osm_roads.json`. Strips follow each way's
  centreline, with one quad per segment. Texture coordinates (across + 40, along) / (80, 4,600) in unorm16;
  along wraps at 3,600 m.
- Types (`COLOR_0.r`):
  - `LANES` 0.12 m over the road, or over the deck;
  - `CROSSING` zebra + stop line, 6 m long, at ends that meet another street (zebras on trunk..unclassified);
  - `SIDEWALK` 0.12 m *below* the road level, so another road wins where a sidewalk runs into it. Widths: trunk
    and primary 5, secondary 4, tertiary 3, residential 2.2, unclassified 2 m;
  - `MEDIAN` on the inner side of one-way carriageways (motorway 2.5, trunk and primary 2, secondary 1.5 m);
  - `RUNWAY` 1.3 m (edge, centre, thresholds, touchdown and aiming marks; b = length / 20 m);
  - `PLAZA` for pedestrian streets.
- `dedupe` (off: 0; Paris 0.6): a ground road way lying that share of its length on the carriageway of a wider
  (or as wide, earlier) way is not painted, so OSM's overlapping carriageways don't double the lane dashes.

  `COLOR_0` g/b/a encode half width × 4, `lane_code` (lanes per direction + 16 one-way + 32 big road + 64
  motorway), and per-type flags (the yellow left edge = centre line of two-way roads).
- **Junctions**: OSM nodes where ≥ 3 road segments meet. Ways are split there and each end is cut back by the
  width of the widest other road plus its sidewalk. Pieces under `MIN_PIECE` 20 m between two junctions (inside
  dual-carriageway junctions) get nothing.
- Sidewalks and medians only where they lie **on land** (`wet_area`: sea outside the land polygons, plus rivers
  and ponds, sampled along the strip).
- Draping: `Terrain.drape_triangles(..., tol=DRAPE_TOL 0.03 m)`; deck strips keep the deck height.
- Output is chunked at 400 m per piece; one mesh per tile; positions uint16 with a non-uniform node scale.
  07_pack's encoder is reused (`importlib.import_module("07_pack")`). About 1.1 M vertices, 12 MB.

## 05e_shores: shorelines and pools → `shores/shores.glb`

- The boundary of the visible land (land ∪ green ∪ aeroway − inland water) is split into:
  - **coast**: sea beyond;
  - **bank**: inland water beyond;
  - **mud**: the mud layer beyond;
  - **mudedge**: the mud layer's seaward edge.
- **Types** come from tagged OSM nearby (cached `raw/osm_shores.json`; query: beach/sand/wetland/mud/shoal,
  landuse port/harbour/basin/reservoir, industrial port/shipyard, man_made quay/pier/breakwater/groyne/dyke,
  harbour, marina, water, riverbank, swimming_pool):
  - coast: `revetment` (default: rock armour with a promenade), `quay`, `beach`, `mudflat`;
  - banks: `embankment` (rivers, canals); `pondbank` (soft, where the land beside is green); `pondedge` (stone,
    where it is paved);
  - `pool`.

  Runs shorter than `MIN_RUN` 12 m merge into their neighbour so types don't flicker.
- Each edge becomes bands of quads with (across, along) UVs, e.g. revetment: land band −4..0 m at 0.75 m, slope
  0..5 m down to the sea at −1, toe 5..13 m.
  - The land side is draped on the ground (0 along the coast); the sea side sits at the sea.
  - The widths are the table `BANDS` in shores.py (beach: sand −16..0, slope 0..14, toe 14..26 m; the toe's
    miter at a sharp tip, a groyne or a breakwater drawn as land, reaches twice that). `[shores] bands` replaces a
    type's bands, `[shores] water_side = { beach = 4.0 }` fits everything seaward of the edge into that many
    metres (land side kept), `[shores] islet_max` (m) gives small closed coast loops typed beach `islet_type`
    instead (a 16 m sand strip covered a whole breakwater islet). Both band settings keep TEXCOORD_0's across
    coordinate (u0, u1 per band, default a0, a1) at the original metres, because web/shores.js shades by it (wet
    sand 2..12 m, swash lines at 14..26 m): the same look squeezed into the narrower geometry; the viewer needs no
    change (shores.json's bands are informational, nothing reads them). Off by default, byte for byte
    (tests/test_shore_bands.py). Singapore (M3 critic: glowing sand bleeding 10-20 m into the sea, islets as glowing
    blobs, a pale groyne wedge) uses it.
  - Banks and pools only within the districts + `DETAIL_MARGIN` 600 m.
  - Pools lie level at the highest ground around them.
- **Quay walls** (`[shores] quay_walls`, with `[terrain] quay_walls`; off by default): bank segments of the
  rivers' type whose ground 1-7 m inland stands `quay_min` over the water's level (the commonest TIN height
  inside the pooled water body) become `quaywall` runs: an apron flat at the highest ground under it (+1.3, as
  bank tops) from `quay_face` 1.5 m out in the water to `quay_apron` 8 m inland, a 1 m chamfer down to the ground
  behind, a vertical face from 0.6 m under the water's surface to the apron (its across = metres over the water:
  ashlar courses, the wet foot), and the quay's shadow band on the water. The face stands out in the water so the
  TIN's step never shows in front of it; its winding follows its shading normal (the other bands face up).
  The apron's height is the highest ground within `quay_top` 5 m of the wall (the TIN's quay cell), not across
  the whole apron, and runs are cut into pieces of `quay_step` 4 m: sampling the full 8 m caught the step up to
  the Place du Pont-Neuf behind the Square du Vert-Galant's lower quay and ramped the aprons along the tip's
  long straight edges, an inclined "concrete wedge" over sunken lawns. Paris sets `quay_apron` 5 (two 8 m aprons
  paved the whole tip) and `quay_face` 2.5 (the TIN's quay cells, a staircase on the 5 m grid, peeked out of a
  face 1.5 m out as small triangles every 20-30 m).
- About 0.43 M vertices, 7 MB.

## 08_trees: street trees, class raster, carpet → `trees/`

- **Street trees**: points on both sides of ground-level roads (not motorways or links), `ROW_OFFSET` 2.6 m
  beyond the carriageway edge, every `STREET_STEP` 9 m (palms 1.25×).
  - Dropped on buildings (+2.5 m), roads (+1 m), water, runways and under decks.
  - One species, height and colour **per road** (a street reads as one planting): major roads 14 % royal palm,
    10 % flowering; others 5 % and 8 %; else broadleaf.
  - Stored as int16 deltas split into low and high bytes, height in dm, kind byte.
- **Class raster**: drawn at 4 m, stored at `MASK_CELL` 8 m; a stored cell is kept only if all its fine cells are
  free.
  - Classes: forest, park, orchard, mangrove, scrub, grass, residential, campus, industrial, open.
  - From **re-fetched tagged green areas** (`raw/osm_green.json`; 05_ground merged them untagged) plus 05c land
    use. Smaller areas win (a wood inside a park). Cemetery counts as forest (Chinese hillside cemeteries).
  - The viewer scatters area trees over it (implied: about 11 M trees in a few hundred bytes per tile).
- **Carpet**: wooded classes polygonized from the stored raster and draped on the TIN with heights baked. It is
  the forest floor, and beyond the tree range the forest itself.
- Per 1 km tile gzip; `web/trees` link created by the script. Delta and byte-split encodings roughly halve the
  gzip size.

## 06d_cars: traffic and parking → `cars/`

- Network as in 06b. Ways that simply continue each other are chained (same lanes and direction), then split and
  cut back at junctions like the markings. Lanes sit where the markings paint them. **Driving on the right.**
- Each lane is a loop of cars at spacings in a "free" coordinate. The viewer maps it through a speed profile that
  queues at signalled stop lines.
  - Per class: speed, mean gap, queue factor, mix (sedan, suv, taxi, van, bus, truck, lorry).
  - Density grows with the **activity** field: the floor area around, blurred about 400 m.
  - More lorries near ports (`landuse=port`, `industrial=port`).
  - Buses and lorries keep right.
- Parked cars:
  - kerbside rows on minor and service streets (more in villages and residential areas);
  - OSM surface car parks (`amenity=parking`, not underground, multi-storey or rooftop), stalls 2.5 × 5 m with 6 m
    aisles;
  - bus stations full of buses (3.8 × 13 m).
- Heights: ground (points every 10 m where it bends) or deck. `[cars] deck_ends` (off by default; Paris, London,
  Berlin): where a chain runs from a ground road onto a deck, their shared node takes the deck's height, not the
  ground's: beside a quay wall the ground there can read the river bed (Admiralbrücke: 6.5 m deck, −0.7 m ground)
  and cars sank metres into the deck towards it. Cached `raw/osm_parking.json`. Output per tile gzip:
  225k moving + 260k parked cars, 4.6 MB.

## 06c_rooftops: roof clutter → `rooftops/`

- Imports 06_tiles' own steps (simplify, road clearance, facade style, seed, landmark facades, `plant_room`), so
  every roof matches its tile.
- Per roof: a grid of free 0.5 m cells in the roof's own frame (long axis), minus the parapet (`PARAPET_T`) and
  the plant room.
- A programme per facade style (village, residential, glass, commercial, civic, factory) places items. Landmarks
  get nothing and are listed so the viewer leaves them without parapets.
- Items are stored per roof in its frame; roofs follow a Hilbert curve per tile; 16-bit columns split into bytes.
  About 0.9 M items, 7.8 MB.
- Parapets are **not** stored: the viewer builds them from the tile walls.

## 07b_blocks: 4 km gzipped bundles → `blocks/`

- Per `BLOCK` 4,000 m square: the packed building tiles and markings tiles concatenated, then
  `gzip.compress(level 9, mtime=0)`.
- `blocks.json` lists `[kind, file, offset, length]` per part.
- The viewer unzips with `DecompressionStream('gzip')`. python's `http.server` can't send `Content-Encoding`, and
  it opens a connection per request, which over a network cost more than the bytes. meshopt streams still shrink
  by about a third under gzip.
- Result: 91 files, 42 MB instead of about 1,700 files, 67 MB. The viewer falls back to separate files if
  `blocks/` is missing.

## Serving

- `web/tiles`, `blocks`, `markings`, `trees`, `shores`, `cars` and `rooftops` are **git-ignored symlinks** into
  `../../data/<city>/`, so `web/` alone is served:
  `python3 -m http.server <port> --bind 0.0.0.0 -d demos/<city>/web`.
- Scripts that produce a viewer folder create their link (`link_web()`).

## Checks written to `checks/`

| File | By | Contents |
|---|---|---|
| `report.md`, `heights_scatter.png`, `coverage_maps.png`, `footprints_detail.png` | 03 | source alignment, coverage, height errors by band |
| `buildings.md` | 04 | counts by footprint source, height source and kind; tallest 8; landmark heights applied |
| `quality.md` | 04b | strips, overlaps, height jumps, invalid geometry; worst cells |
| `road_clearance.md` | 06 | dropped footprints per rule |
| `terrain.md`, `terrain.png` | 05a | summits vs survey, TIN log, hillshade |

Rerun and read them after every change to the building or terrain logic. Judge by the numbers across the whole
city, not by one view.
