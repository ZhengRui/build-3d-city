# Porting checklist: setting up a new city

Everything that differs from one city to the next. Work through it top to bottom when starting `demos/<city>/`.
The engine's defaults come from the first reference build (western Shenzhen: a subtropical, coastal, right-hand
traffic Chinese tower city), so every item below names what that default assumed and what other cities needed.
Values given for other cities are starting points: **[believed]** means check at run time.

**Where each item lives now.** The pipeline began as numbered scripts and became the engine (`engine/pipeline/`,
package `city3d`); the old names survive in this list because they are what the lessons were written against. The
stages are modules (`06_tiles.py` → `stages/tiles.py`, `02_gba.py` → `sources/gba.py`), and nearly every value is a
`city.toml` key (the engine README's configuration reference names them: `common.DISTRICTS` → `[districts]`,
`common.UTM` → `utm_epsg`, `05_ground.MARGIN` → `ground.margin`, `06_tiles.AREAS` → `[views.areas]`,
`05a_terrain.PEAKS` → `[terrain.peaks]`, `STYLES` → `[facade.styles]`, ...). Region tables (styles, species, cars,
rooftop items) come from a region preset (`preset = "..."`, `engine/pipeline/src/city3d/presets/`); the driving side
is `drive`, coast vs inland `coast`, the building sources `[sources]`. The engine already handles the paths and
links, the CRS in the index files, the DEM extent, the driving side in markings and cars, and the inland ground:
items about those are kept only as background. Items marked **(viewer)** live in `web/city.json`; the viewer
reference covers them in depth.

## 0. Start a new city

- [ ] **Pick the nearest example** in `examples/<city>/` (the skill's copies of the reference builds' `city.toml` and
  `web/city.json`): a tower city (Hong Kong, Singapore, Tokyo, New York) or a European block city (Paris,
  London, Berlin); coastal or inland; left- or right-hand traffic. Copy its configuration, never its data.
- [ ] Make the city folder in the layout of SKILL.md ("Project layout"):
  - `demos/<city>/city.toml` (from the example), `pyproject.toml` (the three lines in the engine README; name and
    description your city), `README.md`, `REPORT.md` (`running-a-build.md` has its shape);
  - `checks/` (written by the pipeline), `data/` (landmark research), `scripts/` (city-only scripts, named
    `m<N><x>_<what>.py` after the milestone that needed them), `generated/` (TOML that scripts write, listed in
    city.toml's `include = [...]`), `eval/` (screenshots and measurements, git-ignored);
  - `web/city.json` (from the example), the tracked relative links `web/index.html` and `web/engine` to the skill's
    `engine/viewer/`, and a `.gitignore` listing the data links that `link_web` makes (tiles, blocks, markings,
    trees, shores, cars, rooftops, lamps).
- [ ] Data folder `demos/data/<city>/raw/`, git-ignored; each download with a `README.txt` (source, licence, vintage).
- [ ] Replace what names the example city:
  - `city.toml`: districts, CRS, sources, margins, views, peaks, the region preset, the User-Agent for Overpass;
  - **(viewer)** `web/city.json`: `storagePrefix` (each city its own, or settings leak between cities on one
    origin), `title`, `nativeTitle`, `about`, the sun and time keys (§11);
  - reset what must not carry over: `[views]`, `[terrain.peaks]`, landmark CSVs, `[[structures]]`, the example's
    `generated/` includes.
- [ ] Decide which source stages apply. The example may use region-only sources (Shenzhen: the East Asia footprints,
  CNBH heights, GBA; Tokyo: PLATEAU; Hong Kong: LandsD and the CEDD LiDAR). Use the city's official data where it
  exists (`data-sources.md`); a new source is an adapter in `engine/pipeline/src/city3d/sources/` with the same output
  contract: footprints with `h` (m above ground), `source`, and tags where known.
- [ ] Run order as in `data-pipeline.md` (`uv run city3d all`; `08_trees --green-only` runs before `05a_terrain`).
- [ ] `uv sync` in the new folder; `meshoptimizer ≥ 0.2.30a0` is required by the pack stage.

## 1. Area, boundary, projection

- [ ] **`[districts]`** (was `common.DISTRICTS`): name → OSM relation id. Select by id, never by name. Admin levels differ per
      country; find them with Overpass `is_in(lat,lon); rel(pivot)["boundary"="administrative"]; out tags;`
      at a known point and pick the level that gives the units you want. Values [believed]:

  | City | Units | admin_level |
  |---|---|---|
  | Shenzhen | 区 districts | 6 (used) |
  | NYC | boroughs | 5 |
  | NYC | community districts | not admin (NYC Open Data) |
  | London | boroughs | 8 |
  | London | City of London | 8 |
  | Paris | arrondissements | 9 |
  | Paris | city | 8 |
  | Berlin | Bezirke | 9 |
  | Berlin | Ortsteile | 10 |
  | Tokyo | special wards 区 | 7 |
  | Hong Kong | 18 districts | 6 |
  | Singapore | URA planning areas: not OSM admin; use the data.gov.sg planning-area polygons | — |
  | San Francisco | city-county (one polygon) | 6 or 8; neighbourhoods from DataSF "Analysis Neighborhoods" |

  If the units are not OSM relations, write `boundary.gpkg` from the official polygons instead of
  `01_osm.boundary()`.
- [ ] **`utm_epsg`** (was `common.UTM`; Shenzhen used `EPSG:32650`, UTM 50N). Shenzhen is actually in zone 49; 50N was used and is fine at a
      zone edge. Use `gdf.estimate_utm_crs()` or:

  | City | CRS |
  |---|---|
  | NYC | 18N **32618** |
  | San Francisco | 10N **32610** |
  | London | 30N **32630** (or BNG 27700 to match the EA LiDAR) |
  | Paris | 31N **32631** (or Lambert-93 2154) |
  | Berlin | 33N **32633** (ETRS89 25833 for the Berlin data) |
  | Singapore | 48N **32648** (SVY21 3414 for local data) |
  | Hong Kong | 50N **32650** (HK1980 2326 for LandsD data) |
  | Tokyo | 54N **32654** (JGD2011 plane IX 6677 for PLATEAU) |

  A metric CRS other than UTM works too; the scene frame only needs metres, x east, y north.
- [ ] `LEVEL_H` 3.2 m (storey height for `building:levels`). Consider 3.0-3.3 m
      residential and about 4 m offices. For Paris Haussmann blocks about 3.2-3.5 m [believed]. For NYC
      `heightroof` is given, so levels are rarely needed.
- [ ] Margins:
  - `05_ground.MARGIN` 4 km (ground area)
  - `05b_roads.MARGIN` 1 km (roads)
  - `05b_roads.GROUND_MARGIN` and `08_trees.GROUND_MARGIN` (keep = 05_ground)
  - `08_trees.URBAN_MARGIN` 1 km
  - `05a_terrain.FAR_REACH` 36 km

  Size them to what the skyline views should see.

## 2. OSM fetching for big cities

- [ ] `01_osm.buildings()` fetches one district per query. That was fine up to about 45k buildings per query.
      For large, dense districts (Manhattan ~ 45k, Brooklyn ~ 330k, Tokyo wards, all of London ~ 3 M
      [believed]):
  - split by sub-unit relations or a bbox grid of about 2-5 km, and dedupe by `osm_id`;
  - or skip Overpass: download a Geofabrik or BBBike `.osm.pbf` extract and read it with `pyosmium`,
    `osmium tags-filter` + `ogr2ogr`, or `quackosm` or `pyrosm` [believed]. This is more robust for anything over
    a few hundred MB of answer.
- [ ] The bbox queries in `05_ground`, `05c_landuse`, `05b_roads`, `05e_shores`, `08_trees.fetch_green` and
      `06d_cars.fetch_parking` cover the whole ground area in one request. For a city many times Shenzhen's
      density, tile them the same way. Keep `[timeout:900]` and the `remark` check.
- [ ] Always compare feature counts with the last run. A partial answer can look complete.
- [ ] Mirrors in city.toml's `overpass` list change over time; test them at the start. For a big city run a local
      Overpass instead (`scripts/local-overpass.sh`, `data-sources.md`).

## 3. Building sources and the building table (`04_buildings.py`)

- [ ] Footprint priority for the city:
  - **official footprints + heights** (NYC, SF, Paris APUR/BD TOPO, Berlin LoD2, PLATEAU, HK LandsD);
  - then OSM;
  - then Overture/Microsoft/Google/GBA only to fill gaps.

  Rewrite `choose_footprints` accordingly. The OSM → compact GBA → East Asia chain is for data-poor cities.
- [ ] **A primary (official) footprint layer rules only where it has data**: give it `districts = [...]` in its
      `[sources.<name>]` table when the scene reaches beyond it. With NYC's official layer primary everywhere,
      OSM only filled its gaps, and tall OSM buildings outside New York City were dropped as "probably
      demolished": every tower in New Jersey went. Beyond those districts OSM is the footprint source, whole.
- [ ] A region with no official heights (New Jersey): Overture's **lidar** heights by OSM id
      (`[sources.overture]`, "overture" in `heights`), never its ML heights (`data-sources.md`).
- [ ] **Units**: NYC `heightroof`/`groundelev` are **feet** (× 0.3048). A roof height above ground vs an
      absolute elevation: subtract the ground, and check against a known building.
- [ ] LoD2 sources give eave/ridge or measured height: pick `measuredHeight` or the max roof point for
      extrusion. Note that pitched roofs are then flat-topped at ridge height, which overstates volume; see §7.
- [ ] Per-footprint LiDAR heights where no attribute exists: the DSM − DTM 90th percentile (towers) or median
      (low-rise) inside a footprint shrunk by 1 m.
- [ ] `OSM_MAX_AREA` 5,000 m² and `BIG_BUILDING_TAGS`: estate outlines are a Chinese-compound pattern. In
      European block cities big OSM polygons are often whole perimeter blocks mapped as one building: check a
      few before dropping.
- [ ] `drop_osm_containers`, `DUP_SHARE` 5 %, `ALIGN_CELL` 2 km: keep them if a second footprint source is
      merged; skip alignment when there is only one source.
- [ ] `classify()` thresholds and kinds: `village` (12-40 m, < 450 m²) is the Chinese urban village. Rename or
      re-threshold for local types: rowhouse/brownstone (NYC), terraced house (London), Haussmann block (Paris),
      Altbau/Plattenbau (Berlin), HDB slab (Singapore), 雑居ビル and wooden houses (Tokyo), tong lau and composite
      buildings (HK). Update `OSM_KIND`.
- [ ] Height blend (`0.35·GBA + 0.65·CNBH` in 15-30 m): China only. Re-derive per city from the by-band error
      table of `03_compare.py`, or drop it.
- [ ] `common.load_osm`: keep dropping `location=underground` and `layer<0` everywhere. Tokyo, HK and Paris have
      many underground stations and malls mapped as buildings [believed].
- [ ] `MIN_H` 3.5 m, the default 3 storeys: fine anywhere.
- [ ] Landmark figures and structures: go through `buildings-and-landmarks.md` §5 (coordinates, seating, neighbours,
  bridges on the drawn deck, glows on the footprint, a look at the user's camera).
- [ ] Landmark lists `data/landmarks*.csv` (glob): new research per city (`buildings-and-landmarks.md` §3a). NYC,
      Tokyo and HK have hundreds of 150 m+ towers: cap by area and keep `use_height` strict.
- [ ] `06_tiles.road_clearance`: essential for satellite footprints. With official or complete OSM footprints it
      drops little; keep it for the ML-filled gaps only.

## 4. Terrain (`05a_terrain.py`)

- [ ] DEM tiles (Copernicus GLO-30, 1° each): the ones covering the ground area **and the backdrop** (the engine
      derives the extent from the tiles you list).
- [ ] Local LiDAR DTM available (EA, IGN, 3DEP, Berlin DGM1, GSI, HK): use it for the ground grid.
  - Skip building masking, opening and canopy subtraction (it is already bare earth).
  - Keep smoothing light (the city's streets are real now); keep the TIN.
  - Keep GLO-30 for the backdrop.
  - Mind the datum: Newlyn, NGF-IGN69, NAVD88, EGM2008. The sea plane at 0 must meet the local mean sea level.
- [ ] `PEAKS`: named summits and surveyed heights for `checks/terrain.md`. Examples: Twin Peaks and Mt Davidson
      (SF), Montmartre (Paris), Primrose Hill and Parliament Hill (London), Teufelsberg (Berlin), Victoria Peak
      and Lion Rock (HK), Bukit Timah (SG).
- [ ] `SEA_DROP`/`SEA_KNEE` (5 m total) exist because reclaimed coastal land sits a few metres above the scene's
      sea at 0. Re-tune from the DEM at the waterfront (NYC and SF piers; HK reclamation), or set small values
      where the DTM is accurate.
- [ ] **Inland cities** (Paris, Berlin; London's Thames is tidal but inland):
  - there is no `natural=coastline` in the area, and `05_ground.land_from_coastline` then returns **no land** (the
    single face gets no votes): special-case it to return the whole area;
  - `coast_ramp` and the sea knee do nothing useful: skip them;
  - the river is inland water: level each water body with `inland_water` and check the Seine/Spree/Thames aren't
    held at one level along kilometres (FLAT_SPREAD 4 m rejects sloping rivers, which then follow the ground);
  - the viewer's sea plane must not flood low ground: its height must sit below the lowest land (viewer).
- [ ] `CANOPY` per class (forest 5 m ...): tuned for subtropical evergreen forest over a DSM. For temperate
      deciduous parks 3-4 m forest [believed]; zero with a DTM.
- [ ] `BUILDING_PAD` 12 m, `OPEN` 50 m, `OPEN_FILL`: tuned to GLO-30's 30 m pixels and Shenzhen's block sizes.
      Very dense cores (Manhattan, central HK) are almost all masked, and the fills then come from 750-1,500 m
      windows. That is fine on flat ground, poor on HK's slopes: use a LiDAR DTM there.
- [ ] `TIN_ERROR` 4 m, `TIN_ERROR_FAR` 12 m: for steep cities (HK, SF) expect many more triangles. Check the
      count in the log and raise the far error first.
- [ ] Buildings on steep slopes (HK, SF): the base is the lowest ground plus a 1 m skirt, so hillside buildings
      bury uphill. Consider a terraced pad (flatten the TIN under footprints) or the mean ground plus a deeper
      skirt.

## 5. Ground, water, shores (`05_ground.py`, `05e_shores.py`)

- [ ] `GREEN` tag list: fine globally. Clipping green to the land matters wherever reserves are mapped over water.
- [ ] Mud layer and mangroves (`natural=mud`, `wetland=tidalflat`, `wetland=mangrove`): tropical and
      subtropical coasts only (HK, Singapore). Empty elsewhere is fine.
- [ ] Aeroway default widths 60/23 m; `city.json` **`ground.airportHeading`** (154.3° for Shenzhen's runway)
      (viewer): set per airport.
- [ ] `05e_shores.py` shore types:
  - default coast = `revetment` (rock armour with a promenade on reclaimed land) is Shenzhen's;
  - NYC and SF: piers and bulkheads (`quay`) dominate;
  - HK: seawalls and quays;
  - Singapore: revetments and beaches (East Coast);
  - Paris: stone **quays** (the Seine's banks: embankment → quay style with ramps);
  - Berlin: canal and river walls;
  - London: Thames embankment walls plus tidal mud at low tide [believed].

  Adjust `BANDS`, the default type and `classify_features`.
- [ ] `SEA_Y` −1, `COAST_TOP` 0.75: tied to the viewer's sea plane.

## 6. Roads and markings (`05b_roads.py`, `06b_markings.py`)

- [ ] `LANE_W` 3.5 m (US 3.6-3.7 m; Europe 3.0-3.5; Japan 3.0-3.5) and `DEFAULT_W` per class (tuned to Chinese
      arterials, e.g. primary 18 m). Tune from a few measured streets per city.
- [ ] `width` tag parsing (`number()`) takes the first number, so `"12 ft"` is read as 12 m [believed to occur
      in the US]: convert units.
- [ ] `LAYER_H` 7.5 m, `GRADE` 0.05: fine generally. Stacked interchanges in HK and Tokyo need layer 2-4
      honoured (they are).
- [ ] **Driving side.** Right in Shenzhen, NYC, SF, Paris and Berlin. **Left in London, Tokyo, Hong Kong and
      Singapore.**
  - `06b_markings.py`: lane assignment ("traffic towards the start junction drives against the way: on its
    left"), median side, yellow edge flag.
  - `06d_cars.py`: lane offsets `forward from the right kerb`, "buses and lorries keep right", parked row
    headings.
  - **(viewer)** nothing: `cars.js` follows the lanes; the markings' centre-line colour is `city.json`'s
    `markings.centreColour`.

  All of it follows city.toml's `drive = "right" | "left"`.
- [ ] **Line colours and conventions** (`lane_code`, "yellow left edge", ground.js; viewer):
  - yellow centre line on two-way roads: China, US;
  - white: UK, most of Europe, Singapore, HK [believed];
  - Japan: white centre lines, yellow where overtaking is banned [believed].

  Also: zebra style (UK zebras with Belisha beacons; Paris wide white bars; Japan ladder crossings), stop-line
  placement, bike lanes (red in Shenzhen; green in NYC and SF [believed]; red asphalt in Berlin and Paris
  sometimes), and `SIDEWALK_W` per class.
- [ ] `ZEBRA`, `BIG`, `MEDIAN_W` sets: classes match OSM worldwide; widths local.
- [ ] Tram tracks in streets (Berlin, Paris): `railway=tram` is drawn as a rail strip beside the road; consider
      embedding it in the carriageway (viewer and markings).
- [ ] **Suspension bridges: centre OSM's carriageways** on the towers' line. OSM's two roadways needn't be
      symmetric about it, while the towers, cables and trusses (`[[structures]]`) are: the Brooklyn Bridge's lay
      at −7.7 and +9.0 m, 11.6 and 8.4 m wide, so its central promenade stood over one of them. The structure's
      `roadways = { centre, width }` moves them to ± centre between the anchorages (05b_roads; markings, cars
      and trees follow).

## 7. Facades and roofs (`06_tiles.py`; viewer: `engine/viewer/facade.js`, `styles/<preset>.json`)

- [ ] **Start from a preset and the catalogue** (`references/facade-catalogue.md`): pick the nearest regional preset
      pair (pipeline `presets/<preset>.toml`, viewer `engine/viewer/styles/<preset>.json`; china-south, us-northeast,
      europe-west, uk-london, de-berlin), or make a new pair with `base` on it; set `preset` in city.toml and
      `facade.preset` in city.json. List the region's building types (below), map each to a style built from the
      catalogue's basics and core features (bay, window box, shops, cornice, rustication, balcony rows, brick
      courses, shopfronts, glazing...); write a library pattern (`facade/patterns.js`, named by architecture) only for
      what none of them draws. `pytest tests/test_viewer_presets.py` checks every assigned style has viewer data.
- [ ] `STYLES` (floor heights, palettes) and `OSM_STYLE`, `facade_styles()` rules: Shenzhen vernacular (glass
      towers, tiled residential towers, urban villages, factories). Define local styles from photo research
      (`buildings-and-landmarks.md` §3c general-palettes section). Examples:
  - NYC: brownstone, pre-war brick with setbacks, glass towers, cast-iron SoHo
  - Paris: Haussmann limestone with mansard roofs and balconies
  - London: brick terraces, Portland stone, glass towers
  - Berlin: Altbau stucco, Plattenbau panels
  - Tokyo: tiled mid-rises, 雑居ビル with signage
  - HK: dense residential slabs with tiny windows, AC boxes, tong lau
  - Singapore: HDB slabs with colour bands and void decks
  - SF: Victorian bay-window houses, pastel stucco

  `facade.js` reads the style names from `tiles.json` and each style's data (bay, window box, shops, groups,
  features) from the city's viewer preset (`city.json` `facade.preset`, `engine/viewer/styles/<preset>.json`,
  keys in `styles.js`); a new style name takes the defaults until a preset (or `facade.styles` in city.json)
  describes it, or its parent's data when it is a variant of another (`extends`; the defaults left New York's
  `crowned` towers without windows). Start a region's preset with `base` on the nearest one. Air conditioners and
  refuge floors: a style's `ac` (or `city.json` `facade.acUnits`), `facade.refugeShare`.
- [ ] **Flat roofs everywhere** is a China and modern-city assumption. Pitched roofs dominate London, Paris
      (mansards), Berlin and SF houses.
  - Options: import LoD2 roofs (Berlin, PLATEAU LOD2, NYC 3D model);
  - or add a procedural gable or mansard profile per style (`extrude` profiles are a start: `0:1 0.8:1 1:0.6`
    with an inset reads as a mansard);
  - and adjust `06c_rooftops.py` (no parapets on pitched roofs).
- [ ] `PLANT_MIN_H` 24 m, `PLANT_MIN_AREA` 250 m²: fine generally.
- [ ] Landmark facades CSV: new per city. Styles `fins`, `bands`, `lattice`, `honeycomb` and `panel` exist in the
      shader; add others only when a landmark needs them.
- [ ] `05c_landuse.USE` mapping: universal OSM tags. In cities with complete OSM building tags it matters less.
      In Singapore the URA Master Plan land use is better than OSM [believed].

## 8. Trees (`08_trees.py`; viewer: `engine/viewer/trees.js`)

- [ ] `GREEN` class mapping: `landuse=cemetery → forest` is a Chinese-hillside assumption. Western cemeteries are
      park-like (→ park); Tokyo cemeteries are dense with trees in places.
- [ ] Street-tree species and odds (major roads: 14 % royal palm, 10 % flowering; others 5 % and 8 %) and heights
      (broadleaf 7-14 m, palms 11-16 m). By climate [believed]:
  - NYC: London plane, honey locust, pin oak, linden; deciduous (leafless in winter: pick a season with the sun's
    declination)
  - Paris: plane trees along boulevards, horse chestnut, lime
  - London: London plane dominant
  - Berlin: linden (Linde), maple, chestnut; very many street trees
  - Tokyo: ginkgo, zelkova, cherry
  - Singapore: rain tree, angsana, palms; very dense
  - HK: banyan, Chinese banyan, palms, flame of the forest
  - SF: few street trees (London plane, ficus, Brisbane box), Monterey cypress and eucalyptus in parks
- [ ] `STREET_STEP` 9 m, `ROW_OFFSET` 2.6 m, `NO_STREET_TREES` classes: Shenzhen lines nearly every road on both
      sides. Many cities line far fewer streets (SF, Tokyo side streets, HK old districts). Add a per-class
      probability of being planted at all.
- [ ] Tree inventories: `[trees.street.census] sources` reads several (CSV or GeoJSON, own heights with 0 = unknown,
      crown-diameter-only sets like the Hauts-de-Seine cadastre vert, `dedupe` between them); `cover` keeps
      invented area trees out of parks and cemeteries the inventory lists (>= per_ha) and away from listed trees.
      Inventories miss state gardens (Paris: Tuileries, Luxembourg): those keep invented park trees.
- [ ] Mangrove class: tropical coasts only.
- [ ] **(viewer)** species set and leaf atlas in `engine/viewer/trees.js` (banyan, camphor, acacia, Bauhinia,
      mangrove, royal and coconut palm): add the local species to the engine; deciduous crowns need a season. The
      class mixes are `city.json` `trees.classes`.

## 9. Cars (`06d_cars.py`; viewer: `engine/viewer/cars.js`)

- [ ] `TYPES` dimensions:
  - taxi = BYD e6 (Shenzhen); NYC yellow Camry/Prius-size sedans and minivans; London black cab (TX); Tokyo JPN
    Taxi (tall, dark navy/black); HK Toyota Comfort/Crown taxis; Singapore various; Berlin ivory Mercedes/Toyota
    [believed];
  - bus: BYD K8/K9 12 m. **Double-deckers** (London red, HK, Singapore; about 4.4 m tall) need their own type;
  - lorry: 40 ft container.
- [ ] `PALETTES`:
  - car colour mix: Chinese white/black/silver-heavy. US more varied and larger (SUV and pickup share up); Japan
    many white and kei cars.
  - taxis: Shenzhen blue-white 62 %, red 26 %, green 12 %. NYC yellow; London black (and liveries); Tokyo mixed
    company colours; HK **red urban / green New Territories / blue Lantau**; Singapore blue, yellow, black and
    others by company [believed].
  - vans: SF Express / JD Logistics liveries → local couriers (UPS brown, Royal Mail red, Yamato ...).
- [ ] `CLASS` table (free-flow speed, gap, queue factor, mix per highway class): tune speeds to local limits. The
      mix: no container lorries in central Paris; many buses in London and HK.
- [ ] **No box trucks parked, or on small streets** (`parked_mix` and the tertiary and lesser classes' mixes in
      `[cars]`; the presets still park a few): on New York's narrow streets one parked or crawling truck filled
      the view and read as the road being blocked (the user's feedback). Keep them on the arterials and
      highways (New York's truck routes).
- [ ] Use the data where OSM has it (Paris M6, all off by default): `maxspeed_factor` (free flow from maxspeed),
      `osm_parking` (parking:left/right/both decide a side), `kerbside_major`, `no_kerbside` (expressways,
      bus-lane avenues by name), `restricted_mix` (motor_vehicle=destination;permit streets: buses, taxis,
      scooters), `psv_density` (bus-only ways such as a bus bridge). Two-wheelers (18 % of Paris's traffic) are
      a `moto` type; Europe's cars are hatchbacks (`hatch` model, ~4.1 m), not US saloons.
- [ ] Ports list: from OSM `landuse=port` / `industrial=port` (`fetch_parking`). Fine anywhere; inland cities
      have none.
- [ ] Parking: stall 2.5 × 5 m, aisle 6 m (US stalls about 2.7 × 5.5 m [believed]); kerbside parking frequency
      (villages "most"). In NYC and Paris nearly every kerb is parked; in Tokyo almost none (no kerbside parking
      culture) [believed].
- [ ] `SEED` fixed; `PARK_PITCH`, `LANE_MIN`: fine.

## 10. Rooftop clutter (`06c_rooftops.py`)

- [ ] `PROGRAMME` per style. **China- and urban-village-specific**: stainless and blue plastic water tanks on
      stands, evacuated-tube solar water heaters, blue corrugated lean-to sheds, tiled stair-box "hats", potted
      plants, helipad markings on residential towers over 100 m (a Chinese fire-code look). Local equivalents
      [believed]:
  - NYC: **wooden water towers** on pre-war roofs, bulkheads, HVAC, setback terraces
  - Paris: zinc roofs, **chimney pots** in rows, dormers, skylights (Velux)
  - London: chimney stacks, slate and tile pitched roofs, roof terraces
  - Berlin: pitched tiled roofs, solar PV, green roofs on new builds
  - Tokyo: water tanks, cubicle AC units, **billboards**, golf nets, small shrines
  - HK: rooftop squatter huts, water tanks, masts, huge signs on older blocks
  - Singapore HDB: water tank enclosures, lift motor rooms, rooftop gardens
  - SF: pitched roofs and flat roofs with small decks
- [ ] `south_k(roof)`: solar heaters and panels **face south**. Southern hemisphere: north. Singapore (1.3° N):
      panels near flat, any azimuth.
- [ ] `NAMED` colours (tank blue, shed blue ...): local palette.
- [ ] Parapets: built by the viewer from walls; none on buildings with a roof shape (the rise in `uv2.y`).
- [ ] Roof shapes: items on the flat top only, stacks from the eaves along party walls (materials-and-realism §10).

## 11. Sun, sky and time (viewer; listed for completeness)

All in `web/city.json` (`engine/viewer/README.md` has every key and its default):
- [ ] `location.latitude` (22.54) and `sun.declination` (−10) or `sun.date`: a season when the city looks its best
      and trees are in leaf. Hours are local solar time unless `time.utcOffset` (and `time.zone`, the label) makes
      them clock time: New York shows EDT (−4), whose clock runs about 45 minutes ahead of the sun there in
      October (solar noon ≈ 12:43). For Singapore the noon sun is near the zenith. `time.presets` (Dusk 18.05 in
      Shenzhen; `null`: the hour the sun is 4.5° down). **Judge dusk by the sun, not the clock:** New York's
      "dusk" shots at 18:00 EDT were before sunset (18:23 on 10 October); use the Dusk preset.
- [ ] `camera.azimuth` (200: south-south-west of the target, so the afternoon sun lights the facades seen) and
      `night.moon`: both default to the other side in the southern hemisphere.
- [ ] `night.schedule` (offices lit late: "overtime is common in Shenzhen"); `water.windFrom` (225: "before the
      summer monsoon from the south-west"), `water.sea`/`inland` colours (the Pearl River estuary's);
      `haze.density` (Shenzhen haze vs clear Berlin air), `sky`; `ground.lawn`; `night.skyGlow` (warm brown
      under sodium lamps, grey-mauve under white LED). Still in the engine: red-soil bare lots.
- [ ] **Shenzhen's conventions leak into a new city** unless switched off, each in `city.json` or the region
      preset. New York turned off:
  - green bike bands on wide sidewalks, tactile paving, flower beds, tree pits: `markings.sidewalk`
    (`bike: null`, `tactile: false`, `flowers: false`, `pits: false`);
  - tiled stair-box "hats" and village roofs on rooftops: the region preset's rooftop programme;
  - banyans' aerial roots: `trees.species` (`banyan.shape.roots: 0`, or local species);
  - orange sodium streets: `ground.sodium` (New York 0.08 / 0.03: nearly all white LED), `ground.streetLight`;
  - far haze thinning over hills: `haze.thinHeight` (New York 1e7: off).

  Go through `engine/viewer/README.md`'s keys once with the new city's photos beside you rather than waiting for
  each to be noticed.

## 12. Camera views

- [ ] `06_tiles.AREAS` (name → lon, lat, distance, elevation) and `LANDMARKS` (label → building `name` exactly as
      in the table). Choose postcard views: waterfront skylines, the CBD, an old district, the airport, a hill
      view. Refresh with `06_tiles.py --views-only`.

## 13. Licences and README

- [ ] README "Licences" lists every dataset. Flag non-commercial ones (GBA LoD1 polygons and heights, FABDEM).
      ODbL share-alike applies to derived databases from OSM, Overture and GBA-ODbL.
- [ ] README "Sources tried and dropped" with why (saves the next person the same dead ends).
- [ ] **(viewer)** `city.json` `about`: what is real (footprints, heights, roads, terrain) and what is invented (facades,
      trees, cars, rooftop clutter).
