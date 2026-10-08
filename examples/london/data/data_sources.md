# London data sources (M1 research, 2026-10-01)

Tested from a network in mainland China (a local proxy was available but routed
these hosts DIRECT). "Reachable" = an actual HEAD/range/small GET from here. Area: lon -0.20..0.03, lat 51.47..51.53 plus 4 km
ground margin (lon -0.26..0.09, lat 51.43..51.57) plus a 36 km terrain backdrop. Scratch and scripts:
`<scratch>/london_data/`.

## 1. The Environment Agency LiDAR block, and every way round it

| Route | Result from here |
|---|---|
| `environment.data.gov.uk` root, `/survey`, `/DefraDataDownload/?Mode=survey`, `/api/file/download`, WCS/WMS/WMTS `/spatialdata/...`, `/image/rest/services`, `/arcgis/rest/services`, dataset pages | all **HTTP 403** (Azure Application Gateway v2 page); same with curl UA, browser UA, a data.gov.uk Referer; `http://` answers 301 then 403; WebFetch (another egress) also 403 |
| data.gov.uk / `ckan.publishing.service.gov.uk` CKAN | **works** (metadata only). Every DSM/DTM resource URL in it (WCS, WMS, WMTS, survey download, OGC API features, tile-index) is on `environment.data.gov.uk`: no second hostname exists |
| `api.agrimetrics.co.uk` | connection reset |
| Google Earth Engine `UK/EA/ENGLAND_1M_TERRAIN/2022` (OGL v3; bands dtm, dsm_first, dsm_last, 1 m) | exists, but needs a Google account and Google is unreachable from here; not usable (no accounts) |
| OpenTopography | portal reachable (needs API key, no account allowed); it does not host the EA composite |
| AWS/Azure open-data registries | no EA LiDAR entry found; `registry.opendata.aws` reachable |
| Flickr "environmentagencyopensurveydata" | un-georeferenced JPEG tiles, useless |
| Digimap, LidarFinder | viewers / academic login |

Conclusion: the EA 1 m tiles, WCS and every alias are geo-blocked from this network; the only ways in are an egress outside the
block (a proxy route for `environment.data.gov.uk` through a non-Chinese exit) or a third-party derivative (section 2).
Tile facts (from CKAN, unchanged): 5 km OS-grid GeoTIFF, 1 m, OGL v3, +-15 cm RMSE, England 99 %; DSM/DTM for ~8-20 tiles of TQ.

## 2. Discovered mirror-like route: Carbon & Place (Univ. of Leeds "Place-Based Carbon Calculator") GBDEM + Building Heights

`https://www.carbon.place/data/` (reachable, Azure blob storage `pbcc.blob.core.windows.net`, HTTP range requests work).
Built from the **EA LiDAR composite** (+ OS Terrain 50 to fill gaps) at 2 m; github.com/PlaceBasedCarbonCalculator/GBDEM (code GPL-3.0,
data "open data with attribution", the site's catalogue says ODC-By 1.0; the polygons contain OSM so also ODbL).

| File | Size | What I measured |
|---|---|---|
| `https://pbcc.blob.core.windows.net/pbcc-pmtiles/DTM.pmtiles` | 3.18 GB | PMTiles v3, 512 px WebP tiles, Mapbox terrain-RGB (base -10000, step 0.1 m), z0-**13** => ~5.95 m/px at 51.5 N. 167,795 tiles. |
| `.../pbcc-pmtiles/DSM.pmtiles` | 13.4 GB | same encoding, z0-**14** => ~2.97 m/px. Shard tile: max 295.6 m (nominal 310: spire lost to the 3 m pixel). |
| `https://pbcc.blob.core.windows.net/pbcc-data/bulk/buildings_heights_20260825.zip` | **3.90 GB zip / 10.3 GB gpkg** | GB-wide GeoPackage, one layer, EPSG per gpkg, ~2.5 M pages. Columns: `osm_id, building, building_part, INSPIREID, id, grid, height_max, height_min, volume` (per polygon from 2 m DSM minus DTM; polygons = OS Open + OSM + INSPIRE). One deflate member, so no partial fetch; NOT downloaded (over my 200 MB/2 GB test budget). Single-stream speed measured 0.39 MB/s (whole file about 2.8 h; parallel range download of 16-24 streams should be ~30-60 min: I used 24 streams for the BBBike pbf at ~0.25 MB/s each). |

Crude accuracy test of the PMTiles pair (DSM z14 minus DTM z13 at each footprint's bbox centre, against Overture buildings whose height
comes from OSM tags, 15,916 buildings in the core bbox): correlation 0.70, MAE 4.3 m, median bias +0.9 m; by OSM height band 0-8 m MAE 2.4 m, 8-15 m 4.2 m,
15-30 m 10.0 m, 30-60 m 13.9 m, 60+ m 27 m. That is a centre-point sample at 3-6 m/px on possibly imprecise OSM heights, so a pessimistic
lower bound, but it says the PMTiles pair is a coarse height source, not equal to 1 m EA tiles. The gpkg's `height_max` (2 m DSM-DTM inside
each polygon) is expected to be much better; verify after download by comparing with OSM-tagged towers (Shard, Gherkin, etc.).

## 3. Building footprints and heights: source table

| Source | URL | Reachable | Licence | Coverage of our area | Resolution / accuracy | Fields | Size |
|---|---|---|---|---|---|---|---|
| **OSM (BBBike London extract)** | download.bbbike.org/osm/bbbike/London/London.osm.pbf, `.poly` | yes; **downloaded**, md5 matches, 2362 blobs parse to EOF; single stream only ~16 KB/s, 24 range streams ~250 KB/s | ODbL | poly is the box lon -0.6..0.42, lat 51.28..51.70: covers our area + 4 km margin with 0.34 deg to spare in lon, 0.15 in lat (not the 36 km backdrop: OSM is not needed there) | best footprints; terraces split; ~121 k building ways/multipolygons in the core bbox (Overture view) | tags | 190 MB pbf |
| **Overture Maps buildings** release 2026-09-23.1 | `s3://overturemaps-us-west-2/release/2026-09-23.1/theme=buildings/type=building/`, London is in `part-00124` and `part-00125` (found through stac.overturemaps.org, 512 items; a plain glob over the whole release never finished in 30 min from here) | yes | ODbL (theme) | 498,527 buildings in the 4 km-margin bbox; **91 % OSM, 9 % Microsoft ML footprints** (42,844) | see heights below | id, height, num_floors, class, subtype, names, roof_shape, has_parts, sources | saved 78 MB parquet |
| Overture heights in core bbox (lon -0.2..0.03, lat 51.47..51.53: 121,250 buildings) | | | | height on 17,777 (14.7 %, all from OSM `height`; 0.1 m precision typical, e.g. 7.6, 7.7: probably an OSM lidar-style import), `num_floors` on 50,272 (41 %), neither on 58,399 (48 %); 108 buildings >= 50 m, 53 >= 100 m | Microsoft ML footprints carry ML heights (38,253 of 42,844) but correlate only 0.44 with DSM-DTM and collapse on towers | | |
| **OS OpenMap Local** (Ordnance Survey, GB) | `api.os.uk/downloads/v1/products/OpenMapLocal/downloads?area=TQ&format=ESRI%C2%AE+Shapefile&redirect` (-> Azure blob, range works, SAS link valid ~1 day) | yes; extracted Building + ImportantBuilding + TidalWater + SurfaceWater_Area + Foreshore from the 231 MB zip by range requests | OS OpenData licence (OGL-compatible, attribution "Contains OS data (c) Crown copyright") | TQ 100 km square covers everything; 67,386 building polygons in the core bbox | 1:10 000-ish, terraces merged (median 285 m2, 293 polygons > 10,000 m2), Z = 0 | **only `ID` (TOID) and `FEATCODE`, no height** | 231 MB zip; 0.6 GB unpacked at `raw/os_openmap_local/` |
| OS NGD `bld-fts-buildingpart` (`height_relativemax_m`, `height_absoluteroofbase_m`) and OS MasterMap Building Height Attribute | api.os.uk/features/ngd/ofa/v1 | API root reachable; items -> **401 without API key** | premium (PSGA / MasterMap licence / 6-month Data Exploration trial via account) | GB | best official heights | | **not open, needs account: out** |
| **Carbon & Place Building Heights gpkg** | section 2 | yes (range) | ODC-By 1.0 + ODbL + OGL inputs | GB, London included | derived from EA 1-2 m lidar | height_max/min/volume + osm_id | 3.9 GB |
| **GBA (GlobalBuildingAtlas, TUM) LoD1** | parquet `https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/tge-labs/globalbuildingatlas-lod1/{w005_n55_e000_n50,e000_n55_e005_n50}.parquet` (1.49 GB + 1.43 GB); HF `zhu-xlab/GBA.LoD1` JSON 1.3-1.4 GB per tile | yes (Hugging Face and source.coop reachable; source.coop's `data.` host returned HTTP 520 for a while, the S3 host works); row-group pruning by bbox works (89 + 27 of ~1000 groups) | **CC BY-NC 4.0 (non-commercial)** for heights/LoD1, ODbL for OSM-sourced polygons | global; London footprints in it are `ms` (Microsoft) etc. | ML from 3 m PlanetScope; Shenzhen test r = 0.61 and no tower ranking; London not yet tested | source, id, height, var, region, bbox, geometry | 1.49 + 1.43 GB tiles; London bbox subset saved: 65 MB |
| **Colouring London / Colouring Britain** | `https://colouringbritain.org/api/extracts` (146 weekly extracts; latest 2026-01-26 `/downloads/data-extract-2026-01-26-05_00_02.zip`, **7.9 GB**, range OK). **`colouring.london` no longer belongs to the project: it now serves a gambling-spam site (worldcupbetting.mobi); use colouringbritain.org only** | yes | ODbL; the site requires accepting a data-accuracy agreement on the download page (a click-through, so I did not download or list the archive) | building attributes for GB, crowd-sourced, patchy | **no footprint geometries** (keyed by TOID/UPRN from OS MasterMap, which is not open, so joining to OSM is impossible without the OS ids) | height/storeys fields sparse (names believed `height_apex`, `height_eaves`, `size_storeys_*`) | 7.9 GB: **out** |
| **London Datastore** | data.london.gov.uk (reachable) | yes | OGL | LBSM (London Building Stock Model 1/2): energy data per OS building, "average height of built volume"; per-borough CSVs; also the GLA "Tall Buildings" pipeline list on data.gov.uk | keyed to OS TOIDs, no geometry | | not a height source for our footprints; "Tall Buildings" may help the landmark list. VU.CITY is commercial |
| **EUBUCCO** | eubucco.com / source.coop | reachable | ODbL | EU-27 + Switzerland only: **no UK** | | | out |
| GHS-BUILT-H (JRC) | | | CC BY 4.0 | | 100 m (Sentinel-based average height), too coarse | | note only |
| Google Open Buildings 2.5D Temporal | | | CC BY / ODbL | Africa, S/SE Asia, Latin America only: **no UK** | | | out |
| Verisk UKBuildings, VU.CITY, OS MasterMap BHA | | | commercial | | | | note only |
| Emu Analytics "Building Heights in GB" | buildingheights.emu-analytics.net | viewer only | | derived from OS BHA (premium) | | | no download |

GBA London sample (saved): 472,110 polygons in the 4 km-margin bbox (419,962 OSM-sourced, 49,771 Microsoft, 2,377 TUM `ours2`), every one with an ML height (median 6.0 m); 116,815 in the core bbox.
Against OSM-tagged heights (15,773 buildings matched by bbox centre): correlation 0.60, MAE 3.5 m, bias -0.2 m; for OSM heights >= 30 m (158 buildings) MAE 46.9 m and correlation 0.57.
So GBA cannot place the towers (same finding as Shenzhen) and it is non-commercial; last resort only.

## 4. Terrain

| Source | URL | Reachable | Licence | Details |
|---|---|---|---|---|
| **EA LiDAR DTM 1 m** | environment.data.gov.uk | **403** | OGL v3 | ideal (bare earth, +-15 cm) but blocked |
| **Carbon & Place DTM PMTiles** (EA-derived) | section 2 | yes, range | ODC-By | bare-earth DTM at ~6 m/px (z13), EA lidar under London, OS Terrain 50 where no lidar; 0.1 m vertical step. The London 36 km backdrop (about 1.0 x 0.65 deg = ~550 z13 tiles x ~85 KB) is ~50 MB by range requests. Fits the pipeline's 10 m work grid. The 3 m DSM (13.4 GB file, z14) is only useful to sample building heights (see the accuracy test) |
| **Copernicus GLO-30** | `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N51_00_{W001,E000}_00_DEM/...tif` | yes; **downloaded** both tiles (32.7 MB + 30.9 MB, sizes equal Content-Length, TIFF magic OK) at `raw/terrain/glo30/` | Copernicus licence, attribution | DSM (roofs and canopy in), 30 m; use for the far backdrop beyond the lidar; London tiles N51_W001 (lon -1..0) and N51_E000 (lon 0..1) cover the whole 36 km backdrop |
| **OS Terrain 50** | `api.os.uk/downloads/v1/products/Terrain50/downloads?area=GB&format=ASCII+Grid+and+GML+(Grid)&redirect` | yes; **downloaded** 162 MB zip (2,859 members, testzip OK; London is `data/tq/tq28`, `tq37`, `tq38` etc. inside it) at `raw/terrain/os_terrain50/` | OS OpenData (OGL-compatible) | 50 m DTM (bare earth), GB, 162 MB zip of 10 km ASCII tiles; correct bare-earth backdrop, too coarse for the core |
| FABDEM v1-2 | HF `links-ads/fabdem-v12`, source.coop `c-core/fabdem` (both reachable) | not downloaded | **CC BY-NC-SA 4.0 (non-commercial)** | GLO-30 with buildings and trees removed, 30 m; flagged non-commercial |
| EU-DEM v1.1 | Copernicus land service | not tested | | 25 m, superseded by GLO-30 (believed); skip |

## 5. Downloads on disk (all under `<project>/demos/data/london/raw/`, git-ignored)

| Path | Size | What |
|---|---|---|
| `raw/osm/London.osm.pbf` | 190 MB (199,629,030 B) | BBBike London extract, md5 c4cd89c1..., dated 2026-09-26 |
| `raw/osm/London.poly` | 77 B | box lon -0.6..0.42, lat 51.28..51.70 |
| `raw/os_openmap_local/TQ_Building.*`, `TQ_ImportantBuilding.*`, `TQ_TidalWater.*`, `TQ_SurfaceWater_Area.*`, `TQ_Foreshore.*`, `licence.txt`, `readme.txt` | 643 MB unpacked (about 135 MB transferred) | OS OpenMap Local TQ, EPSG:27700 shapefiles |
| `raw/overture/overture_buildings_2026-09-23.1_london_bbox.parquet` | 75 MB | 498,527 buildings, columns id, height, num_floors, class, subtype, name, sources, has_parts, roof_shape, bbox, geometry |
| `raw/gba/gba_lod1_london_bbox.parquet` | 65 MB | 472,110 GBA polygons with ML heights (CC BY-NC) |
| `raw/terrain/glo30/*.tif` (2) | 63 MB | Copernicus GLO-30 N51_W001 and N51_E000 |
| `raw/terrain/os_terrain50/terr50_gagg_gb.zip` | 162 MB | OS Terrain 50 GB ASCII grids |

Total transferred about 0.75 GB. Scripts (range extractor for zip members `zx.py`, parallel range downloader `pdl.py`, Overture/GBA/PMTiles queries `ovq*.py`, `gq.py`, `cmp.py`) are in `demos/data/london/research/` (git-ignored scratch).
`pdl.py <url> <out> <size> <streams>` is the fix for slow hosts: 24 parallel range streams took bbbike from 16 KB/s to ~250 KB/s and OS Azure blobs to a few MB/s.

## 6. RECOMMENDATION

- **Footprints**: OSM from the BBBike London extract (local Overture-style Overpass later, per the Paris recipe), as before. Overture (saved
  parquet) is a good cross-check and gives the 9 % Microsoft-only footprints (do not trust their heights); OS OpenMap Local (OGL) only as a
  fallback where OSM has holes: its polygons merge terraces and carry no attributes.
- **Heights, in this priority**:
  1. **EA LiDAR DSM - DTM, 1 m** (best; blocked here; needs the user's egress, see the question).
  2. **Carbon & Place `buildings_heights` gpkg** (`height_max`, `height_min`, `volume`; derived from the same EA lidar at 2 m, polygons carry `osm_id`, so it joins to our OSM
     footprints directly): one 3.9 GB download by 16-24 parallel range streams (< 1 h expected). Licence ODC-By/ODbL/OGL (commercial use fine). Needs verification of its
     tower behaviour (max vs 90th percentile) after download, and it is a third-party build of unknown QA.
  3. **OSM `height` (Overture: 14.7 % of core buildings, tall towers included) and `building:levels` x 3.2 m (41 %)** for the explicit/landmark buildings and as a
     validator of 2; the hand-checked landmark list for the skyline (Phase 0 already found OSM heights for ~20 towers).
  4. DSM z14 minus DTM z13 from the PMTiles at footprint level (coarse: MAE 4.3 m in a crude test, 27 m on 60 m+ towers): only if 2 is unusable and the user does not open EA.
  5. **GBA** only for footprints without any other height; **non-commercial (CC BY-NC 4.0)**, ML, cannot rank towers. Overture's Microsoft ML heights: do not use.
  Not available: OS NGD/MasterMap height attributes (account, premium), Colouring London (no geometry, click-through), EUBUCCO (no UK), Verisk (commercial).
- **Terrain**: Carbon & Place DTM PMTiles (EA-derived bare earth, ~6 m) for core, margin and the 36 km backdrop (~50 MB by range); OS Terrain 50 as the far/gap fallback; GLO-30
  (already downloaded) as an independent check and for anything beyond. If the user opens EA, replace the core with the 1 m DTM and keep the rest.
  FABDEM is non-commercial: avoid.
- **OSM**: BBBike London pbf + poly downloaded; box covers the area with margin; not imported.
- **Question for the user**: "Can you route `environment.data.gov.uk` through a UK (or any non-Chinese) exit so I can pull the EA 1 m DSM/DTM (best quality, 8-20 tiles, ~1-2 GB)?
  If not, we continue with the Carbon & Place lidar-derived heights (2 m, one 3.9 GB download, third-party build, polygons snapped to OSM) and 6 m terrain: roughly 90 % as good for ordinary
  buildings, weaker on tower tops and roof ridges, and I cannot re-derive per-footprint percentiles myself."

## 7. Not verified / caveats

- The Carbon & Place gpkg was not downloaded, so its quality and the exact height definition are unmeasured; its schema was read from the first 40 MB of the deflate stream.
- The PMTiles accuracy test samples one pixel at each footprint's bbox centre against OSM heights that may themselves be imprecise.
- GBA was compared only against OSM-tagged heights matched by bbox centre.
- Colouring Britain field names and coverage are from documentation memory; the archive needs a click-through.
- Not tested through a proxy exiting outside China (the geo-block needs a non-Chinese egress).
