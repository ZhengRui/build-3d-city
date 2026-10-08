# Data sources

What the first build (Shenzhen) used, what it tried and dropped, and what the seven cities after it used
(section 3; their `city.toml` files are in `../examples/`). Legend:

- **[used]** used in one of the reference project's cities, behaviour observed first hand.
- **[verified 2026-09]** checked on the web while writing this (page exists, licence as stated). URLs and
  licences still change: re-check at run time and record the licence in the city README's "Licences" section.
- **[believed]** from memory or secondary sources; must be checked before relying on it.

Rule of thumb: **official city/national 3D or LiDAR data beats every global ML dataset** where it exists (Europe,
US, Japan, Singapore, Hong Kong). The global ML datasets (GBA, Microsoft, Google, East Asia, CNBH) are for places
without official open data, like mainland China. OSM is always the base for boundaries, roads, water, land use,
names and hand-drawn landmark footprints.

---

## 1. Used in Shenzhen (the first city)

### OpenStreetMap via Overpass [used]

- Everything vector: district boundaries (admin relations), buildings with `height`/`building:levels`/`layer`/
  `location` tags, roads/railways/bridges, coastline, water, green, land use, aeroways, parking, ports, pools,
  shore features. Licence ODbL.
- `common.overpass(query)` posts to mirrors in turn, twice round, 10 s pause after a failure:
  `overpass-api.de`, `overpass.kumi.systems`, `overpass.private.coffee` (`/api/interpreter`). Send a
  `User-Agent`. The main server often answers 429/504.
- **Local Overpass: the default for a big city.** The public servers answer 429/504 under the volume of a
  large city's queries (Paris, 2026: overpass-api.de and Geofabrik unreachable from one network, the mirrors
  504; Singapore, Hong Kong and Tokyo were all built on local servers). `scripts/local-overpass.sh <BBBike city>
  [port]` imports the city's BBBike extract (`download.bbbike.org/osm/bbbike/<City>/<City>.osm.pbf`, 170-240 MB,
  reachable when the Overpass hosts were not) into a `wiktorn/overpass-api` Docker container; put
  `http://127.0.0.1:<port>/api/interpreter` first in `city.toml` `overpass`, the public mirrors after it (the
  engine falls through when the container is down). Area lookups (`area(3600000000+id)`) work; answers matched
  overpass-api.de exactly (Paris 1er: 1,643 buildings) at 3x the speed.
  - Cost: ~15 min per import, ~3 GB RAM peak (capped at 5 GB), Docker volumes of 2-5.5 GB per city. Run **one
    import at a time**, under the pipeline lock (`scripts/lock.sh take pipeline ...`), with at least 6 GB of RAM
    available. Download and place the extract first (the script resumes a stalled download).
  - Three traps (handled by the script): the image reads bz2 XML only (convert the pbf with
    `OVERPASS_PLANET_PREPROCESS: osmium cat -f osm.bz2`); `OVERPASS_FLUSH_SIZE=1` or the import is OOM-killed at
    4 GB; `chmod 755 /db` after init or every query says "Permission denied osm3s_osm_base". Also
    `OVERPASS_STOP_AFTER_INIT=false`.
  - Check that the extract's poly box covers the ground area (districts + margin); BBBike's city boxes can be cut
    to order for a bigger area.
  - Every answer is cached in the city's `raw/overpass_cache/`, so once the OSM stages have run, stop and remove
    the container and its volume (`docker rm -f`, `docker volume rm`); a re-run replays the cache.
  - Public mirrors answer 429/406 without a `User-Agent`, so always send one (`user_agent` in `city.toml`, with
    your contact).
- **Partial-answer detection (important).** A query that runs out of time or memory still returns **HTTP 200**
  with a `remark` like "runtime error: Query timed out" and partial `elements`. It once silently returned an
  **empty Futian district**. `common.overpass` treats any `remark` containing "error" or "timed out" as a
  failure and tries the next mirror. Also compare element counts with the previous download before
  overwriting.
- Query shapes that worked:
  - Buildings per district: `area(3600000000 + relation_id)->.a; (way["building"](area.a);
    rel["building"]["type"="multipolygon"](area.a);); out geom;` with `[timeout:600]`.
  - Everything else by bbox: `[out:json][timeout:900][bbox:s,w,n,e]`. The bbox is the scene's bounding box plus a
    margin.
- One query per district for buildings (22k to 45k buildings each was fine). For huge cities, split further,
  e.g. by sub-district relation or a 5-10 km bbox grid (see `porting-checklist.md`).
- Cache every raw answer (`raw/osm_roads.json`, `osm_green.json`, `osm_shores.json`, `osm_parking.json`). Later
  scripts re-read the cache for tags the gpkg dropped, and a re-run must not depend on a busy server. Delete the
  cache to refresh.
- Select districts by **relation id**, never by name. Names are ambiguous and change. Record the ids in
  `common.DISTRICTS`.
- Coverage in Shenzhen: about 44k OSM buildings in the three districts (Bao'an alone: 22.9k buildings, 8.7 % with
  levels, 0.6 % with height). Good footprints where mapped, and it names the towers, but it has nowhere near all
  buildings. In NYC, Paris, Berlin and Tokyo OSM building coverage is near complete (often imported from official
  data) [believed].
- **Pitfall:** metro stations are mapped as `building=train_station` outlines tagged `location=underground`
  and/or `layer<0`. Kept, they took 70-150 m heights and displaced 826 real buildings above them.
  `common.load_osm` drops them. Keep `layer` and `location` when you fetch.

### GlobalBuildingAtlas (GBA), TUM zhu-xlab, 2025 [used] [verified 2026-09]

- Global building polygons plus ML heights from PlanetScope (3 m) imagery. Hugging Face datasets:
  - `zhu-xlab/GBA.LoD1`: `LoD1/<region>/<tile>.json` holds the heights, keyed by source+id+region
    `{height, var}`, with `-999` meaning no estimate. `Polygon/<region>/<tile>.geojson` holds the non-OSM
    footprints. Licence **CC BY-NC 4.0 (non-commercial)**.
  - `zhu-xlab/GBA.ODbLPolygon`: `<region>/<tile>.geojson` holds the footprints that come from OSM or Microsoft.
    Licence **ODbL**.
  - `produce_lod1.py` in the LoD1 repo is their join script (kept as `produce_lod1_reference.py`).
  - Also mirrored on source.coop (`tge-labs/globalbuildingatlas-lod1`) [verified 2026-09, not used].
- Tiles are 5°×5°. Shenzhen was `asiaeast/e110_n25_e115_n20`: polygons 3.7 GB, ODbL polygons 175 MB, heights
  549 MB.
- Download with `curl -C -` in a retry loop with `--speed-limit 51200 --speed-time 60`. A plain download froze
  for an hour. See `raw/fetch_gba_polygon.sh`. Get sizes first via `POST /api/datasets/<repo>/paths-info/main`.
- **Polygons are EPSG:3857 even when a file claims otherwise**: `set_crs(3857, allow_override=True)`. Clip with
  `pyogrio.read_dataframe(path, bbox=...)`. Stream the heights JSON with `ijson.kvitems`, since it is too big for
  `json.load`.
- `source` values seen: `ours2`, `clsm`, `osm`. Only non-OSM sources test alignment against OSM.
- Quality in Shenzhen (`checks/report.md`):
  - Alignment is fine: median shift +1.8/-0.4 m versus OSM, so no GCJ-02 offset.
  - Heights against 965 OSM-tagged buildings: median abs error 16.9 m, RMSE 38 m, correlation 0.61.
  - For towers of 60 m and over, the correlation is -0.03. GBA cannot rank towers: **tall buildings need the
    landmark list**.
- **Footprint flaw:** 3 m imagery merges urban-village blocks (1-2 m alleys) into blobs that extrude as
  continuous walls. This is why the East Asia footprints were added.

### East Asia 0.5 m building footprints (Zenodo 8174931) [used]

- "A first high-quality vector data of buildings in East Asian countries" (China, Japan, Korea, ...). Mapped from
  0.5 m imagery, **no heights**, licence CC BY 4.0. Shenzhen has 656k footprints.
- It is one **23 GB zip**, but only `China/Guangdong/Shenzhen.*` (about 50 MB) was needed. Read it with **HTTP
  range requests** using `remotezip.RemoteZip(url)`, then `infolist()` and `extract()` on the wanted members
  (`02b_eastasia.py`). The zip's central directory is at the end, so listing costs a few requests. The same
  trick works on any big zip on Zenodo or S3 that supports ranges.
- Flaws:
  - It over-splits single buildings with several roof parts into 2-4 pieces.
  - It sits 4-8 m off OSM, and the offset varies by imagery tile, so it is aligned per 2 km cell.
  - Its extent ends at 113.768 E, cutting off 12 km² of reclaimed land that GBA and OSM fill.
- It keeps urban-village buildings apart, which nothing else does.

### CNBH-10m (Zenodo 7923866) [used]

- China building height raster at 10 m, 2020, UTM 49N, CC BY 4.0. Tiles `CNBH10m_X<lon>Y<lat>.tif`; Shenzhen used
  `X113Y23` (182 MB).
- Sampled per footprint by `common.sample_cnbh`: the median of the covered pixels, else the pixel under the
  centroid.
- Error against OSM by height band:

  | Band | CNBH error | GBA error | Better |
  |---|---|---|---|
  | 15-30 m | **4.7 m** | 7.4 m | CNBH |
  | 60 m and up | 62.8 m | 28.3 m | GBA |

- It saturates at about 40 m, so it cannot see towers.
- Used as a 0.65 weight blend in the 15-30 m band and as a fallback for OSM-only footprints. It is a minor input;
  dropping it would cost little.

### Copernicus GLO-30 DEM [used] [verified-in-use]

- 1 arcsecond **surface** model (roofs and canopy included), heights over EGM2008. Free (Copernicus DEM licence;
  attribution required) [believed: re-check wording].
- Public AWS bucket, no login:
  `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N22_00_E113_00_DEM/Copernicus_DSM_COG_10_N22_00_E113_00_DEM.tif`
  (one 1°×1° COG per tile; the tile name is the south-west corner).
- Summits land within a few metres of survey. It must be turned into bare earth; see `data-pipeline.md` §05a.
- Fetch every tile the backdrop reaches, not just the city. The backdrop in Shenzhen was capped where the two
  tiles ended (23°N).

---

## 2. Tried and dropped

| Source | Why dropped | Lesson |
|---|---|---|
| **CMAB**, China Multi-Attribute Building dataset (Mendeley Data `b4t2wxhn2y` v5, CC BY 4.0) | 7.9 GB download with **no data for western Shenzhen**. The Pearl River Delta tiles run 一 to 七 with no 八. A bounding-box scan of all 3,602 shapefiles (read from the `.shx` headers, without extracting) found one file overlapping Bao'an, on a 108 m strip. | Before downloading a big dataset, check coverage for the actual boundary: index files, bbox headers, sample tiles. Coverage claims ("3,667 cities") hide holes. |
| **3D-GloBFP** (Zenodo 15487037 index, data on figshare) | figshare answers **HTTP 403** to scripted downloads, even with a browser User-Agent and through a proxy. | Probe the download path with `curl -w '%{http_code}'` on day one. If it is blocked, ask the user to download by hand, or drop it. |
| **gltfpack** for tile compression (not data, but a pipeline source of loss) | It drops custom attributes and mesh names, and quantizes or rescales texture coordinates that no texture uses (the facade UVs are metres). | Quantize in your own writer and meshopt-encode with the Python bindings (`data-pipeline.md` §07). |
| Chinese web maps (Amap, Baidu) | Terms of use, plus the GCJ-02/BD-09 offset of 300-500 m. | Fine for eyeballing, never as data. `03_compare.offset` checks that a dataset has no such offset. |

---

## 3. Other cities

Pick per city, in this order: official 3D or LoD2 → official footprints plus height attribute → official
LiDAR DSM minus DTM sampled per footprint → OSM heights and levels → global ML heights. Always also: OSM for
roads, water, land use and names; a hand-checked landmark list for the skyline (`buildings-and-landmarks.md`).

| City | Buildings (footprints + heights) | Terrain | Notes |
|---|---|---|---|
| **New York** | NYC Open Data **Building Footprints** (`data.cityofnewyork.us`, id `5zhs-2jue`) with `heightroof` (roof height above ground, feet) and `groundelev` (feet), BIN/BBL, construction year [verified 2026-09]. **3-D Building Model** (DoITT, `tnru-abg2`, published 2016, updated 2023; also by community district, `u5j4-zxpn`) [verified 2026-09]; CityGML, LoD2 from 2014 imagery [believed]; TUM's CityGML/glTF conversion [verified 2026-09]. PLUTO for land use and floors. | NYC 1 ft DEM / 2017 LiDAR (NYC Open Data) [believed]; USGS 3DEP 1 m [believed] | **Convert feet to metres.** `heightroof` is well filled; use it before anything ML. |
| **San Francisco** | DataSF **Building Footprints** (`ynuv-fyni`) with LiDAR-derived heights. Heights are the **median** over the footprint (e.g. `hgt_median_m`), so downtown towers with setbacks come out low [verified 2026-09]. | 2010 SF LiDAR (DataSF) [believed]; USGS 3DEP 1 m DEM [believed] | Landmark list still needed for Salesforce/Transamerica tips. Hills matter (Twin Peaks, Nob Hill): use the local DTM, not GLO-30. |
| **Berlin / Germany** | **Berlin LoD2 CityGML 1.0** (ALKIS footprints, laser-scan roof heights, generalised standard roofs, no textures), free under **dl-de/zero-2.0**: the INSPIRE ATOM feed `https://gdi.berlin.de/data/a_lod2/atom/` (925 tiles of 1 x 1 km, `LoD2_<E>_<N>.zip`, ETRS89/UTM33 = EPSG:25833, z = m above NHN, ~3.5 MB zip / 28 MB xml per inner-city tile; there are no district packages; needs a custom User-Agent from CN) [verified 2026-10]. The Berlin 3D download portal (`download-berlin3d.virtualcitymap.de`) now serves only the 2025 photogrammetric **mesh** (OBJ + textures, terms click-through), not LoD2. The same LoD2 as 2D footprints with `hoehe`, `geschosse`, `dachart`, `funktion` is the Umweltatlas WFS `https://gdi.berlin.de/services/wfs/ua_gebaeudehoehen` (954 k buildings, JSON output). | **DGM1** (1 m, bare earth, laser 2021): `https://gdi.berlin.de/data/el_dgm/atom/dgm1_33_<E>_<N>_2_be_2025.tif` (GeoTIFF float32, 2 x 2 km, 16 MB/tile; the xyz-zip twin is `.../data/dgm1/atom/`) [verified]; Brandenburg DGM1 (dl-de/by-2.0, 1 km tiles) at `https://data.geobasis-bb.de/geobasis/daten/dgm/tif/`; backdrop Copernicus GLO-30 (a DSM, +4 m vs the DTM) | Building heights and storeys: the LoD2 `measuredHeight` and Umweltatlas `geschosse` (OSM has a third of the buildings). Trees: Baumkataster WFS `.../wfs/baumbestand` (street 435 k + park 528 k trees, species/height/crown, dl-de/zero-2.0). Street lamps: WFS `.../wfs/beleuchtung` (210 k points, `betriebsart` Strom/Gas, `rotation`). OSM extract: BBBike `Berlin.osm.pbf` (poly lon 12.76-13.98, lat 52.23-52.82). Extrude-vs-roof: LoD2 has real roofs, so import them. |
| **Paris / France** | APUR **Emprise bâtie Paris** (128k polygons, one per building *part*, no parent id; heights above ground `h_min/h_med/h_max/h_moy` from APUR's surface minus terrain model, `an_const` 63 %, roof shape and material, the high-rise flag `b_igh`), ODbL, attribution "Source : Apur, DGFiP, Ville de Paris (STDF), Orthophotoplans (Aerodata)"; download it through opendata.apur.org's Hub API (`/api/download/v1/items/85fa0a4303744ad4ab6e2a89882b5fca/geojson?layers=0`): the ArcGIS service behind it, carto2.apur.org, resets TLS from China [verified 2026-09]. `h_med` ≈ BD TOPO `hauteur` on ordinary buildings but under-reads stepped towers (Tours Duo 83 m for 180): take `h_max` on high-rise parts over 60 m, never on every part (cranes, chimneys, spires). Only the 20 arrondissements; APUR's metropolitan layer merges La Défense's towers with the dalle. IGN **BD TOPO v3** `batiment` (one polygon per building, `hauteur` above ground on 92 % in Paris, 78 % in La Défense; tower heights exact), Licence Ouverte Etalab 2.0 "Source : IGN", from the Géoplateforme WFS (`https://data.geopf.fr/wfs/ows`, `BDTOPO_V3:batiment`, EPSG:2154, paged per 1 km cell) [verified 2026-09]; drop `etat_de_l_objet` "En projet"; Z −1000 = unknown. Neither has the Tour Triangle (built 2025). Both draw the Eiffel Tower as stacked blocks: drop them. Both are read by the engine's `file` adapter (`demos/paris/city.toml`). | IGN **LiDAR HD MNT** 1 m (bare earth from the national lidar, NGF-IGN69) and **RGE ALTI** 1–5 m, Etalab 2.0, from the WMS-Raster `https://data.geopf.fr/wms-r/wms` as `image/x-bil;bits=32` in 2000 px blocks (layers `IGNF_LIDAR-HD_MNT_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93`, `ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES`; open, no key) [verified 2026-09]; engine adapter `ign`. The lidar has voids where no ground points were classified (the Mont-Valérien fort flat at 137 m for ~162) and shafts to −7 m: fill them from RGE ALTI where lower, never where higher (La Défense's dalle, spoil heaps) | Haussmann blocks: footprints share party walls, so the "touching buildings" and height-jump checks fire a lot, and that is correct. |
| **London / UK** | OSM (good in London) plus heights from EA LiDAR (**DSM − DTM** median per footprint). OS OpenMap Local has open footprints without heights [believed]. OS NGD Building Height is not open (Data Hub licence) [believed]. | Environment Agency **LIDAR Composite DTM/DSM 1 m** (England ~99 %, 5 km GeoTIFF tiles on OS National Grid, **OGL v3**) [verified 2026-09] | Heights over Newlyn datum in EPSG:27700; the city grid is British National Grid, not UTM (UTM 30N or 31N works too). **London (Oct 2026):** environment.data.gov.uk answers 403 from China; the same lidar came through **Carbon & Place** (Univ. of Leeds, ODC-By 1.0, carbon.place/data): its GB-wide *Building Heights* GeoPackage (3.9 GB zip; OS/OSM/INSPIRE polygons split per plot, `height_max` = max 2 m DSM − DTM, r 0.95 vs OSM `height`, within 5 % on 56 of 81 towers ≥ 100 m; its `osm_id` join is unusable: join spatially; towers since ~2020 missing) and its *GBDEM* DTM PMTiles (z13 ≈ 6 m, terrain-RGB, ODN; the Thames a flat ~3 m plane, construction pits to −42 m) read with the engine's `geotiff` DEM adapter. Its `volume` / area is no mean height on towers (the Gherkin 4 m): use `height_max`. `demos/london/checks/sources.md` |
| **Singapore** | data.gov.sg **HDB Property Information** (storeys per HDB block; over 13k blocks, over 80 % of residents) joined to OSM footprints: UAL's `hdb3d-code` does this [verified 2026-09]. URA Master Plan land use [believed]. SLA **OneMap3D** has CityGML (Bentley) but open download was only for a sample area or developer programme [verified 2026-09: not open city-wide]. | GLO-30 or SLA/other LiDAR if available [believed] | Condos and offices: OSM levels plus the landmark list. The city is flat, so terrain is minor. |
| **Hong Kong** | Lands Department **3D Spatial Data** (3D Digital Map; territory-wide since March 2025; buildings, infrastructure, terrain; textured; formats Max/3ds/FBX/VRML, and the `3D-BIT00` dataset) via the **CSDI portal** and DATA.GOV.HK, free [verified 2026-09]. iB1000 building polygons with heights or levels [believed]. | CEDD/LandsD LiDAR DTM 2020 [believed]; GLO-30 fallback | Mountains right behind the towers: terrain quality matters as much as heights. Textured meshes are heavy; use them for heights and landmark shapes, and keep the procedural facades. |
| **Tokyo / Japan** | MLIT **PLATEAU** CityGML (LOD1 for all 23 wards, LOD2 for about 32 km² of centres such as Shinjuku, Shibuya, Ikebukuro; plus bridges, roads, land use, terrain), free including commercial use, via G空間情報センター `geospatial.jp` and `mlit.go.jp/plateau/open-data/` [verified 2026-09]. Zips can exceed 5 GB compressed. Also 3D Tiles/MVT versions. The East Asia 0.5 m footprints cover Japan too [believed]. | GSI 5 m DEM (基盤地図情報) [believed]; PLATEAU relief | CityGML parsing: the engine's `citygml` adapter with `flavour = "plateau"` (one mesh file at a time, ~4 s and +40 MB per 160 MB mesh). **FY2025 data [verified 2026-10-06]:** one dataset per ward (`geospatial.jp/ckan/dataset/plateau-131xx-<ward>-2025`); the data catalog API `api.plateauview.mlit.go.jp/datacatalog/citygml/m:<mesh>` lists one `<mesh>_bldg_6697_op.gml` per 1 km mesh, served gzip-encoded (~8x), saved as `.gml.gz` and read in place; a mesh on a ward border is the same file byte for byte in every ward that touches it (dedupe by `gml:id`; adjacent meshes shared none). posList is **lat lon h** (EPSG:6697; heights TP); every building has `lod0RoofEdge` + `lod1Solid`, LoD2 ones `boundedBy` surfaces too (LoD3 ones add `lod3MultiSurface` twins); no `roofType`, no BuildingParts in the central meshes sampled; codes (`usage`, `class`, uro `detailedUsage`) need the codelists (English glosses in the engine's `sources/plateau_codelists.json`). `measuredHeight` is -9999 where `lod1HeightType` is 0 (uniform 3 m: ~6 % of rows, sheds and canopies): use the solid's `roof_top_z - ground_z` there. For LOD1 rows `measuredHeight` is the point-cloud maximum and the lod1Solid top the median (4.5 m lower, median); for LoD2 rows it matches the roof top within 0.5 m for half the rows and is >3.3 m lower for a tenth (rooftop structures). Footprints sit on OSM's: 113 matched buildings in Marunouchi, Yaesu, Azabudai, centroid offset median 0.9 m (no systematic shift). |
| **Mainland China** (other cities) | The Shenzhen recipe: OSM + GBA + East Asia 0.5 m + CNBH-10m, plus a landmark list. Check CMAB coverage for the city first; it may exist elsewhere. | GLO-30 | No Google 3D tiles; no government downloads. |

### Global and regional datasets (fallbacks and cross-checks)

| Dataset | What | Licence | Status |
|---|---|---|---|
| **Overture Maps buildings** | Merged OSM + Microsoft + Google + Esri footprints, `height`, `num_floors`, building parts; GeoParquet on S3/Azure, query by bbox with DuckDB or the `overturemaps` CLI | ODbL (theme) | [verified 2026-09] A good one-stop footprint source outside China; heights only where upstream has them. **Take only its lidar heights** (each property records its source): its Microsoft ML heights collapse on towers (a 34-storey Jersey City tower at 11 m). In New Jersey, which has no official building heights and OSM heights on 0.3 % of buildings, USGS-lidar heights covered 59 %. The engine's `[sources.overture]` adapter reads just those, joined to OSM footprints by id; where OSM's levels say a building is 1.5× taller than the (2014) lidar saw, it was built since and the levels win. |
| **Microsoft Global ML Building Footprints** | Footprints for most countries, some with ML heights | Upstream relicensed to CDLA-Permissive-2.0 in 2026; ODbL inside Overture | [verified 2026-09, secondary source] |
| **Google Open Buildings** (v3 polygons) and **2.5D Temporal** (4 m raster of presence, count and height, 2016-2023) | Africa, South and South-East Asia, Latin America, Caribbean | CC BY 4.0 or ODbL (dual) | [verified 2026-09] Not Europe, US, Japan or China. |
| **GBA** | See above; global | CC BY-NC 4.0 plus ODbL | [verified 2026-09] |
| **EUBUCCO** | European building stock with heights where known | [believed] ODbL / CC BY | [believed] |
| **GHSL Built-H** (JRC) | 100 m average built height | CC BY 4.0 [believed] | Too coarse per building; use it for sanity maps only. |

### Terrain: global DEMs vs local LiDAR

- **Copernicus GLO-30** (DSM; used): global, good summits, but roofs and canopy must be removed. The Shenzhen
  bare-earth recipe (`data-pipeline.md` §05a) works.
- **FABDEM** V1-2: GLO-30 with forest and buildings removed; **CC BY-NC-SA 4.0** [verified 2026-09]. It saves the
  bare-earth step but is non-commercial. Also on Hugging Face (`links-ads/fabdem-v12`).
- NASADEM or SRTM (older, noisier) and ALOS AW3D30 are alternatives [believed].
- **Local LiDAR DTM** (EA 1 m, IGN LiDAR HD, USGS 3DEP, Berlin DGM1, GSI 5 m, HK LiDAR): use it wherever it
  exists. It is already bare earth.
  - Resample to the 10 m work grid, keep the sea-level knee and water levelling, and skip the building masking
    and canopy subtraction.
  - Keep GLO-30 for the far backdrop, which usually reaches beyond the LiDAR coverage.
- A local **DSM − DTM** gives per-footprint heights (median or 90th percentile of the pixels inside the
  footprint). That is often better than any ML height, and it is how SF's heights were made. Use the 90th
  percentile for towers, the median for low-rise.

### Checks to run on any new footprint or height source (the `03_compare.py` pattern)

1. **Alignment** against OSM: median nearest-centroid shift of buildings over 400 m² (expect under 3 m).
2. **Coverage**: count and footprint km² per 1 km cell for each source, with a coverage map. Look for holes and
   dataset edges (the East Asia edge at 113.768 E).
3. **Heights** against OSM-tagged `height` or `building:levels`×3.2 m: median error, median abs error, RMSE and
   correlation, **by height band** (0-15, 15-30, 30-60, 60+ m). A source can be good in one band and useless in
   another (CNBH).
4. A close-up plot of footprints from the different sources over one known neighbourhood.
