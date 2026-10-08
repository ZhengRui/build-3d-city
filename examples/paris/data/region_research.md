# Paris — region preset research (`europe-west`)

Compiled 2026-09-30 for the build-3d-city engine, for Paris's milestones M2 (building kinds), M4 (facades), M5
(ground), M6 (trees, cars, rooftops) and M8 (night). Units: metres unless noted. Tags:
**(src)** = read in the named source this session; **(measured)** = computed by me from open data downloaded
here (method named); **(sampled)** = PIL colour sampled from a real image (IGN orthophoto or a Wikimedia Commons
photo, method in §5.4); **(derived)** = computed from sourced numbers; **[believed]** = my estimate or recall,
unverified. Hex values sampled from photographs are photo tones (exposure, haze, sun angle), not albedo: use
them as hints, and see §4.3 and §5.4 for how far to trust each.

What this file feeds: `europe-west.toml` is still an exact copy of New York's `us-northeast` (30 Sept 2026).
Each section ends with **"Preset: NYC now → Paris needs"**, naming the table to replace.

---

## 0. Headline preset values

| Key | Value |
|---|---|
| Driving side | **Right** |
| Centre line (two-way) | **White**, never yellow: `markings.centreColour = "white"` (already set). Axial line 2u = **12 cm** wide (u = 6 cm on Paris streets), dashed T1 **3 m stripe / 10 m gap** (period 13 m), or continuous; double continuous line 2 × 18 cm with 18 cm gap |
| `markings.dashes` (`[period, painted]`, m) | street / arterial / centre **[13, 3]** (T1); Périphérique 7.5 cm units, still [13, 3]. Shorter T3 (3 m / 1.33 m, period 4.33) only before a continuous line and on bus/bike lane edges |
| Lane line | White T1 3 m / 10 m, 12 cm wide (2u); bike-lane and bus-lane boundary 30 cm (5u), T3 or continuous |
| Stop line | White continuous **0.50 m**; traffic-light stop line 0.15 m dashed 0.5/0.5 m; give-way line 0.5 m dashed 0.5/0.5 |
| Zebra ("passage piéton") | White bands **parallel to the road axis**, **0.50 m wide, 0.50–0.80 m gap** (IISR); measured pitch on the ground 1.0–1.15 m; crossing depth (bar length) median **3.9 m** (p25–p75 3.4–4.0 m, n = 22,123 mapped crossings), minimum 2.5 m; median crossing span 8.5 m |
| Bus lane ("couloir de bus") | **Not painted red.** Plain asphalt bounded by a white line (5u = 30 cm, T3 or continuous), the word "BUS" in white; width 3.5–4.5 m (4.5 m for shared bus-bike lanes) |
| Bike lane | **No citywide colour**: plain asphalt with white edge lines (9 cm on tracks), white bike pictogram; two-way protected tracks on Rivoli/Sébastopol ~3.5–4 m, concrete separators. `markings.sidewalk.bike` stays `null` (no coloured paint) |
| Travel lane | 2.75–3.25 m [believed]; Haussmann boulevard roadway 14.0 m (measured), avenue-type carriageway 3 lanes each way |
| Parking bay | Longitudinal **1.8 m wide** (delivery bays 2.0 m), ~**5.2 m per car place** (24.2 m per 4.67 places); motorcycle bays 1.8 m × 4.5 m "en bataille" (measured, Paris open data) |
| Sidewalk | Haussmann boulevard **8.0 m each side** (measured: Bd Haussmann and Bd de Sébastopol both 14.0 m roadway + 2 × 8.0 m = 30 m); ordinary streets 3–6 m; surface mostly asphalt with granite kerb [believed]; Cerema recommends 2.5 m, legal clear width 1.40 m |
| Street widths (facade to facade) | Bd Haussmann **30 m** (33.6 m in places), Bd Saint-Germain 30 m, Av. de l'Opéra 30 m, Bd de Sébastopol 30 m, Rue de Rivoli 22 m, Champs-Élysées **70 m** (roadway ~30 m, 20 m each side), Av. Foch **120 m**, Av. de la Grande-Armée 70 m, Périphérique ~35 m, typical side street 10–15 m [believed] |
| Speed limit | **30 km/h** almost citywide since 30 Aug 2021; **50 km/h** on the Maréchaux, Champs-Élysées, Av. Foch, Grande-Armée, bois roads; **Périphérique 50 km/h** since 1 Oct 2024 (was 70) |
| One-way share | 69 % of primary–living_street ways in OSM are one-way (residential 72 %, primary 77 %, secondary 61 %, tertiary 58 %) (measured, local Overpass, n = 26,092) |
| Kerbside parking | Both sides on most streets, but only ~118,000 on-street car places city-wide in 2024 (~600 km of kerb, ~18 % of all kerb length): parked share `residential` 0.6, `tertiary` 0.5, `secondary` 0.35, `primary` 0.2 (derived) |
| Vehicle mix (motor traffic, central Paris) | Cars 51 %, **motorcycles/scooters 18 %**, vans 17.6 %, taxis 7 %, buses 2.5 %, coaches 0.5 %, heavy trucks 3.3 % (measured, Ville de Paris traffic counts 2022); bikes are ~11 % of all units on top |
| Taxi | Black (~70 %) with the roof light "TAXI PARISIEN": **green = free, red = occupied**; Prius/Corolla/RAV4 hybrids, Tesla Model 3, Mercedes E-Class |
| Bus | RATP/IDFM 12 m × 2.55 m × ~3.1–3.3 m (Heuliez GX 337, Bluebus 12, Iveco Urbanway); white with blue IDFM bands (exact blue [believed] ~#1E3C8C) |
| Car colours (France) | White ~29 %, grey ~21 %, black ~20 % (Europe 2023: white 29, grey 21, black 20); blue, red, green 4–8 % each |
| Street trees | **220,215** trees in the Paris open-data inventory, **110,244** "Alignement" (street) trees; alignment species: **plane 32 %**, horse chestnut 15 %, lime 11 %, Japanese pagoda tree 8 %, maples 6 %; median height 10 m (p10 5 m, p90 18 m), median trunk circumference 80 cm; median nearest-neighbour spacing 6.2 m |
| Early-October foliage | Planes green with some brown tips; **horse chestnuts largely brown and thin** (leaf-miner, since 2001), limes and pagoda trees turning yellow-green; lawns dry green |
| Roof | **Zinc, blue-grey**: real aerial mean **#909699** (shaded slope #676c70, mid #959b9e, sunlit #b1b6b8); APUR: 78.5 % of building parts have "other (zinc/slate)" as dominant roof material (68 % by footprint area), 71 % of parts are mansard-type "brisis-terrasson" |
| Mansard | brisis 70–80° (visible slope, ~3–4 m high), terrasson 10–20° (barely visible from the street); 1859 rule: 45° line, 1884: circular arc, ceiling 28.5 m |
| Facade (Haussmann) | Lutetian limestone, cream–honey: base **#d2c8b0** (sunlit p90 #dfdacf, photographed shaded #b0aba3, low-sun golden #a58d63); black wrought-iron balconies on the 2nd and 5th floors; ground floor + entresol 4–5 m, then 3.0–3.6 m floors; 7 storeys incl. attic = 22 m to the mansard's mid-height (measured) |
| Building heights | Haussmann-class (built 1801–1914, brisis roof): median surface height **21.4 m** (p10 16.7, p90 25.2); city cap 37 m (31 m centre in the 1967 plan) |
| Street lights | **75 %** LED on open-air public streets (83,413 of 110,788 points, Sept 2026 inventory); 3000 K (57 %), 2700 K (12 %), 2200 K (12 %, parks/quays); sodium ~8 % (HPS 2000 K), metal halide 7.5 %; Périphérique still 40 % low-pressure sodium (1800 K, yellow-orange); 66 % on candélabres (7 m most common), 27 % on wall consoles |
| Eiffel Tower | Golden (sodium-like, ~2000–2200 K) from 336 projectors; **sparkle** 20,000 bulbs for 5 min at the top of each hour after dusk; white rotating beacon; off at 23:45 |
| Seine | 30–200 m wide (mean ~100 m), colour dark green-brown: sunlit street level **#234C4A**, aerial **#3E4A45–#51605A**, overcast #7A7878; lower quay 2.6–2.9 m above normal water (26.7 m NGF), upper quay 6–9 m |
| Sun, 2026-10-10 (48.857° N, 2.352° E) | Declination −6.76°, EoT +13.0 min; sunrise 08:04, **solar noon 13:37**, sunset **19:12**, civil dusk 19:43, nautical 20:20, astronomical 20:56 (all CEST, UTC+2); noon altitude **34.4°** |
| 16:15 CEST (city.json start) | Sun altitude **24.6°**, azimuth **223.8°** (SW) |

`demos/paris/web/city.json` agrees: `sun.date "10-10"`, `time.utcOffset 2` (CEST until 25 Oct 2026),
`time.start 16.25`, `Night 21.5` (sun −23.5°, astronomical dark); `city.toml [sun] latitude 48.86,
declination −6.8` matches my −6.76°.

---

## 1. Road markings and street geometry

### 1.1 What the French rules say (IISR livre I, 7th part, and the Ville de Paris guide, Nov 2025)
(src) IISR 7th part art. 113–118 (arrêté of 24 Nov 1967, consolidated 2009) and the Ville de Paris
"Guide des signalisations verticale et horizontale à Paris, partie 1" (Nov 2025). All numbers below read in
those texts.

**Unit width u.** Line width is a multiple of u: 7.5 cm on motorways and separated carriageways, 6 cm on
"grande circulation" roads, 5 cm on other roads, 3 cm on cycle tracks. **Paris chose u = 6 cm on all its
streets, 7.5 cm on the Périphérique, 3 cm on pistes cyclables.** So on an ordinary street 2u = 12 cm,
3u = 18 cm, 5u = 30 cm.

**Dashed-line modulations** (stripe / gap; all multiples of 13 m):

| Type | Stripe / gap | Where used |
|---|---|---|
| T1 | 3 m / 10 m | Axial line and lane separator (ratio 1:3) |
| T'1 | 1.5 m / 5 m | Low-speed axial line, cycle-track axis |
| T2 | 3 m / 3.5 m | Edge line ("ligne de rive"), width 3u |
| T3 | 3 m / 1.33 m | Warning line before a continuous line; lane lines with two lanes in one direction in town; bike-lane and bus-lane edges (5u wide) |
| T'2 (transversal) | 0.5 m / 0.5 m | Give-way lines, traffic-light stop lines (15 cm), parking-bay limits |
| T'3 / T4 | 20 m / 6 m; 39 m / 13 m | Slip-road and interchange edges (Périphérique junctions) |

| Marking | Width | Notes |
|---|---|---|
| Axial line, lane separator | 2u (12 cm) | Continuous or T1; 3u on islands' approaches |
| Double continuous line | 3u each (18 cm), gap 3u | |
| STOP line | 50 cm, continuous | |
| Traffic-light stop line | 15 cm, T'2 | |
| Zebra band | 50 cm, gap 50–80 cm | Parallel to the road axis; length ≥ 2.5 m in town; 3–5 bands on a 4–6 m roadway, 8–11 on 10–12 m; the centre line is broken 0.5 m either side |
| Bike box ("sas vélo") | Two stop lines 3–5 m apart | Bike pictogram in each lane; colour of the box not fixed by the IISR |
| Bus lane | Edge 5u (30 cm), T3 (normal direction) or continuous (contraflow); "BUS" lettering at crossings and along the lane; "damier" of 0.8–1.2 m squares through junctions | |
| Yellow lines | 2u | Yellow (RAL 1023) only for no-stopping lines, bus-stop zigzag (≥ 10 m), temporary works |
| Parking bay limit | 2u white | Paris "does not use red or blue" markings (Ville de Paris guide, p. 27): no blue zones |
| Taxi rank | white bay + "TAXI" | |
| Marking colour | White (RAL 9016) | |

**Measured on the ground (IGN orthophoto, 20 cm/px, 11e arrondissement, my tile "faubourg_11e" centred at 48.8600 N, 2.3790 E).** Zebra bars pitch 5.6–5.75 px = 1.1–1.15 m; bars are cream-white **#b7b5af** (top 15 %
brightest pixels; photo tone), junction asphalt **#6d6e70**. Bar length 3.7–4.4 m. This matches the
Paris-wide mapped crossings (below).

**Mapped crossings (measured).** Ville de Paris "Plan de voirie – Passages piétons" (22,123 polygons, each one
crossing): minimum-rotated-rectangle short side (bar length) percentiles 5/25/50/75/95 = **2.9 / 3.4 / 3.9 /
4.0 / 5.1 m**; long side (span across the roadway) 4.1 / 6.4 / **8.5** / 11.2 / 16.3 m.
Source: opendata.paris.fr `plan-de-voirie-passages-pietons` (records export, geojson).

**Engine mapping.** `city.json markings.dashes` is `[period, painted]` in metres: Paris T1 is **[13, 3]**
(Shenzhen's [12, 3] happens to be within 1 m, but set it explicitly); T3 = [4.33, 3]. `centreColour "white"`
already set. The engine's zebra keeps NYC's high-visibility layout (bars along the traffic direction) but with **0.5 m bars,
~0.55 m gaps and ~3.9 m long** (NYC: 0.6 m bars, 3–4.5 m); stop line 0.5 m.

### 1.2 Asphalt, kerbs and pavements
- **Asphalt colour** (sampled, IGN orthophoto): avenue **#7b7876**, Marais street in sun **#918e8b**, shaded
  street **#76706b** (median of 3 boxes), junction **#6d6e70**, one shaded boulevard **#5b5d60**. The orthophoto is a
  photograph, so keep a mid-grey base **#6d6b69–#7d7977** and rely on wear, patches and the lane paint. The "pale enrobé" impression in central
  Paris comes mostly from light limestone facades and light pavements [believed], not from the asphalt.
- **Kerbs:** granite kerb (bordure granit), mid grey with a paved or granite gutter (caniveau), 12–14 cm
  upstand, lowered to ~2 cm at crossings [believed, common knowledge; no source read].
- **Sidewalk surface:** mostly asphalt (enrobé) with granite kerb and, on boulevards, wide bitumen sidewalks with
  tree grates; granite slabs or setts only in specific places (Champs-Élysées' famous beige-grey bitumen
  with granite kerbs; Place de l'Étoile [believed]). Sampled pale paving at the Étoile: **#d4cec4** (sunlit
  pale slabs/pavers; the base ring is darker #969191). A shaded asphalt sidewalk (11e) read **#66676b**.
- **Cobbles/setts** are rare and local. OSM `surface=sett` occurs on **~7 %** of residential ways (975 of 13,217)
  and ~7 % of primary ways (316 of 4,521) in the Paris bbox (measured, local Overpass); the Ville de Paris
  publishes a small polygon layer `plan-de-voirie-paves-mosaiques-du-plan-de-voirie-de-paris` (372 polygons)
  for mosaic paving. Typical granite setts ~10 × 10 cm [believed]. Real cobbled places: Montmartre's lanes,
  parts of the Marais, cours and passages, Place de la Concorde forecourt [believed].
- **Tree grates** ("grilles d'arbre"): cast iron, dark grey-black; standard catalogue sizes 0.8–1.5 m square
  (795, 995, 1195, 1495 mm) (src: manufacturer catalogues via search); Paris's own planting pit is ~3 × 3 m
  and 1.4 m deep (src: search summary); pits sit in the furnishing zone next to the kerb.
- **Kerbside furniture** [believed]: Wallace fountains (dark green cast iron, ~2.7 m), Morris columns (~3.5 m ×
  1.5 m), steel bollards ("potelets") 1.0–1.2 m in dark grey/green-black at kerbs and crossings.

### 1.3 Street widths and profiles
(src) widths from the French Wikipedia pages of each street unless marked; roadway/sidewalk split (measured)
from the Ville de Paris Plan de voirie ("chaussées" and "trottoirs – emprises" polygons within 25 m of a street
tree; minimum-rotated-rectangle short side of the strip polygon, so ±0.5 m).

| Street | Total width | Roadway (measured) | Sidewalk each side (measured) | Notes |
|---|---|---|---|---|
| Bd Haussmann | 30 m (33.6 m in places) | **14.0 m** | **8.0 m** | 2,530 m long, plane trees |
| Bd de Sébastopol | 30 m | **14.0 m** | **8.0 m** | Two-way protected bike track, 14,900 bikes/day (2024) |
| Bd Saint-Germain | 30 m | 16–19 m | 6.5–7 m | 3,150 m |
| Av. de l'Opéra | 30 m | — | — | 698 m, **no trees** |
| Rue de Rivoli | 22 m (20.8 m along the Tuileries) | — | — | One general lane + bus lane + two-way bike track since 2020 |
| Rue de la Paix | 22.5 m | — | — | |
| Champs-Élysées | 70 m total | ~26–30 m | 20 m (beige bitumen, 4 tree rows) | 8 lanes; 1,910 m; 50 km/h |
| Av. Foch | 120 m incl. gardens | 15.2 m (each carriageway) | 12 m (with unpaved bridle path) | 1,300 m |
| Av. de la Grande-Armée | 70 m | ~36 m | ~11 m + wide lawns | 775 m |
| Bd Montparnasse | ~40 m | 20.4 m | 9–11 m | |
| Bd de Clichy | ~35 m | 2 × 9 m either side of the mall | 5.5 m | Planted central mall |
| Périphérique | ~35 m | 2 × 4 lanes (2 × 2 Italie–Orléans, 2 × 3 Orléans–Sèvres) | — | 35.04 km; ~half on viaduct/embankment, 40 % trench, 10 % ground; u = 7.5 cm |

Typical Haussmann-era cross-section of a 30 m boulevard: 8 m sidewalk (with a row of planes at 8–10 m centres,
grates, kiosks) + 14 m roadway (3 traffic lanes or 2 lanes + bus lane + kerbside parking/bike) + 8 m sidewalk.
Narrower side streets are 10–15 m facade to facade [believed] with 3–5 m sidewalks and one lane plus parking
each side. Random sample of 150 street-tree sites (so biased to the wider planted streets), elongated strip polygons
only: **roadway width p10/25/50/75/90 = 6.0 / 7.7 / 10.7 / 14.2 / 16.5 m; sidewalk strip 4.6 / 5.5 / 6.8 / 8.9 /
10.2 m** (the sidewalk figure includes the tree pit strip).

Other network facts (src): 1,700 km of roads over 26.5 km² (60 % carriageway, 40 % sidewalks and cycle);
minimum clear pedestrian width 1.40 m (arrêté of 15 Jan 2007); Cerema recommends 2.5 m.

### 1.4 Lanes, one-way streets, speed (OSM, local Overpass, Paris bbox 48.815–48.905 N, 2.22–2.47 E)
| Class | Ways | One-way | Mean `lanes` (tagged ways) | `maxspeed=30` | `maxspeed=50` |
|---|---|---|---|---|---|
| motorway (Périphérique, A1/A13 stubs) | 177 | 100 % | 3.24 | — | 37 (70: 82, 90: 54) |
| trunk | 372 | 100 % | 3.73 | — | 356 |
| primary | 4,521 | 77 % | 2.67 (3,986 tagged) | 2,283 | 2,033 |
| secondary | 3,594 | 61 % | 2.23 | 2,250 | 837 |
| tertiary | 2,604 | 58 % | 1.97 | 2,113 | 216 |
| residential | 13,217 | 72 % | 1.39 | 10,748 | 314 |
| living_street | 1,261 | 72 % | 1.18 | (20 km/h: 952) | — |

OSM `lanes` on one-way roads counts the lanes in that direction. Note OSM's speed tags reflect the zone 30
(since 2021) and the axes left at 50; the Périphérique carries 50 in reality since 1 Oct 2024 (OSM still shows
70 on 82 motorway ways).

### 1.5 Bus lanes, bike lanes, parking (details)
- **Bus lanes:** bordered by white lines, lettered "BUS", often shared with bikes ("couloirs bus-vélo", 4.5 m
  wide, max ~30 buses/h) and taxis. **No red or coloured surface** (IISR: coloured surfacing may not replace
  markings; the Ville de Paris guide states it uses no red/blue markings) (src).
- **Bike lanes:** Paris's 2020+ "coronapistes" and permanent tracks are on Rivoli, Sébastopol, Bd de Magenta,
  the Champs-Élysées etc.: two-way, ~3.5–4 m, separated by concrete separators/kerbs, surface plain asphalt with
  white pictograms; green paint is used at some conflict zones and bike boxes [believed]; I found no citywide
  colour rule (src: search summaries; unverified). All one-way streets in the zone 30 allow contraflow cycling
  ("double sens cyclable") (src). Bike modal share 11.2 % in 2024, 117,607 bike parking places (src: paris.fr
  bilan 2024).
- **Parking (measured)** from `stationnement-voie-publique-emplacements` (65,833 bay records, 2024):
  longitudinal pay bays average **1.8 m wide** and **24.2 m long per record of 4.67 places** (5.2 m per
  place); delivery bays 2.0 m wide, 11 m per record; motorcycle bays "en bataille" 1.8 m × 4.45 m, 134,138
  places; "en épi" (angled) two-wheel bays 1.67 × 8.5 m. City-wide 2024 on-street counts (src: paris.fr
  bilan 2024): **118,383 car places**, **43,483 motorised two-wheeler places**, 117,607 bike places; car places
  fell 3 % in a year and the city plans to convert half of them.

### 1.6 What the engine needs (Preset: NYC now → Paris needs)
| Table (europe-west.toml / city.json) | NYC now | Paris |
|---|---|---|
| `markings.centreColour` | yellow (US) | **white** (already in city.json) |
| `markings.dashes` `[period, painted]` | Shenzhen [12,3] | **[13, 3]** all classes (T1) |
| zebra bars (06b_markings) | 0.6 m bars, along traffic | **0.5 m bars, gap 0.55 m, length 3.9 m, along the road axis**, up to 4–5 m on avenues |
| stop line | 0.45–0.6 m | 0.5 m |
| bus lane | red terra-cotta paint | **none** (asphalt with "BUS" lettering, white edge) |
| bike lane | green paint | none (asphalt, white pictogram); `markings.sidewalk.bike = null` |
| `[markings.sidewalk_w]` | trunk 5.0, primary 5.5, secondary 5.0, tertiary 4.5, residential 4.0 | trunk 4, primary **7** (Haussmann boulevards 8 m; Champs 20 m), secondary **5**, tertiary 4, residential **3.5**, unclassified 3, living_street 2.5 |
| `[markings.median_w]` | Park Avenue-type | primary 3 (planted malls like Bd de Clichy, Bd Richard-Lenoir), motorway/trunk 1.5 (Périphérique barrier) |
| `[roads.parking_lanes]` | 2 | primary **1**, secondary 2, tertiary 2, residential 2 (only a share of the kerb is bay: see `cars.kerbside`) |
| `[roads.default_w]` (kerb to kerb) | primary [21,18] (Manhattan avenues) | motorway [26,13] (Périphérique 4 lanes + shoulders), trunk [18,10], primary **[14, 12]** (Haussmann roadway 14 m), secondary [10, 9], tertiary [8, 7], residential **[7, 6]**, living_street [5, 4], service [4, 3.5] [believed for the small classes] |
| `LANE_W` | 3.5 (Shenzhen) | **3.0–3.25 m** [believed] |
| `lanes` for OSM roads without tags | US | primary 2 per direction, secondary 1–2, residential 1 (one-way 72 %) |
| sidewalk paving `markings.sidewalk.paving`, `flag`, `red`, `tactile`, `pits`, `flowers` | NYC flags, brick-red 28 % blocks | grey asphalt-like paving ~[0.42,0.41,0.39] (already Shenzhen-ish), `red: 0`, `tactile: false` for old streets, no flags, tree grates (pits) on boulevards |
| `grid` / lamps | | see §6 |

---

## 2. Vehicles

### 2.1 Traffic mix (measured, Ville de Paris open data "Compositions du trafic à Paris")
The city's counting campaign (mid-November, 10:00–16:00 averages over count sites on the main axes and the
Maréchaux). Percent of all counted units:

| Class | 2014 intra-muros | 2022 intra-muros | 2022 Maréchaux | 2022 Périphérique |
|---|---|---|---|---|
| Cars | 55.3 % | **45.1 %** | 53.3 % | 56.1 % |
| Vans (utilitaires) | 14.9 | 15.5 | 14.2 | 16.5 |
| Motorised two-wheelers | 14.5 | **15.9** | 18.5 | 18.8 |
| Taxis | 9.1 | 6.2 | 4.8 | 4.9 |
| Buses | 1.4 | 2.2 | 1.7 | 0.2 |
| Coaches | 0.3 | 0.4 | 0.7 | 0.1 |
| Heavy trucks | 1.6 | 2.9 | 1.9 | 3.4 |
| Vélib' + personal bikes + e-scooters | 2.8 | **11.6** | 6.9 | ~0 |

(Heavy vehicles above 7.5 t are restricted in Paris and Crit'Air 5 trucks and buses are banned 8:00–20:00, so
"heavy truck" means mostly 12–19 t delivery rigid trucks: src search summaries.) Car traffic inside Paris fell
12.5 % in 2024 and ~60 % since 2002 (src: paris.fr bilan 2024).

Motor-only, renormalised (2022 intra-muros): cars 51.1 %, vans 17.6 %, two-wheelers 18.0 %, taxis 7.0 %,
buses 2.5 %, coaches 0.5 %, heavy trucks 3.3 %.

**Suggested spawn mix, central Paris streets, daytime, motor vehicles (derived):**

| Class | Share | Engine type |
|---|---|---|
| Hatchbacks/city cars (Clio, 208, C3, Sandero, Twingo, Yaris) | 32 % | `sedan` (short 4.1 m) |
| SUVs and crossovers (2008, Captur, T-Roc, Model Y) | 19 % | `suv` (4.35 m) |
| Taxis | 8 % (12 % on the big axes, near stations) | `taxi` |
| Vans (Kangoo/Berlingo 55 %, Trafic/Expert 30 %, Master/Sprinter 15 %) | 16 % | `van` |
| **Motorcycles and scooters** | **17 %** | new type `moto` (the engine has none) |
| Buses | 4 % on bus-lane axes, 0 % on side streets | `bus` |
| Rigid delivery trucks | 3 % | `truck` |
| Coaches, emergency, other | 1 % | |
Add bikes at ~12 % of all units (30–40 % on Rivoli and Sébastopol; 14,900 bikes/day on Sébastopol in 2024).
Central artics (`lorry`) essentially none: set the `lorry` column to 0 except on the Périphérique (3 %).

Traffic density: ~600–900 vehicles/hour/lane in a congested central lane [believed]; Paris is slow: measured
average speeds are in the 15–20 km/h range on the main axes [believed], so the engine's free-flow speeds should
be **8.3 m/s (30 km/h)** on zone-30 streets and 13.9 m/s (50 km/h) on the axes and Périphérique.

### 2.2 Taxis
- Fleet ~17,100 (2013) to ~18,000 (2024, Ministry figure); G7 ~9,000 in Paris; G7 says > 50 % hybrid/electric in
  Île-de-France (src: Wikipedia "Taxis parisiens", journalauto).
- Models (src: press): Toyota Prius/Prius+, Corolla, Camry, RAV4 hybrid, Tesla Model 3 (readmitted 2022), Model
  S, Mercedes E-Class/EQE, Škoda Enyaq. Body length 4.6–4.9 m.
- **Colour:** no legal body colour in the source I found. Most Paris taxis are **black**; use black 70 %,
  white 15 %, grey/silver 10 %, other 5 % **[believed]**. (Not yellow.)
- **Roof light ("lumineux")**: mounted across the roof at the front, min 210 × 100 × 40 mm, capital letters
  "TAXI" 50–100 mm high, **green when free, red when occupied** (Arrêté of 13 Feb 2009 via search
  summary); real units ~40–55 cm wide [believed]. The Paris-specific version reads "TAXI PARISIEN" (name on the
  light and on a plate on the rear doors [believed]).
- Taxi rank marking: white bay lines and the word "TAXI".

### 2.3 Buses
| Fact | Value | Source |
|---|---|---|
| RATP fleet | ~4,700 buses in Île-de-France (end 2024), ~1,000 electric, ~1,300 biomethane; 315 lines | ratpgroup.com Bus2025 (search summary) |
| Electric fleet Feb 2025 | 549 Heuliez GX 337 Elec, 233 + 88 Bluebus 12 (IT3), 50 Alstom Aptis, 60 Irizar ie bus | transbus.org 2025-02 |
| Standard length | **12.0 m** (GX 337, Bluebus 12, Iveco Urbanway 12); midibus 9.5 m; articulated 18 m | search summaries |
| Width / height | 2.55 m; ~3.0–3.3 m (roof batteries on e-buses) | [believed] |
| Livery | Old STIF grey "vif-argent"; since 2017/18 IDFM: **white body (RAL 9003) with blue bands and a blue rear** (IDFM blue "50555"), IDFM logo repeated | IDFM charter via search summary; hex [believed] |

Suggested engine values: `bus` = 12.0 × 2.55 × 3.15; palette body #f2f3f4, band #1e3c8c (IDFM blue
[believed]), lower skirt #5a5f66, roof #c9cdd1 [believed]. Tramways (T3a/T3b along the Maréchaux) are not
buses: separate from the road (OSM `railway=tram`).

### 2.4 Car dimensions (mm; L × W without mirrors × H) (src: Wikipedia model pages via the research helper)
| Model | L | W | H | Note |
|---|---|---|---|---|
| Renault Clio V | 4,050 | 1,798 | 1,440 | France's best-seller |
| Peugeot 208 II | 4,055 | 1,745 | 1,430 | |
| Peugeot 308 III | 4,367 | 1,852 | 1,440 | |
| Peugeot 2008 II | 4,300 | 1,815 | 1,550 | best-selling SUV |
| Citroën C3 III / IV | 3,996 / 4,015 | 1,749 / 1,813 | 1,470 / 1,577 | |
| Dacia Sandero III | ~4,090 | 1,758 | ~1,500 | |
| Renault Captur II | 4,228 | 1,797 | 1,566 | |
| Tesla Model Y | 4,751 | 1,920 | 1,624 | |
| Smart fortwo | 2,695 | 1,663 | 1,555 | |
| Renault Kangoo III van | 4,486 | 1,919 | 1,838 | |
| Citroën Berlingo III M / XL | 4,403 / 4,753 | 1,848 | ~1,800 | |
| Renault Trafic III | 5,080 / 5,480 | 1,904 | 1,971–2,498 | |
| Renault Master / Fiat Ducato / Sprinter | 5,048–6,848 / 4,963–6,363 / 5,931–7,366 | 2,070 / 2,050 / ~2,020 | 2,300–2,760 / 2,450–3,050 | [believed] except Sprinter (Wikipedia) |
| Motorcycles/scooters | Yamaha NMAX 125 1,955 × 740 × 1,115; TMAX ~2,200 × 765 × 1,420; Honda Forza ~2,140 × 750 × 1,330; Vespa ~1,860 × 700 × 1,190 | | | NMAX Wikipedia; others [believed] |
| Vélib' | ~1.9 × 0.6 × 1.1 m, 20.6 kg (e-bike > 25 kg) | | | ~20,500 bikes, ~1,500 stations |

Engine `cars.types` (name, L, W, H): sedan **[4.10, 1.78, 1.47]**, suv **[4.35, 1.83, 1.60]**, taxi **[4.62, 1.80,
1.48]** (Prius/Corolla with a 0.15 m roof light), van **[4.6, 1.9, 1.85]** (Kangoo/Berlingo; add Trafic
[5.1, 1.9, 1.97] as a variant), bus **[12.0, 2.55, 3.15]**, truck **[7.5, 2.4, 3.3]**, lorry [12.0, 2.55, 3.8], plus a new
`moto` [2.0, 0.75, 1.2] and optionally `bike` [1.8, 0.6, 1.1] (11–12 % of units).

### 2.5 Colours (France)
(src) Europe 2023 new cars (BASF via L'Argus): **white 29 %, grey 21 %, black 20 %**, blue fourth; the three
neutrals are 81 % of new cars; France's top chromatic colour is green (6 %). France 2024 registrations
(AutoScout24, secondary): grey ~570,000 (~1 in 3), white 337,000, black 265,000, blue > 189,000, green ~63,000
(+260 %), yellow 23,000. Older cars in Paris are more silver/red/blue than a new-car list shows.

Suggested palette for parked and moving cars (share, hex; a synthesis, not a statistic):

| Colour | Share | Hex |
|---|---|---|
| White | 20 % | #f0f0ee |
| Black | 19 % | #16171a |
| Mid/silver grey | 16 % | #8d9196 |
| Anthracite | 12 % | #4b4f55 |
| Blue (dark/mid) | 8 % | #2c4a78 |
| Red | 6 % | #a32028 |
| Green (khaki/forest) | 4 % | #4e6a57 |
| Beige/champagne | 4 % | #c9bb9f |
| Light blue | 3 % | #7f9bb5 |
| Brown/bronze | 3 % | #6d4f3a |
| Bright (orange/yellow/other) | 3 % | #d9822b |
| Taxi black | fleet | #101114 |

Delivery: La Poste vans are yellow (RAL 1023-ish **#ffcc00** [believed]) with blue logo (Kangoo ZE, Master,
Staby); Chronopost/DPD/Amazon vans mostly white 3.5 t vans; police Renault Trafic/Peugeot 3008 dark blue and
white [believed]; BSPP fire engines red [believed].

### 2.6 Parking rows in the engine
Kerb length lined with parked cars: 118,383 car places × 5.2 m ≈ 616 km of the ~3,400 km kerb of the 1,700 km
network (18 %); adding the streets without parking (Périphérique, tunnels, pedestrian areas) it is ~30 % of
parkable kerb. So kerb shares of **residential 0.6, tertiary 0.5, secondary 0.35, primary 0.2** (Haussmann
boulevards keep parking only on some segments; many have a bus/bike lane at the kerb) (derived), and **0.85–0.9
occupancy** of bays by day (search: paid-parking occupancy is very high in the centre) [believed]. Motorcycle
bays: 43,483 places (bay 1.8 × 4.5 m "en bataille", groups of 2–6) parked at ~90 % occupancy.

### 2.7 Preset: NYC now → Paris needs
| Table | NYC now | Paris |
|---|---|---|
| `cars.types` | Camry sedan, NYC taxi, NV200, Xcelsior bus 12.5 × 2.59 | see §2.4; add `moto` |
| `cars.class` mix (sedan, suv, taxi, van, bus, truck, lorry) | avenue [30,22,26,10,7,7,0] | primary **[28,17,9,16,4,3,0]** + moto 17 (renormalise to 100 with a moto column); secondary [30,18,8,17,2,3,0]+moto 17; residential [33,19,5,18,0,2,0]+moto 17; motorway (Périph) [42,26,5,12,2,5,3]+moto 5 |
| free-flow speed | 10 / 9 / 7 m/s (25 mph) | primary **9.0** (30 km/h zone; 13.9 on the 50 axes), secondary 8.3, tertiary/residential 7.0–8.3, motorway/trunk 13.9 (50 km/h Périph) |
| `cars.palettes.taxi` | #ffbf0f yellow | **black #101114 (70 %), white #f0f0ee 15 %, grey #8d9196 10 %**, roof light green #40ff70 / red #ff3030 (emissive) |
| `cars.palettes.bus` | white/blue MTA, navy | white #f2f3f4 with blue #1e3c8c bands 100 %, occasional articulated 18 m |
| `cars.palettes.van` | UPS brown, FedEx | white 60 %, yellow La Poste 6 %, grey 14 %, blue/red/other 20 % |
| `cars.palettes.sedan/suv` | US Axalta | French palette in §2.5 |
| `cars.kerbside` | 0.45–0.95 | primary 0.2, secondary 0.35, tertiary 0.5, residential 0.6, unclassified 0.5, living_street 0.5, service 0.2 |
| `cars.oneway_both_sides` | true (alternate-side parking) | true (parking both sides is normal), **`kerb_occupancy` 0.9**, more two-wheeler rows |
| `parked_mix` | mostly sedans/SUVs, few vans | 45 hatch, 25 SUV, 3 taxi, 9 van, 0, 2 truck, 0, plus ~16 motorcycles in dedicated rows |

---

## 3. Street trees and parks

### 3.1 The Paris tree inventory can be downloaded here (tested)
- **Dataset:** Ville de Paris open data, "Les arbres" (`les-arbres`), licence ODbL.
  Page: https://opendata.paris.fr/explore/dataset/les-arbres/
- **API (works from this machine, no account):**
  `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/les-arbres/records?limit=2` returns
  `"total_count": 220215` and rows with `idbase, typeemplacement, domanialite, arrondissement, adresse,
  libellefrancais, genre, espece, varieteoucultivar, circonferenceencm, hauteurenm, stadedeveloppement,
  remarquable, geo_point_2d{lon,lat}`.
- **Bulk export (27–33 MB, ~1 min):**
  `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/les-arbres/exports/csv?delimiter=%3B&select=idbase,domanialite,arrondissement,adresse,libellefrancais,genre,espece,circonferenceencm,hauteurenm,stadedeveloppement,remarquable,geo_point_2d`
  (`geo_point_2d` in the CSV is "lat, lon"). My copy: scratch `paris_region/trees.csv`.
- **Count: 220,215 trees**, of which `domanialite`: Alignement (street) **110,244**, Jardin 56,711, Cimetière
  31,974, DASCO (schools) 8,645, Périphérique 6,013, DJS (sports) 4,891, DFPE (nurseries) 1,589, DAC 119,
  DASES 28. **In the 20 arrondissements: 177,010 trees, 100,695 street trees**; the rest are in the Bois de
  Boulogne (6,353) and Vincennes (11,808) and in Hauts-de-Seine/Seine-Saint-Denis/Val-de-Marne
  (25,044 in total: Seine-Saint-Denis 12,137, Val-de-Marne 7,600, Hauts-de-Seine 5,307, on the Périphérique verges and city-owned parks outside the boundary). 183 are "remarquable".
- **Caveats (measured):** heights are class values (5, 6, 8, 10, 12, 14... m), not measurements; 91 % of all
  records and 99.6 % of street trees have a height. **The state-run gardens are missing or thin** (the
  Tuileries belong to the Louvre, the Luxembourg to the Senate: my box around the Tuileries holds only 254
  trees, all from the streets around it). Use it as the source for street trees exactly like NYC's street tree
  census, and use the OSM park polygons with the class mix for the rest.
- `demos/data/paris/` has no tree file yet: the M6 stage should read the CSV, project lon/lat, and place a tree
  per row (species via `genre`, height via `hauteurenm`, crown from `circonferenceencm`).

### 3.2 Street-tree species (measured on the inventory)
Alignment (street) trees, 110,244 rows (species level):

| Species | Share |
|---|---|
| London plane (*Platanus × hispanica*, "platane") | **29.7 %** (all *Platanus* 32.3 %; + occidentalis 1.6 %, orientalis 0.8 %) |
| Horse chestnut (*Aesculus hippocastanum*, "marronnier") | **11.0 %** (+ red horse chestnut *A. × carnea* 3.0 %: all *Aesculus* 14.6 %) |
| Japanese pagoda tree (*Styphnolobium japonicum*, "sophora") | **7.3 %** (7.7 % as genus) |
| Silver lime (*Tilia tomentosa*) | 5.2 % (all *Tilia* 11.3 %: + cordata 2.1, platyphyllos 1.3, × euchlora 0.9, × europaea 0.8) |
| Hackberry (*Celtis australis*, "micocoulier") | 3.0 % |
| Norway maple (*Acer platanoides*) | 2.3 % (all *Acer* 6.2 %: + campestre 1.4, pseudoplatanus 1.1) |
| Turkish hazel (*Corylus colurna*, "noisetier de Byzance") | 2.2 % |
| Callery pear (*Pyrus calleryana*) | 2.1 % |

Others: ash (*Fraxinus*) 2.2 %, cherry (*Prunus*) 2.1 %, oak 1.6 %, elm 1.3 %, honey locust 1.3 %, poplar 1.1 %,
hornbeam 1.0 %, hop-hornbeam 0.8 %, paulownia 0.7 %, *Toona* 0.6 %, ginkgo 0.6 %.
By French name: platane 35,576; marronnier 16,034; tilleul 12,394; sophora 8,095; érable 6,829; micocoulier 3,392.

Inside the 20 arrondissements only (100,695 street trees): plane 33.5 %, chestnut 13.8 %, lime 10.0 %,
sophora 8.2 %, maple 5.7 %, hackberry 3.3 %, pear 2.3 %, ash 2.2 %, cherry 2.2 %, hazel 1.9 %.
All 220,215 trees (parks, cemeteries, schools included): plane 19.4 %, chestnut 11.3 %, lime 10.5 %, maple
9.6 %, sophora 5.2 %, cherry 4.2 %, oak 2.9 %, ash 2.9 %, hackberry 2.4 %, pine 2.4 %.

Street-specific (measured; NN = median distance to the nearest tree of the same set):

| Street | Trees | Species | NN | Median height |
|---|---|---|---|---|
| Av. des Champs-Élysées | 1,327 | horse chestnut 765, plane 549 | 5.2 m (double rows) | 12 m |
| Bd Haussmann | 344 | plane 339 | 9.1 m | 14 m |
| Bd Saint-Germain | 536 | plane 533 | 9.1 m | 15 m |
| Bd de Sébastopol | 215 | plane 202, walnut 13 | 9.5 m | 10 m |
| Av. Foch | 51 (+ lawns) | lime 51 | 4.9 m | 8 m |
| Rue de Rivoli | 32 | elm 24, cherry 8 | 4.6 m | 8 m |
| Bd Richard-Lenoir | 544 | plane 354, sophora 185 | 6.0 m | 10 m |
| Bd Voltaire | 572 | plane 388, hazel 77 | 5.5 m | 10 m |
| Bd de Magenta | 574 | elm 320, plane 146 | 5.1 m | 11 m |
| Av. de la Grande-Armée | 241 | plane 241 | 9.5 m | 10 m |
| Bd de Clichy | 219 | hackberry 143, plane 75 | 6.2 m | 9 m |
| Av. des Gobelins | 322 | ash 238, sophora 45 | 5.0 m | 6 m |
| Quais (all "QUAI ...") | 4,654 | plane 2,484, poplar 670 | 6.2 m | 10 m |
Av. de l'Opéra has none (src: Wikipedia). All alignment trees: NN 10/25/50/75/90 % = **4.7 / 5.3 / 6.3 / 7.9 /
9.8 m**; 6–10 m is the boulevard planting pitch, 4.5–5.5 m on newer avenues and double-row avenues.
Paris counts ~100,000–110,000 street trees along ~700 of its 1,650 public streets (src: paris.fr).

### 3.3 Size, form, age
Heights by species (measured; class values; p10 / p50 / p90, m) and trunk circumference at 1.3 m (p10 / p50 / p90, cm):

| Species | n | Height | Circumference | Crown width [believed] |
|---|---|---|---|---|
| London plane | 32,732 | 6 / **13** / 20 | 38 / **100** / 200 | 9–14 m (0.7 × height; pollarded rows 6–8 m) |
| Horse chestnut | 12,123 | 6 / 12 / 18 | 45 / 108 / 178 | 9–13 m, dense round |
| Japanese pagoda tree | 8,036 | 5 / 10 / 15 | 40 / 85 / 150 | 8–12 m, open |
| Silver lime | 5,763 | 5 / 10 / 15 | 45 / 95 / 142 | 6–9 m (often trimmed cubic on squares) |
| Hackberry | 3,335 | 5 / 8 / 15 | 25 / 85 / 140 | 6–9 m |
| Red horse chestnut | 3,328 | 5 / 7 / 12 | 30 / 55 / 119 | 6–8 m |
| Norway maple | 2,555 | 5 / 8 / 13 | 27 / 70 / 115 | 6–9 m |
| Turkish hazel | 2,387 | 5 / 8 / 12 | 35 / 75 / 95 | 5–7 m, pyramidal |
| Small-leaf lime | 2,365 | 5 / 10 / 14 | 25 / 76 / 120 | 5–8 m |
| Callery pear | 2,305 | 5 / 7 / 10 | 25 / 52 / 80 | 4–6 m |
| American plane | 1,722 | 7 / 12 / 20 | 50 / 100 / 190 | 8–14 m |
| Field maple | 1,495 | 5 / 5 / 9 | 20 / 37 / 75 | 4–6 m |

All street trees: height p10/25/50/75/90/99 = 5 / 6 / **10** / 14 / 18 / 25 m; circumference p10/50/90/99 =
25 / **80** / 165 / 250 cm; only 1 % have circumference ≥ 2.5 m. Age classes (street trees): Adulte 49 %, Jeune
24 %, Jeune-adulte 24 %, Mature 3 %. Planes by class: Jeune 7 m (circ 40 cm), Jeune-adulte 10 m (70 cm),
Adulte **15 m (130 cm)**, Mature **22 m (225 cm)**.
So typical street trees are **8–14 m** and reach the 3rd–4th storey (a Haussmann cornice is ~19–20 m); the big
old planes (15–25 m) are on the quais, the Champs-Élysées and in parks. Trunk diameter = circumference / π.

### 3.4 Early-October foliage
- **Horse chestnuts** (15 % of street trees) are the first to go: the leaf miner *Cameraria ohridella* (in
  Paris since 2001; three generations a year) browns and drops the leaves from July–August, so by early October
  most chestnuts are brown, thin and half bare (src: Wikipedia FR "Mineuse du marronnier", Futura-Sciences).
  Render them 40–70 % thinned, tinted **#8a6a3a–#9a7a44** with a few green leaves.
- **London planes** stay green until late October, olive with brown tips and the first yellowing; the fruit balls
  hang; some early leaf drop on the dry quays [believed].
- **Limes** turn yellow-green from late September (#a8a24a on 20 % of crowns) [believed]; **pagoda trees**
  yellow-green and drop leaflets; hackberry yellow-brown [believed].
- Peak Paris autumn colour is **late October to mid November** [believed]; on 10 October the canopy is ~75 %
  green overall.
- **Foliage tones sampled from the aerial imagery (photograph, flight in summer, so these are green-season tones,
  not October):** shaded plane crowns on an 11e boulevard **#3a4444**, Champs-Élysées shaded
  crowns **#434941**, sunlit park crowns (Olympiades) **#4f5d56 (mean)–#536258 (median)**, deep-shadow crowns in
  Buttes-Chaumont **#2b3037**. Move these toward warmer olive for October: suggested render base colours (albedo):
  plane **#5f6d3a**, chestnut **#7d6a3a**, lime **#70803c**, pagoda **#7e8a3f**, hackberry **#66743a**, maple
  **#6b7a3a**, pine/yew/cedar **#2f4a36** [believed].

### 3.5 Parks and other planting
- **Composition by ownership (measured):** parks/gardens ("Jardin", 56,711 trees): lime 9.6 %, maple 9.6 %,
  cherry 7.4 %, pine 7.3 %, oak 6.3 %, horse chestnut 5.2 %, yew 3.8 %, plane 3.7 %; **cemeteries** (31,974):
  maple 19.8 %, chestnut 12.4 %, lime 10.3 %, plane 9.8 %, ash 6.2 %, cypress 2.8 %; **Périphérique verges**
  (6,013): maple 12.4 %, plane 10.1 %, oak 7.6 %, poplar 6.7 %, black locust 6.7 %; **Bois** (18,161 in the
  inventory): lime 15.2 %, chestnut 13.6 %, oak 11.2 %, maple 11.0 %, plane 10.7 %, pine 6.8 %.
- **Champ de Mars** (2,236 trees in my box): plane 35 %, lime 25 %, sophora 12 %, chestnut 10 %; **Buttes-Chaumont**
  (2,948): yew 16 %, maple 13 %, pine 9 %, plane 8 %, chestnut 8 %; **Parc Monceau** (611): plane 25 %,
  maple 10 %, chestnut 7 %; **Jardin des Plantes** (310): plane 62 %. Median park tree height 8–11 m.
- **Tuileries** (src: Wikipedia FR and search summaries): **stabilised gravel/sand paths** (sable stabilisé,
  beige), sixteen chestnut groves along the central axis, formal limes, planes, a few elms and mulberries;
  central walk kept dust-free with raw-water sprinklers. Aerial samples: **gravel #cdc4b7 (median of sunlit
  boxes; mean #c3bbae–#c9c1b4)**, pale flagstone/gravel at the Luxembourg **#ddd9d1 (mean #d5d1c8)**; lawns
  **#8ca36e** (Luxembourg's bright irrigated octagon), Tuileries lawns **#475741–#606545**, Buttes-Chaumont
  lawn **#565c4b–#5c6150**.
- **Jardin du Luxembourg:** ~4,500 mobile "Luxembourg" chairs in "reed green" (#5a7a4a [believed]), fountains, the
  octagonal basin, clipped chestnut and plane rows, formal parterres with pale gravel; **Champ de Mars**: big
  central lawn, plane-lined side allées; **Buttes-Chaumont**: hilly, rocks, cliffs, lake, dense mixed trees
  (yews, pines); **Parc Monceau**: English-style landscape; **Bois de Boulogne/Vincennes**: 846 and 995 ha of
  woods, lakes and lawns [believed].
- **Tree grates and pits** (§1.2). The tree dataset has no tree-pit type.
- Grass tone for `ground.lawn` in city.json: current Shenzhen-ish `[[0.052,0.074,0.03],[0.1,0.122,0.052]]`
  linear; Paris parks in October read slightly dry: use the sampled sRGB range **#475741–#8ca36e** with the
  lighter end only in irrigated formal parterres [believed].

### 3.6 Preset: NYC now → Paris needs
| Table | NYC now | Paris |
|---|---|---|
| `[trees.street] default` | "broadleaf" (honey locust, pear, ginkgo, pin oak) | broadleaf: plane 33 %, chestnut 14 %, lime 10 %, sophora 8 %, maple 6 %, other 29 % (engine's species set must gain a plane/chestnut look; `trees.classes.street.mix`) |
| `step` | 8.5 m (25–30 ft) | **7.5 m** on 30 m boulevards (NN median 6.3, planes 9 m), 6 m on avenues; or place real trees from the inventory |
| `row_offset` | 1.0 m from kerb | 0.9–1.2 m (tree grate centre ~1.0 m from kerb) |
| `[trees.street.planted]` | major 0.45, minor 0.8 | primary **0.7** (Haussmann boulevards, quais), secondary 0.6, tertiary 0.45, residential **0.45** (many old narrow streets have none; Rivoli, Opéra, the centre few); the 1st, 2nd, 3rd, 4th, 9th have very few trees (2e: 478, 1er: 1,138) |
| `[trees.street.height]` | broadleaf major [9,16] minor [7,14] | major **[10, 20]**, minor **[7, 15]**; planes on quais [14, 24] |
| `[trees.street.odds]` | no palms/flowering | none (no palms) |
| `[trees.green]` `landuse=cemetery` | park | park (Paris cemeteries hold ~32,000 trees, maple/chestnut/lime) |
| `city.json trees.classes` | banyan/camphor/acacia (Shenzhen) | park: plane 25 %, lime 15 %, chestnut 12 %, maple 10 %, oak 8 %, pine/yew 10 %, other 20 %; forest (Bois): oak 25 %, lime 15 %, chestnut 12 %, maple 12 %, plane 10 %, hornbeam 8 %, pine 8 %, other |

---

## 4. Rooftops

### 4.1 What the APUR roof fields say (measured)
Source: APUR "Emprise bâtie de Paris" (128,175 parts, `emprise_batie_paris.geojson` already in
`demos/data/paris/raw/footprints/apur/`, ODbL). Fields (from the APUR layer's coded domains): `c_forme_toit`:
**1 Plate (flat), 2 À deux pentes – tuile (gabled, tile), 3 À deux pentes – tissu petite échelle (gabled,
small-scale fabric), 4 Brisis-terrasson (mansard)**; `c_toiture_mat`: **T Tuile, M Minéral (flat mineral
terrace), V Végétal, A Autre** ("other, of which zinc": zinc and slate are not separated: `m2_autre_dont_zinc`
is empty in the download); `b_terrasse` O/N; `b_psolaire` (solar panels, only 675 parts flagged);
`c_perconst` period code; `c_tissu` fabric class; `c_morpho` morphology.

All 128,175 parts (count): brisis-terrasson **71.4 %**, flat 18.1 %, gabled tile 6.6 %, gabled small-scale
3.7 %; dominant material A (zinc/slate) **78.5 %**, M (mineral) 11.6 %, T (tile) 6.7 %, V (vegetal) 2.8 %.
Main parts only (94,875 parts, excluding slabs `b_dalle` and h < 6 m; 27.6 km²), by footprint area: A **68.0 %**,
M 24.4 %, T 5.4 %, V 1.6 %; brisis 57.0 %, flat 35.8 %, gabled-tile 5.1 %, gabled-small 1.4 %.
Roof-area sums over all parts: tile 3.33 km², mineral 6.18 km², vegetal 1.17 km², flat (< 10 % slope) 5.99 km²,
of 32.25 km² footprint, so "other" (zinc/slate) ≈ **21.6 km² = 67 %** of footprint area.
So "zinc is ~80 % of Paris roofs" holds by count (78.5 %), and is ~2/3 by area.

By construction period, main parts (n; brisis %; flat %; tile %):

| Period (`c_perconst`) | Parts | Brisis | Flat | Gabled tile | Mat A / T / M / V (%) | Median h (m) | p10–p90 h |
|---|---|---|---|---|---|---|---|
| < 1800 (1) | 8,989 | 92.4 | 1.2 | 5.8 | 93 / 6 / 1 / 0 | 17.7 | 10.8–21.9 |
| 1801–1850 (2) | 13,765 | 87.1 | 2.1 | 7.5 | 91 / 8 / 2 / 0 | 17.2 | 9.5–22.0 |
| **1851–1914 (3)** | **44,512** | **83.7** | 3.9 | 7.9 | 89 / 8 / 3 / 0 | **21.1** | 10.2–25.3 |
| 1915–1939 (5) | 7,887 | 54.1 | 21.9 | 15.5 | 63 / 16 / 20 / 1 | 21.2 | 9.1–27.4 |
| 1940–1967 (6) | 4,236 | 26.3 | 68.8 | 3.3 | 48 / 4 / 47 / 1 | 23.3 | 11.3–31.4 |
| 1968–1975 (7) | 2,935 | 13.0 | 85.6 | 0.8 | 26 / 1 / 70 / 2 | 23.4 | 14.1–36.9 |
| 1976–1981 (8) | 1,570 | 14.4 | 83.9 | 0.9 | 26 / 1 / 70 / 4 | 20.8 | 11.9–31.3 |
| 1982–1989 (9) | 1,651 | 24.2 | 73.0 | 1.7 | 36 / 2 / 57 / 5 | 17.4 | 9.7–25.0 |
| 1990–1999 (10) | 3,315 | 31.9 | 66.0 | 1.3 | 51 / 2 / 45 / 3 | 17.9 | 9.5–25.1 |
| 2000–2007 (11) | 1,478 | 39.0 | 56.8 | 2.0 | 65 / 2 / 30 / 3 | 16.5 | 8.8–23.8 |
| 2008– (12) | 1,711 | 21.8 | 69.8 | 1.2 | 59 / 2 / 22 / 12 | 17.6 | 8.8–29.7 |
| undated (99) | 2,826 | 67.7 | 17.0 | 11.7 | 72 / 12 / 14 / 3 | 11.6 | 6.9–21.6 |
(APUR heights are the surface model minus the terrain model per part: the median lies between the eaves and
the ridge of a mansard.)

Also: `b_terrasse` (terrace present) on 18 % of all parts, 22 % of 1915–39 parts and 86 % of 1968–75; green
terraces > 100 m² on 2.7 % of parts (3,466).

### 4.2 Mansard geometry, dormers, chimneys
- **Profile:** the Mansart roof has two pitches: the **brisis** (steep lower slope, typically **70–80°**, clad
  in zinc or slate, holds the dormers) and the **terrasson** (gentle upper slope, **10–20°**, in zinc, barely
  visible from the street) (src: guide-toiture.com, dsdrenov.com, greder.fr). The regulations (src: Wikipedia FR
  "Règlements d'urbanisme de Paris"): 1783–84 rule: mansard inside a 45° line from the eaves; **1859**: facades
  up to 20 m in streets ≥ 20 m wide (17.55 m before), attic still inside the 45° line; **1884**: heights 12 / 15 /
  18 / 20 m by street width (< 7.8 m, 7.8–9.74 m, 9.75–20 m, > 20 m), attic within a circular arc,
  ceiling **28.5 m** (20 m facade + 8.5 m attic); **1902**: attic may rise above the cornice line, oriels
  allowed, "eighth-circle arc continuing as a 45° line"; **1967 plan**: caps of 31 m (centre) and 37 m
  (periphery). "45°" in casual sources is the 1859 diagonal, not the brisis pitch: for rendering use brisis
  70–75° and terrasson 15°.
- **Proportions for an extruded profile** (vertical rise / horizontal run): brisis rises 3.0–4.0 m over a 0.9–1.4 m
  set-back; terrasson rises 1.0–1.8 m over 4–7 m to a flat ridge; the whole attic is 4.5–6 m high [believed,
  derived from the 1884/1902 rules and photos].
- **Dormers (lucarnes):** on the brisis, one per 1–2 window bays (every ~3–6 m along a facade), 1.0–1.2 m wide,
  with a zinc pediment or round-head; the top floor is the "chambres de bonne" floor; round "œil-de-bœuf"
  windows on some (src: Wikipedia FR "Toits de Paris"; spacing from photos, [believed]).
- **Chimney stacks ("souches de cheminée"):** in rows along the **party walls (murs mitoyens)**, brick or
  rendered, 0.6–1.2 m wide, rising 1–2.5 m above the ridge with terracotta or zinc pots ("mitrons"): roughly
  **2–5 stacks per Haussmann roof** each carrying 4–12 flues (the count of flues follows the number of
  apartments, one hearth per room) [believed]. Chimney pots are decorative clay or metal caps, 0.3–0.5 m.
- **Skylights:** Velux/châssis de toit on many renovated mansards and terrasson slopes; ~1 per 6–10 m of
  frontage [believed].
- **Roof access:** zinc-clad "abergement" (flashing) and a **guard rail/"crosse" line along the ridge** [believed].
- **Rooftop terraces and greenery:** Paris's "végétalisation des toits" plan; green terraces on 2.7 % of parts (3,466).
- **Heat:** zinc roofs exceed 70 °C in heatwaves (src: Wikipedia FR "Toits de Paris").
- **Cultural status:** the Paris roofs have been proposed for UNESCO listing since 2014 (src: same).

### 4.3 Roof colours sampled from the IGN orthophoto
Method: IGN Géoplateforme WMS `https://data.geopf.fr/wms-r/wms`, layer `ORTHOIMAGERY.ORTHOPHOTOS`, 512 × 512 px
GetMap, CRS EPSG:2154 (BBOX in **x,y order = easting, northing** for EPSG:2154: with y,x the server returns an
empty white tile), 0.2 m/px (102.4 m tiles), PNG. 15 tiles fetched (Haussmann blocks in the 11e, Marais,
Canal Saint-Martin, Montmartre, Étoile, Champs-Élysées, Tuileries, Luxembourg, Champ de Mars, Buttes-Chaumont,
Olympiades, HBM at Porte de Clignancourt, La Défense, Pont-Neuf); each was viewed as a 4 × 4 contact sheet
before boxes were chosen, and every box was checked on a crop sheet (`crops.png`, `crops2.png`, in
`paris_region/`). The imagery is late-summer 2024 (Olympic-arena at the Champ de Mars, scaffolding on the Arc)
[believed from content]. Values are photo tones in sRGB; the aerial photographs are rendered with a slight blue
haze and contrast typical of orthophotos, so I expect albedo ≈ photo tone within ±10 % for light surfaces
[believed].

| Surface | Where (tile, box) | Mean | Median | Dominant cluster |
|---|---|---|---|---|
| **Zinc roofs (aggregate)**: pixels with blue-grey tint (b−r 4–30, sat < 0.16, L 85–215) over 4 tiles (11e, Marais, Montmartre, canal) | 2 M pixels | **#909699** | #959c9f | shaded slope (bottom quartile) **#676c70**, mid **#959b9e**, sunlit (top quartile) **#b1b6b8** |
| Zinc roof, sunlit slope | Marais (135,270,175,300) | #798188 | #80898f | #818990 |
| Zinc roof, sunlit | 11e (300,300,350,330) | #8c8e8e | #a3a4a2 | #b6b8b7 |
| Zinc roof, large, sunlit | 11e (410,300,470,345) | #989c9d | #adb0b0 | #b1b4b4 |
| Zinc roof, shaded slope | 11e (415,370,470,405) | #767a80 | #818891 | #81878e |
| Zinc roof | Montmartre (20,290,90,320) / (130,380,190,410) | #989993 / #757879 | #9e9d95 / #797a7a | #bfbfbc / #a4a8a9 |
| Terracotta tile roof | Canal (200,395,260,440) | #816c68 | #987a69 | **#ab897c** |
| Slate/zinc dark (street photo, Opéra, shaded) | Commons photo | #505863 | #424c5b | #444e5d |
| Flat gravel/terrace roof | Olympiades (120,150,200,190) | #8f8d84 | #98958b | #97958b |
| Grande Arche marble roof | La Défense (120,110,240,180) | **#dbdbd7** | #dfdeda | #e4e3df |
| La Défense dalle paving | (20,400,120,460) | #a7a9aa | #bfbfbb | #c4c4c0 |

So the brief's "#8a9296-ish" zinc is right for the average, with a spread from **#676c70 (shaded slope) to
#b1b6b8 (sunlit)**: give each roof slope a ± 8 % lightness variation by facing, and dormers/chimneys darker
(#5a5f64) with zinc pot caps. Slate roofs (older buildings, some churches, Marais hôtels) read **#4f5966–#5d6c84**
(street photo, shaded) and **#444e5d** dominant; terracotta on faubourg and Belle Époque pavilions
**#a86f5a–#ab897c** (aerial).

### 4.4 Flat roofs, plant rooms and towers
- **1915–39 and later blocks** carry roof terraces (22–86 % of parts by period): gravel/bitumen (#8f8d84 /
  #3a3a3a), pavers, planters; stair/lift bulkheads brick or rendered; 1–2 chimney stacks (boiler flues).
- **HBM blocks (1919–39)**: brick facades with a stepped skyline; flat or low-pitch roofs with parapet (38 % flat,
  54 % brisis-type).
- **1960s–70s towers/slabs (13e, Front de Seine, Maine-Montparnasse)**: flat roof, plant enclosure (2 storeys),
  cooling units, window-cleaning gondola rails; the Tour Montparnasse's roof has a terrace ring with glass
  screen. Cooling towers on offices: **100 %** at La Défense towers [believed].
- **La Défense**: flat roofs with plant rooms, crowned tops (Tour First, Tour Total/Coupole, CMA CGM
  tower), Grande Arche marble/glass top, the dalle (podium) with hard paving.
- **Solar panels:** APUR flags 675 parts (0.5 %); Paris has a "solar roofs" plan [believed]; PV on ~1 % of roofs.
- **Green roofs**: 3.6 % of roof area is "végétal" (1.17 km², APUR), mostly terraces on 1980s+ buildings and
  Bercy/Batignolles.
- **Satellite dishes/antennas** on many roofs [believed]; **water tanks**: none of NYC's wooden tanks (Paris
  has water pressure supply, small tanks hidden) [believed]; **fire ladders**: none on street facades.

### 4.5 Rooftop programme by building kind (share of roofs; [believed] unless noted)
| Kind | Dormers | Chimney stacks | Skylights | Plant/bulkhead | Terrace |
|---|---|---|---|---|---|
| Haussmann (brisis) | **95 %** | **95 %**, 2–5 stacks | 40 % | stair lantern 30 % (2–3 m glass hip) | 5 % (top terrace) |
| Faubourg low (h < 15 m) | 40 % | 80 %, 1–3 | 30 % | — | 4 % |
| Small house/villa | 30 % | 80 %, 1–2 | 30 % | — | 8 % |
| HBM / interwar | 20 % | 60 % | 20 % | stair box 60 % | 22–38 % |
| Post-war block (1940–81) | 5 % | 30 % (boiler stack) | 10 % | lift machine room 100 % | 78 % flat |
| Modern (1982+) | 5 % | — | 20 % | plant 100 %, PV 5 % | 70 % flat, green 10 % |
| Tower (IGH ≥ 37 m) | — | — | — | plant enclosure 100 %, cooling 90 %, antennas 50 % | 89 % flat |
| Civic/monument | landmark-specific | 30 % | — | — | domes, lanterns, statues and spires per landmark; churches: slate/lead roofs, tall zinc/lead spires |

### 4.6 Preset: NYC now → Paris needs
| Table | NYC now | Paris |
|---|---|---|
| `europe_west/rooftops.py PROGRAMME` | wooden tanks, bulkheads, HVAC, rowhouse/prewar/`nyc_office` programmes | new programmes: `haussmann` (mansard profile with brisis/terrasson, dormers along the eaves, chimney stacks in party-wall rows with terracotta pots, ridge crest, occasional Velux), `faubourg`, `hbm`, `postwar`, `tower` (plant room + cooling), `civic` (spires/domes as landmarks) |
| `[rooftops.named]` | cedar water-tank browns (`cedar` etc.) | **`zinc` #909699, `zinc_sun` #b1b6b8, `zinc_shade` #676c70, `slate` #4f5966, `tile_red` #a86f5a (already `tile_red` #8c4c3a: lighten), `chimney_brick` #8b5a45 (already `brick`), `pot` #a5563a, `lead` #7b7f83**; drop cedar |
| `[rooftops.parapet_t]` | village 0.2, glass 0.3 | pitched roofs get no parapet; flat post-war roofs 0.2–0.3 |
| Roof shapes | flat with parapets | `c_forme_toit`: 4 → mansard profile, 1 → flat, 2/3 → gabled (tile); from APUR (kind fields carry it, §5.3) |
| `city.json facade.roofs` (tones for flat roofs) | NYC greys/blacks | zinc-only dominates; flat roof tones sunlit gravel #8f8d84, bitumen #3a3a3a, green #6b7f4a [believed] |
| Solar | NYC | PV 1 % of flat roofs |

---

## 5. Facades by building type

### 5.1 The types (with a share of buildings and the fields that tell them apart)
Shares are **counts of "main" APUR parts** (94,875 of 128,175: the rest are slabs/courtyard roofs `b_dalle = O`
and parts under 6 m) and their footprint area, using the proposed rules of §5.3 (measured). A "part" is a building
or a piece of one, so building-level shares are close but not identical; the intra-muros Paris footprint is
~27.6 km² of main parts.

| Style (proposed engine name) | Parts | Footprint | Median height (p10–p90) | Floors | Ground + upper floor-to-floor | Roof | Windows |
|---|---|---|---|---|---|---|---|
| **Haussmann / pre-1914 perimeter block** `haussmann` | **47.5 %** (45,049) | **36.6 %** (10.1 km²) | **21.4 m** (16.7–25.2) | 6–8 levels (5–6 storeys + entresol + 1–2 mansard) | 4.0–5.0 (ground + entresol), 3.3–3.6 (2nd), 3.0–3.2 (3rd–4th), 2.9–3.0 (5th), 2.5–3.0 (mansard) | Mansard, zinc | Tall 1.0–1.3 × 2.2–2.5 m French windows, bay 2.6–3.2 m, balconies |
| **Faubourg / pre-Haussmann low** `faubourg` | 10.2 % (9,659) | 6.2 % | 12.6 m (10.1–14.5) | 3–5 | 3.0–3.3; shop 3.5–4 | Steep zinc/slate/tile, 80 % mansard-type | Casements, shutters, 1.0 × 1.8–2.1 m, bay 2.0–2.6 m |
| **Small house / villa / Montmartre lower houses** `house` | 12.1 % (11,459) | 3.7 % | 9.0 m (6.6–14.0) | 2–3 | 2.8–3.0 | 41 % pitched-mansard type, 9 % flat | Casements, plaster/stone, timber or iron balconies |
| Pre-1914 other (flat or irregular roofs, taller) | 3.5 % | 3.1 % | 19.4 m | 6 | 3.2 | flat/terrace 39 % | as Haussmann |
| **HBM (1919–39 social housing)** `hbm` | 1.1 % (1,091) as `c_tissu = HBM`; more in "interwar" | 2.6 % | **23.0 m** (18.6–27.2) | 6–8 (up to 9–10 on the Maréchaux ring) | 3.0–3.1 | 54 % mansard-like, 38 % flat | Brick with stone/concrete bands, window 1.1 × 1.6–1.9, bay 2.4–3.2 |
| **Interwar blocks (1915–39)** `interwar` | 5.3 % (5,068) | 6.7 % | 22.9 m (12.8–27.9) | 7–9 | 3.0–3.2 | 68 % brisis, 22 % flat | Art Déco brick and stone, bow windows, rounded corners |
| **Post-war blocks/slabs (1940–81)** `slab` | 8.1 % (7,699) | 14.4 % | 22.7 m (14.1–30.8) | 7–12 (up to 13–20 for the 1960s towers) | 2.8–3.0 | flat 78 % | Concrete panel or brick, window bands, 1.2–1.5 m modules |
| **Modern (1982–today)** `modern` | 7.5 % (7,091) | 14.6 % | 18.1 m (11.3–25.5) | 5–9 | 3.0–3.3 | flat 70 %, mansard-like 28 % | Curtain wall, zinc cladding, large loggias |
| **Towers (`c_tissu = IGH` or h ≥ 37 m)** `tower` | 0.7 % (669) | 2.3 % | 42.8 m (36.3–74.7) | 12–60+ | 3.0–4.2 | flat 89 % | Concrete grid/curtain wall |
| **Civic/monument (`c_tissu = ER`)** `civic` | 2.1 % (1,968) | 8.2 % | 15.4 m (7.5–23.3) | | 4–6 (large storeys) | 68 % mansard/steep, 18 % flat | Stone, tall arched windows |
| Undated | 1.9 % | 1.5 % | 15.0 m | | | | |
| (Not in APUR:) La Défense towers (BD TOPO) | | | 90–230 m | 25–60 | 3.9–4.2 | flat/crowned | Glass curtain wall |

**Calibration of floor heights (measured).** I joined the OSM `building:levels` (60,756 buildings with a level tag)
to APUR's surface-model height per part. Median APUR height / OSM levels: **1851–1914 3.28 m** (p25–p75
3.11–3.62), 1801–1850 3.25, before 1800 3.46, 1915–39 3.23, **1940–67 3.01**, **1968–75 2.89**. Height by
levels for 1851–1914 (n): 5 → 16.8 m (2,876), **6 → 20.8 m (6,196), 7 → 22.2 m (12,166)**, 8 → 25.7 m (2,624);
40 % of tagged 1851–1914 buildings have 7 levels. `city.toml level_h = 3.3` is right for pre-1940; use **3.0**
for 1940–67 and **2.9** for 1968 and later.

**Haussmann anatomy** (facade heights from the regulations; details are common architectural knowledge unless
sourced): ground floor with shopfronts and an **entresol** (4–5 m together) → the **étage noble** (2nd floor,
ceilings up to 3.2 m, continuous stone balcony) → 3rd and 4th floors (individual balconies or guard rails,
3.0–3.2 m) → 5th floor (second continuous balcony) → cornice (18–20 m above the pavement) → the mansard
(two levels, 4.5–6 m) (src: several French real-estate/architecture pages: "balcons filants aux 2e et 5e étages",
"ceiling height 3.20 m on the second floor, decreasing upward", "1852–1870 core era"; Haussmannian buildings are
said to make ~60 % of Paris's stock, though APUR's own 1801–1914 mansard class is 47.5 % of parts).
The Haussmann-era street rule ties height to street width (1859: 20 m facade on streets ≥ 20 m; 1884: 18 m
on 9.75–20 m, 12–15 m on narrow streets), so streets of 30 m (Haussmann boulevards) have the tallest walls
and side streets of 10–12 m carry 15–18 m walls.

### 5.2 Palettes (hex)
Colour sources: **(sampled)** = PIL sampling on Commons photos, method in §5.4; palettes are my albedo
adjustments of those photo tones, marked [believed] where an adjustment is a guess.

| Style | Wall colours (albedo hints) | Photo samples |
|---|---|---|
| Haussmann | **Lutetian limestone, cream–honey:** base `#d6ccb6`, `#cfc4ab`, `#c8bca2`, `#d9d0bc`, `#c2b697`, `#cbc2b0`; soot-grey `#b8ad94`, `#a9a397`; honey/golden (old, unwashed) `#c8b48a`, `#c2aa7c` [believed]; ravalement-fresh pale `#e0d8c6` | Rue Étienne-Marcel overcast: mid **#b0aba3**, p90 **#d2cec8**, largest cluster #ccc9c1 (sampled); Bd Voltaire sunlit: mid #aca59b, p90 **#dfdacf**, cluster #d7d1c6; Place Saint-Michel golden sun: mid #9a8056 / dominant **#a58d63** (warm cast); Av. de l'Opéra shade: mid #80766f / p90 #a09791; Clignancourt: #7b726e mid / p90 #b1adad |
| Ironwork/balconies/shutters | balcony rails black `#1c1c1e` (over 90 %), some dark green `#2c3d33`; shutters/persiennes (faubourg): white `#e8e6de`, pale grey-green `#9aa79a`, blue-grey `#7a8fa0`, brown `#5a4634`, olive `#68705a` | |
| Ground floor | shopfront frames black `#1c1c1e`, deep green `#2f4a3a`, navy `#26364d`, burgundy `#5a1f2b`; brasserie red awnings `#a01f28` (seen at Bd Voltaire); wooden carriage doors (porte cochère) 3.0–3.5 m tall, dark green/brown `#3a4a3e` | |
| Faubourg / plaster | cream `#d9d3c3`, `#cfc8b4`, white `#e0dccf`, pale ochre `#d6b98a`, pale yellow `#dcc998`, pale pink `#d2b0b4`; plinth grey stone | Rue Crémieux cream plaster (shade): #a8a5a0 (sampled); Montmartre pink plaster #a09099 mid / #d9c3d2 p90 |
| Montmartre rubble stone (lower houses) | `#8f8980` stone, `#6b655c` shade; half-timber dark green `#2c4a3a`, plaster white | Rue de l'Abreuvoir stone #8f8980 mid / #b8b4ad p90 (sampled) |
| HBM / brick | brick `#9a5f4a`, `#8b5140`, `#a4694f`, `#7c4a3c`; stone/concrete bands `#cfc6b4`; sometimes yellow-orange brick `#b57a4e` | Av. Bizot brick-stone: mid **#917468**, dominant **#785446**, p90 #b8a8a0; polychrome brick Rue Boissonade mid **#9b787e**; Rue de Vouillé mid #8c7168; Place des Vosges upper storeys brick/stone mix mid **#c6baac**, brick cluster **#9c7a64** |
| Marais hôtel particulier / Place des Vosges | pale stone `#cfc6b0`, `#d8cfba`; red brick `#a5674e` with stone quoins `#d9cfba`; steep slate roofs `#4f5966` | Place des Vosges arcades stone mid #918573 / p90 #daccb3 |
| Post-war slab / 1960s–70s tower (Olympiades, Front de Seine) | concrete panel `#b9b6ae`, `#a8a49c`; window bands dark `#2b3038`; white/grey `#c8c9c8`; brown-red panel tower `#8a4a44` | 13e slab tower mid #8c8b8f, p90 #d0d0d1; Front de Seine blue glass tower mid **#49576a**, dark #1a2434; brown-red tower (Novotel) mid #635c65 dark; pale tower #e0e7ee (sky glare) |
| Modern glass (La Défense, Batignolles) | teal-blue `#4b6f80`, `#5d7d8c`; silver `#a9b3b5`; dark `#2d4756`; grey-green `#6c7f86` | La Défense curtain wall mid **#597f8e**, cluster #376476 / #0c374b (sampled) |
| Civic stone (churches, ministries, museums) | `#c9bfae`, `#b8a88f`, `#d4ccbd` (existing preset `civic` is fine) | |
| Grande Arche | white Carrara marble `#e6e4dc`, glass grey-blue; roof `#dbdbd7` (aerial) | |
| Roofs | zinc `#909699` (shaded #676c70, sunlit #b1b6b8), slate `#4f5966`, tile `#a86f5a` | §4.3 |

### 5.3 Classification rules from the data (proposal for M2 `building_kind()` / M4 `facade_styles()`)
Fields available (verified in `demos/data/paris/*.gpkg` / raw files):

| Source | Fields | Notes |
|---|---|---|
| APUR `emprise_batie_paris` (Paris only) | `c_perconst` (1 < 1800, 2 1801–50, 3 1851–1914, 5 1915–39, 6 1940–67, 7 1968–75, 8 1976–81, 9 1982–89, 10 1990–99, 11 2000–07, 12 2008+, 99 undated), `an_const` (63 % filled), `an_rehab`, `an_surelevation`, `c_forme_toit` (1 flat, 2 gabled tile, 3 gabled small-scale, 4 brisis-terrasson), `c_toiture_mat` (T/M/V/A), `b_terrasse`, `b_dalle`, `b_igh`, `b_horspu`, `c_morpho` (1 individual house < 10 m and 3–190 m², 2 / 3 low collective, 4 collective > 3 storeys 10–37 m < 1000 m², 5 large 20–37 m > 1000 m², 6 large < 20 m, 7 tower ≥ 37 m), `c_tissu` (ER remarkable, TR regular, TC composite, TPE small scale, TD discontinuous, TI industrial, HBM, IGH), `h_med/h_max/h_min`, `Shape_Area`, `m2_tuile/mineral/vegetal/penteinf10` | present in `apur_buildings.gpkg` (`an_const`, `c_forme_toit`, `c_toiture_mat`, `b_terrasse`, `b_igh`, `c_morpho`, `h_med`, `h_max`); `c_perconst` and `c_tissu` are only in the raw GeoJSON: **add them to the gpkg** |
| IGN BD TOPO (La Défense, Neuilly; cross-check in Paris) | `usage_1` (Résidentiel 79,697; Indifférencié 22,845; Commercial et services 15,961; Annexe 2,296; Religieux 422; Sportif 416; Industriel 335; Agricole 49), `nature` (Indifférenciée 119,229; Industriel, agricole ou commercial 2,110; Église 251; Monument 204; Chapelle 71; Tribune 68; Serre 46; Tour, donjon 13; Silo 10; Arc de triomphe 9), `date_d_apparition` (60 % filled), `nombre_d_etages` (69 %), `hauteur` (92 %), `construction_legere` (2,432 yes) | 121,879 rows in `bdtopo_buildings.gpkg` |
| OSM | `building`, `building:levels` (~60 %), `height` (0–2 %), `name`, roof tags rare | `osm_buildings.gpkg` |

**Decision order (first match wins):**
1. **Landmark/named building** → its own style (`landmarks_paris.csv`).
2. **Tower** `c_tissu = IGH` or `b_igh = O` or `h ≥ 37 m` (APUR), or `h ≥ 50 m` (BD TOPO in La Défense) →
   `tower` (glass in La Défense/Front de Seine/Batignolles/Bercy: use `c_perconst ≥ 8` or BD TOPO; concrete
   panel for `c_perconst` 6–7). (669 parts)
3. **Civic/monument** `c_tissu = ER` or BD TOPO `nature` in (Église, Chapelle, Monument, Arc de triomphe, Tour,
   château) or `usage_1 = Religieux` or OSM church/civic tags → `civic`/stone.
4. **HBM** `c_tissu = HBM` (1,091 parts) → `hbm` (brick).
5. **Small house** `c_tissu = TPE` or (`c_morpho = 1`, or `h < 10 m` and footprint < 190 m²) → `house`
   (plaster/stone, small windows) (11,459 parts).
6. **Haussmann** `c_perconst ∈ {1, 2, 3}` and `c_forme_toit = 4` and `h ≥ 15 m` and `c_tissu ∈ {TR, TC}` (or
   `an_const` 1853–1914) → `haussmann` (45,049 parts; 2/3 of them TR and TC; ~1,600 of `c_perconst = 1`
   in the Marais/Île Saint-Louis can be `hotel`).
7. **Faubourg low** `c_perconst ∈ {1, 2, 3}` and `h < 15 m` → `faubourg` (9,659).
8. **Interwar** `c_perconst = 5` → `interwar` (brick/stone bands, 5,068).
9. **Post-war** `c_perconst ∈ {6, 7, 8}` → `slab` (concrete/brick panel, 7,699).
10. **Modern** `c_perconst ≥ 9` → `modern` (glass/zinc, 7,091).
11. Otherwise by `usage_1`: Commercial → `commercial`; Industriel → `factory`; Annexe/`construction_legere` → `plain`.
12. Undated parts (`c_perconst = 99`, 1.9 %) inherit the neighbour's kind by nearest dated building on the block.
   Shed/low glass: `b_dalle = O` are slabs/courtyard covers (25,701): treat as ground-floor annexes (no windows).

**Extra rules:** `an_surelevation` (raised storeys) or `an_rehab` marks a rehabilitated facade: brighten the stone
(post-"ravalement" #e0d8c6) [believed]. `b_terrasse = O` → flat roof terrace; `c_forme_toit` decides the roof
profile (§4). Use `h_med` as the ridge-ish height minus 2 m for the cornice line of mansard roofs (§4.2).
Storeys for windows = round((cornice − ground floor) / 3.1) for Haussmann, `h_med / 3.3`, or `nombre_d_etages` where
present. Paris's OSM `building:levels` counts the mansard and (often) the ground floor.

### 5.4 Colour sampling method
- **Photos:** Wikimedia Commons 960 px thumbnails through the Commons API with a polite User-Agent and a 2 s pause:
  Haussmann: "16 rue Etienne-Marcel.jpg", "2 boulevard Voltaire à Paris le 7 août 2016.jpg", "Avenue de l'Opéra,
  Paris, France 2009.jpg", "2018 1-3 Place Saint-Michel.jpg", "Angle rue Christiani, rue de Clignancourt, Paris
  2015.jpg"; brick: "Avenue du Général Michel Bizot, 117.jpg", "39 rue Boissonade, Paris 14e 2.jpg", "Paris 15 - Rue
  de Vouillé - Rue Brancion (31473513610).jpg"; Marais "Paris 3e Place des Vosges Pavillon de la Reine 583.jpg";
  Montmartre "Rue de l'Abreuvoir Montmartre Paris France.JPG"; faubourg "Rue Crémieux in July 2022.jpg"; towers
  "Beaugrenelle @ Paris (25530225466).jpg", "Vue tours du 13e.JPG", "Buildings on south of Place des Pyramides, La
  Défense, Paris.jpg". I viewed each with a grid, chose fractional boxes over plain wall, discarded sky pixels
  (b > r + 25) and white/black clipping, and report the **mean**, the **mid 40–90 % lightness median** (walls without
  window shadows), the **90th percentile** (the sunlit wall) and the largest k-means cluster ("dominant").
- Sampling script: `paris_region/fsample2.py`; crops `paris_region/fcrops2.png`.
- **Trust:** photographed tones depend on exposure and light; sunlit values read brighter than albedo and shaded
  ones darker. The Haussmann cream #d2c8b0 base I recommend is the p90 sunlit stone pulled slightly warm, in
  line with the brief's #d9cbb0 guess; the brick values come from two photographs only.

### 5.5 Preset: NYC now → Paris needs
| Table | NYC now | Paris |
|---|---|---|
| `[buildings]` `cantilever_code`, `split`, `reconcile` (MapPLUTO/NYC ids) | NYC's | drop `cantilever_code`; `split` for APUR parts joined to towers; `reconcile` sources = APUR `h_med` (already in `city.toml heights`) |
| `[buildings.osm_kind]` | house → rowhouse, church → civic | house → `house`, terrace/townhouse → `faubourg`, keep civic list; add `apartments` → by period |
| `building_kind()` / KIND_FIELDS | shape rules + MapPLUTO class | §5.3 decision order from `c_perconst`, `c_tissu`, `c_forme_toit`, `h_med`; the code already lists the fields (`an_const c_morpho c_forme_toit c_toiture_mat b_terrasse usage_1`): add **`c_perconst` and `c_tissu`** |
| `[facade.styles.*]` | glass, residential, brownstone, brick, stone, castiron, commercial, civic, factory, plain, signs, spire | glass (keep, palette §5.2), **`haussmann` (floor 3.3, palette limestone)**, `faubourg` (3.1), `house` (2.9), `hbm` (3.1), `interwar` (3.1), `slab` (2.9), `modern` (3.2), `tower` (3.2–4.0), civic (keep), commercial (keep), factory (keep), plain (keep), spire (keep); **remove** brownstone, castiron, signs; landmark styles as needed; `facade.js` must know each style |
| `[facade.osm_style]` | house → brownstone | house/detached → `house`; retail → commercial; keep the rest |
| `facade.acUnits` (city.json) | brick 0.22, residential 0.18, brownstone 0.05 | air conditioners are rare on Haussmann facades (`haussmann` ≈ 0.03, modern 0.15, glass 0.1) [believed]: Paris homes seldom have AC |
| `facade.refugeShare` | 0.1 | 0 (French towers have no refuge floors) [believed] |
| Balconies | none | **wrought-iron balconies**: continuous on the 2nd and 5th floors of every Haussmann facade, guard rails on the others; modules 2.6–3.2 m |
| Ground-floor shops | | 4.0–4.8 m storey with dark shopfront frames and awnings, porte cochère at ~1 per 20–25 m of frontage; `plan-de-voirie-portes-cocheres` (33,914 points on opendata.paris.fr) gives real positions |
| `level_h` | 3.3 | 3.3 (pre-1940), 3.0 (1940–67), 2.9 (1968+) |

---

## 6. Night

### 6.1 Street lighting: the real inventory can be downloaded (measured)
The Ville de Paris publishes **every lamp** as open data: `eclairage-public` (165,581 records, updated
**2026-09-01**), https://opendata.paris.fr/explore/dataset/eclairage-public/ ; API
`https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/eclairage-public/records?limit=2`; CSV export with
`.../exports/csv?select=voie_categorie,lib_ouvrag,support_hauteur,lampe_famille,lampe_temperature_couleur,x_wgs84,y_wgs84,voie_libelle,lampe_puissance`
(14 MB for the open-air streets). Fields: fixture type `lib_ouvrag` (Candélabre, Console, Projecteur, Applique, ...),
`support_hauteur` (m), `support_famille`, `lampe_famille`, `lampe_temperature_couleur` (K), `lampe_puissance` (W),
`voie_categorie`, WGS84 position. It can place real lamps with real colours instead of the procedural posts.

Records by `voie_categorie`: **VOIES PUBLIQUES 110,788**, SOUTERRAINS (tunnels) 35,454, BOULEVARD PÉRIPHÉRIQUE 6,216,
squares and gardens 7,382, private roads 1,535, Bois de Boulogne 1,494, Bois de Vincennes 1,123, **VOIES SUR BERGES
983**, RATP 485, junctions 121.

**Open-air public streets (110,788 lamps):**

| Lamp family | Count | Share | Colour |
|---|---|---|---|
| **LED** | 83,413 | **75.3 %** | 3000 K 67 %, 2700 K 16 %, 2200 K 15 % |
| Metal halide ("iodures métalliques") | 8,339 | 7.5 % | ~3000–4200 K, white |
| High-pressure sodium (substituted 7,128, existing 1,412, very high 80) | 8,620 | **7.8 %** | 2000 K, orange |
| Cosmopolis (ceramic metal halide) | 4,275 | 3.9 % | ~2800–3000 K [believed] |
| Fluorescent tubes / balloons / compact | 4,280 | 3.9 % | 4000–4200 K, cool white |
| Induction | 871 | 0.8 % | |
| Path markers ("plots de jalonnement") | 780 | 0.7 % | |

Colour temperatures on these streets: **3000 K 56.9 %, 2700 K 12.1 %, 2200 K 11.5 %, 2000 K 7.7 %, 2800 K 6.5 %**;
4000–4500 K only 2.2 %. So 95 % of the lamps are warm (≤ 3000 K), matching the national 3000 K cap of Dec 2018 (src:
paris.fr "pollution lumineuse") and Paris's "warm light" policy (roads 3000 K since 1 Jan 2020, parks, Seine banks
and canals 2200 K).
Fixtures: **candélabre 73,072 (66 %)**, **wall/facade console 29,921 (27 %)**, projectors 2,379 (2.1 %),
appliqués 1,867, ground lights 1,234, ceiling lights 1,159. Of 52,700 candélabres with a support family, "de style"
(historic/ornamental) are 7,589 (14 %), functional 45,129.
Support heights where known (55,000 candélabres): **7 m 25 %**, 6 m 15 %, 4 m 14 % (pedestrian/ornamental), 5 m 5 %,
3.75 m 4 %, 7.83 m 3 %, 6.5 m and 6.3 m 3 % each, 9 m 3 %, 3 m 2 %, 10 m 0.5 %; the big 10–13 m columns are on the
Périphérique and interchanges. Spacing along one side of a street: nearest same-type neighbour median **20–21 m**
for 6–10 m columns and 13 m for 4 m posts (many are doubled on boulevards, hence NN 0).
Wall consoles (facade brackets) are 4–6 m up and carry the light in narrow old streets [believed]; suspended
lanterns exist too (the inventory has "Lanterne" 142 and "Suspension" is not a category).

By axis (Sept 2026): Rue de Rivoli **LED 581 of 587, 2700 K**; Bd de Sébastopol 159/159 LED 3000 K; Bd Saint-Germain
386/390 LED 3000 K; Av. de la Grande-Armée 136/147 LED 3000 K; **Champs-Élysées** 373 LED (2700 K), 245 sodium
2000 K (4 m posts); **Bd Haussmann** 160 LED, 118+ sodium; **Av. Foch** mostly fluorescent-balloon and Cosmopolis
lamps, 4200 K and 2800 K.
**Périphérique (6,216 lamps):** low-pressure sodium **2,483 (40 %, 1800 K, monochrome yellow-orange)**, LED 2,385
(38 %, mostly 2700 K), fluorescent tubes 510 (tunnel tubes), HPS 456; 10–12 m columns [believed].
**Seine banks and berges (983):** LED 860 (87 %), **2200 K on 66 %**, 3000 K on 23 %.
Other numbers (src): ~122,000 lighting points in 2025 incl. ~13,000 on the Périphérique (Wikipedia FR "Éclairage
des rues à Paris"); the "~200,000" of the Cielis contract counts every lighting point; Cielis (Citelum +
Eiffage, 2021–31, 704 M€) replaces 70,000 lamps with LED and renews 12,000 supports, −30 % energy.

**Emissive colours (blackbody approximations, sRGB; use as the lamp tint):**

| Lamp | CCT | Blackbody sRGB (Helland) | Suggested emissive |
|---|---|---|---|
| LED street (roads) | 3000 K | #ffb16e | **#ffc48a** (slightly whitened) |
| LED 2700 K (Rivoli, Champs) | 2700 K | #ffa757 | **#ffb872** |
| LED 2200 K (quays, canal, parks, Bois) | 2200 K | #ff9227 | **#ffa653** |
| High-pressure sodium | 2000 K | #ff890e | **#ffa040** |
| Low-pressure sodium (Périphérique) | 1800 K, 589 nm | — | **#ffb400** (monochrome yellow-orange) [believed] |
| Metal halide, Cosmopolis | 3000–4200 K | #ffb16e–#ffcea6 | #ffd6a8 |
| Fluorescent tubes/balloons | 4000–4200 K | #ffcea6 | #ffe2c4 |

Share for `ground.sodium` (city.json, fraction of cells with sodium lamps): `arterial` **0.10** (Champs-Élysées,
Haussmann, Maréchaux, Périphérique 40 %), `street` **0.06** (measured 7.8 % citywide HPS). `ground.streetLight`
1.2 (now) stays.

### 6.2 Extinction and curfews (src)
- Monuments: the municipal ornamental lighting (Hôtel de Ville, Tour Saint-Jacques, mairies) has been **off at
  22:00** since 23 Sept 2022; the Eiffel Tower goes off at **23:45** (the last visitors); digital ad panels and
  city screens off **23:45–06:00** since 1 Nov 2023; shop windows and facade lighting **off by 01:00** (national
  arrêté 2013, replaced 29 Dec 2018), offices' interior lighting off 1 h after the end of occupation.
  10 October: sunset 19:12, so the whole evening (19:12–22:00) is fully lit.
- **Night preset** (city.json `night.schedule`): the `feature` curve `[[0,0],[16.5,0],[17,0.3],[23,0.3],[23.5,0],[24,0]]`
  (lit features) needs to reach ~1.0 by 19:45 CEST and fall at 22:00 (ornamental) and ~01:00 (shops).

### 6.3 Monuments (src unless marked)
- **Eiffel Tower:** golden light since 1985 from **336 sodium projectors** (Pierre Bideau design; inaugurated
  31 Dec 1985); four 200 W LED projectors light the antenna; **sparkle**: 20,000 × 6 W bulbs flash white for **5 minutes at the start of each hour after dusk until closing** (designer credit not verified); a rotating white
  beacon (two beams) at the top; since 7 June 2024 the **Olympic rings** (29 m × 13.5 m, 100,000 LED, white at
  night) hang between the first and second floors. Whether the sodium is now LED is **not verified**; colour ~2000–2200 K,
  suggested **#ffa93a** lit steel, cone #ffb347 (search snippets; toureiffel.paris returned 403).
- **Notre-Dame** (reopened Dec 2024): LED with 1,400 projectors, 2,175 luminous points, 2200–5000 K range,
  3000–3500 K at normal; suggested **#ffd9a8**.
- **Pont Alexandre III:** 32 bronze candelabras (warm incandescent look, #ffd08a), gilded Renommées on the
  pylons (floodlit gold #ffc94d).
- **Arc de Triomphe, Sacré-Cœur, Opéra Garnier, Pont Neuf, Grand Palais, Invalides dome (gold leaf), Louvre
  pyramid:** no technical source found: warm/golden 2200–3000 K floodlighting by tradition
  (**#ffd6a0–#ffc080**; Sacré-Cœur cooler #ffe2b8; Invalides #ffc24a; Louvre pyramid neutral #e6f0ff) [believed].
- **Windows:** Haussmann apartments warm 2700–3000 K (#ffb870–#ffd9a0), 5–10 % TV-blue #b8d0ff [believed];
  shop windows brighter and whiter (#ffe2b0–#fff1d8) [believed]; La Défense towers cool-neutral office LED
  3500–4500 K (#e9f1ff–#fff3dc), floors go dark progressively after 20:00 and mostly after 22:00 (a
  regulation turns interior lights off 1 h after occupation) [believed]; the Grande Arche's faces lit white/cool.
- **Boats:** tourist boats with white-blue searchlights sweeping the quays and green hull-line LEDs (photo:
  Commons "Île de la Cité - panoramio") [believed for the count]; Vedettes lit white.
- **Sky glow:** Paris is Bortle 8–9 (src: light pollution maps); horizon warm orange-grey `#5a4638` fading to
  `#1a1f33` overhead [believed]; city.json `night.skyGlow [0.043, 0.04, 0.046]` is neutral: warm it slightly to
  [0.06, 0.045, 0.04] linear [believed].

### 6.4 Preset: NYC now → Paris needs
| Table | NYC now | Paris |
|---|---|---|
| `ground.sodium` | (Shenzhen values) | arterial 0.10, street 0.06 |
| Lamp colour/warmth (viewer `ground.js` LED / WARM_LED / SODIUM) | NYC 4000 K neutral | **warm LED 3000 K (#ffc48a) dominant**, 2200 K on quays, sodium orange minority |
| Pole height, spacing | 9–10 m avenues / 7.5 m side; 25–35 m | **7 m** typical (6–10), 4 m ornamental; spacing 20–25 m staggered; consoles on facades in old streets (or real lamps from the dataset) |
| Times Square signs | yes | **none**; billboards.js off (Paris limits advertising; digital panels off 23:45–06:00) |
| Landmarks | ESB colours | Eiffel gold + hourly sparkle + beacon; monuments floodlit gold; `floodlit`/`crowned` styles for Notre-Dame, Arc, Sacré-Cœur, Invalides, Opéra |
| Office lights | Midtown schedule | Paris offices ~50 % at 20:00, 25 % at 23:00, La Défense 60 % at 20:00, 20 % at 23:00 [believed] |

---

## 7. Water

### 7.1 The Seine and its quays
- **Width** (src: Wikipedia FR "Seine à Paris", search summaries): 30 m (petit bras at Notre-Dame, Quai de Montebello)
  to **200 m** (Pont de Grenelle), mean ~100 m in the centre; depth 3.4–5.7 m; ~13 km in Paris. Pont Neuf
  spans 238 m (grand bras 154 m, petit bras 78 m), Pont de l'Alma bridge 153 m; from the 1 m LiDAR terrain model
  (measured) the Île Saint-Louis main arm is 90–100 m wide, and ~220 m north–south at the tip of the Cité
  downstream of the Pont Neuf.
- **Level:** normal about 0 on the Austerlitz gauge = **26.72 m NGF69** (gauge zero 25.90 m); the LiDAR shows water at
  26.8–27.0 m (measured). Flood thresholds (Austerlitz gauge, src: paris.fr): lower quays close at **3.0 m**, road
  closures from 3.2 m, navigation stops at 4.3 m, 1910 flood 8.62 m, 2016 peak 6.10 m.
- **Quays** (measured from the 1 m LiDAR bare-earth model at Pont Neuf, Pont de l'Alma and Île Saint-Louis):
  **lower quay deck (berges/ports) 2.6–2.9 m above normal water**; **upper quay (street level) 6–9 m above
  water** (Pont Neuf right bank 7.6–8.0 m, left 8–9 m; Alma right 7.3 m, left 5.7–6 m; Île Saint-Louis 7.7–8.6 m).
  For ~2 km on both sides the river has double-decker quays (src: paris.fr). Walls: limestone ashlar with stone coping,
  parapet ~1.1 m [believed], cast-iron bollards every 10–20 m [believed]; parapet colour weathered
  **#b5aa98** (from a Commons photo, [believed]); modern quay lamps dark green **#2e4a3c** [believed].
- **Berges de Seine:** Left bank 2.3–2.5 km pedestrianised (Orsay to Alma), right bank 3.3–4.5 km (Tuileries to the
  Henri IV tunnel, sources differ), ~10 ha of park (src: paris.fr, sortiraparis).
- **Bouquinistes:** ~900 green boxes on ~3 km of the upper-quay parapet (right bank Pont Marie to Quai du Louvre,
  left Quai de la Tournelle to Quai Voltaire); box 2.00 m long × 0.75 m deep × 0.60 m (river side) / 0.35 m
  (quay side) high, "vert wagon" (src: Wikipedia FR "Bouquinistes de Paris"); colour ~**#2f4f3a** [believed].
- **Bridges:** 37 over the Seine in Paris (src: Wikipedia FR "Liste des ponts de Paris"). Pont Alexandre III:
  160 × 45 m, single arch 107.5 m, 4 pylons with gilded Renommées; Pont des Arts 155 × 11 m (7 arches); Pont
  Neuf 20.5 m wide (11.5 m roadway + 2 × 4.5 m footways); the arch bridges are limestone, with iron arch bridges
  (Alexandre III, Arts).

### 7.2 Water colour
- **Sampled from Commons photos and the aerial:** sunny street level (Seine, Sept 2025) **#234c4a** (dark
  teal-green; p10 #194133, p90 #345e6b), reflecting-sky far reach #447792; aerial from the Eiffel Tower, Oct 2017
  **#3e4a45–#51605a**; **IGN orthophoto at the Pont Neuf (sampled): #353d3a (mean), #343d39 (dominant)**;
  overcast Pont de l'Alma **#7a7878** (sky reflection); the Front de Seine reach under overcast **#5e6163**
  (mid), #555758 (median) (sampled). Dusk reflections can be purple (#4d3769). Turbid green-brown, visibility
  ~0.5 m [believed].
- `city.json water.inland.river` is already `[0.03, 0.042, 0.034]` (linear) ≈ **#3b4a41 sRGB**: within the
  aerial samples (#3e4a45): keep. Fresnel/sky reflection controls the look (overcast grey to sunny teal).
  Night: near-black body #0b1418 with strong specular of lamps and the Eiffel gold.

### 7.3 Barges, boats, canals
- **Péniche (Freycinet gauge):** 38.5 × 5.05 m, draught ~1.8 m, steel hull; commercial barge photo: dark blue-black
  hull, grey/silver hold covers, white wheelhouse (my look at a Commons photo); > 200 house-boats/péniches
  moored in Paris (~1,200 in Île-de-France), Port de l'Arsenal ~177 berths (src: VNF via search).
- **Bateaux-mouches and vedettes:** ~60 × 10 m, white with glazed roofs; Batobus ~30 × 6 m; the Commons photo of the
  Front de Seine reach (Beaugrenelle) shows two moored white river-cruise ships of ~100 m [believed for the sizes].
- **Canal Saint-Martin:** 4.5–4.6 km, **9 locks**, 2 swing bridges (Rue Dieu, Grange-aux-Belles), ~2 km (2,069 m)
  covered in three tunnels (Temple, Richard-Lenoir, Bastille); boats to 40.7 × 7.7 m, air draught 4.27 m, water draught
  1.90 m; 25 m drop from the Villette basin to the Seine; ~9–10 iron footbridges in the open part; chestnut and plane
  trees along both quays; width ~27 m [believed 25–28 m]; water green (src: Wikipedia EN, paris.fr).
- **Canal de l'Ourcq / Bassin de la Villette:** Ourcq large-gauge section 11 km without locks; Villette basin
  ~700 × 70 m [believed]; Canal Saint-Denis 6.6 km, 7 locks (src: paris.fr).
- **Île aux Cygnes / Allée des Cygnes:** ~890 m long, ~11 m wide, plane-lined (from LiDAR/OSM [believed]).
  **Bois de Boulogne lakes** not researched.
- Engine: `[shores] coast_type "quay"` fits the Seine's stone quays; but Paris has **no tide, no mud, no coast**
  (`coast = false` already): remove `mudflat` entries, no `SEA_Y` shore bands; the river is an "inland" surface.
  `city.json water.windFrom 225` (SW) is plausible for the mild Atlantic-influenced October [believed].

### 7.4 Preset: NYC now → Paris needs
| Table | NYC now | Paris |
|---|---|---|
| `[shores] coast_type` | quay (Manhattan bulkheads) | **quay** (stone quays; upper wall 6–9 m, lower quay 2.6–2.9 m above the water) |
| `mudflat*` | tidal flats | delete (inland) |
| `city.json water.sea` | Hudson/East River | unused (`coast = false`); `water.inland.river` set |
| Rooftop boats | | péniches (38.5 × 5 m) moored at the lower quays in rows; bateaux-mouches under the bridges |

---

## 8. Sun and season

Location **48.8566° N, 2.3522° E** (Notre-Dame/Hôtel de Ville), time zone **CEST (UTC+2)**; DST ends 25 Oct 2026, so
10 October is still summer time. Computed with the NOAA/Meeus solar algorithm in my script
`paris_region/sun.py` (refraction −0.833° for sunrise/sunset; civil/nautical/astronomical at −6/−12/−18°).

| Date (2026) | Declination | EoT | Solar noon (CEST) | Noon alt. | Sunrise | Sunset | Civil dusk | Nautical | Astronomical |
|---|---|---|---|---|---|---|---|---|---|
| Oct 5 | −4.85° | +11.6 min | 13:39 | 36.3° | 07:56 | 19:22 | 19:53 | 20:30 | 21:07 |
| **Oct 10** | **−6.76°** | **+13.0 min** | **13:37** | **34.4°** | **08:04** | **19:12** | **19:43** | 20:20 | 20:56 |
| Oct 12 | −7.51° | +13.5 min | 13:37 | 33.6° | 08:07 | 19:08 | 19:39 | 20:16 | 20:52 |

Sun on 10 Oct (altitude / azimuth from north, clockwise): 12:00 CEST 30.5° / 151.6°; 13:00 33.8° / 168.7°; 14:00
34.2° / 186.7°; **16:15 (city.json start) 24.6° / 223.8°**; 17:00 19.0° / 234.3°; 18:00 10.4° / 246.8°; 19:00 1.0° /
258.5°; 19:35 −4.7° / 265.0°; **21:30 (city.json "Night") −23.5° / 287.4°**. Day length ~11 h 08 min. The sun sets at
azimuth ~259° (WSW). **Note:** the "sunset ~19:35" I had passed on in the brief for the night research is the
civil-twilight end (19:43), not the sunset (19:12).

**city.json check** (`demos/paris/web/city.json`): `location 48.8566, 2.3522` ✓; `sun.date "10-10"` ✓; `time.utcOffset 2`,
`zone "CEST"` ✓; `time.start 16.25` = 16:15 CEST → sun 24.6° high, azimuth 224° (SW), a warm late-afternoon light
with long shadows towards NE; `presets.Day 16.25`; `Dusk: null` (computed from the sunset, 19:12 CEST);
`Night 21.5` = 21:30 CEST, sun −23.5° (past astronomical dusk 20:56, dark sky) ✓. `city.toml [sun] latitude 48.86,
declination −6.8` ✓ (−6.76°). `camera.azimuth 200` (view toward the SSW) is fine. Paris is at UTC+2 in
October: **do not** use CET.

Climate context for the look [believed]: mean October afternoon ~16–17 °C, cloud cover ~60–65 %, mean wind ~4 m/s
from the SW–W; a clear low-sun view is a fair-weather day. Sky/haze in city.json (`haze.colour [1.05,1.18,1.35]`)
is a clear-air Shenzhen look: Paris on a clear October afternoon is a paler, slightly warm haze; adjust in M9.

---

## 9. Driving side
**Right-hand traffic**, left-hand-drive vehicles, overtaking on the left; priority to the right at unmarked junctions
[believed]. Parking on both kerbs of one-way streets, most streets one-way (69 %). Buses and taxis stop at the
right kerb; bus lanes usually on the right kerb, or contraflow "à contresens" on the left kerb of some one-way streets;
the two-way bike tracks on Rivoli and Sébastopol are on the left side of the one-way roadway or the kerb side
depending on the section [believed]. Right turn on red is **not** allowed (only where a yellow arrow sign says so).

---

## What I could not verify
1. Hex of the IDFM bus blue; whether Paris's bike tracks have a coloured surface (no citywide rule found); exact
   asphalt colour of Paris roads (estimates from the aerial photo); kerb heights and lane widths (2.75–3.25 m is
   general knowledge).
2. Number of chimney stacks and dormers per building (typical values only; would need a roof survey or the APUR 3D
   model); cobble street list (only the OSM `sett` tags and the small `pavés mosaïques` layer).
3. The colour temperature of the Arc de Triomphe, Sacré-Cœur, Opéra, Louvre and Invalides lighting; whether the
   Eiffel Tower's golden projectors are now LED; Paris VIIRS radiance.
4. Île Saint-Louis arm width (only a rough LiDAR transect), Canal Saint-Martin width (27 m), bateau-mouche and
   Batobus dimensions, Île aux Cygnes dimensions.
5. Street-tree data completeness in the state-run gardens (Tuileries, Luxembourg, Palais-Royal, Jardin des Plantes).
6. The imagery date of the IGN orthophoto tile mosaic (I inferred summer 2024 from the Olympic arena at the Champ de
   Mars and the Arc's scaffolding); the facade brick samples come from two photographs.
7. Traffic mix on small streets (the counts are from main axes and the Maréchaux); traffic density per lane.
8. Whether `city3d` still needs new engine species (plane/chestnut crowns in `trees.js`) or a `moto` type in
   `cars.js`: I checked the presets and viewer file names only, not the rendering code.

---

## Sources
- IISR (Instruction interministérielle sur la signalisation routière), livre I, 7e partie, "Marques sur chaussées"
  (consolidated 2009): https://www.widling.fr/documents/Livre1-7partie.pdf ; Ville de Paris, "Guide des signalisations
  verticale et horizontale à Paris, partie 1", Nov 2025:
  https://cdn.paris.fr/paris/2025/12/15/guide-sh-sv-partie-1-principes-generaux-nov-2025-1-web-ZImB.pdf
- Ville de Paris open data (ODbL): `les-arbres` (220,215 trees), `eclairage-public` (165,581 lamps, 2026-09-01),
  `plan-de-voirie-passages-pietons` (22,123), `plan-de-voirie-chaussees`, `plan-de-voirie-trottoirs-emprises`,
  `stationnement-voie-publique-emplacements` (65,833), `compositions-du-trafic`, `plan-de-voirie-portes-cocheres`,
  `plan-de-voirie-paves-mosaiques-du-plan-de-voirie-de-paris`: https://opendata.paris.fr/explore/dataset/<id>/
- APUR "Emprise bâtie de Paris" (fields and code lists: https://capgeo2.paris.fr/mobile/rest/services/BASEMAPS/FDC_CAPGEO_Fond_Ville/MapServer/259
  and https://www.apur.org/open_data/EMPRISE_BATIE_OD.pdf; data: https://opendata.apur.org/), ODbL; IGN BD TOPO
  (Etalab): local copies in `demos/data/paris/`.
- IGN Géoplateforme WMS-Raster orthophotos: https://data.geopf.fr/wms-r/wms (layer `ORTHOIMAGERY.ORTHOPHOTOS`).
- Wikipedia FR: "Règlements d'urbanisme de Paris", "Toits de Paris", "Mineuse du marronnier", "Éclairage des rues à Paris",
  "Seine à Paris", "Pont Neuf", "Pont des Arts", "Pont Alexandre-III", "Liste des ponts de Paris", "Bouquinistes de Paris",
  "Boulevard Haussmann", "Boulevard périphérique de Paris", "Avenue Foch", "Réseau viaire de Paris", "Vélo à Paris",
  "Taxis parisiens"; Wikipedia EN "Eiffel Tower", "Canal Saint-Martin", "Freycinet gauge", model pages of the car types.
- paris.fr: "Pollution lumineuse", "Crues", "Les rives de Seine", "L'arbre à Paris", bilan des déplacements 2024,
  "50 km/h sur le périphérique", "Paris réforme son stationnement"; franceinfo (extinction 2022, Olympic rings);
  filiere-3e (Notre-Dame lighting); L'Argus/BASF (colours); ratpgroup.com, transbus.org (buses).
- Wikimedia Commons photos listed in §5.4 (Seine photos: "Seine-Paris.jpg" 2025-09-06, Pont de l'Alma Nov 2014,
  aerial from the Eiffel Tower Oct 2017).
- Scripts and scratch (not in the repo): `<scratch>/paris_region/`
  (`fetch.py`, `sample.py`, `sample2.py`, `fsample2.py`, `sun.py`, `apur_stat2.py`, `rules.py`, `lv.py`, `tstat2.py`,
  `sect.py`, `research_roads_vehicles.md`, `research_night_water.md`).
