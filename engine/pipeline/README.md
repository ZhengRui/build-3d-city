# city3d: the build-3d-city data pipeline

The data half of a build-3d-city reconstruction as an engine: open data in (OSM, footprint datasets, a DEM),
the viewer's tiles out (glb tiles, ground, terrain, markings, shores, trees, cars, rooftops, blocks). A city is
a folder with a `city.toml`, not a copy of the code. The defaults were tuned on western Shenzhen, the first
city; seven later cities' `city.toml` files are in `../../examples/` (start a new city from the nearest one of the
same type). Every stage is described in `../../references/data-pipeline.md`.

Default layout, relative to the project root: the skill at `.agents/skills/build-3d-city/`, a city's config at
`demos/<city>/` (city.toml, pyproject.toml, scripts/, generated/, checks/, web/) and its data at
`demos/data/<city>/` (`paths.data`, default `../data/<name>` from the city folder; git-ignored, raw downloads in
`raw/`).

## Use

```sh
cd demos/<city>                 # holds city.toml, and a pyproject.toml depending on this engine
uv run city3d list              # the stages, and the order `all` runs them in
uv run city3d all               # the whole pipeline
uv run city3d 06_tiles          # one stage
uv run city3d 06_tiles --views-only
uv run city3d config            # the resolved settings as JSON (engine defaults < preset < city.toml)
uv run city3d stale             # the viewer's layers older than the data they were made from (run after any single stage)
```

The city's `pyproject.toml` is three lines plus the source (the path is relative to the city folder: change it
if the skill or the city lives elsewhere, then `uv sync`):

```toml
[project]
name = "<city>"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["city3d"]

[tool.uv]
package = false

[tool.uv.sources]
city3d = { path = "../../.agents/skills/build-3d-city/engine/pipeline", editable = true }
```

## CLI

| Command | Does |
|---|---|
| `city3d <stage> [args]` | one stage, by its familiar name: `01_osm`, `02_gba`, `02b_eastasia`, `02_arcgis`, `02_<name>` (a source read by the `file` adapter), `02_dem`, `03_compare`, `04_buildings`, `04b_quality`, `05_ground`, `05a_terrain`, `05b_roads`, `05c_landuse`, `05e_shores`, `06_tiles` (`--views-only`), `06b_markings`, `06c_rooftops`, `06d_cars`, `07_pack`, `07b_blocks`, `08_trees` (`--green-only`) |
| `city3d all [--from S] [--to S] [--skip S,S] [--min-free GB]` | everything in order, each stage in its own process; prints each stage's time and peak memory and writes them to `checks/runtimes.md`. `--min-free` waits before a stage until its usual peak (`stages.PEAK_GB`) plus that many GB are available: for a machine shared with browsers and other jobs |
| `city3d list` | the stages and the run order |
| `city3d config` | the resolved settings |
| `city3d stale` | every layer (tiles, markings, shores, trees, cars, rooftops, blocks) whose index is older than one of its inputs (buildings, roads, terrain, ground; for 06_tiles also the `include` files, which hold [[structures]]), with the stage to run again; 07b_blocks runs it at the end. A stage run on its own leaves the ones after it stale: rooftop items keep the old building bases and float (New York) |
| `city3d verify --against DIR [--data DIR] [--checks DIR --against-checks DIR] [--ignore GLOB,...]` | compare the city's products with another copy (below) |

Options before the command: `--city PATH` (a city.toml or its folder; default: found from the working
directory upwards, or `$CITY3D_CITY`), `--overpass-cache DIR` (record every Overpass answer there and
replay it on later runs; for checking a change against the same OSM data).

Run order of `all`: `01_osm` → the footprint sources' stages (`02_gba`, `02b_eastasia`, `02_arcgis`, `02_<name>`)
→ `02_dem` (DEM adapters that fetch) → `03_compare` (when a footprint source besides OSM has heights) → `04_buildings` → `04b_quality` → `05_ground` → `05c_landuse` → `08_trees --green-only` →
`05a_terrain` → `05b_roads` → `06_tiles` → `07_pack` → `06b_markings` → `05e_shores` → `08_trees` →
`06d_cars` → `06c_rooftops` → `07b_blocks`. The green-only run caches OSM's green areas, which the terrain
takes its canopy allowance from; the full `08_trees` needs the terrain and the roads.

## Package layout

```
engine/pipeline/
  pyproject.toml, uv.lock        dependencies (geopandas, shapely 2, rasterio, scipy, meshoptimizer >= 0.2.30a0 ...)
  src/city3d/
    cli.py                       the city3d command
    config.py                    loads city.toml over the preset over defaults.toml
    defaults.toml                every setting with its default and a comment (the reference below)
    common.py                    the city's paths and CRS, Overpass (with record/replay), OSM helpers,
                                 Terrain (the ground TIN every stage stands things on), weld, best_match
    stages/                      one module per stage (the numbered scripts of old): osm, compare,
                                 buildings, quality, ground, terrain, roads, landuse, shores, tiles, markings,
                                 rooftops, cars, pack, blocks, trees; __init__ maps names and run order
    sources/                     regional data source adapters: gba (+ GBA's own join script,
                                 gba_lod1_reference.py), eastasia, cnbh, copernicus, arcgis (an ArcGIS
                                 FeatureServer layer), overture (lidar heights by OSM id), usgs3dep (US
                                 bare earth), ign (France's LiDAR HD / RGE ALTI bare earth), geotiff (any
                                 local elevation GeoTIFF, any CRS), file (any vector file, configured per
                                 source in city.toml)
    presets/                     region presets: <name>.toml (tables) and <name>/ (code), see "Region presets"
    verify.py                    city3d verify
    stale.py                     city3d stale
  tests/test_inland.py           a synthetic inland town through every stage (uv run pytest tests)
  tests/test_district_clip.py    [districts] clip: inline ring (same Overpass query text) and GeoJSON file (Polygon, MultiPolygon, errors)
  tests/test_file_source.py      the file adapter and two primary layers in their own districts
  tests/test_citygml_source.py  the citygml adapter on a synthetic LoD2 tile (a gabled building, a building of two parts)
  tests/test_citygml_plateau.py the citygml adapter's flavour "plateau" on two small PLATEAU-style meshes (tests/fixtures/plateau/)
  tests/test_roof_split.py      the citygml adapter's opt-in roof_split: a tower on its podium cut by roof level
  tests/test_dem_ground.py      04_buildings' split_ground and landmarks ground = "point" on a tiny sloping DEM
  tests/test_geotiff_dem.py      the geotiff DEM adapter (a web-mercator raster) through 02_dem's named points,
                                 and a file source's height expression over `area`
```

Each stage reads its settings once at import (`CFG = config.get()`, then module constants as before), so
the stage code reads like the scripts it came from. Outputs, file names and formats are unchanged: the
viewer's contract (`tiles.json`, glb mesh names and attributes, the binary tile formats) lives in the stage
docstrings. The data folder is `paths.data` (default `../data/<name>`), reports go to `checks/`, and stages
that make a viewer folder link it into `web/` (`web/trees -> ../../data/<name>/trees`).

## Configuration reference

`defaults.toml` holds every key with its default and a one-line comment; this is the overview. Tables merge
key by key (city over preset over defaults); lists and values are replaced whole. Keep a value's type: `3.0`
where a float is shown (some values reach JSON the viewer reads).

### Generated settings (`include`)

A script that writes figures into city.toml (the [[structures]] of a landmark script) rewrites a file that is
hundreds of KB, and every run is a commit that the repo's readers pull again. Instead, the script writes its
own file (`demos/<city>/generated/structures-<name>.toml`, git-tracked, with a header saying so) and city.toml
names it in an opt-in top-level key, before any table:

```toml
include = ["generated/structures-m4h.toml", "generated/structures-m10f.toml"]   # paths relative to the city folder
```

Each included file is plain TOML with the same keys as city.toml; it may not include others. The files are laid
UNDER city.toml, in list order, with city.toml on top (`config.merge_layers`):

- arrays of tables (`[[structures]]`, `[[structures.glazing]]`...) are appended: the included files' entries
  first, in list order, then the city's own. So a city's hand-written [[structures]] stay in city.toml and come
  after the generated ones (the order is kept: it is the order the structures are built in);
- tables merge key by key; a key set in more than one file is the later one's: city.toml beats the includes, a
  later include beats an earlier one (a conflict is not an error, so keep a key in one file);
- plain lists and values are replaced whole (as everywhere).

The resolved settings (`city3d config`) do not contain the `include` key, only the merged result: a city that
moves a block out of city.toml into an include, in the same order, resolves to the byte-identical settings.
`config.sources()` lists the files read. A missing include is an error naming it (run its script first).
`city3d stale` treats the included files as inputs of the layers that read [[structures]] (`tiles_raw`, 06_tiles):
one rewritten after the tiles were built makes them stale. (05b_roads reads the structures too, for the named
bridge decks: run it again after changing those.)

**City** (top level)

| Key | Default | Meaning |
|---|---|---|
| `name` | required | short name: data folder `demos/data/<name>`, glb `generator` strings |
| `title` | `name` | readable name in reports |
| `preset` | `"china-south"` | region preset |
| `include` | none | files (city-folder-relative) that scripts write, laid under city.toml: see "Generated settings" below |
| `utm_epsg` | required | metric CRS of every computation (a UTM zone: 326xx N, 327xx S) |
| `level_h` | 3.2 | metres per storey |
| `coast` | `"auto"` | `true`: land from `natural=coastline`; `false`: inland; `"auto"`: inland without a coastline / sea |
| `drive` | `"right"` | driving side (`"left"` mirrors lanes, parking, medians, stop lines) |
| `generator` | `"3D-Fun {name}"` | glb generator prefix |
| `user_agent` | `"3D-Fun {name} reconstruction (hobby project)"` | HTTP User-Agent: set your own, with a contact (Overpass and data hosts ask for one) |
| `overpass` | three public mirrors | tried in turn |
| `[districts]` | required | name = OSM relation id, or `{ relation = id, clip = ... }` for the part of a relation inside a clip: a ring `[[lon, lat], ...]`, or (opt-in) a path `"data/districts.geojson"` (relative to the city folder, or absolute) to a GeoJSON FeatureCollection (WGS84) whose Feature with `properties.name` = the district's key is the clip, a Polygon or MultiPolygon: keeps generated outlines out of city.toml; a missing file or name stops with an error naming both (`stages/osm.py`, `tests/test_district_clip.py`) |
| `[paths]` | `data = "../data/{name}"`, `checks = "checks"`, `web = "web"`, `landmarks = "data/landmarks*.csv"`, `landmark_facades = "data/landmark_facades.csv"` | relative to the city folder |
| `[sun]` | `latitude = 0.0`, `declination = 0.0` | the viewer's sun; the pipeline takes the hemisphere (solar panels face the equator) |

**Sources**

| Key | Default | Meaning |
|---|---|---|
| `sources.footprints` | `["osm"]` | footprint sources in order: `osm`, then adapters `gba` (role blocks), `eastasia` (role pieces), `arcgis` (role primary), or any name with a `[sources.<name>]` table `adapter = "file"` (below) |
| `sources.heights` | `["landmark", "osm_height", "osm_levels", "default"]` | height sources by priority: also `blend`, a footprint source with heights (`gba`), `cnbh` |
| `sources.<name>.districts` | all | the districts a footprint source covers; beyond them OSM is the footprint source, whole (a primary layer ruling everywhere dropped every tall OSM building outside it as "demolished": New Jersey's towers) |
| `sources.overture.release`, `.datasets` | `"2026-09-23.1"`, `["USGS Lidar"]` | height source `overture`: Overture's heights by OSM id, only from these sources (its Microsoft ML heights collapse on towers); OSM levels win where 1.5× taller (built since the lidar) |
| `sources.dem`, `sources.backdrop` | `"copernicus"`, `""` (= dem) | DEM adapters of the ground and the backdrop: `copernicus` (a global surface model), `usgs3dep` (US bare earth), `ign` (France), `geotiff` (local files) |
| `sources.geotiff` | `ground` [], `backdrop` [] (= ground), `bare` true, `note` "" | any local elevation GeoTIFFs (paths in raw/), in their own CRS: 05a_terrain warps them onto its UTM grid, nothing is prepared or fetched (02_dem checks they exist and reports them); `bare` false for a surface model; `note` a line for checks/dem.md. An entry may be `{path, shift}` (a file or glob with a vertical shift in m added wherever it is read, 05a_terrain and 02_dem's report: a coastal city's datum offset, Hong Kong's mPD − 1.30 m = mean sea level, without a prepared copy; each run of one CRS and one shift is warped on its own; none set: as before) or `{archive, members (globs), ext}` (`shift` too): the rasters inside a zip (nested zips too), read in place through /vsizip/. Files in several CRSs are warped run by run, an earlier entry's data winning (a national DTM fills only where the first ends). London: Carbon & Place's web-mercator mosaics of the EA lidar DTM, OS Terrain 50's ASCII grids beyond (M7) |
| `sources.<name>` with `adapter = "file"` | | a footprint source read from a local vector file (GeoPackage, GeoJSON, shapefile...; `sources/file.py`), stage `02_<name>`: `path` (in raw/, or a list), `layer`, `crs`, `url` (fetched when missing), `role` ("primary"), `districts`, `height` (a field, or an expression such as `"where((b_igh == 'O') & (h_max >= 60), h_max, h_med)"`), `height_scale`, `keep`, `rename` (e.g. a ground altitude as `ground_elevation`, which 03_compare checks against the DEM), `drop` ({field = [values]}), `label`, `mean` (a mean height over the polygon, as `height`, column h_mean: the test of [buildings.spikes]; London: `"volume / area"`). The `height` expression may use `area` (the footprint's m²; London: a mean height from Carbon & Place's `volume`). Several primaries each rule in their own `districts` (Paris: APUR in the arrondissements, BD TOPO in La Défense); a primary's heights reach every other footprint it covers too |
| `sources.<name>` with `adapter = "citygml"` | | a footprint source read from CityGML LoD2 tiles (`sources/citygml.py`; Berlin's LoD2 CityGML 1.0, any AdV state's), stage `02_<name>`: file's keys (role, districts, height (default `measuredHeight`), keep, rename, drop, label, lend) plus `path` (glob patterns in raw/; zips are read member by member in place) and `crs` (the tiles' horizontal CRS). Tiles are parsed one at a time, one cityObjectMember at a time (0.9 s and ~0.1 GB per 28 MB Berlin tile). A row per solid (a Building without parts, or each BuildingPart; a parent's function and generic attributes reach its parts): `gml_id`, `parent_id`, `part`, `function`, `roofType`, `measuredHeight`, `ground_z` (lowest GroundSurface z), `roof_top_z`, `eave_z`, `roof_area`, `n_roof`, `n_wall`, every gen: attribute; footprint = the union of the GroundSurfaces (the roofs' 2D union where there are none, `fp_from` "roof"). The 3D roof and wall surfaces are not kept yet. Tiles may be `.gml.gz` (read in place); CityModel members, the appearance block too, are dropped while streaming. `flavour` (default `""`: as above, unchanged): `"plateau"` reads Japan's PLATEAU CityGML 2.0 + i-UR (FY2023-25): lat/lon/h posLists projected from `crs` (default `"EPSG:6668"`; 6697 works too) to the city's UTM per solid; LoD2 surfaces only (LoD3 twins ignored); LOD1-only buildings get footprints from `lod0FootPrint`, `lod0RoofEdge` or the `lod1Solid`'s bottom (`fp_from` says which) and z values from the `lod1Solid` (column `lod` 2/1/0); fields `usage`, `class`, `storeysAboveGround`, `storeysBelowGround`, uro's `detailedUsage`, `buildingStructureType`, `fireproofStructureType`, `buildingRoofEdgeArea`, `surveyYear`, `lod1HeightType`, `lodType`, `buildingID` (-9999/9999 = unknown), English `<field>_name` columns from the embedded standard codelists (`sources/plateau_codelists.json`); rows deduped by `gml_id` across files (ward datasets repeat border meshes); in a ward zip only `udx/bldg/*.gml`. Use `height = "where(isnan(measuredHeight), roof_top_z - ground_z, measuredHeight)"`: measuredHeight is missing (-9999) where `lod1HeightType` is 0 (~6 % of central Tokyo, small structures). `roof_split` (default `{}`: off; Tokyo M2): a LoD2 solid with roofs at several levels (a tower and its podium drawn as one Building) becomes a row per level: `{ min_area 300, tol 3, rel_tol 0.08, min_part 40, min_width 2, cover 0.8, max_parts 12 }` (any key given turns it on with the rest at these values), columns `roof_level` (0 = highest; NaN: not split), `roof_levels`, gml_id `<id>#r<k>`, parent_id the Building; a level's height is `roof_top_z - ground_z` |
| `sources.ign` | `crs` "EPSG:2154", `ground`, `fill`, `backdrop` (raw/ paths), `layers`, `cells`, `cell` 5.0, `pit_below` 15, `pit_diff` 8, `pit_grow` 1.5, `unbake` 10, `unbake_grow` 2, `unbake_open` 200 | France's bare earth: LiDAR HD MNT for the ground, its voids and pits filled from RGE ALTI, RGE ALTI for the backdrop; fetched from the Géoplateforme WMS-Raster when missing, warped to UTM (`raw/ign_ground.tif`, `raw/ign_backdrop.tif`) |
| `sources.gba.tile` | `""` | GBA 5° tile, e.g. `e110_n25_e115_n20` |
| `sources.eastasia.url`, `.region` | Zenodo 8174931, `""` | archive and path prefix (`China/Guangdong/Shenzhen`) |
| `sources.cnbh.file` | `""` | CNBH-10m tile in `raw/` |
| `sources.copernicus.tiles` | `[]` (all in raw/) | e.g. `["N22_00_E113_00"]`; their extent limits the backdrop |

**Stages**

| Section | Keys (defaults) |
|---|---|
| `[osm]` (01) | `area` true: a district's buildings and parts by Overpass `area()`; false: by the district polygon's bounding box, kept where they meet the polygon (the same set; for a server without areas: Berlin's local Overpass); both off by default (the gpkg columns are then exactly as before): `underground_drop` true (01 also keeps the `underground` and `level` tags; load_osm and the building:parts drop outlines with `underground=yes`, `location=underground\|indoor` or a `level` entirely < 0, besides `layer` < 0: malls, passages, stations), `min_height` true (01 keeps `min_height` / `building:min_level` on buildings too; 04 builds a building with one from there to its height, as a part: the MBS SkyPark on its towers, sky bridges; such a deck is never a duplicate of the towers it overlaps, nor an estate outline, nor a roof for what lies under it, nor a landmark's building); `min_height = "decks"`: only deck-like ones are raised (`building=bridge`, a name with bridge / deck / sky park, or half over two or more buildings reaching its underside), the rest (towers with `building:min_level` over a podium ring) stand on the ground |
| `[buildings]` (04) | `min_h` 3.5, `min_piece` 12 m², `default_floors` 3, `osm_max_area` 5000, `big_building_tags` (terminal, stadium, halls...), `dup_share` 0.05, `align_cell` 2000, `osm_kind` {} (preset), `needle` {cover 0.3, height 40, area 250, share 0.4}, `blend` {sources [gba, cnbh], weights [0.35, 0.65], band [15, 30]}, `join` {weighted 0: > 0, a footprint no polygon covers by needle.cover takes the area-weighted median of the polygons covering that share of it}, `spikes` {sources []: a lidar-maximum source's tops that are a chimney or a neighbour's edge, lowered to OSM's height/levels or the mean × mean_scale; needs the source's `mean`}, `fill` {} (a fill source's polygons: min_area, min_h, skip_tags, not_in OSM areas such as landuse=construction; never on osm_skip'd or excluded OSM outlines), `exclude_inside` false (what lies inside an outline excluded by id goes too); M2 London fix round, all off by default: `keep` {osm: [ids]} built whatever osm_skip or the estate rule say, `part_outlines` (share: an OSM outline its building:parts cover is one building at any size), `container_inner` (a building inside a dropped estate outline stays), `surface_layers` (layer < 0 kept where location=surface or a fill polygon covers it), `water` {path, deck} (fill and layer ≥ 1 OSM pieces over water stand on a deck), `volume_dedupe` (pieces overlapping on the map and in height clipped), `join.big` (m²: big footprints without a height take whatever polygons touch them), `spikes` `alone_ratio`/`alone_mean`/`alone_min_h`/`body_tags`/`body_scale`/`caps`/`podium` (despike(), split_podiums()), `landmarks` `raise_parts`, `cap_keeps_lift`, `max_d`, `min_area`; M2 Berlin, all off by default: `rules` [] (a primary source's footprints by field values or prefixes, height and area, first match wins: drop, keep (no min_piece or strip rule: a cadastre's small building parts), exact (and its own height, not floored) or roof (a canopy drawn as its roof, raised from under its eave); a fill source's polygons by the rules naming it; what a primary's rules drop no other source fills), `keep` with a primary (the OSM building is built over it, which is clipped round it, no fill_max_h), `parts_in` [ids] (only these OSM buildings' building:parts), `dedupe_keep_taller` (a smaller, taller footprint inside another stays); Singapore M2, off by default: `lift_parts = "gaps"` (`true`: Paris's rule, unchanged; "gaps": a raised part floats only over a real gap in a low building: thin, nothing of the building on the ground under it or up to its underside, the building's own height known and below it, under half its footprint; its body stays under it at the rest's height: sky bridges over a podium, a stadium's roof rings, not a tower's roof part or crown), `parts_fill_shafts` 0.0 (a ratio: a `part_rest` piece closed by taller grounded parts whose lowest is ratio × its width or more is a shaft, filled to that part: a tower's hollow core); M2 Berlin fix round, all off by default: `own_ground` (a piece with its source's own ground_elevation and roof_top_z is never nested on a taller piece's roof nor stacked over it), `recheck` {of, source, low, ratio, field, values, diff, storeys, storey_h} (a second source with the same footprints over the primary's placeholder heights, at `low` m or less where it is `ratio` x higher, and over its generalised solids (`field` in `values`) more than `diff` m off it, lower only where closer to the storeys), `copied_keep` [sources] (copied() leaves a piece alone where one of them measures the same height) and `copied_storeys` (where none has one, storeys that carry it at 5 m each), `fix_h` {field: {value: m}} (final heights of a primary's pieces), `afloat` {areas, share, h, tag} (OSM fill on water: boats at h m); `station_untagged` "drop" \| "<metres>" (off by default "": OSM building=train_station\|transportation outlines of 150 m² or more with no height or levels, no building:parts inside: dropped like osm_skip's (no fill source builds there), or set to that height after every estimate and never fed to one, h_src station; the underground station boxes and entrance sheds of Hong Kong, Tokyo, Singapore); Hong Kong M2 fix round, off by default: `kind_map` {} ({kind = other}: a preset kind renamed after every other kind rule: Hong Kong's `{village = "midrise"}`), `valid_out` false (buildings.gpkg's geometries make_valid'ed after the reprojection to WGS84); the table gains `eave_h` (eave_z − ground_elevation, where the piece keeps its source's top) when the source has eave_z |
| `[quality]` (04b) | `second` "" (h_<second>: pieces at 5 m or less it puts over 2× higher, and over 8 m off it), `storeys` "" (pieces under storeys × `storey_min` 2.5 m); with roof_top_z and ground_elevation in the table, pieces over their own solid's top + 1 m (stacked) are counted too |
| `[compare]` (03) | `detail` [] = [lon, lat, name] of the footprint close-up |
| `[ground]` (05) | `margin` 4000 (also the roads' and trees' fetch area), `green` {leisure, landuse, natural: values}, `aeroway_width` {runway 60.0, taxiway 23.0}, `pools` false (split the water at dams, weirs and locks: each pool levelled on its own), `gravel_parks` [] (parks by name drawn as layer `gravel` round their mapped lawns), `paths` {}, `paved` false (with `paths`: stone pedestrian areas as layer `paved`, asphalt ones as `asphalt`, instead of the land's lots), `path_relations` false (pedestrian multipolygon relations are areas too), `green_min_width` 0 (m: narrower green pieces left out), `masses_tall` {} ({area, h}: footprints of `area` m² or more over `h` m held at h: a tower and its podium in one OSM outline, Tokyo's CO·MO·RE Yotsuya 145 m over 10,570 m², stood as a block-wide slab), `masses_within` "" (06e_masses: a GeoJSON of WGS84 polygons, a path from the city folder; only masses inside their union are kept, whole buildings by a point inside, and OSM is fetched only over the chunks that touch it; `cover_buildings` paints only inside it too; Singapore's land-side band, Tokyo's gaps; "": off, the whole margin); Singapore M5, off by default: `yards` [] (OSM "key=value" areas, e.g. `industrial=port`, drawn as paved yards on the aeroway layer, kind "yard": concrete panels instead of the land's lots, no trees, parked cars lifted with it; cached as osm_yards.json); Singapore M5 fix round, off by default: `green_tags` [] (more green areas by tag combinations, "a=b;c=d", e.g. `leisure=pitch;surface=grass`), `green_ids` [] (OSM elements drawn as green, "way/<id>" or "relation/<id>": the Padang, a cricket field with no surface tag); both cached as osm_green_extra.json in the data folder |
| `[landuse]` (05c) | `use` {"key=value": use} |
| `[terrain]` (05a) | `spots` {name: [lon, lat, expected m]} (02_dem's named points besides the peaks), `work` 10.0, `tin_cell` 20.0, `building_pad` 12.0, `open` 50.0, `open_fill`, `canopy` {forest 5.0, park 3.0, orchard 3.0, scrub 1.0}, `smooth_open` 45.0, `smooth_town` 120.0, `sea_drop` 3.0, `sea_knee` 2.0, `coast_flat` 40.0, `coast_ramp` 160.0, `flat_spread` 4.0, `water_flat` 25.0, `water_ramp` 90.0, `bank_slope` 0.35, `water_all_touched` true, `tin_error` 4.0, `tin_error_far` 12.0, `tin_error_edge` 0.5, `tin_error_bank` 0 (off) within `bank_reach` 40.0 of levelled water, `far_from` 1500.0, `far_over` 4000.0, `far_cell` 200.0, `far_reach` 36000.0, `back_error` [6.0, 30.0], `sea_y` -3.0, `datum` "auto" (inland), `water_levels` {} ({name: [lon, lat, level]}: the water body holding the point held at that scene level whatever the ground under it reads, even over `flat_spread`; Tokyo: the tidal Sumida and canals, which the 5 m DEM reads 0.5-2.5 m, at the sea's 0), `patches` [], `patches_file` "" (a GeoJSON of WGS84 polygons, path from the city folder, re-filled as `patches`: generated ones; Hong Kong's LiDAR excavations under buildings built since), `pits` {} ({below, grow, window}: dry pits in a bare-earth DEM, seeded by a cell under `below` m and reaching as far as the ground lies `grow` m under its closing over `window` m, re-filled from their outlines; `max_raise` (off): a hole deeper than this under its outline is left alone; checks/terrain.md lists the five largest; London: the Tideway shafts and basements; `keep_ways` [] highway/railway values and `keep_len` 50: a pit holding that many metres of such a ground-level way is a cutting, left alone; Berlin: the A100's trough), `deck_ends` {} ({reach 12, ramp 20, landings []} or true: bridge abutments, the ground under a road deck's end raised to the level of the ground roads it meets (each road's line 8-20 m on carried back to the node), easing back along them; 05b_roads then ends the deck on the ground at the node; `landings`: footbridges whose free ends take the highest dry ground within 10 m), `back_peaks` false (the named summits beyond the ground area pinned in the backdrop at their surveyed heights), `dem_window` false (true: `dem_on` reads each CRS's run of DEM tiles only over the grid it fills, plus 2 cells, and keeps one float32 copy; cells no tile covers are NaN, not merge's 0; false merges the whole run at its finest resolution first: Hong Kong's 2 m LiDAR mosaic and the territory's 5 m DTM in one CRS merged 64 x 48 km at 2 m, 02_dem 10.2 GB; true: each run merged into a temporary tiled GeoTIFF in the data folder over the grid's bounds, on its own pixel grid, and warped from it in chunks: 02_dem 1.8 GB, 05a_terrain 1.9 GB; the grids equal the default's to 1e-3 m in tests where the tiles share a pixel grid), `cover_buildings` false (06e_masses: the town's footprints painted into the inner cover map; with masses_within only those inside the clip; "all": every OSM footprint over the inner map, its own cache cover_buildings.gpkg: Tokyo's painted town round two gaps), `edge_land` false (true: the cells within 3 of the ground area's outline take the land/sea of the cells further inside; without it a coastal city's land edge is ramped to 0 m over the coast's 200 m all round the area, leaving pyramids where the backdrop meets it: Singapore M3), `cover_yards` (off; Singapore M5: [r, g, b] sRGB, the `[ground] yards` areas painted into both land cover maps, not WorldCover's built-up town: container terminals past the ground area), `peaks` {name: [lon, lat, surveyed m] or [lon, lat]} |
| `[roads]` (05b) | `margin` 1000, `layer_h` 7.5, `rail_layer_h` 0 (a railway's first layer; 0: layer_h; London 9.5: tracks on top of the brick arches OSM maps as buildings), `grade` 0.05, `lane_w` 3.5, `default_w` {highway: [two-way, one-way]} (preset), `footbridges` false, `decks` {name: height or {deck, lower, rail_lower, water, reach, level_on (a bridge outline's name: the span held level at its highest over it, the approaches down at `grade`)}}, `decks_ref` "ground" ("water": a named deck counts from the lowest ground under its span), `decks_level` false (with `decks_ref` "water": from the level of the water under the span, not its lowest ground, which with `[terrain] quay_walls` lies 6 m under it by the walls), `decks_ease` [] (named decks whose non-pinned nodes are raised so none lies more than `grade` x distance under a neighbour: a span climbing to a higher bank's road at the grade, not a step), `bridge_ways` [] (OSM way ids counted as bridges though not tagged so: Tower Bridge's roadway through its towers, tunnel=building_passage), `built_only` {} ({margin, keep}: ground-level ways cut `margin` m beyond the districts and the masses' clip (`[ground] masses_within`), railways, decks and the `keep` highway values running on to `margin`; Tokyo, masses only in two gaps: streets, street trees and cars ran 1-2 km across the painted town), `span_ways` {} ({span: [OSM way ids]}: elevated ways taking a decks span as if it were their bridge:name, `"<span> lower"` its lower level; Tokyo's Rainbow Bridge, whose lower deck's roads and Yurikamome carry no bridge:name), `rail_join` false (an unnamed elevated railway between ways of one rail decks span takes it), `rail_on` {} ({field, values, near 2, gap 80, step 10}: railway decks on the building table's viaduct structures' tops, no stick piers inside them; Berlin's Stadtbahn arches), `piers` {span: {..., upper, arcade = {bay, pier, wall, rise, colour}}} (the upper ways on a brick arcade over the pavement: the Oberbaumbrücke's U1) |
| `[tiles]` (06, and the tile grid of every later stage) | `size` 1000, `plant_min_h` 24, `plant_min_area` 250, `plant_h` 3.6, `pillars_in_water` (bridges on piers in the water, or only on land), `clearance` {major 0.3, minor 0.6, deck 0.5, any 0.55}, `roof_eave` false (Berlin M4: the preset's roof shapes rise from the table's `eave_h`, the LoD2's eaves, where it lies 1-6 m under the top, not from the height; de-berlin turns it on), `small_exact` false (Berlin M10 fix round: pieces a `[buildings] rules` row keeps at their exact height, `h_exact`, are drawn down to 0.2 m², not skipped under 4 m²: the Holocaust Memorial's 2.4 m² stelae) |
| `[blocks]` (07b) | `size` 4000: the square (m) whose building and markings tiles go into one gzipped block, the viewer's download unit; smaller blocks let the first view wait for less (Paris 2000) |
| `[views]` (06) | `areas` {name: [lon, lat, distance, elevation(, azimuth(, lift(, hour)))]} (hour: a dusk or night preset; choosing it moves the menu's time there, and `?view=` starts at that hour unless `?time=` is given), `landmarks` {label: building name or [name, azimuth(, distance(, elevation))]}, `groups` {menu group: [view names]} (areas are "Areas", landmarks "Landmarks" otherwise; the menu shows Areas, these groups in order, then Landmarks), `group_order` (false: a group's chips in `areas`' order; true: in its `groups` list's order) |
| `[facade]` (06) | `styles` {style: {floor, palette}} (facade.js finds them by name), `osm_style` {style: [tags]} (preset); `zones` {style: {polygon}} (buildings touching it) or {name: {style, polygon}} (buildings whose inside point is in it) |
| `[markings]` (06b) | `big`, `zebra` (highway classes), `sidewalk_w`, `median_w` (preset); UK options (defaults.toml); `setts` [] (OSM surface values drawn as granite setts), `sidewalk_style` {} (highway -> share of ways with sidewalk style 1: Berlin's mosaic-and-slab Gehweg), `trams` false (railway=tram as grooved rails over the roads, bed asphalt/setts/grass/ballast; `{setts, road_w, off_w}`) |
| `[shores]` (05e) | `detail_margin` 600, `coast_type` "revetment", `bank_type` "embankment" (rivers and canals; "pondedge": stone coping and face, masonry quays such as Paris's), `pond_edge_area` 0 (km²: lakes and reservoirs this large take the stone edge all round, beside lawns too; Singapore's Marina Bay), `quay_walls` false, `step_walls` false (the steps from lower to upper quays under stone blocks: `step_reach` 70, `step_slope` 32, `step_min` 2, `step_close` 3, `step_top` 7), `bands` {} and `water_side` {} (per shore type: replace its bands `{ beach = [[a0, a1, y0, y1, slope(, u0, u1)], ...] }`, y in metres or `"coast_top"`, `"sea"`, `"toe_sea"`, `"mud"`, `"bank_top"`, `"bank_foot"`, `"pool"`; or fit everything seaward of the edge into a few metres, `{ beach = 4.0 }`, the shader's across coordinate unchanged so the sand is shaded the same, squeezed; off = the built-in widths byte for byte), `islet_max` 0 (m: a closed coast loop this small, typed beach, takes `islet_type` "revetment") |
| `[trees]` (08) | `urban_margin` 1000, `building_gap` 2.5, `road_gap` 1.0, `green` {"key=value": class} (preset), `landuse` {use: class}, `street` {`step` 9.0, `row_offset` 2.6, `none_on` [...], `default` "broadleaf", `odds` {major/minor: [[species, cumulative share]]}, `height` {species: [min, max] or {major, minor}}, `census` {file, lon, lat, dbh, species, height, groups, districts; `species_bits` 2, `sources` [...] (several inventories: CSV or GeoJSON, `height_field`, `latlon`, `sep`, `jitter`, `dedupe`), `cover` {per_ha, cells, classes}, `crown_field` (crown diameter caps the crown), a source's `street`} (defaults.toml)}, `none_on_paved` false (no invented trees on the paved and asphalt squares), `none_on_layers` [] (nor on these 05_ground layers: Tokyo's `["gravel"]`, Kokyo Gaien's plaza and paths), `none_extra` [] (OSM "key=value" areas with no tree at all, census or invented: London's rail land and platforms; cached in the data folder), `height_q` 10 (street-tree heights stored in 1/height_q m: 10 caps them at 25.5 m), `clip_walls` {} ({gap, min}: crown radius capped at the distance to the nearest footprint + gap, stored per tree), `squares` {} (tags, named, area, per_ha, step, inset, height, group, inner, inner_group: rings of invented tall trees in named garden squares the census leaves bare), `lift_flag` false (only trees on the drawn street surface take the viewer's streetLift: trees.json liftBit; Berlin), `census_off_decks` false (no census tree under an elevated way), `street.named` {} (Singapore M6, opt-in: {road name: {species, height [lo, hi], step, rows [offset or [offset, height factor]], first}}: named avenues with a planting of their own, several rows each side (a lower second row: Orchard Road's double canopy), `first` the viewer's first broadleaf slot) |
| `[cars]` (06d) | `seed`, `parking_margin` 1000, `types`, `palettes`, `class`, `link_speed`, `parked_mix`, `kerbside` (preset), `twin_limits` false (a one-way carriageway of a dual road drawn closer than its width stops at its share of the gap to the other one: London), `bus_routes` {} ({min, split, dd, dd_refs, dd_share, networks, skip}: buses only on OSM's route=bus ways, a double-deck type on the routes named; any type named bus_* counts as a bus), `trams` {} ({modules, gap, speed, spacing}: trains of module types on OSM's railway=tram tracks, the track's direction from its partner; Berlin); class mixes and parked_mix shorter than `types` leave the later types out |
| `[rooftops]` (06c) | `named` {colour: hex}, `parapet_t` {style: m} (preset), `parapet_default` 0.25, `stack_cols` / `pot_cols` ([name, weight] of `named`: europe-west's chimney stacks and pots), `stack_cap` false (europe-west: a cover slab in a `pot_cols` colour on each stack instead of a row of pots, the stack at most `stack_cap_len` 1.6 m long; Berlin); china-south's programmes, Singapore M6, off by default: `helipads` (false: none), `residential` ("hdb": lift motor rooms, a raised water-tank housing, PV rows), `village` ("shophouse": a box now and then, condensers, plants) |

What stays in code on purpose: the viewer's contracts (tile size and formats, `CLASSES` of the tree raster,
the street species ids, rooftop prototypes and materials, facade texture ranges, layer heights such as
`ROAD_Y`), and algorithm constants that are not city-specific (grid steps, simplification tolerances,
junction cut-backs).

## Landmark facades and massing

`data/landmark_facades.csv` (06_tiles `landmark_facades()`): `name, facade, tint, module, variant, profile[,
whole][, take][, roof], notes`. `profile` is a massing profile for a single footprint and/or directives on a
landmark made of parts, separated by `;` (heights in metres over the building's base):

| Entry | Does |
|---|---|
| `0:1 0.9:1 1:0.8` | lofts through height fraction : scale about the centroid (`f:k:d` also moves the outline in by d m) |
| `dome:f`, `shell:f:d`, `anti:f` | quarter-ellipse dome; inset shell; square antiprism turning 45 degrees |
| `long:f:sl:sw ...` | scales by sl along the footprint's long axis and sw across it: a wedge or trapezoid in side view (`long:0:1:1 1:0.1:0.6`), a gable roof (`long:0:1:1 1:1:0.02`) |
| `lean:b:f:s ...` | scales by s along compass bearing b (degrees) about the footprint's far side opposite it, which stays vertical: a wedge (the Leadenhall Building `lean:180:0:1 1:0.15`) |
| `shape@m:<profile>` | the largest part whose top is m (to 0.6 m) lofted through the profile from its own base (a landmark of OSM parts otherwise keeps their massing) |
| `crown@m:<profile>[:#hex]` | the tallest (largest of equally tall) body cut at m; the piece above lofted as a crown (spire style: no windows, its roof its own colour), coloured #hex |
| `crown@m-top:<profile>[:#hex]` | the same for every body part `top` m high (to 0.6 m); a part already starting at m is reshaped whole (a nave's roof piece) |
| `tops@m:<p1>\|<p2>` | the tallest spire parts (one per profile, lowest first) stacked from m, each lofted through its profile |
| `h@a=b` | parts a m high (to 0.6 m) become b m high |
| `lid@m` | a hollow block's lifted parts merged into one lid from m to the top; the walls reaching into it raised to the top |
| `wing@m:<osm id>` | the footprint cut to that OSM building's outline (osm_buildings.gpkg), the rest a wing m high |
| `slot@w:e` | twin towers on one footprint: the largest row split along its long axis by a w m slot, a 4 m bridge across it every e m from 30 m (The Link `slot@9:24`) |
| `base@a=b` | parts a m high (to 0.6 m) start at b m (a piece OSM maps from the ground that belongs over a vault) |
| `roofs@d[/a]:<profile>[:#hex]` | every body part of at least a m2 (30) and more than d + 2 m high: its top d m cut off as a roof (spire style, coloured) lofted through the profile; `0:1:0 1:1:5` moves the outline in 5 m, a hipped roof over any outline, courtyards included (the Palace of Westminster's iron roofs `roofs@7/60:0:1:0 1:1:5:#4a5058`) |
| `fill@m` | one solid top over the landmark's whole outline (holes and gaps under 1 m closed) from m to its top; parts wholly above m go into it, those reaching above m are cut to m (the Arc de Triomphe's attic over its piers and vaults: `base@49.5=29.2;fill@29.2`) |

Order: `wing@`, `slot@`, `h@`, `base@`, `fill@`, `lid@`, `shape@`, `tops@`, `crown@`, `roofs@`. After all rows, `grounded()` checks
every raised landmark part (min_h > 0): it must touch or overlap a part that starts lower and reaches its underside;
one whose highest neighbour below stops short is let down onto it (the Sainte-Chapelle's flèche, drawn
from 47 m over a 42 m roof), a sliver under 1 m2 or a part with nothing under it is dropped, each printed as
`FLOATING landmark part dropped` (Notre-Dame's lightning rods 4 m over its towers). `crown@m-top` skips parts of
that height starting above m (a lantern's tip). Columns: `whole=true` merges the parts into one outline for the
profile; `take` (m) names unnamed buildings and parts whose representative point lies within that distance of the
landmark's outline (holes filled), or lying 90 % inside its convex hull, and the other unnamed parts of their buildings, after it, so its row reaches them (Notre-Dame's towers, the Opéra's flytower);
`roof` is the colour of its spires and crowns (default `#b8bcc0`). `near` ("lon lat m|lon lat m", optional, the last column): unnamed
buildings and parts whose representative point lies within m metres of a point join the landmark first (Tower
Bridge's nameless tower parts, dropped by its `h@` rows for [[structures]] figures). `[facade.zones]` entries
may carry a `tint` (sRGB hex): the zone's buildings take it as their wall colour unless a landmark row sets one,
and keep their roof shapes (the Tower of London's ragstone walls).

## Inland cities

With `coast = false`, or `"auto"` and no `natural=coastline` in the ground area, `05_ground` makes the whole
area land (the coastline vote would otherwise find no land at all). `05a_terrain` then skips the sea knee
and the coast ramp (which would have pulled the ground to 0 along the area's edges) and lowers the ground by
`terrain.datum` (default: its lowest point), so the lowest ground, usually the river, is at 0 and the
viewer's sea plane (-1) stays under everything; the value goes into `terrain.npz` as `datum`. The backdrop
has no sea either. `05e_shores` finds no coast edges, only banks and pools. `tests/test_inland.py` runs a
synthetic inland town through every stage. Paris (the first real one): a river held by dams must be split
into its pools (`[ground] pools`: OSM's dams, weirs and lock gates cut the water, each pool is levelled on its
own: the Seine at 3.55 m through Paris, 0.47 below the Suresnes dam, the canals lock by lock); with a lidar
DTM keep the banks' walls (`water_flat` 0, `water_all_touched` false, `tin_error_bank`) instead of the flat
band and ramp a 30 m DEM needs. Still to check: the viewer's water mirror, which assumes water at sea level.

## Adding a source adapter

A footprint source that is a file (most official layers: GeoPackage, GeoJSON, shapefile, FlatGeobuf, GML) needs
no code: a `[sources.<name>]` table with `adapter = "file"` (the keys above; Paris's `apur` and `bdtopo` are the
examples) makes it source `<name>` with stage `02_<name>`. Anything else (a web service, an archive to unpack,
a format needing its own reading) is a module in `sources/` registered in `sources.FOOTPRINTS`:

- `STAGE = "02_<name>"` and `main()`: fetch or read the raw data, clip it to `common.boundary()`, write
  `<name>_buildings.gpkg` into `DATA`; add the stage to `stages.STAGES` so `city3d 02_<name>` and `all` run it;
- `ROLE`: `"blocks"` (whole buildings from coarse imagery, kept where compact and not duplicating OSM) or
  `"pieces"` (fine footprints filling what is left; `ALIGN = False` to skip the per-cell shift onto OSM);
- `HEIGHTS`: True when it carries heights (`h`); it is then a height source named after it;
- `load()`: its footprints in UTM (`h` in metres above ground when it has heights).

Official footprints with heights (NYC, Paris, Berlin LoD2 (the `citygml` adapter), PLATEAU) are usually best listed first after (or
instead of) OSM as `"blocks"`, with their name first in `heights`. A raster height source is a module with
`sample(g)` registered in `sources.RASTER_HEIGHTS`; a DEM, one with `tiles()` and `extent()` in `sources.DEMS`
(a local LiDAR DTM also wants the building masking, opening and canopy steps of 05a switched off).

## Region presets

Eight, each with a viewer preset of the same name (`../viewer/styles/<name>.json`). `base` builds on another preset
(every table of it holds unless this one sets it); `replace` drops the base's facade styles or OSM style map.

| Preset | Base | For | What it brings |
|---|---|---|---|
| `china-south` | — | western Shenzhen; other southern Chinese cities | the engine's original tables: urban villages, tiled residential towers, glass offices, R&D parks; banyans and palms; BYD taxis; water tanks and solar heaters |
| `us-northeast` | — | Manhattan; Boston, Philadelphia | brownstones, brick tenements, limestone setback towers, cast iron; US street widths; honey locusts and planes; yellow cabs; wooden water tanks |
| `europe-west` | — (started as a copy of us-northeast) | Paris; other Western European block cities | Haussmann, faubourg, HBM, post-war; mansard and zinc roofs from APUR's roof fields; chimney pots and Velux |
| `uk-london` | europe-west (styles replaced) | London | Georgian and Victorian terraces, stucco, Portland stone, mansion blocks, estates, warehouses |
| `de-berlin` | europe-west (styles replaced) | Berlin | Altbau and courtyard wings, Plattenbau, Karl-Marx-Allee, Hansaviertel; the Berliner Dach from LoD2 roof types |
| `sg-singapore` | china-south (osm_style replaced) | Singapore | HDB slabs and point blocks with corridors and void decks, shophouses, condos, colonial civic |
| `hk-hongkong` | china-south (osm_style replaced) | Hong Kong | public estates, tong lau, composite buildings, industrial; kinds per building from Lands Department rows |
| `jp-tokyo` | china-south (styles replaced) | Tokyo | 雑居ビル with vertical signs, tiled mid-rises, mansions, department stores, wooden houses, temples; from PLATEAU usage |

## Adding a region preset

Copy `presets/china-south.toml` and `presets/china_south/` to a new name and change what differs: facade
styles and palettes (the viewer's `facade.js` must know every style by name), OSM tag mappings, road
widths and sidewalks, street tree species and odds, vehicle types, colours, speeds and mix, kerbside parking,
rooftop colours; in code, `building_kind()` (04_buildings), `facade_styles()` and optionally `roof_shapes()`
(06_tiles: "mansard", "pitched" or "berliner" (a 60-degree front slope to a flat top, de-berlin's Berliner Dach) and a roof material per building, europe-west's from APUR's roof fields, de-berlin's from the LoD2's roof type and eaves) and the rooftop
`PROGRAMME` (06c_rooftops: a function per facade style placing items with the helpers in
`stages/rooftops.py`). A city picks it with `preset = "<name>"` and overrides single tables in its city.toml.
`references/porting-checklist.md` lists what is regional.

## Checking a refactor

`city3d verify` compares every product under the data folder (not `raw/`) with a copy made before the
change: identical bytes, or the same content where files carry time stamps (gzip headers, the npz's zip
entries, GeoPackage metadata: compared unzipped, as arrays, or row by row with geometries `equals_exact`
within 1e-6), and `checks/*.md` with times like "(12 s)" masked. Make the reference with the old code on a
copy of the data folder (link `raw/` file by file, copy the rest: stages rewrite their outputs in place),
run the new code on another copy, then `city3d verify --against <old copy>/data/<name> --against-checks <old
copy>/checks`. Stages that ask Overpass (`01_osm`, `05_ground`, `05c_landuse`) can be compared on the same
answers with `--overpass-cache`.
