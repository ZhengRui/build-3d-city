# Berlin data sources (M1 research, 2026-10-02)

Tested from a network in mainland China (no proxy needed for any of these hosts). "Reachable" = an actual HEAD/range/GET from here.
Area "A" = Ortsteile Mitte 16566, Tiergarten 55750, Moabit 28339, Hansaviertel 16567, Friedrichshain 55763, Kreuzberg 55765, Alt-Treptow 55762 + Charlottenburg east of
lon 13.3055 (polygon `layer opts / name A` in `demos/data/phase0/berlin/opts.gpkg`): **53.25 km2**, EPSG:25833 bounds x 384,966-397,570, y 5,815,694-5,822,575.
Margins: roads 1 km (lon 13.292-13.504, lat 52.470-52.553), ground and painted town 4 km (lon 13.249-13.547, lat 52.442-52.580), backdrop 36 km
(lon 12.793-14.013, lat 52.147-52.873; centre 13.398, 52.511). Scratch and scripts: `<scratch>/berlin_data/`.
Data on disk: `<project>/demos/data/berlin/raw/<source>/` (git-ignored), each with a README.txt. Total 3.0 GB (2.5 GB without the stray xyz zips).

**Network notes.** Berlin's own hosts (gdi.berlin.de, download.bbbike.org, data.geobasis-bb.de, AWS S3) are all reachable and fast enough: 200-270 KB/s per stream, so 6-8 parallel
streams give ~1.5-2 MB/s (1.3 GB of DGM1 took ~25 min, LoD2 419 MB 2 min because tiles are small). `gdi.berlin.de/data/*` needs a custom User-Agent (a Chrome-like UA timed out
at first); the geonetwork catalogue works through CSW (`/geonetwork/srv/ger/csw`, CQL `AnyText like '%x%'`), its JSON search API answers 403 (CSRF). daten.berlin.de / govdata.de pages
403 to curl (WebSearch reaches them). Nothing in Berlin was geo-blocked (unlike London's EA LiDAR).

## 1. Buildings

| Source | URL | Reachable | Licence | Coverage of A + margins | Resolution / accuracy | Fields | Size |
|---|---|---|---|---|---|---|---|
| **Berlin LoD2 CityGML** (ALKIS footprints, laser-scan roof heights, generalised standard roofs) | `https://gdi.berlin.de/data/a_lod2/atom/LoD2_<E>_<N>.zip` (feed `.../a_lod2/atom/0.atom`, 925 tiles, 1 km, ETRS89/UTM33) | yes; **downloaded** | dl-de/zero-2.0 (no attribution needed) | whole city; downloaded **123 tiles = A buffered by 1 km** (79 touch A, 99 within 0.5 km); 82,257 Building + 149,876 BuildingPart | footprint = cadastre; roof = standard shape (flat / mono / gable / hip ...), z in m above NHN (DHHN2016); roof heights from laser scan 2021 ("DatenquelleDachhoehe 5000"); ground z is one flat value per solid | gml:id (ALKIS id), function (ALKIS code), roofType, measuredHeight, Grundrissaktualitaet, DatenquelleLage/Bodenhoehe/Dachhoehe, lod2Solid + Wall/Roof/Ground/Closure surfaces, lod2TerrainIntersection; **no storeys, no textures, almost no names** | 419 MB zip (about 2.9 GB XML; median tile 3.4 MB zip / 28 MB xml, max 7.6 MB) |
| LoD2 content check (tile 392_5820, Alexanderplatz) | | | | 732 Buildings + 873 BuildingParts = 1,419 solids; 12,971 Wall + 2,744 Roof + 1,419 Ground + 3,118 Closure surfaces | `measuredHeight` = highest roof z minus ground z, matches the geometry to 1 mm on all 1,419 solids; measuredHeight median 17.95 m, p95 38.6, p99 64.5, max 253.5 (Fernsehturm base); roofType: flat 479, mono 394, hip/mixed 274, gable 117, other 151, 3200/3500 4 (parents with parts carry none) | function codes 51009_1610 (426 buildings, = "Ueberdachung" in the WFS clear text) and 31001_xxxx (Wohn-, Geschaefts-, ...), `31001_1010` 132 | |
| **Umweltatlas Gebaeudehoehen WFS** (same LoD2, as 2D footprints with heights) | `https://gdi.berlin.de/services/wfs/ua_gebaeudehoehen` layer `gebaeudehoehen` (954,230 citywide) | yes; **downloaded** for A + 4 km | dl-de/zero-2.0 | 377,387 buildings in the bbox (A 90,211; A+1 km 148,900; A+4 km 313,912) | footprints exact cadastre; `hoehe` = ridge height above ground (laser scan 94 %), 550 >= 50 m, 13 >= 100 m in A | gisid, gml_id (join key to LoD2), name (8,146 in A), funktion + _txt, role (Gebaeude 23 k / Gebaeudeteil 67 k in A), dachart + _txt, **geschosse** (88 % in A), hoehe, strasse, hnr, Grundrissaktualitaet | 302 MB geojson |
| ALKIS Berlin Gebaeude (WMS only) / `gebaeude_geschosse` WFS | `https://gdi.berlin.de/services/wfs/gebaeude_geschosse` (layers a_..f_ by storey class, 261,340 in the bbox) | yes; metadata + 1 sample | dl-de/zero-2.0 | | footprint + `aog` (storeys above ground), `aug`, `gfk` (function) | | **not downloaded**: `geschosse` in the Gebaeudehoehen layer covers it |
| Berlin Gebaeude Atlas (WFS) | `.../wfs/gebaeudeatlas` | yes | dl-de/zero-2.0 | 808 points in the bbox (Berlin-Modell project documentation: names, architects, years of post-1990 central buildings) | | a candidate for landmark names/dates | not downloaded |
| **Berlin 3D-Meshmodell 2025** (photogrammetric OBJ + textures, flight June 2025) | `https://download-berlin3d.virtualcitymap.de/` (index `datasource-data/berlin-mesh-2025/mesh-index-2025.json` answers 200) | portal yes | **dl-de/zero-2.0** per the catalogue / WebSearch, but the portal makes you accept its terms before a tile export (a click-through) | whole city, ~0.36 x 0.36 km tiles, ZIP per tile with OBJ + JPG | real facades and roofs, no semantics | | **not downloaded** (click-through, tile sizes unknown, tens of MB each with textures). The terms page `.../resources/terms/terms.de.html` 404s from here. Report to the controller if facade texture capture is wanted |
| OSM buildings (Berlin.osm.pbf) | section 3 | yes; downloaded | ODbL | | per Phase 0: 2.5-3x fewer buildings than the cadastre (Mitte OT 8,676 vs 24,169), `height` on 7 %, `building:levels` on 71 % | | |
| Overture / Microsoft / GBA | not needed here | | | | | | Berlin has an official LoD2 with exact heights, so the ML/Overture routes of London are unnecessary |

## 2. Terrain

| Source | URL | Reachable | Licence | Coverage | Resolution / accuracy | Format | Size |
|---|---|---|---|---|---|---|---|
| **Berlin ATKIS DGM1** (bare earth, laser scan Feb/Mar 2021) | GeoTIFF: `https://gdi.berlin.de/data/el_dgm/atom/dgm1_33_<E>_<N>_2_be_2025.tif` (297 tiles, 2 km); same data as ASCII-xyz zips `https://gdi.berlin.de/data/dgm1/atom/DGM1_<E>_<N>.zip` | yes; **downloaded as GeoTIFF** | dl-de/zero-2.0 | **81 tiles = A buffered by 4 km** (27 touch A; 36 within 1 km); Berlin plus a ~250 m Brandenburg buffer | 1 m grid, float32, m above NHN (DHHN2016); LoD2 ground z minus DGM1 at the footprint centroid: median -0.26 m, p5 -2.3 m, p95 0 (the LoD2 ground is a flat DGM10 value per building) | 2000 x 2000 float32 uncompressed, nodata -9999, GeoTIFF tags (tiepoint NW corner, scale 1 m); the EPSG code is not in the GeoKeys (ESRI PCS name only): set EPSG:25833 by hand | 1.3 GB (16.0 MB per tile) |
| DGM1 artifacts | | | | 80 of 81 tiles clean; 1 nodata pixel in 380_5820 | z range over the 81 tiles 6.0-120.1 m (Teufelsberg 120 m); outliers are cut-and-cover tunnels and pits (15.2 m at Potsdamer Platz 13.369, 52.504 in the Tiergarten tunnel; 6.0 m at 13.281, 52.526 Westend); normal ground is 28-45 m | | clamp road/building z to the surrounding ground when a tunnel portal makes the DEM dive |
| **Copernicus GLO-30 DSM** (backdrop) | `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N52_00_E01{2,3}_00_DEM/...tif` | yes; **downloaded** | Copernicus licence (free, attribution text in the README) | 2 tiles = lon 12-14, lat 52-53 = the whole 36 km box | 1 arc-second (28 x 31 m); a **DSM**: against DGM1 at 363,609 points GLO-30 minus DGM1 is median +4.3 m, mean +5.3, p5 -0.8, p95 +15.3, p99 +19.6 (buildings, forest) | COG float32 EPSG:4326, EGM2008 heights | 64 MB |
| Brandenburg DGM1 (bare earth) | `https://data.geobasis-bb.de/geobasis/daten/dgm/tif/dgm_33<E>-<N>.zip` (1 km tiles, listing works; 32,360 tiles statewide, 1.0-1.6 MB each) | yes (HEAD) | **dl-de/by-2.0** (attribution "GeoBasis-DE / LGB") | statewide Brandenburg (Berlin itself is not in this set) | 1 m | zipped GeoTIFF | the part of the 36 km box has **7,470 tiles = ~9.7 GB**: over the 5 GB budget, **not downloaded**. A coarse 3-5 km ring is ~300 tiles / 0.4 GB if the GLO-30 forest bias of +20 m bothers beyond 4 km |
| Berlin DOM 1 m (surface model), bDOM, ALS point cloud | `.../data/dom/atom/` | feeds yes | dl-de/zero-2.0 | | | | not needed (LoD2 has the roofs); DOM 1 m would give canopy heights if wanted: 16 MB per 2 km tile |
| ESA WorldCover 10 m v2 2021 | `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N51E012_Map.tif` | yes (HEAD) | CC BY 4.0 | one 3 x 3 deg COG (lat 51-54, lon 12-15) = the whole backdrop | 10 m land cover classes | COG | 76 MB, **read in place by the engine; nothing stored** |

## 3. OpenStreetMap

| Source | URL | Reachable | Licence | Coverage | What I checked | Size |
|---|---|---|---|---|---|---|
| **BBBike Berlin extract** | `https://download.bbbike.org/osm/bbbike/Berlin/Berlin.osm.pbf` + `Berlin.poly` + `CHECKSUM.txt` | yes; **downloaded** (13 range streams) | ODbL | poly = box lon 12.76-13.98, lat 52.23-52.82: covers A + 4 km (lon 13.249-13.547, lat 52.442-52.580) with 0.49 deg lon / 0.21 deg lat to spare; the 36 km backdrop corners lie outside (south of 52.23, north of 52.82), OSM is not needed there | md5 7ee30b4b... matches; 1,903 blobs parse to EOF; header bbox as the poly; extract dated 2026-09-26 (Last-Modified) | 182 MB (174 MB on disk) |
| OSM inside A (counted with pyosmium, 193 s, 90 MB RSS) | | | | `natural=tree` 46,715 (species 1,687, height 522, crown 316); `highway=street_lamp` 16,286 (typed: electric 2,416, led 186, gaslight 127, sodium 88; 13,372 untyped); `highway=traffic_signals` 2,006 | | |

## 4. Trees

| Source | URL | Reachable | Licence | Coverage | Fields / quality | Size |
|---|---|---|---|---|---|---|
| **Baumkataster Strassenbaeume** | WFS `https://gdi.berlin.de/services/wfs/baumbestand` layer `baumbestand:strassenbaeume` (434,765 citywide) | yes; **downloaded** | dl-de/zero-2.0, no restrictions | 232,576 in the bbox (A 42,293; A+1 km 78,574; A+4 km 182,422) | art_dtsch, art_bot (with cultivar), gattung(_deutsch), art_gruppe, pflanzjahr, standalter, stammumfg (cm), **baumhoehe** (99.7 % known in A, median 12 m, p95 21.4), **kronedurch** (99.1 %, median 8 m, p95 16); genus mix in A: Linde 17.7 k, Ahorn 6.9 k, Platane 3.7 k, Eiche 1.9 k, Rosskastanie 1.5 k | 121 MB geojson |
| **Baumkataster Anlagenbaeume** (park trees) | layer `baumbestand:anlagenbaeume` (527,780 citywide) | yes; **downloaded** | same | 291,652 in the bbox (A 58,487; A+1 km 92,563; A+4 km 230,149) | same fields; height 99 %, crown only 73 % (median 7 m); "a part of the trees in green spaces" (not forest, not private) | 150 MB geojson |
| OSM trees | section 3 | | ODbL | 46,715 inside A, species/height rarely tagged | | |
| Umweltatlas Vegetationshoehen 2020 / Gruenvolumen | `.../wfs/ua_vegetationshoehen_2020` (block means), WMS | yes | dl-de/zero-2.0 | | block-level only | not downloaded |

Berlin street+park trees inside A: 100,780 vs OSM 46,715, with heights and crowns, so the Baumkataster is the tree source (OSM only for trees missing in it, e.g. private gardens).

## 5. Street lamps

| Source | URL | Reachable | Licence | Coverage | Fields | Size |
|---|---|---|---|---|---|---|
| **Oeffentliche Beleuchtung** (every lamp point of the city's lighting) | WFS `https://gdi.berlin.de/services/wfs/beleuchtung` layer `beleuchtung:beleuchtung` (210,203 citywide) | yes; **downloaded** | dl-de/zero-2.0, "keine Bedingungen" | 113,828 in the bbox; **A 27,709** (A+1 km 45,762) | betriebsart **Strom | Gas**, status, strasse, ortsteil, **rotation** (deg), leuchtentyp: Lichtmast mit Auslegerleuchte 11,072 / Aufsatzleuchte 9,122 / Ansatzleuchte 2,628 / Doppelausleger 1,671 / Dreifach 411 ... in A; **Gas** 1,687 in A = Gas-Aufsatzleuchte 1,185, Gas-Haengeleuchte 421, Gas-Sonderleuchte 81; Schaltkasten 112 (not lamps); 989 out of service or dismantled. No mast height, no LED/sodium colour | 62 MB geojson |
| **Erhaltungsbereiche Gasbeleuchtung** (zones where gas lamps stay gas) | WFS `.../wfs/gasbeleuchtung` | yes; **downloaded** | dl-de/zero-2.0 | 28 areas citywide (Frohnau, ... ) with counts per lamp type | polygons + gal/ghl/gml/gsl/grl counts | 55 KB |
| Lichtsignalanlagen | WFS `.../wfs/lsa` | yes; **downloaded** | dl-de/zero-2.0 | 1,587 | standort, number | 0.5 MB |
| OSM | section 3 | | ODbL | 16,286 `street_lamp` in A, 127 `gaslight` | | |

## 6. Other

| Item | Source | Status |
|---|---|---|
| Land use / green / built-up blocks | Umweltatlas Flaechennutzung 2024 WFS (`ua_flaechennutzung`: reale_nutzung, gruen_und_freiflaechenbestand; 11,167 block-part polygons in the bbox), dl-de/zero-2.0 | **downloaded** (2 x 15 MB). Biotoptypen 2024 (31,216 polygons, finer vegetation) and Vegetationsbedeckung layers on the same service: not downloaded |
| ATKIS land use / Basis-DLM | only a WMS presentation service (`.../wms/atkis`); the vector Basis-DLM is not offered as open download here | not available as vectors; Flaechennutzung and OSM replace it |
| Water bodies (Spree, Landwehrkanal, Landwehrkanal's bank) | OSM (water polygons + waterways) is the practical source; Gewaesserkarte is WMS only; the Flaechennutzung "Wasser" blocks are coarse | use OSM; check against the DGM1 (the rivers are flat there) |
| ALKIS building heights/storeys | no open ALKIS vector download of the cadastre, but the Umweltatlas Gebaeudehoehen (heights, `geschosse`, function) and `gebaeude_geschosse` expose them | **downloaded** (section 1) |
| Berlin Gebaeude Atlas | 808 points in bbox, WFS | not downloaded |
| Hochwasser / Ueberschwemmungsgebiete, Morphologie Berliner Gewaesser (bathymetry contour lines) | same GDI, WMS/WFS | not checked in depth (not needed) |

## 7. Downloads on disk (`<project>/demos/data/berlin/raw/`, 3.0 GB)

| Folder | Content | Size |
|---|---|---|
| `lod2/` | 123 `LoD2_<E>_<N>.zip` + `tiles.csv` (flag within_0.5km) + README | 419 MB |
| `dgm1/` | 81 `dgm1_33_<E>_<N>_2_be_2025.tif` (+ `ElevationGridCoverage_dgm1_33_390_5818_2_be_2025.gml` sample) + `tiles.csv` | 1.3 GB |
| `dgm1_xyz_zip_partial/` | 32 xyz zips (some partial) fetched before I found the GeoTIFF feed: **duplicates, delete** (my `rm` was refused by the safety check, so I moved them) | 497 MB |
| `osm/` | Berlin.osm.pbf, Berlin.poly | 174 MB |
| `trees/` | strassenbaeume_bbox.geojson, anlagenbaeume_bbox.geojson | 260 MB |
| `lamps/` | beleuchtung_bbox.geojson, erhaltungsbereiche_gasbeleuchtung.geojson | 60 MB |
| `buildings_heights/` | gebaeudehoehen_bbox.geojson | 289 MB |
| `landuse/` | reale_nutzung_2024_bbox.geojson, gruen_freiflaechen_2024_bbox.geojson | 29 MB |
| `backdrop/` | 2 GLO-30 COGs | 62 MB |
| `other/` | lichtsignalanlagen_bbox.geojson | 0.5 MB |

LoD2 tiles (E_N in km, ETRS89/UTM33): every tile that intersects A buffered by 1 km, see `raw/lod2/tiles.csv` (E 383-398, N 5814-5823).

## 8. RECOMMENDATION for M1

1. **CRS**: work in EPSG:25833 (ETRS89 / UTM 33N) = what every Berlin source uses. For the engine's UTM 33N (EPSG:32633) the coordinates are the same to < 1 m (pyproj shows identical to 1e-4 m
   for the same lon/lat), so `crs = "EPSG:32633"` and Berlin's x/y can be used without a shift; just transform OSM (lon/lat) with pyproj. Heights: everything official is metres above NHN (DHHN2016); GLO-30 is
   EGM2008 (differs from DHHN by a few decimetres at most; accept). Ground datum = NHN directly (Berlin 28-45 m, set the datum to ~30 m like London's ODN datum).
2. **Buildings**: LoD2 CityGML for A + 1 km (real roofs). Parse with a streaming parser (xml.etree iterparse, 28 MB per tile, ~3 GB total, memory < 1 GB per tile; do one tile at a time): for each Building/BuildingPart take
   the RoofSurface and WallSurface polygons (resolve nothing: surfaces are in `boundedBy`, the Solid only references them), skip ClosureSurface and GroundSurface (ground is one flat z), triangulate roofs (roof polygons are planar,
   3-4 vertices mostly). Height for LOD-less use = `bldg:measuredHeight`; eave height can be derived from the lowest RoofSurface z. Footprint area per tile is the union of the GroundSurface polygons. Join the WFS `geschosse` / `name` / `funktion_txt`
   by `gml_id` (= building `gml:id`; BuildingParts are separate rows in the WFS too, role "Gebaeudeteil"). Drop sheds and canopies (function 51009_1610 "Ueberdachung" = 10.7 k of 90 k in A; 33 % of all footprints < 25 m2).
   Margin ring (1 km to 4 km): the Gebaeudehoehen WFS footprints extruded to `hoehe` with `dachart` as the roof shape (flat / gable / hip / mono) instead of OSM (OSM has a third of Berlin's buildings).
   Do not stitch LoD2 and OSM footprints: OSM only for names/landmarks/roads/water.
3. **Terrain**: DGM1 GeoTIFFs (81 tiles, A + 4 km) as the `ground` DEM; downsample (e.g. 2 m or 4 m) for the 4 km area; GLO-30 for the `backdrop` (36 km; bias +4 m median, +15 m p95 over the Grunewald/Spandau/Koepenick forests and city: lower it by the median or accept).
   Mind the cut-and-cover tunnels (Tiergarten tunnel at Potsdamer Platz dips to 15 m; Tunnelportale) when draping roads and building ground z (LoD2 ground z = DGM10, median 0.26 m below DGM1, p5 2.3 m).
   If the +20 m forest on the backdrop shows, the Brandenburg DGM1 route is the upgrade (9.7 GB for the box, a 4-12 km ring is a fraction).
4. **Trees**: Baumkataster street + park trees as the real tree points with species, height and crown diameter (genus mix = Linde/Ahorn/Platane/Eiche/Rosskastanie: map `gattung` to the engine's species classes);
   treat height 0 and crown 0 as unknown; ~101 k trees in A, ~320 k in A + 4 km (instance by LOD). Add OSM `natural=tree` not within ~3 m of a Kataster tree if you want private trees.
5. **Lamps**: `beleuchtung` points (27.7 k in A) with `rotation` and `leuchtentyp` (+ `betriebsart` Gas = 1,687 warm gas lamps: Aufsatz/Haenge/Sonder): the first city where lamp models can be taken straight from an inventory. Skip status "Ausser Betrieb"/"zeitw. Demontiert" and "Schaltkasten".
6. **Licences**: all official data dl-de/zero-2.0 (no attribution duty; a courtesy line is fine). OSM ODbL ("(c) OpenStreetMap contributors"). GLO-30: the Copernicus attribution (in `raw/backdrop/README.txt`). ESA WorldCover CC BY 4.0. Brandenburg DGM (not used) would need dl-de/by-2.0.
7. **Do not** use: the 3D mesh (click-through terms), ALKIS WMS, GBA/Overture.

## 9. Blocked / not verified / issues

- Nothing was blocked by the network. **Click-through:** the Berlin 3D download portal (mesh model, OBJ+textures; dl-de/zero-2.0 but needs terms acceptance): not downloaded, report to the controller if wanted.
- Brandenburg DGM1 for the full 36 km box (9.7 GB) was not fetched (budget 5 GB); GLO-30 DSM replaces it at +4 m median bias.
- DGM1 GeoTIFF: no EPSG GeoKey (set EPSG:25833 manually); a few tunnel/pit artifacts.
- Not verified: the exact copyright holder text for the Baumkataster/Beleuchtung (the dl-de/zero licence needs none); building `geschosse` quality (0 on 12 % in A); the OSM water polygons vs DGM water (not checked); roof type code list (AdV standard, not in the feed).
- First 19 DGM1 xyz zips were fetched before I found the GeoTIFF feed: duplicates in `raw/dgm1_xyz_zip_partial/` (497 MB), safe to delete (my own `rm` was blocked by the safety check, so I did not delete them).
- Phase 0's correction to the skill row: the "Berlin 3D download portal / district packages / <= 9 km2" description is out of date for LoD2 (see below).

## 10. Corrected Berlin row for `references/data-sources.md` (text for the controller; I did not edit that file)

> | **Berlin / Germany** | **Berlin LoD2 CityGML 1.0** (ALKIS footprints, laser-scan roof heights, generalised standard roofs, no textures), free under **dl-de/zero-2.0**: the INSPIRE ATOM feed `https://gdi.berlin.de/data/a_lod2/atom/` (925 tiles of 1 x 1 km, `LoD2_<E>_<N>.zip`, ETRS89/UTM33 = EPSG:25833, z = m above NHN, ~3.5 MB zip / 28 MB xml per inner-city tile; there are no district packages; needs a custom User-Agent from CN) [verified 2026-10]. The Berlin 3D download portal (`download-berlin3d.virtualcitymap.de`) now serves only the 2025 photogrammetric **mesh** (OBJ + textures, terms click-through), not LoD2. The same LoD2 as 2D footprints with `hoehe`, `geschosse`, `dachart`, `funktion` is the Umweltatlas WFS `https://gdi.berlin.de/services/wfs/ua_gebaeudehoehen` (954 k buildings, JSON output). | **DGM1** (1 m, bare earth, laser 2021): `https://gdi.berlin.de/data/el_dgm/atom/dgm1_33_<E>_<N>_2_be_2025.tif` (GeoTIFF float32, 2 x 2 km, 16 MB/tile; the xyz-zip twin is `.../data/dgm1/atom/`) [verified]; Brandenburg DGM1 (dl-de/by-2.0, 1 km tiles) at `https://data.geobasis-bb.de/geobasis/daten/dgm/tif/`; backdrop Copernicus GLO-30 (a DSM, +4 m vs the DTM) | Building heights and storeys: the LoD2 `measuredHeight` and Umweltatlas `geschosse` (OSM has a third of the buildings). Trees: Baumkataster WFS `.../wfs/baumbestand` (street 435 k + park 528 k trees, species/height/crown, dl-de/zero-2.0). Street lamps: WFS `.../wfs/beleuchtung` (210 k points, `betriebsart` Strom/Gas, `rotation`). OSM extract: BBBike `Berlin.osm.pbf` (poly lon 12.76-13.98, lat 52.23-52.82). Extrude-vs-roof: LoD2 has real roofs, so import them. |
