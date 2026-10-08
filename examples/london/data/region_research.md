# London — region preset research (`europe-west`, second city after Paris)

Compiled 2026-10-01 for the build-3d-city engine, for London's milestones M2 (building kinds), M4 (facades), M5
(ground), M6 (trees, cars, rooftops) and M8 (night). Area: City of London, City of Westminster, riverside
Southwark and Lambeth (South Bank, Bankside, Borough, Vauxhall/Nine Elms), Tower Hamlets west plus the Isle of Dogs
(Canary Wharf), Battersea Power Station, the BT Tower corner, Greenwich (Park, Observatory, peninsula). All
"in the area" counts use the core box **lon -0.20..0.03, lat 51.47..51.53 (about 106 km²)** unless a line says
otherwise. Units: metres unless noted. Tags, as in Paris's file: **(src)** = read in the named source this session;
**(measured)** = computed by me from open data downloaded here (method named); **(sampled)** = PIL colour sampled
from a Wikimedia Commons photo (method in §5.4); **(derived)** = computed from sourced numbers; **[believed]** =
my estimate or recall, unverified. Hex values sampled from photographs are photo tones (exposure, haze, sun
angle), not albedo: hints only.

What this file feeds: `europe-west.toml` is now Paris's (M2, M4, M5, M6 tables done). Each section ends with
**"Preset: Paris now → London needs"**, naming the table to replace. London differs from Paris in six ways that
matter to the engine: **left-hand traffic**; **brick terraced houses, not a stone boulevard block** (59 % of
London's footprints share a wall with a neighbour, §5); **a tidal river with a muddy foreshore** (Paris's Seine has
no tide); **double-deck buses and cyclists** (39 % of street traffic in the City by day); **20 mph streets**; and a
much less regular street grid (median facade-to-facade gap 20 to 27 m on ordinary roads, §1.3).

Data I downloaded for this (all under `demos/data/london/raw/dl/`, git-ignored, 364 MB): the London Datastore
"Public Realm Trees" CSV (1,136,049 rows, OGL), Historic England's listed-building points (382,270, OGL) and
conservation areas (9,696 polygons, OGL) from planning.data.gov.uk. Reference photos: 46 JPEGs (960 px) in
`demos/data/london/research/region_refs/` (index at the end). Scripts are in the session scratchpad, not the repo.

---

## 0. Headline preset values

| Key | Value |
|---|---|
| Driving side | **LEFT** (vehicles on the left, driver on the right, buses stop at the left kerb, roundabouts clockwise) |
| Centre line (two-way) | **White**, never yellow. TSRGD diagram 1008 (limit ≤ 40 mph, i.e. all of central London): **2 m mark / 4 m gap (module 6 m), 100 mm wide**; 150 mm where the road is ≥ 10 m wide or has four lanes (src: DfT Traffic Signs Manual ch. 5 tables 2-1, figure 2-1) |
| `markings.dashes` (`[period, painted]`, m) | centre line **[6, 2]** (1008); lane line **[6, 1]** (1005: 1 m / 5 m, 100 mm); warning line before junctions and on bends **[6, 4]** (1004: 4 m / 2 m, 100 or 150 mm). The over-40 mph modules (3/6, 2/7, 6/3) are for the A13 and outer roads, not here |
| Yellow kerb lines | **Double yellow** (no waiting at any time, diagram 1018.1) = two 75 mm lines 75 mm apart, 250 mm off the kerb; **single yellow** (1017) 75 mm; 100 mm only where the limit is over 40 mph; yellow kerb "blips" for loading bans (src: TSM ch. 3 §13.4) |
| Red routes (TfL) | **Double red line** = no stopping at any time (diagram 1018.2), **single red line** (1017.1) = part-time; red lines along the kerb of TfL's "Red Route" roads (A-roads: Westminster Bridge, Whitehall approaches, Tower Bridge Rd, Euston Rd...); [src TSM ch. 3 §16; sampled faded red #d77d91 in a photo] |
| Zebra crossing | Belisha beacon = **yellow globe 275–335 mm** (diagram 4007) on a **black-and-white striped pole 2.1–3.1 m**; stripes **500–715 mm wide, equal black/white** (asphalt is the black), **2.4–10 m long, running along the direction of travel**, repeated across the carriageway; give-way line 200 mm wide, 500 mm marks/500 mm gaps, 1.1–3 m before the stripes; **zig-zag "controlled area"** lines in white, 2 m unit length between guide lines 500 mm apart, both kerbs and (on wide roads) the centre (src: TSM ch. 6 §15.8, §16.2) |
| Signalled crossings | **pelican** (2,678 nodes in the area), **puffin** (77), **toucan** (272), zebra **about 850**, parallel 47 (measured, OSM `crossing_ref`); no stripes at pelican/puffin/toucan, only two lines of studs and a 200 mm stop line [believed] |
| Box junctions | **Yellow** box with cross-hatch diagonals **150 mm wide, about 2 m apart** (2.5 m if the shortest side ≥ 9 m) (src: TSM ch. 5 §8.4) |
| Bus lane | Desirable **4.25 m** (≥ 4.0; absolute minimum 3.0), boundary a **continuous white line 250–300 mm** (diagram 1049A), white legend "BUS LANE". **Surface: red in many places, plain asphalt in others** (TSRGD: "coloured surfacing has no legal significance"; sampled red lane #8f6658 in Waterloo Road-type photo, plain asphalt #555050 on Westminster Bridge). OSM tags 30 km of bus lane in the area (src: TSM ch. 3 §9.3; measured) |
| Cycle tracks | TfL quality criteria: preferred minimum **2.2 m one-way, 3.0 m two-way** (src); segregated tracks kerb- or wand-separated, asphalt, white symbol; 198 km of OSM `highway=cycleway` plus on-road lanes on 912 primary ways (measured). Blue "Cycle Superhighway" paint is being replaced by plain tracks [believed] |
| Travel lane | 3.0–3.25 m [believed]; a two-lane two-way London street carriageway is 6–7 m [believed] |
| Speed limit | **20 mph**: `maxspeed=20 mph` on **91.6 %** of primary ways (4,725 of 5,159), **92 %** of secondary, 93 % of tertiary, **90 %** of residential; trunk (TfL Red Route A-roads) 71 % at 20, 26 % at 30 mph, 3 % at 40-50 (measured, OSM) |
| One-way share (OSM, measured) | trunk **68 %**, primary 48 %, tertiary 48 %, unclassified 41 %, secondary 40 %, residential **23 %** (Paris: 69 % overall) |
| Facade-to-facade gap (measured, rays from centre lines to building footprints every 25 m) | trunk median **39.1 m**, primary **26.9**, secondary **25.4**, tertiary **24.7**, residential **20.0** (p25 14.8), unclassified 18.5, living_street 21.6. Streets: Whitehall 44.8, Strand 23.5, Piccadilly 25.2, Pall Mall 20.2, Regent St 26.2, Cheapside 19.5, Threadneedle St 9.3, Shad Thames 10.0, Kingsway 30.9, Euston Rd 39.5, Marylebone Rd 44.7, The Mall 90 |
| Pavements | TfL minimum **2 m**, 3–5 m at bus stops (src: TfL bus-stop guidance via search); City of London: **York stone slabs 600 mm wide, random lengths, 63 or 75 mm thick**, silver-grey granite kerbs **300 × 200 × 900 mm, 125 mm upstand** (src: City Public Realm Technical Manual); elsewhere concrete flags or asphalt. OSM footway surface (tagged 34k): paving_stones 50 %, asphalt 32 %, paved 12.6 %, concrete 2.2 %, sett 0.9 % (measured) |
| Parking bays | White lines 50 mm, **2.0–2.4 m wide** bay, 4.5 m minimum per car (6.6 m disabled) (src: TSM ch. 3 §13.6: echelon ≥ 2.0 m, parallel space ≥ 4.5 m); Central London is "permit and pay" controlled parking (CPZ): bays next to double yellows; fewer cars per household than Paris [believed] |
| Vehicle mix (measured, DfT 2025 AADF, link-length weighted, major roads) | Westminster + City + Southwark + Lambeth **motor-only**: cars and taxis ~65 %, **vans (LGV) 19–20 %**, motorcycles 6–7 %, **buses 5–6 %**, HGVs 3 %. **Pedal cycles add 10 % (Westminster), 13 % (Southwark + Lambeth), 21 % (City)** of all counted units; 39 % of City street traffic 7am–7pm in 2024 (src: City Streets 2025) |
| Bus | **TfL red** (Pantone 485, sRGB ~ #da291c–#dc241f; sampled New Routemaster body mid #c6292d, median #be1220); **8,797 buses** (31 Mar 2025: 1,951 electric, 3,776 hybrid incl. **996 New Routemasters**, 20 hydrogen); double-deckers ~4.3–4.4 m tall; New Routemaster **11.23 × 2.52 × 4.39 m** (src: TfL fleet audit via search; Wikipedia via search) |
| Taxi | **Black cab**, LEVC TX **4.857 × 1.874 × 1.888 m** (src Wikipedia), mostly black (sampled #161b1e), a minority in advert wraps or other colours [believed 15 %]; **14,470 licensed taxis (Feb 2025), 8,828 zero-emission capable**; **96,517 private-hire vehicles** (src: TfL via search) |
| Car colours (UK) | New 2025: grey 27.6 %, black 23.0, blue 15.2, white 13.1, silver 6.3, red 5.8, green 4.9. Cars in use (MOT, 69 M vehicles): blue 19.1, silver 17.7, black 16.0, white 14.0, grey 12.3, red 12.1, green 5.2 (src: SMMT Jan 2026; motcheckup.co.uk) |
| Street trees | **London Datastore "Public Realm Trees": 1,136,049 trees** (OGL v3), **134,467 in the area**, of them 55,968 on highways, 46,780 in parks (**incl. The Royal Parks: 15,586**), 28,137 "other". Highway trees: **plane 22.5 %** (Westminster 29 %, Camden 33 %, Southwark 25 %), cherry 10.3, maple 8.9, pear 8.3, lime 6.8, birch 6.0, whitebeam 3.5, ash 3.3. Median street tree height **8.6 m** (plane **15 m**), median nearest-neighbour spacing **8.6 m** (measured) |
| Early-October foliage | Planes still green, turning yellow-brown from mid-October; **horse chestnuts brown from leaf miner**; cherries, birches and maples first to turn; peak autumn colour mid-to-late October (src: Woodland Trust / RHS / London guides via search). ~75 % green on 10 Oct [believed] |
| Roofs | Pitched **slate** (Georgian and Victorian terraces, sampled aerial tones #4a5155–#59524a shade to #776f69 lit), **clay plain tile** (Edwardian and suburbs, #a0583f [believed]), **flat lead/membrane** on institutions (#969993 sampled); **brick chimney stacks with clay pots on every party wall**; **butterfly and parapet roofs** hidden behind Georgian parapets; slate **mansards with dormers**. OSM `roof:shape` (12k tagged): gabled 54 %, flat 23.5 %, hipped 11.4 %, mansard 0.8 % (measured) |
| Facade, terrace | **London stock brick**, yellow-brown, sooted grey-brown: sampled mid **#a48e77** (Westminster Georgian), **#b89f74** (Southwark Victorian, sun), sooty #70675b; white stucco **#d8d3cb**; red brick **#be7e54** lit / #9c5f42 median; floors: ground 3.3–3.5, piano nobile 4.0–4.5, upper 3.0–3.3, attic 2.4–2.7 [believed] |
| Facade, Portland stone | **Sunlit #cdbca3**, overcast #b2ac9d, sooty (Bank of England) #7d705e; Parliament's limestone **#d3c0a6** (sunlit) |
| Street lights | **Westminster standard 3,000 K LED** (2,200–2,700 K for heritage lanterns); ~14,000 lights; ~6,500 heritage lanterns being LED-retrofitted (80 % "Grey Wornum"); **~300 gas lamps** survive, 94 being converted to a warm LED "honey" glow; **City of London all LED: 4,000 K main roads, 3,000 K minor, 2,700 K heritage**; Victoria Embankment **dolphin lamps** (1870) (src) |
| Floodlit landmarks | Parliament warm-gold floodlight, Elizabeth Tower clock faces 228 luminaires / 55,000 LED chips (green + white mix reads yellow); Tower Bridge 2012 colour-changing LED (2 km of linear LED, ~1,000 projectors); St Paul's 1980s floodlights being replaced by LED "warm wash"; Westminster Bridge arches lit green; Greenwich **green meridian laser** north from dusk to 23:00 (src) |
| Thames | **Tidal**: mean spring range about **6.6 m**, neap about 4.4 m at London Bridge (PLA booklet via search; up to 7 m per Wikipedia); colour **brown-tan to grey-olive**: sampled **#877b62** (Limehouse Reach aerial), sunlit #664f31 (brown, Albert Embankment), sky-reflecting #696a71–#8b8a96; **foreshore = 1.2 km² of the ~7.0 km² river** in the area (17 %, OS OpenMap Local, measured); Canary Wharf docks impounded (no tide) |
| Sun, 2026-10-10 (51.507° N, 0.128° W) | Declination −6.74°, EoT +13.0 min; sunrise **07:16**, **solar noon 12:48**, sunset **18:19**, civil dusk 18:52, nautical 19:31, astronomical 20:10 (all **BST, UTC+1**; DST ends Sun 25 Oct 2026); noon altitude **31.75°**; day 11 h 02 min |
| 16:15 BST | Sun altitude **16.8°**, azimuth **234.7°** (SW): much lower than Paris's 24.6° at the same local clock time, because London's local sunset is 53 min earlier |

---

## 1. Road markings and street geometry

### 1.1 What the UK rules say (TSRGD 2016; DfT Traffic Signs Manual chapters 3, 5, 6)
(src) The Traffic Signs Manual (TSM) is the DfT's guidance on the Traffic Signs Regulations and General Directions
(TSRGD). I read chapters 3 (regulatory signs, incl. waiting restrictions, bus lanes, red routes), 5 (road markings)
and 6 (pedestrian crossings), PDFs from gov.uk and tsrgd.co.uk. All numbers below are read in those texts.

**Longitudinal white lines (diagram numbers in brackets; speed limit ≤ 40 mph, i.e. everything in central London):**

| Line | Mark / gap | Width | Notes |
|---|---|---|---|
| **Centre line** (1008) | **2 m / 4 m** (module 6 m) | 100 mm (150 mm if the road is ≥ 10 m wide, or three or four lanes) | Over 40 mph: 1008.1 = 3 m / 6 m |
| **Lane line** (1005) | **1 m / 5 m** | 100 mm (150) | Over 40 mph: 1005.1 = 2 m / 7 m; the centre line must never be narrower than the lane line |
| **Warning line** (1004) | **4 m / 2 m** (the inverse of the centre line) | 100 or 150 mm | Replaces the centre/lane line approaching junctions, roundabouts, bends; minimum 5 marks at 30 mph, 7 at 40 mph; 1004.1 (over 40 mph) = 6 m / 3 m |
| Edge of carriageway (1009A, 1010, 1012.1) | continuous 100 mm; 1010 broken (junction mouths) | 100 (≤ 40 mph) | Rare in town |
| Double white (centre, urban multi-lane) | two lines | 100–150 each | [believed] |
| Zig-zag at crossings | zig-zag marks of **2 m** unit length between guide lines **500 mm** apart | [believed 100 mm] | White; also replaces the lane line/centre line through the controlled area |
| Give-way line at a crossing (1001.5) | 500 mm marks / 500 mm gaps | 200 mm | 1.1–3 m before the stripes |
| Junction give-way (1003A) and STOP (1002.1) | [believed] broken/continuous | [believed 200 mm] | Not read |
| Yellow box (1043) | outline 100–150 mm yellow, hatch diagonals 150 mm | | See §0 |
| Waiting restrictions | double yellow: two 75 mm lines, gap = line width (75 mm), 250 mm from kerb; single yellow 75 mm; kerb "blips" mark loading bans | 75 mm (100 over 40 mph, 50 in sensitive areas) | (src TSM ch. 3 §13.4.4–5) |
| Parking bay outline | white, 50 mm (75 or 100 mm for emphasis) | | (src §13.6.4) |
| Bus lane boundary (1049A) | continuous white | **250 or 300 mm** | Lane 4.25 m desirable, ≥ 4.0, min 3.0 (src §9.3) |

Colour: prescribed colours are white, yellow and **red** (red for red routes and congestion-charge entries); the
waiting-restriction yellow is BS 381C No. 355 (src §12.5.3). Photographed on granite setts/asphalt: fresh-ish
double yellow **#ddc045** (sampled mid), faded double red **#d77d91** (sampled: the paint weathers to a pinkish
red; fresh red is deeper, [believed] ~#c8323c), granite kerb **#a6a49e–#b5b7b5**, asphalt **#686a6d–#7e7c78**.

**Belisha beacons and zebras (src TSM ch. 6 §16.2).** One yellow globe at each end of the crossing (275–335 mm, on
a 2.1–3.1 m black-and-white banded pole, often with a flashing amber globe); black and white stripes must be
equal-width, **500–715 mm** (380–840 mm by exception), with a black stripe against the kerb at each side (≤ 1.3 m
wide); stripes **2.4 m to 10 m long "in the direction of travel"**, i.e. each stripe is a long bar parallel to the
kerb, repeated across the road. On the ground a typical 2.4–4 m crossing has pitch 1.0–1.3 m. Give-way line
200 mm wide of 500 mm marks/500 mm gaps, 1.1–3 m back. **"LOOK RIGHT / LOOK LEFT" legends** are painted on the
kerbside at busy tourist crossings (Westminster, South Bank) [believed].

**Crossings mapped in OSM in the area (measured, nodes):** `crossing_ref=pelican` 2,657 traffic-signal nodes (a
pelican node per carriageway, so about 1,300 crossings), `toucan` 272, `puffin` 77, `zebra` about 855
(uncontrolled 692 + marked 131 + zebra/zebra 28 + unmarked 4), `informal_zebra` 56, `parallel` 47, plain
`traffic_signals` crossings 859, `unmarked` 8,318 (kerb drops, no paint), islands 1,290. There are **4,543 traffic
signal nodes**, 2,439 bus stops, **3,132 speed humps, 1,658 raised tables, 1,184 speed cushions** and 365 bumps
(measured) — the 20 mph zones are heavily calmed, which also means raised-table crossings at most junctions.

**Engine mapping.** `city.json markings.dashes` `[period, painted]`: London centre line is **[6, 2]**; the engine's
Paris T1 [13, 3] would be wrong. `centreColour "white"` is already set. The zebra keeps the NYC/Paris layout
(bars along the traffic) with **0.5 m bars, 0.5 m gaps (black = asphalt), 3–4 m long** (Paris: 0.5 bar, 0.55 gap,
3.9 long); add the **Belisha beacon** prop (globe 0.3 m on a striped pole 2.5 m) and white zig-zags along both
kerbs for ~14 m (unit 2 m, guide lines 0.5 m apart).

### 1.2 Asphalt, kerbs and pavements
- **Asphalt** (sampled, Commons photos): Westminster Bridge **#555050** (wet-dark), Pimlico street in sun
  **#7e7c78**, the red/yellow-line close-up **#686a6d–#6d6f73**; Paris values (#6d6b69–#7d7977) hold. London asphalt
  is darker and patched more, with yellow lines and red-route edges: lines matter more than the tone.
- **Kerbs:** granite, City of London: **silver-grey granite 300 × 200 × 900 mm, flamed front and top, 125 mm
  upstand**; 150 mm-wide narrow kerb for lanes and courtesy crossings; double mid-grey granite channel beside the
  kerb; **granite setts 300 × 150 mm** (two-colour light/mid grey, or three-colour with a pink tone) as carriageway
  surface in historic lanes, loading bays and raised courtesy crossings (src: City Public Realm Technical Manual,
  2016). Sampled kerb tones: **#a6a49e–#b5b7b5**. Westminster uses granite kerbs and York stone in the West End
  and St James's [believed].
- **Pavements:** **York stone** (Scoutmoor) is the City's standard: **600 mm wide, random lengths, 63/75 mm
  thick, 6 mm joints, laid perpendicular to the kerb**; smaller setts only where < 1.5 m wide (src). Elsewhere
  concrete flags (600 × 600 or 450 × 450, grey, [believed]) and asphalt. OSM footway `surface` (tagged, 34k ways):
  `paving_stones` 17,032, `asphalt` 11,024, `paved` 4,276, `concrete` 754, `sett` 320 (measured). Tactile
  blister paving at crossings (buff/red/pink in London: red at signal crossings, buff at uncontrolled, [believed]).
  Residential roads: `surface=sett` 324 of 11.6k ways (3 %), `paving_stones` 667 (6 %), `cobblestone` 56 (0.5 %):
  London's setts survive on the docks lanes (Shad Thames), Covent Garden, parts of the City (measured).
- **Furniture** (OSM nodes in the area, measured): **bollards 3,835, benches 6,304, post boxes 1,189 (red, Royal
  Mail pillar boxes ~1.5 m tall [believed]), telephone 1,007 (many red K6 kiosks ~2.4 m [believed]), bicycle_rental
  620 (Santander docks + Lime), EV charging 251, street_cabinet 189**. Street lamps are poorly mapped (3,100 nodes,
  against ~40,000 real lights [believed]).

### 1.3 Street widths and profiles (measured)
Method: for every OSM centre line of a class inside the area (no tunnels or bridges), a sample point every 25 m, a
70 m ray to each side, the nearest building footprint each side (Overture, 219,592 polygons in the wider box);
samples with no hit on one side are dropped. Facade-to-facade gap in metres:

| Class | Ways | Samples kept | p10 | p25 | **median** | p75 | p90 |
|---|---|---|---|---|---|---|---|
| trunk (TfL A-roads) | 3,275 | 1,801 | 20.7 | 26.5 | **39.1** | 60.6 | 79.5 |
| primary | 5,159 | 1,770 | 17.7 | 21.2 | **26.9** | 43.4 | 65.1 |
| secondary | 1,299 | 1,455 | 14.9 | 17.8 | **25.4** | 42.8 | 67.1 |
| tertiary | 2,273 | 1,683 | 14.2 | 17.1 | **24.7** | 44.8 | 65.9 |
| residential | 11,578 | 1,925 | 11.4 | 14.8 | **20.0** | 35.5 | 60.5 |
| unclassified | 4,358 | 1,759 | 8.7 | 12.3 | **18.5** | 36.9 | 63.0 |
| living_street | 108 | 147 | 12.3 | 15.8 | **21.6** | 36.2 | 58.8 |

The high p75–p90 values are where a road runs beside a park, the river, a rail cutting or a square (the ray
finds nothing close on one side); the p25 is the terraced-street value. **Named streets** (median, p25–p75; n
samples): Whitehall 44.8 (31.6–76.6), Parliament Street 43.5, Victoria Street 48.5 (22.8–78.1, the post-war
open plazas), Victoria Embankment 79 (river side open), The Mall 90, Strand **23.5** (21.7–37.1), Piccadilly
**25.2** (24.0–25.6), Pall Mall 20.2, Regent Street **26.2** (24.3–27.4), Kingsway 30.9 (30.7–32.3), High Holborn
19.9, Cheapside 19.5, Gracechurch St 19.3, Fenchurch St 18.3, **Threadneedle St 9.3**, Bishopsgate 26.1, London
Wall 29.3, Queen Victoria St 29.3, Cannon St 20.9, Borough High St 25.1, Southwark St 24.4, Blackfriars Rd 32.2,
Waterloo Rd 26.3, Tooley St 19.8, **Shad Thames 10.0**, Tower Bridge Rd 22.1, Jamaica Rd 46.4, The Highway 45.5,
Commercial Rd 32.7, Cable St 29.3, Narrow St 29.5, Westferry Rd 36.9, Euston Rd **39.5**, Marylebone Rd 44.7,
Old Kent Rd 38.2, Vauxhall Bridge Rd 32.4, Nine Elms Lane 40.8, Wandsworth Rd 33.0, Greenwich High Rd 33.3,
King William Walk 30.2, Lower Marsh **14.2**, Gower St 18.9, Oxford St **24.7**.

Typical cross-section [derived from the gaps, TfL and City guidance, believed for the carriageway split]: **Regent
Street-type 26 m gap** = 2 × 4–5 m pavement + 16–17 m roadway (two lanes each way plus bus/bay); **ordinary
residential 20 m** = 2 × 2–3 m pavement + 2 × 3–4 m front-garden/lightwell setback + 6–7 m carriageway;
**Georgian terrace street 14–15 m** = 2 × 2.5 m pavement + 6–7.5 m carriageway with parking on one side;
**City lane 9–10 m** = 1.5–2 m pavements + 5 m carriageway. Paris's boulevards are wider (30 m) with much wider
pavements (8 m); London has no Haussmann pavement: plan for 2–4 m.

### 1.4 Lanes, one-way streets, speed (OSM, local copy of the BBBike London extract, 2026-09-26; area box)
| Class | Ways | One-way | `lanes` tagged (share) | `maxspeed` 20 mph | 30 mph |
|---|---|---|---|---|---|
| trunk | 3,275 | **68 %** (2,213) | 2: 1,324, 3: 680, 4: 449, 5+: 109, 1: 284 (87 % tagged) | **71 %** | 26 % (40–50 mph 3 %) |
| primary | 5,159 | 48 % (2,487; 4 alternating) | 2: 2,188, 1: 785, 3: 652, 4: 267 (76 %) | **91.6 %** | 8 % |
| secondary | 1,299 | 40 % | 2: 544, 1: 230, 3: 32 (62 %) | 94 % | 4 % |
| tertiary | 2,273 | 48 % | 2: 939, 1: 300, 3: 73 (58 %) | 93 % | 4 % |
| residential | 11,578 | **23 %** (2,612) | 2: 780, 1: 374 (10 %) | 90 % | 0.8 %; 5 mph 78, 10 mph 32 ways (mews, estates) |
| unclassified | 4,358 | 41 % | 2: 763, 1: 480 (29 %) | 86 % | 1 % |
| living_street | 108 | 19 % | few | 53 % | 8 % |

Surface: primary 98.9 % asphalt, residential asphalt 6,969 of 8,188 tagged, `sett` 324, `paving_stones` 667 (shared
surfaces, mews). **Lit**: 100 % of primary/secondary, 54 % of residential tagged `lit=yes`. OSM `lanes` on a
one-way road counts the lanes in that direction. **Bus lanes tagged:** trunk 14.7 km, primary 14.8 km, service 51 ways,
links 0.7 km (only 30 km; real coverage is larger, [believed ~60–80 km]); `cycleway=lane` on 912 primary and
477 trunk ways, `share_busway` on 487 primary and 509 trunk ways (cyclists allowed in bus lanes), `track` 136 + 75,
`separate` 682 + 390 (a parallel cycleway way). Bus-only `highway=busway` ways: 5.

### 1.5 Bus lanes, cycle lanes, parking, and London's kerb
- **Bus lanes:** with-flow on the nearside (left) kerb, white boundary 250–300 mm continuous, "BUS LANE" legend;
  hours vary. Where coloured, the surface is **oxide red** (sampled in a street-level photo of a red lane with white
  lettering: mid **#8f6658**, p90 #af7f68; the paint reads brown-red, a dark-red ~#8a4b3f at albedo [believed]); on
  Westminster Bridge the same white-line legend sits on plain dark asphalt. Model as **a mix**: 50 % red-surfaced,
  50 % plain, per lane (no dataset tells which). Bus stop "cages" red or white-lined with "BUS STOP" legend (src
  TSM ch. 3 §13.24; TfL: "red coloured surface treatment is used within bus stop cages").
- **Cycle lanes/tracks:** TfL Cycleways have preferred widths 2.2 m (one-way) and 3.0 m (two-way) and are separated
  by kerbs or light segregation; the Embankment and Blackfriars tracks are two-way, about 3–4 m [believed]. Cyclists
  lead the traffic mix in the City: 39 % of street traffic 7am–7pm, **56 % in the 8–9am and 6–7pm peaks** (2024
  counts); dockless cycles are 17 % of all cycles (src City Streets 2025 Summary Report).
- **Parking:** OSM has `parking:*` tags on only 13 % of residential ways (1,497 of 11.6k) and 14 % of primary
  (748 of 5.2k), so most parking is default-modelled; `amenity=parking` with `parking=street_side` 671, `lane` 109,
  `surface` 799, `multi-storey` 21, `underground` 25 (measured). UK bay: **2.0–2.4 m wide, at least 4.5 m long per
  car**, white 50 mm outline, marked "Residents only/Pay and display" on signs; parallel kerbside bays along most
  residential streets; yellow lines on junction mouths and all red routes. Double yellows mean **no kerbside parking on
  most primary/trunk roads**: parked-share much lower on TfL roads than on back streets.
- **Red routes (TfL "Red Route" network)**: A-roads such as Westminster Bridge Road, Euston Road, Tower Bridge Road,
  Jamaica Road, Old Kent Road: double red lines, bus lanes, no stopping; very few parked cars there.

### 1.6 Preset: Paris now → London needs
| Table (europe-west.toml / city.json) | Paris now | London |
|---|---|---|
| Traffic side (engine) | right | **LEFT**: lane offsets, turn arcs, bus/taxi stops, bus lane on the left kerb, roundabouts clockwise; needs an engine flag (`traffic.side = "left"`) [not in engine] |
| `markings.centreColour` | white | **white** (no change) |
| `markings.dashes` `[period, painted]` | [13, 3] | centre **[6, 2]**, lane **[6, 1]**, warning **[6, 4]**; a per-kind dash table is better than one pair |
| Kerbside yellow | (none) | **double yellow** along primary/trunk kerbs and junction mouths (75 mm, 75 mm gap, 250 mm off kerb) and junction keep-clears; single yellow on back streets; red double line on TfL red routes |
| zebra bars (06b_markings) | 0.5 m bars, gap 0.55, 3.9 long | 0.5 m bars, **gap 0.5 (asphalt)**, **3–4 m long**, along the traffic, **+ Belisha beacon props and white zig-zags** |
| Signalled crossings | | pelican/puffin/toucan: two lines of studs + stop line 0.2 m; no stripes (2,678 + 77 + 272 OSM nodes) |
| Box junctions | (none) | **yellow cross-hatch**, 150 mm diagonals at 2 m |
| Speed calming | | **3,132 humps, 1,658 tables, 1,184 cushions** from OSM `traffic_calming`: raised tables at junction mouths |
| bus lane | none (white line + BUS) | **4.25 m**, white boundary 0.25–0.3 m, "BUS LANE", **red surface on ~50 %** of lanes (tag from OSM `lanes:bus`/`busway`) |
| bike lane | none | **2.2 m one-way / 3.0 m two-way** plain asphalt with white symbol; segregated from `cycleway=track/separate` |
| `[markings.sidewalk_w]` | trunk 4.0, primary 6.5, secondary 5.0, tertiary 4.0, residential 3.5, unclassified 3.0, living_street 2.5 | trunk **4.0**, primary **4.5**, secondary **4.0**, tertiary **3.2**, residential **2.5**, unclassified **2.3**, living_street 2.0 [believed; gaps above leave 2–4 m] |
| `[markings.median_w]` | primary 3.0, secondary 2.0 | trunk 1.0, primary 0 (a hatched centre or refuge is not a planted median); Embankment-style divided roads keep 2.0 |
| `[roads.parking_lanes]` | primary 2, secondary 2, tertiary 2, residential 2 | trunk 0, primary **0–1**, secondary 1, tertiary 2, residential 2 (parking on the far kerb of a one-way street) |
| `[roads.default_w]` (kerb to kerb, [two-way, one-way]) | trunk [16, 9], primary [14, 11], secondary [12, 9], tertiary [10, 7.5], residential [9, 6], unclassified [7, 5.5], living_street [5, 4.5] | trunk **[14, 10.5]**, primary **[12, 9]**, secondary **[10.5, 8]**, tertiary **[9, 7]**, residential **[7, 5.5]**, unclassified **[6.5, 5]**, living_street [5, 4] [derived: gap minus 2 × pavement minus front-garden setback; believed] |
| `LANE_W` | 3.2 | **3.0–3.25 m** |
| One-way handling | 69 % one-way | **23 % (residential) to 68 % (trunk)**: read OSM `oneway`; do not assume |
| Street furniture | Wallace fountains, Morris columns | **red pillar boxes (1,189), red K6 kiosks (1,007), Santander docks (620), bollards 3,835, benches 6,304**: all mapped in OSM |

---

## 2. Vehicles

### 2.1 Traffic mix (measured, DfT road traffic statistics, AADF 2025, London region file)
Source: `dft_aadf_region_id_6.csv` (DfT "Annual Average Daily Flow" by count point, 2025 estimates; vehicle types
pedal cycles, two-wheeled motor vehicles, cars and taxis, buses and coaches, LGVs, HGVs), from
storage.googleapis.com/dft-statistics/road-traffic (public). Shares weight each count point by its link length
(0.3 km where missing); all are "Major" roads except a handful of minor ones. **Percent of all counted units**
(including pedal cycles), and motor-only in brackets:

| Area | Count points | Cycles | Motorcycles | Cars and taxis | Buses and coaches | LGV (vans) | HGV |
|---|---|---|---|---|---|---|---|
| Westminster | 118 | 9.9 | 6.2 (6.9) | 59.8 (66.4) | 5.2 (5.8) | 16.3 (18.1) | 2.5 (2.8) |
| **City of London** | 33 | **21.4** | 7.3 (9.3) | 44.3 (56.4) | 4.7 (6.0) | 18.6 (23.7) | 3.6 (4.6) |
| Southwark + Lambeth | 184 | 13.0 | 6.6 (7.6) | 56.0 (64.3) | 5.3 (6.0) | 16.6 (19.1) | 2.6 (3.0) |
| Tower Hamlets | 54 | 4.8 | 5.5 (5.8) | 64.8 (68.0) | 1.7 (1.8) | 19.9 (20.9) | 3.3 (3.5) |
| Greenwich | 73 | 1.1 | 3.0 | 71.1 (71.9) | 2.0 | 19.4 (19.6) | 3.5 |
| Westminster + City + Camden + Southwark + Lambeth + Tower Hamlets + Greenwich (541 points) | | 7.9 | 5.4 (5.9) | 62.1 (67.4) | 3.6 (4.0) | 17.9 (19.5) | 3.0 (3.2) |

AADF point counts are dominated by A-roads. On the City's own street counts (2024, all streets, 7am–7pm), **cycles
are 39 % of on-street traffic** and "almost twice as many as cars and private hire vehicles", rising to 56 % in the
8–9am and 6–7pm peaks; motor traffic is about a third of 1999 (src: City Streets 2025 Summary Report).
"Cars and taxis" include black cabs and private-hire cars (the DfT does not separate them). Best guess for
splitting [believed]: black cabs ~10 % and PHVs ~20–25 % of the cars in central London.

**Suggested spawn mix, central London roads, daytime (derived), motor vehicles only:**

| Class | Share | Engine type |
|---|---|---|
| Hatchbacks and saloons (Corsa, Golf, Fiesta, Prius, Model 3, Mercedes E) | 30 % | `sedan` |
| SUVs and crossovers (Puma, Qashqai, Juke, Sportage, Model Y) | 27 % | `suv` |
| **Black cabs** | 8–10 % (12 % near stations, Whitehall, Strand) | `taxi` |
| Vans (Transit Custom, Vivaro, Berlingo) | 18 % | `van` |
| **Motorcycles and mopeds** (delivery riders included) | 6–7 % | `moto` |
| **Buses (double-deck)** | 5 % (10 % on bus corridors), 0 on back streets | new `bus_dd` |
| Rigid trucks | 3 % | `truck` |
| Artics, coaches | ≤ 1 % | |
Add **bicycles: 10–20 % of all units on central A-roads (City 21 %, cycle superhighways 40–55 % in peak hours)**,
also e-bikes and Lime/Santander hire bikes. Average traffic speed is 8–10 mph [believed, TfL "Travel in London"]:
free-flow on 20 mph streets 8.9 m/s, derate to ~0.6.

### 2.2 Black cabs, private hire, buses
- **Taxis:** TfL licences **14,470 taxis (Feb 2025; 22,810 in 2013-14, −35 % in ten years)**, **8,828 zero-emission
  capable (61 %)**; 16,816 taxi drivers; **96,517 private hire vehicles** and 105,734 PHV drivers (src: London
  Assembly/TfL via search). The LEVC TX (range-extender electric) "makes up half of the fleet"; > 9,000 TXs in 2025
  (src: levc.com via search). **LEVC TX: 4,857 mm × 1,874 mm × 1,888 mm, wheelbase 2,986 mm** (src: Wikipedia); the
  TX has a short nose with a big black grille, a full-length glass roof and a tall cabin (photo
  `cab_tx.jpg`) [believed for the details]. The older TX4 and Mercedes Vito/NV200 taxis are the rest [believed].
- **Colour:** black dominates (sampled TX body #161b1e), TfL allows other colours and full-wrap advertising; a
  minority wear white, silver, blue, red, green or advert wraps: **black 85 %, other 15 %** [believed]. The roof
  sign reads "TAXI" (yellow when vacant, off when hired [believed]; sampled TX roof sign not visible). Taxi ranks:
  "TAXI" legend on a bay (src TSM ch. 3 fig 16-10 variant on red routes).
- **Private hire:** Toyota Prius/Corolla hybrids, Tesla Model 3, Mercedes E/V-class, Skoda Octavia: dark colours
  (black, grey, silver), no roof sign [believed].
- **Buses:** TfL fleet **8,797 (31 Mar 2025)**: 1,951 electric, 3,776 hybrid (996 New Routemasters), 20 hydrogen,
  the rest diesel; all PSVAR-compliant (src: TfL Bus Fleet Audit 31 March 2025 via search). The **New Routemaster
  (LT) is 11.23 × 2.52 × 4.39 m** (src: Wikipedia via search), with a rear open platform (kept closed in service since the
  pandemic [believed]), three doors on the left, two staircases, a distinctive curved glass front and rear; the
  Enviro400 (Alexander Dennis) **10.5–11.1 m × 2.55 m × 4.3 m** and Wrightbus StreetDeck are the other double-deck
  types, and single-deckers (Enviro200, 10.5 m, ~3.0 m) on a few routes [believed]. **Double-deckers are more than
  80 % of the fleet** [believed]. **Livery: TfL red** (Pantone 485; the sample of a New Routemaster side #c6292d
  lit, #be1220 median), white-grey roof, dark grey skirt at the base, black window band, white route number and the
  destination blind in amber LEDs at the front; the ad panel on the side and the back is sold (TfL red overall is
  ~80 % [believed]). Bus stops on the left kerb with a red "cage" or white box, some stops have a flag and a shelter
  (2,439 OSM stops in the area, measured).
- **Bikes:** Santander Cycles (TfL hire): **about 10,000 pedal bikes and 2,000 e-bikes at 800+ docking stations**
  (src: visitlondon/TfL via search); bike livery white and red with "Santander" on the red mudguards and a red
  logo panel (photo); docking stations in rows of 12–24 stands with a central terminal (photo
  `santander_dock.jpg`), OSM `bicycle_rental` 620 nodes in the area. Dockless Lime e-bikes: lime-green; other dockless
  schemes (Human Forest, Forest, Dott): green/lilac/blue [believed]. **Private bicycles: black/grey/silver with
  helmets in black and neon** [believed].

### 2.3 Car dimensions (mm; L × W without mirrors × H): UK best-sellers and London's taxi/PHV fleet
(src) 2025 UK new-car top ten (SMMT via search): Ford Puma 55,488, Kia Sportage 47,788, Nissan Qashqai 41,141,
Vauxhall Corsa 35,947, Nissan Juke 34,773, VW Golf 32,478, Volvo XC40 30,404, MG HS 30,191, VW Tiguan 29,857,
Hyundai Tucson 28,613; the best-selling models are SUVs/crossovers. Dimensions [believed, from memory of the
Wikipedia pages; not re-fetched], round numbers:

| Model | L | W | H | Note |
|---|---|---|---|---|
| Vauxhall Corsa (F) | 4,060 | 1,765 | 1,433 | supermini |
| Ford Fiesta (VII) / Ford Puma | 4,040 / 4,207 | 1,735 / 1,805 | 1,476 / 1,537 | Puma is the best seller |
| VW Golf (VIII) | 4,284 | 1,789 | 1,456 | |
| Nissan Juke / Qashqai (III) | 4,210 / 4,425 | 1,800 / 1,838 | 1,595 / 1,635 | |
| Kia Sportage (V) | 4,515 | 1,865 | 1,650 | |
| Toyota Prius (IV) / Corolla | 4,600 / 4,370 | 1,760 / 1,790 | 1,470 / 1,435 | PHV workhorses |
| Tesla Model 3 / Model Y | 4,694 / 4,751 | 1,849 / 1,921 | 1,443 / 1,624 | |
| Mercedes E-Class / V-Class | 4,950 / 5,140 | 1,860 / 1,930 | 1,470 / 1,880 | PHV |
| **LEVC TX taxi** | **4,857** | **1,874** | **1,888** | src Wikipedia |
| Ford Transit Custom / Vauxhall Vivaro | 4,970 / 4,960 | 1,990 / 1,920 | 1,970 / 1,940 | standard LWB vans |
| Ford Transit (Luton, 3.5 t) | 6,000–7,000 | 2,100 | 2,600–3,300 | [believed] |
| Rigid delivery truck (18 t) | 8,000 | 2,450 | 3,300 | [believed] |
| **New Routemaster** | **11,230** | **2,520** | **4,390** | src Wikipedia |
| Enviro400 double-decker | 10,500–11,100 | 2,550 | 4,300 | [believed] |
| Moped / scooter (Honda PCX / Vespa) | 1,900 | 700 | 1,200 | delivery riders (Deliveroo) |
| Santander bike | 1,900 | 600 | 1,100 | ~22 kg [believed] |

Engine `cars.types` (name, L, W, H): sedan **[4.15, 1.77, 1.46]**, suv **[4.40, 1.83, 1.60]**, taxi **[4.86, 1.87,
1.89]** (TX), van **[5.0, 1.95, 1.95]** (Transit Custom/Vivaro; London vans are the real long-wheelbase type, not
Kangoo-size), **bus_dd [11.2, 2.52, 4.39]** (NRM) **plus a second double-decker [10.8, 2.55, 4.3]**, truck [8.0,
2.45, 3.3], lorry [12.0, 2.55, 3.8] (none in the centre), moto [1.95, 0.72, 1.2], bike [1.85, 0.6, 1.1].

### 2.4 Colours (UK)
(src) **New cars 2025** (SMMT, 16 Jan 2026): **grey 27.62 %, black 22.98, blue 15.16, white 13.14, silver 6.30,
red 5.77, green 4.94, yellow 0.53, orange 0.48, mauve 0.28**. **Cars in use** (MOT record, 69.0 M vehicles):
**blue 19.06 %, silver 17.69, black 16.04, white 14.02, grey 12.26, red 12.12, green 5.17**, yellow 0.60, orange
0.56, beige 0.52 (src: motcheckup.co.uk). UK 2024: grey 27.8, black 21.7, blue 14.9, white 14.93 (SMMT via search).
Suggested palette for the mix (synthesis, weighted to new cars and London's PHVs; hex as in Paris's file):

| Colour | Share | Hex |
|---|---|---|
| Black | 21 % | #16171a |
| Grey (mid + anthracite) | 19 % | #8d9196 / #4b4f55 |
| Blue (dark/mid) | 15 % | #2c4a78 |
| White | 14 % | #f0f0ee |
| Silver | 12 % | #b5b9bd |
| Red | 8 % | #a32028 |
| Green (dark/forest) | 4 % | #2f4a3a |
| Beige/gold/brown | 3 % | #c9bb9f |
| Other (orange, yellow) | 4 % | #d9822b |
Black cab fleet: black #101114 (85 %), other 15 % (white, silver, advert wraps). Delivery: Royal Mail vans red
(#c8102e [believed]), Amazon/DHL/DPD white or branded; police marked Vauxhall/BMW estates in **white/silver with a
blue-yellow Battenburg check** [believed]; fire engines red; ambulances yellow-green; **red buses, blue-and-white
police, black cabs and red post vans** are London's colour accents.

### 2.5 Parking rows in the engine
Central London streets are in controlled parking zones; the measured OSM facts: parking tagged on 13–15 % of
streets (`parking:*`), `street_side` lots 671 and `lane` 109 (amenity=parking), `multi-storey` 21 and
`underground` 25. The defaults should be **lower than Paris**: fewer households own a car [believed: most
central-borough households have no car, Census 2021], double yellow lines ban kerbside parking on most primary
and all red-route roads, and cars park in one direction on the nearside or in marked bays. [Believed]
per-side odds: primary 0.06, secondary 0.18, tertiary 0.3, residential 0.45, unclassified 0.35,
living_street 0.15, service 0.1; occupancy 0.7–0.85 (resident permit bays) and more two-wheeler bays (Westminster
"motorcycle parking"); one-way streets are parked on both sides only when wide enough.

### 2.6 Preset: Paris now → London needs
| Table | Paris now | London |
|---|---|---|
| `cars.types` | sedan 4.10, suv 4.35, taxi 4.62 (Prius), van 4.60 (Kangoo), bus 12.0 × 2.55 × 3.15 (IDFM), truck 7.5, lorry, moto 2.05 | sedan [4.15, 1.77, 1.46], suv [4.40, 1.83, 1.60], **taxi [4.86, 1.87, 1.89]** (TX), van **[5.0, 1.95, 1.95]**, **bus (double-deck) [11.2, 2.52, 4.39]**, truck [8.0, 2.45, 3.3], moto [1.95, 0.72, 1.2], add **bike** [1.85, 0.6, 1.1] |
| `cars.class` mix (sedan, suv, taxi, van, bus, truck, lorry, moto) | primary [34,20,10,9,4,3,0,17], secondary [36,21,8,10,2,2,0,17], residential [38,22,5,12,0,0,0,17] | primary **[30,27,9,18,5,3,0,7]**, secondary [31,27,8,19,4,3,0,7], tertiary [32,28,6,20,2,3,0,7], residential [34,29,3,21,0,1,0,7] (re-normalise), trunk [29,26,8,18,8,4,0,7]; **+ cyclists 10–20 % of units** on primaries and cycleways |
| free-flow speed | primary 11, residential 7 m/s | **20 mph = 8.9 m/s** on all classes except 30 mph trunk pieces (13.4); heavy queueing (×0.6) |
| `cars.palettes.taxi` | black 70 %, white 15 %, grey 10 % | **black 85 %**, other 15 % (white, silver, advert wraps); roof sign lit when free |
| `cars.palettes.bus` | white + IDFM blue | **TfL red #da291c, grey roof #9ea2a6, black window band, dark skirt**; ~4 % with a full-wrap advert |
| `cars.palettes.van` | white 60 %, La Poste yellow 6 % | white 55 %, silver/grey 20 %, **Royal Mail red 6 %**, other 19 % |
| `cars.palettes.sedan/suv` | French: white 29, grey 21, black 20 | UK: black 21, grey 19, blue 15, white 14, silver 12, red 8, green 4, other 7 (§2.4) |
| `cars.kerbside` | primary 0.2, secondary 0.25, tertiary 0.3, residential 0.33 | primary **0.06**, secondary **0.18**, tertiary 0.3, residential **0.45** (CPZ), unclassified 0.35; occupancy 0.75 |
| `cars.oneway_both_sides` | true | **false unless wide** (one-way streets park on both sides only when ≥ 7 m) |
| `cars.park_w` / `park_pitch` | 2.0 / [4.9, 5.8] | **2.1** / **[5.0, 6.0]** (bay 2.0–2.4 m, ≥ 4.5 m per car) |
| `moto_bays` | 0.07 | 0.04 |
| `cars.restricted_density` (Rivoli-type) | 0.45 | **bus-only streets** (Whitehall's Horse Guards, bus gates): buses, taxis, cycles only: mix [0,0,25,0,35,0,0,5] + 35 cyclists |

---

## 3. Street trees and parks

### 3.1 The London tree inventory can be downloaded here (tested)
- **Dataset:** London Datastore, **"London Public Realm Trees"** (formerly "Local Authority Maintained Trees"),
  compiled by GiGL/GLA, **Open Government Licence v3**, **about 1,140,000 trees**. Page:
  https://data.london.gov.uk/dataset/local-authority-maintained-trees/
  (works from this machine, no account). Files on the page: `Borough_tree_list_2025Nov.csv` (**199 MB**, what I
  used), `Borough_tree_list_2021July.csv` (100.9 MB), `Borough_tree_list.csv` (80.9 MB), and the 2018 GLA street
  tree CSV `london_street_trees_gla_20180214.csv`. Direct download (HTTP 200, no login):
  `https://data.london.gov.uk/download/2r45m/e62a6a1f-390d-4193-ae32-3aabd9846f36/Borough_tree_list_2025Nov.csv`.
- **Fields (measured):** `borough, lat, lon, uniqueid, taxon_species, common_name, taxon_genus, common_genus,
  gla_name, taxon_family, maintainer, location, climate_suitability, cs_confidence, age_cat, canopy_m, height_m,
  girth_dbh`. `lat/lon` WGS84; `gla_name` a 40-class common name (no nulls); `location` = Highways / Parks /
  Other / Housing; sizes are strings ("10 m", "54 cm"), 88–90 % filled; `age_cat` ("Young (0-15)", "Early mature
  (16-30)", "Mature (31-80)", "Over mature (81-150)", "Veteran"; 48 % "Not provided" on streets).
  `girth_dbh` values (plane median 54 cm) look like a stem **diameter at breast height**, not circumference
  [believed; the field says "girth" but planes of 15 m do not have 1.7 m girths in the median].
- **Count: 1,136,049 rows, 33 boroughs/authorities**; by `location`: Highways 542,900, Parks 293,096, Other 275,786,
  Housing 24,247. **Sources include all 32 boroughs, the City of London, TfL, The Royal Parks (48,545 trees),
  Queen Elizabeth Olympic Park and Wembley Park** (src: dataset page; measured). **The Royal Parks ARE included**
  (contrary to "royal parks not in borough data"): in the area 15,586 trees belong to The Royal Parks.
  **Incomplete boroughs:** Kensington & Chelsea has only 4,433 trees in total, Hammersmith & Fulham 9,351,
  Croydon 1,209, Havering 2,062, the City of London 1,623 (so the City's numbers are thin), and "three boroughs
  could not provide complete location data" (src: dataset page).
- **In the area (box above): 134,467 trees**: Southwark 34,010, Westminster 26,750, Tower Hamlets 20,717,
  Lambeth 9,587, Greenwich 8,959, Wandsworth 7,337, Lewisham 7,204, Newham 5,715, Camden 4,657, Islington 3,389,
  Kensington & Chelsea 2,379, City of London 1,623, Hammersmith & Fulham 1,269, Hackney 828. By maintainer:
  Southwark 33,021, Tower Hamlets 19,972, **The Royal Parks 15,586**, Westminster 14,816, Lambeth 9,128,
  Wandsworth 7,384, Lewisham 7,115, Newham 5,706, Greenwich 5,637, **TfL 4,238**, Camden 3,967.
- **Tower Hamlets, Westminster and City tree data:** all three boroughs' trees are inside this dataset (Tower
  Hamlets 28,026 total, Westminster 34,089, City of London 1,623); I did not look for the boroughs' own portals.
- **Caveats (measured):** heights are class values ("3 m", "6 m", "10 m" ...) not measurements; 10–12 % of rows have no
  size; the ownership is mixed (TfL highways, housing estates, schools ("Other")).
- **OSM:** `natural=tree` has **66,282 nodes in the area** (only 33,676 with a species/genus tag, of which
  *Platanus × hispanica* 4,639, sycamore 1,570, Norway maple 1,562, ash 1,547, wild cherry 1,428, small-leaf lime
  1,330) and **315 `natural=tree_row` ways** (measured): useful for parks but the Datastore CSV is the source for
  streets. `demos/data/london/raw/dl/Borough_tree_list_2025Nov.csv` is the local copy; the stage should read it, project
  lon/lat, and place a tree per row (species via `gla_name`, height via `height_m`, crown via `canopy_m`).

### 3.2 Street-tree species (measured, area, `location = Highways`, 55,968 trees)
| Species (gla_name) | Share | Notes |
|---|---|---|
| **London plane** (*Platanus × hispanica* 14,328 + *Platanus* 7,054 in the whole area; mostly *P. × hispanica*) | **22.5 %** (12,574) | **Westminster 29 %, Camden 33 %, Southwark 25 %, Tower Hamlets 22 %, Lambeth 16 %, Greenwich 13 %, City 13 %** |
| Cherry (*Prunus*) | 10.3 % | flowering cherries, *P. avium* |
| Maple (*Acer*) | 8.9 % | Norway, field |
| Pear (*Pyrus calleryana* 'Chanticleer') | 8.3 % | Westminster 19 % |
| Lime (*Tilia*: *europaea* 5,846, *cordata* 1,860, *platyphyllos* 738) | 6.8 % | |
| Birch (*Betula*) | 6.0 % | |
| Whitebeam (*Sorbus*) | 3.5 % | |
| Ash, apple, hornbeam, alder, sweetgum, sycamore, hawthorn, ginkgo, black locust, rowan | 3.3, 2.8, 2.2, 2.0, 2.0, 1.8, 1.8, 1.5, 1.5, 1.4 % | |
Elm 0.7 %, oak 0.7 %, honey locust 0.8 %, magnolia 0.8 %, serviceberry 0.7 %. **Horse chestnut is rare on highways:
in the whole area 2,572 "Horse Chestnut" (2,090 *Aesculus hippocastanum* + *carnea* 255 + *indica* 138) and 1,348
sweet chestnut (*Castanea sativa*), 77 % in parks (Greenwich Park, Hyde Park).** Species by `location`:
- **Parks (46,780):** plane 13.6 %, lime 11.6, cherry 10.6, maple 6.8, oak 5.3, ash 4.3, birch 4.2.
- **The Royal Parks (15,586):** **lime 20.1 %, plane 15.2, oak 10.7, sweet chestnut 7.5, horse chestnut 7.2,**
  cherry 6.0, maple 4.1, hawthorn 3.3.
- **Hyde Park + Kensington Gardens (6,344 trees in the box):** lime 22 %, plane 21, oak 11, horse chestnut 8, sweet
  chestnut 6, maple 3.5; median height 10 m (p10–p90 5–20).
- **Green Park + St James's Park (1,658):** plane **49 %**, cherry 8.5, hawthorn 3.5, pear 3.5, lime 3.4; median
  height 13 m (5–25).
- **Greenwich Park (2,003):** sweet chestnut **23 %**, oak 15.6, horse chestnut 14, lime 11, cherry 4.5, hornbeam 3.2;
  median height 10 m (5–15) [the famous sweet-chestnut avenues].
- **Victoria Embankment gardens and Embankment (433):** plane **44 %**, cherry 8.5, honey locust 4.4, privet 3.2.
- **Canary Wharf (704, all Tower Hamlets):** plane 49.6 %, birch 8, maple 7, cherry 5.5, hornbeam 4, black locust 3.4;
  median height 8.5 m, canopy 2.5 m (young planting).
- **Whitehall/Parliament Sq/Westminster (996):** plane 52 %, cherry 7.5; median height 15 m (canopy 10 m).
- **Housing land (3,582):** cherry 14 %, maple 14, lime 10, ash 8.

### 3.3 Size, form, age (measured; class heights)
Heights and canopy in m (p10 / p50 / p90), stem DBH in cm; **street trees**:
| Species | n | Height | Canopy | DBH [believed] | Nearest-neighbour (same species) |
|---|---|---|---|---|---|
| **London plane** | 12,574 | 7 / **15** / 21 | 3 / **10** / 15 | 18 / 54 / 85 | 10.3 m |
| Maple | 4,956 | 4 / 9 / 15 | 1 / 5 / 10 | 8 / 27 / 51 | 11.0 m |
| Lime | 3,823 | 5 / 10 / 17 | 2 / 5 / 10 | 10 / 31 / 55 | 9.5 m |
| Cherry | 5,768 | 3 / 6 / 12 | 1 / 3 / 8 | 5 / 17 / 42 | 11.2 m |
| Pear | 4,635 | 3 / 6 / 10 | 1 / 3 / 5 | 5 / 15 / 26 | 11.0 m |
| Birch | 3,378 | 3 / 6 / 12 | 1 / 3 / 7 | 5 / 13 / 28 | 10.0 m |
| Whitebeam | 2,715 | 3.5 / 7 / 12 | 1 / 4 / 7 | 6 / 18 / 39 | |
| Plane, in parks (n 6,364) | | 10 / **20** / 29 | 4.5 / **15** / 20 | 30 / 75 / 126 | |
All street trees: height p5/25/50/75/90/99 = **3 / 5 / 8.6 / 14 / 18 / 24 m**; canopy 0.8 / 2.5 / **4.5** / 8 / 12 / 18 m;
DBH p10/50/90/99 = 6 / 24 / 64 / 104 cm. Planes by age class (median height/canopy): Young 8 m/5 m; Early mature
12 m/8 m; Mature **15 m/10 m**; Over mature (81–150 yr) **19 m/14 m**; Veteran 20 m/15 m. Street age mix:
Young 19 %, Early mature 8 %, Mature 19 %, Over mature 1.4 %, not provided 48 %.
**Nearest-neighbour spacing (all highway trees, measured): p10/25/50/75/90 = 2.8 / 5.4 / 8.6 / 12.2 / 17.5 m**;
London street trees are sparser than Paris's (NN median 6.3 m) and of smaller species. **Density:** 55,968 street
trees on ~1,650 km of centre-line roads (primary to unclassified, OSM) = **34 trees per km of street**, against
Paris's ~59 (derived; the dataset is thin in Kensington & Chelsea, Wandsworth, Hammersmith and the City).
London plane crown (old, mature) **12–20 m wide and 20–30 m tall in the parks**; street planes are
**pollarded or crown-lifted** in the West End [believed].

### 3.4 Early-October foliage
- **London planes** ("yellow-brown" in autumn, Woodland Trust) stay green into October: olive with brown-yellow tips
  on 10 Oct, most leaves drop November to December; hanging fruit balls (src search summaries).
- **Horse chestnut leaf miner** (*Cameraria ohridella*, in the UK since 2002; three broods June–September) browns the
  leaves from August: by early October most horse chestnuts are brown and thin (src: RHS, Woodland Trust via
  search). Horse chestnut is 1.9 % of the trees in the area (2,572; Greenwich Park 14 %, Hyde Park 8 %): tint **#8a6a3a–#9a7a44**,
  thinned 40–70 %. **Sweet chestnut** turns yellow-gold in late October [believed].
- **Cherries, birches, maples** colour first (yellow, orange, red: "hues of saffron, rust and crimson from late
  September, peaking mid to late October"; src London guides via search); **limes** yellow from late September;
  oaks stay green-brown until November [believed].
- On 10 October the London canopy is ~70–75 % green [believed]; give cherry, birch and maple 30–40 % yellow/orange
  crowns, chestnut 50 % brown, plane 10 % yellowing.
- **Foliage tones sampled** (summer photos, so not October): St James's Park canopy seen from above mid **#5e7562**
  (p25 #3f5441, p90 #789195, `whitehall_from_eye.jpg`); aerial Isle of Dogs green patches **#54564a** (shaded);
  the suggested October albedos: plane **#6a7038** green-olive, chestnut **#8a6a3a**, lime **#7d8040**, maple/cherry
  **#a8752e** orange-brown, birch **#8a8a3c**, oak **#5d6a34**, conifer **#2f4a36** [believed].

### 3.5 Parks and other planting
- **Royal parks in the area** (The Royal Parks, in the dataset): **Hyde Park (142 ha) and Kensington Gardens (111 ha)**
  [Wikipedia, believed], **Green Park (19 ha), St James's Park (23 ha)**, **Greenwich Park (74 ha)**, Battersea Park is
  Wandsworth's (not Royal), Victoria Embankment Gardens (Westminster). Hyde Park: lime and plane avenues, oaks,
  the Serpentine (lake); Green Park: open meadow grass with mature planes (49 %) and **no flower beds**; St James's:
  the lake with **pelicans**, plane-dominated; **Greenwich Park: sloping lawns, the sweet-chestnut avenues, Observatory
  hill at the top (Royal Observatory, Wren's Flamsteed House, red time ball)**.
- **Lawns:** London grass in October: mid-green with dry patches after the summer; use `ground.lawn` of the existing
  preset lightly warmed (#475741–#6a7a4a [believed]). Paths: **gravel #b8a98a–#c9bb9f (golden hoggin)** in the royal
  parks, tarmac paths in Hyde Park [believed].
- **Squares:** London's **garden squares** (Bedford, Russell, Belgrave, Berkeley, Finsbury...): railed, plane- and
  lime-planted, private or key-holder; **railings** (black cast iron, 1.0–1.8 m) line squares and terraces
  (OSM `barrier=fence/railing`).
- **Street planting pits** and "New Tree Pit" (1,229 OSM tree nodes are tagged "New Tree Pit") show
  sites awaiting trees; tree pits with cast-iron grilles in the West End [believed].
- **Open-space polygons in OSM (area, ways):** `leisure=garden` 7,130 (houses' private gardens included),
  `pitch` 1,080, `playground` 706, `park` 650, `nature_reserve` 22 (measured).

### 3.6 Preset: Paris now → London needs
| Table | Paris now | London |
|---|---|---|
| `[trees.street] default` | broadleaf (plane, chestnut, lime, sophora) | broadleaf: **plane 22.5 %, cherry 10, maple 9, pear 8, lime 7, birch 6, whitebeam 3.5**, ash/hornbeam/alder/sweetgum 10, other 24 (Westminster 29 % plane, Camden 33 %); or **place the real inventory trees** (134,467 in the area, lat/lon, species, height, canopy) |
| `step` | 7.5 m | **8.6 m** (NN median; p25 5.4) on streets with trees; 10 m for planes on boulevards (Embankment NN 10.3 m) |
| `row_offset` | 1.0 m | 1.0 m (tree pits at the kerb; Embankment planes 1.5 m) |
| `[trees.street.planted]` | major 0.7, minor 0.45 | major **0.3**, minor **0.25** (34 trees per km of street against 59 in Paris; concentrated in Westminster, Southwark, Camden) [derived] |
| `[trees.street.height]` | broadleaf major [10,20] minor [7,15] | major **[9, 18]**, minor **[5, 12]**; planes [12, 22]; flowering cherry/pear/birch [4, 8] |
| `[trees.street.odds]` flowering | none (Paris October) | cherry/pear/birch/whitebeam 36 % as smaller "flowering"/ornamental class (they are the small, autumn-coloured trees) |
| `[trees.green]` park classes | plane 25, lime 15, chestnut 12, maple 10, oak 8 | **Hyde Park/Kensington Gardens: lime 22, plane 21, oak 11, horse chestnut 8, sweet chestnut 6**; Green/St James's: plane 49 (open meadow); **Greenwich Park: sweet chestnut 23, oak 15.6, horse chestnut 14, lime 11**; generic park: plane 14, lime 12, cherry 11, maple 7, oak 5, ash 4, birch 4 |
| `trees.classes` tints (October) | planes green, chestnut brown | plane olive-green (10 % yellow), **horse chestnut brown (50 %)**, cherry/birch/maple yellow-orange (30–40 %), lime yellow-green |
| Royal Parks source | | **use the Royal Parks rows of the same CSV** (15,586 in the area) and OSM park polygons for grass |

---

## 4. Rooftops

### 4.1 What the open data says about roofs (measured)
London has **no Paris-style roof inventory** (APUR's `c_forme_toit`/`c_toiture_mat`). What exists:
- **OSM `roof:shape`** on about 12,000 of 118,298 building ways (10 %): **gabled 6,484 (54.1 %), flat 2,825 (23.6 %),
  hipped 1,364 (11.4 %), gambrel 351 (2.9 %), double_saltbox 256 (2.1 %), skillion 188 (1.6 %), pyramidal 162
  (1.4 %), quadruple_saltbox 126 (1.1 %), mansard 98 (0.8 %)**, round 39, many 34, half-hipped 17, dome 6 (butterfly 2).
  The tagged set is biased to mapped terraces (Georgian "gabled" is the parallel-pitch terrace roof). Overture
  `roof_shape`: 90.3 % null, gabled 5.3, flat 2.2, hipped 1.2 (measured, 128,651 buildings).
- **OSM `roof:material`** (about 2,100 tagged): roof_tiles 781 + tiles 740 + tile 70 (**tile 76 %**), **slate 382 (18 %)**,
  concrete 83, metal 41, tar_paper 38, glass 24, asphalt 13. **`roof:colour`** (about 6,200): **grey 2,916, black 1,470,
  darkgrey 1,275** (89 %), lightgrey 158, brown 140, white 23, silver 17, red 3; `roof:levels=1` on 5,686 buildings
  and `=0` on 2,535 (attics: half the terraces have a loft).
- **Carbon & Place heights** (`height_max` = roof apex or plant maximum from 1–2 m lidar): the roof is about **+2 m
  above the eaves** of an ordinary house; tall and post-2021 towers are missing or low (src: README of the local cut).
- **Sampled roof tones** (photographs, §4.3).

### 4.2 Roof forms, stacks, dormers, parapets
- **Georgian and Regency terraces (1714–1830, built as 3–4-storey houses with basements):** a **parapet** at the
  top of the brick front hides a **slate roof behind**, pitched front-to-back in **paired pitches with a central
  valley gutter ("butterfly" or M-roof)**, so from the street there is no visible slope, only the parapet line
  (Bedford Sq, Cowley St photos); on the terrace sides the roofs slope back; ridges run front to back [believed;
  photo check: `georgian_cowley_st.jpg`: flat parapet line, stacks with pots above].
- **Mansards.** London's "mansard" is **not Paris's zinc attic**: a **slate-hung roof storey behind a parapet at
  60–70° (lower slope 2–3 m high), one dormer per bay**, added to Georgian terraces from the 1850s and on
  Victorian/Edwardian frontages (Russell Square photo: four dormers with pediments, slate hung at ~70°, stock brick
  below `roofs_russell.jpg`). OSM `roof:shape=mansard` is only 98 ways, so read **`building:levels` + `roof:levels=1`
  and brick + a parapet** to infer them [believed]. Belgravia's stucco terraces and Mayfair mansions often have a
  **grey slate mansard with lead-roll dormers and a balustrade** (Belgrave Sq photo: slate #8e918e sunlit, #7a7369 shade).
- **Victorian terraces (1837–1901):** a simple pitched roof, **slate (Welsh, blue-grey to purple-grey)**, pitch ~30–35°,
  ridge running parallel to the street on standard plots and **front-to-back on two-up-two-down**; a "closet wing" or
  back addition with a lower roof [believed]; **chimney stacks on the party walls** (shared between houses, in
  pairs) **1.5–2.5 m above the ridge, 0.9–1.2 m wide, of stock brick, carrying 4–8 round terracotta pots each**
  (`roofs_russell.jpg`: stacks of 6–8 pots; Ada Road photo: stacks at the ridge every two houses). Count: about 1
  stack per house on average for a terrace (one per party wall serving the pair) [believed].
- **Edwardian mansion blocks and terraces (1890–1914):** **steep clay plain-tile roofs** (red-brown), **gables** and
  Flemish gables, tall decorative brick stacks, dormers, **turrets on corners** (Cheyne Walk photo: red brick with
  a white gabled top, tiles red, stacks) [believed].
- **Civic and classical:** **flat lead roofs and skylights behind balustrades** (Whitehall from above: light
  grey membranes/lead `#969993`, plant boxes), slate pavilion roofs with lantern domes; **domes**: St Paul's (lead,
  grey), Old Royal Naval College (blue-grey lead with a gilt ball, Greenwich), Queen's House low roof behind a
  balustrade; the Houses of Parliament's slate roofs and spires with cast-iron crestings [believed].
- **Post-war estates:** flat or shallow-pitched roofs with parapets, lift and stair bulkheads (Churchill Gardens,
  Barbican: concrete towers with flat roofs and plant), tar-and-gravel or bitumen membrane.
- **Offices and towers (City, Canary Wharf, Bankside, Nine Elms):** flat roofs with **plant enclosures**,
  louvred boxes, lift overruns, **window-cleaning cradles (BMU)**, cooling towers; crowned tops on Canary Wharf
  (One Canada Square's pyramid with the aircraft warning light, HSBC/Citi towers), helipad-free. **Roof terraces and
  gardens:** Sky Garden (20 Fenchurch), the Shard View, Battersea Power Station's roof garden, rooftop bars [believed].
- **Green roofs:** London has the most in the UK; **no inventory here** [believed a few %, mostly offices and
  estates]. **PV:** estates, schools; ~1 % of roofs [believed]. **Satellite dishes and TV aerials** on every terrace
  roof; **no wooden water tanks** (no NYC tanks).
- **Skylights:** loft conversions add roof lights and rear dormers; ~1 per 6 m of frontage on renovated terraces [believed].

### 4.3 Roof colours sampled from photographs
Method as in §5.4 (PIL on 960 px Commons thumbnails, sky excluded, mean, mid 40–90 % lightness median, p25/p50/p90).
There is **no London orthophoto** here (Paris's IGN imagery has no free equivalent reachable; Environment Agency
and Bluesky imagery are blocked or licensed), so these are oblique and street-level photographs.
| Surface | Where | Mean | Mid (40–90 %) | p25 / p50 / p90 |
|---|---|---|---|---|
| **Slate roof, shaded** (Scotland Yard, Whitehall from the London Eye) | `whitehall_from_eye`, (0.30,0.68,0.50,0.76) | #4a4a48 | **#4d4e4b** | #2c3436 / #454440 / #787c7b |
| Slate roofs, left block | same (0.05,0.60,0.20,0.66) | #4a5052 | #4a5155 | #32393f / #3d484e / #7c8081 |
| **Slate mansard with dormers** (Russell Sq, sunlit and shaded slopes) | `roofs_russell` (0.62,0.22,0.86,0.36) | #636361 | **#776f69** | #303642 / #59524a / #b7b8bc |
| Mansard slate, Belgravia (stucco mansion, sunlit) | `stucco_belgrave` (0.25,0.05,0.75,0.17) | #8e918e | #a1a5a1 | #7a7369 / #92958a / #cfd2c9 |
| Flat lead/membrane and plant (Treasury/FCO roofs) | `whitehall_from_eye` (0.42,0.36,0.60,0.41) | #858b86 | **#969993** | #626868 / #88857c / #c5cfce |
| City offices, plant roofs (street-level view from above) | `roofs_city` | #636064 | #7e7a80 | #2c2d32 / #6e6266 / #aca9b0 |
| City roofs aerial, sunlit mix | `aerial_lhr_05` (0.05,0.22,0.35,0.35) | #9e9f9f | #b6b5b3 | #797a7e / #9e9ba4 / #dce1db |
| Low City roofs, aerial shade | `aerial_city_1024` | #8b888c | #979395 | #676b77 / #847e8c / #c5c7c2 |
| Terrace/estate roofs, Isle of Dogs (aerial, distant) | `aerial_lhr_03` (0.35,0.75,0.60,0.88) | #877e74 | #9d9184 | #65584f / #867c73 / #ccbfb6 |
| Red-brown clay tile (Edwardian) | not sampled [believed] | | ~#a0583f | |
So **London's roofs from above read grey-brown to dark slate-blue**: slate **#4a5155 (shade) to #776f69 (mid)** with
sunlit slopes to **#a1a5a1 / #b7b8bc**; flat roofs **#969993 light, #3a3a3a bitumen, #8f8d84 gravel**; red tile
accents on Edwardian blocks; **chimney brick #8a7a62 (stock) and pots #a5563a terracotta**. Paris's zinc-blue-grey
(#909699) is lighter and bluer; London reads darker and warmer-grey. Photo tones, not albedo.

### 4.4 Flat roofs, plant rooms and towers
- **City cluster and Canary Wharf:** glass towers with flat roofs, mechanical floors at the top (2–3 floors of
  louvres), crowns (Shard spire, Gherkin's glass dome, the Cheesegrater's slope), cooling plant, aircraft warning
  lights. Cooling towers ~80 % of towers [believed]. **Canary Wharf** dockside blocks: flat roofs with plant and
  roof terraces.
- **Post-war** slabs and towers (Barbican, estates): flat roofs with parapets, bulkheads; 15–20 % of the estate
  stock has shallow pitched roofs [believed].
- **Warehouses (Butlers Wharf, Wapping):** shallow slate or flat roofs behind brick parapets, with **loading-crane
  hoods ("taking-in hoists")** and metal catwalks/bridges between warehouses (Shad Thames footbridges, 2005 and 2013
  photos). **Converted power stations** (Battersea: four 103 m chimneys, brick, with a roof garden between; Bankside/
  Tate Modern: brick chimney 99 m, glass "light beam" roof strip).

### 4.5 Rooftop programme by building kind (share of roofs; [believed] unless noted)
| Kind | Stacks | Pots | Dormers | Mansard | Flat/parapet | Terrace/plant |
|---|---|---|---|---|---|---|
| Georgian terrace (parapet) | **90 %**, 1–2 per house | 4–6 | 20 % (mansard storeys) | 35 % | parapet 90 % | rear terraces, rooflights |
| Regency stucco (Belgravia) | 80 % | 4–6 | 30 % | 50 % | balustrade 60 % | roof terraces 15 % |
| Victorian terrace | **85 %**, party-wall stacks | 4–8 | 25 % (loft) | 5 % | 0–10 % | rear outrigger |
| Edwardian mansion block | 95 %, tall | 6–12 | 50 % | 10 % | 10 % | roof plant 20 % |
| Civic/institution | 60 % | | | | flat lead 60 % | plant 60 % |
| Post-war estate | 10 % (boiler) | | | | **85 % flat** | bulkheads 80 % |
| Office/tower | | | | | 95 % flat | **plant 100 %**, BMU 40 % |
| Warehouse | 40 % | | | | flat/low pitch 70 % | crane hood 30 % |

### 4.6 Preset: Paris now → London needs
| Table | Paris now | London |
|---|---|---|
| `europe_west/rooftops.py PROGRAMME` | `haussmann` (zinc mansard with brisis, dormers, chimney stack rows, terracotta pots), `faubourg`, `hbm`, `postwar`, `tower`, `civic` | new **`georgian`** (parapet + hidden M-roof, stack pairs on party walls, optional slate mansard behind), **`victorian`** (pitched slate roof, party-wall stacks with 4–8 pots, closet wing), **`edwardian`** (steep tile roof, gables, tall stacks), `estate` (flat, bulkheads), `tower` (plant room + BMU + crown), `civic` (lead flat roofs, domes, lanterns), **`warehouse`** (shallow slate/flat, hoist hoods) |
| `[rooftops.named]` | `zinc` #909699, `zinc_sun` #b1b6b8, `zinc_shade` #676c70, `slate` #4f5966, `tile_red` #a86f5a, `lead` #7b7f83, `chimney_brick` #8b5a45, `pot` #a5563a | **`slate` #4d4e4b (shade) / `slate_mid` #776f69 / `slate_sun` #a1a5a1**; **`tile_red` #a0583f**; `lead` #7b7f83; **`membrane` #969993**; `bitumen` #3a3a3a; `gravel` #8f8d84; **`chimney_stock` #8a7a62 (yellow-brown) and `chimney_sooty` #6d6253**; `pot` #a5563a; drop `zinc*` |
| `[rooftops.parapet_t]` | pitched roofs none | **Georgian terraces: parapet 0.25 m**, pitched Victorian none, post-war 0.25 |
| Roof shapes | APUR `c_forme_toit` → mansard/flat/gabled | **OSM `roof:shape` where present (gabled 54 %, flat 24 %, hipped 11 %)**, else by kind: Georgian = flat parapet (hidden pitched), Victorian = gabled ridge parallel to the street (or across on narrow plots), Edwardian = hipped/gabled tile, mansard for `roof:levels≥1` + Mayfair/Belgravia conservation areas, flat otherwise |
| Chimney stacks per building | 2–5 | **terrace: 1 per house (shared pairs), 4–8 pots; mansion block 3–5 stacks** |
| Satellite dishes / aerials | | add on Victorian terraces (40 %) |
| Solar | PV 1 % | PV 1–2 % (estates, schools) |
| Green / roof gardens | green 10 % modern | Sky Garden, Battersea PS and estate roofs as landmarks; else 5 % of modern offices |

---

## 5. Facades by building type

### 5.1 The types (with shares measured from OSM + Overture + the lidar heights, and the fields that tell them apart)
**Fields in the area (measured):** OSM building ways **118,298** (+ ~2,300 multipolygon relations) in the area box:
`building=house` **43,343 (36.6 %)**, `yes` 37,596 (31.8 %), `residential` 12,227 (10.3 %), `apartments` 10,661
(9.0 %), `commercial` 2,287 (1.9 %), `retail` 2,130 (1.8 %), **`terrace` 2,048 (1.7 %)**, `office` 1,176 (1.0 %),
`garages` 788, `service` 724, `school` 596, `semidetached_house` 530, `garage` 475, `industrial` 468, `roof` 402,
`university` 353, `church` 326, `shed` 224, `hotel` 169, `hospital` 132, `train_station` 120, `houseboat` 114,
`warehouse` 97. **`building:levels`** on 50,032 (42 %): 2 levels 14,346, 3 levels 14,338, 4 levels 11,010, 5: 4,354,
1: 2,124, 6: 1,351, 7: 636, 8: 425, 9: 251, 10+ about 900. **`start_date`** on only about 560 buildings (0.5 %):
useless for dating. `building:material` (9.6k): **brick 7,958 (83 %)**, plaster 934, stone 404, glass 111, concrete 88,
sandstone 32, limestone 21. `building:colour` (about 6,000): **brown 2,495, white 1,737, gray 485, light_brown 443,
grey 402, lightgrey 134, red 105, black 75, yellow 55**, hex tones e.g. #dfd8bf, #9D8C71, #b8a088, #e0c78d, #D3BE78
(stock brick/stucco variants), #B52222 (50 red). `building:architecture` only ~130 (baroque 27, neo-gothic 18,
brutalism 13, modernism 13, gothic revival 9, victorian 9, classicism 8, palladian 5, georgian 3, art deco 4).
`heritage=*` on 681 buildings, `historic=building` 89.
Overture (128,651 buildings in the core box): class house 36.3 %, none 33.4 %, residential 9.8 %, apartments 9.0 %,
commercial 1.8 %, retail 1.7 %, terrace 1.7 %, office 0.9 %; **`height` from OSM on 14.7 %**, `num_floors` on 41 %.

**Terraced or not (measured, shared-wall test: footprints sharing > 1.5 m of boundary with a neighbour, Overture
core box, 128,651 buildings):** **59 % of all buildings are "terrace-like" (two or more party walls), 22 % have one
(semi/end-of-terrace), 19 % are detached.** `house` (43,384): **97 % attached, 72 % mid-terrace**, median footprint
**56 m²** (p25 46, p75 70), median 2 levels and **8.8 m** (lidar max); `terrace` class 65 % attached, median
footprint **406 m²** (a whole row); `residential` 88 % attached; `apartments` 59 % attached, median 345 m², 4 levels,
16.5–17.5 m; `commercial` 19.5 m, `office` 23.0 m (median lidar heights); `retail` 13.6 m, 92 % attached. So in this
centre **OSM `building=house` means a terraced house in a row, not a detached house**: the Paris `house → house`
mapping in `[buildings.osm_kind]` is wrong for London (it would paint every terrace as a detached villa).
Footprints 25–200 m² with ≥ 2 party walls number 60,527 (**50 % of all buildings**), median 61 m², 3 levels, 10.5 m.
**Heights (Carbon & Place lidar `height_max`, 267,082 polygons in the area):** p25 7.9, **median 10.5**, p75 15.2, p90 21.0,
p99 38.1 m; **2.3 % ≥ 30 m, 0.5 % ≥ 50 m, 0.07 % ≥ 100 m**.

**Calibration of floor heights (measured, Overture/OSM `num_floors` vs lidar `height_max`, 50,003 matched buildings):**
| OSM levels | n | lidar height (median, m) | per level (m) |
|---|---|---|---|
| 1 | 2,030 | 6.8 | 6.8 (sheds, garages with a roof) |
| 2 | 14,240 | **8.2** | 4.1 |
| 3 | 14,489 | **12.1** | 4.0 |
| 4 | 11,252 | **16.5** | 4.1 |
| 5 | 4,393 | **20.8** | 4.2 |
| 6 | 1,369 | 23.7 | 3.95 |
| 7 | 624 | 26.85 | 3.8 |
| 8 | 415 | 29.7 | 3.7 |
| 10 | 167 | 33.9 | 3.4 |
| 12–14 | 83 / 48 | 41 / 46.9 | 3.4 |
Reading: **lidar height ≈ 3.2 m × levels + 2 m for the roof ridge** for residential (2 levels 8.2 = 6.4 + 1.8), so
the eaves are at about `0.8 × lidar_height`; for blocks above 6 levels, roofs are flat and the floor-to-floor is
3.3–3.7 m. By class: house 3.9 m/level, terrace 4.5, apartments 3.7, residential 4.4, retail 4.2, commercial 4.6,
office 4.7, university 5.25, school 5.1, hotel 4.75, hospital 5.1 (tall institutional floors). `level_h` for the
engine: **3.2 (houses, blocks ≤ 6 levels), 3.4 above 6 levels, 4.0–4.2 for offices** [derived].

| Style (proposed engine name) | Share of buildings (derived) | Height / levels | Ground + upper floor-to-floor | Roof | Windows and details |
|---|---|---|---|---|---|
| **Georgian terrace** `georgian` (1714–1830) | ~8 % of buildings, ~3 % of area [believed: Bloomsbury, Marylebone, Mayfair, Belgravia, Pimlico, Kennington, Greenwich, Southwark] | 4–5 storeys incl. basement, **11–14 m** to parapet | ground **3.3–3.5**; **piano nobile (1st) 4.0–4.5**; 2nd 3.3; 3rd 3.0; attic 2.4–2.7 | parapet, hidden slate M-roof, often slate mansard | **tall 6-over-6 sash windows** (1.0–1.2 × 1.8–2.3 m, tallest on the 1st floor), shallow reveals, **iron balcony and railings**, **lightwell and area railings**, stucco ground floor with rustication, **fanlight and panelled door** (black or dark green, white or black door surround); plot width 5.5–6.5 m (7 m in squares) |
| **Regency stucco terrace** `regency` (1800–1840) | ~3 % | 4–5 storeys, 13–16 m | as Georgian, ground 3.5 | balustrade, slate mansard | **white/cream stucco over the entire facade**, **pilasters and porticos**, projecting cornices, balconies; Belgravia, Pimlico, Regent's Park terraces |
| **Victorian terrace** `victorian` (1837–1901) | **~35 %** of buildings [believed: most of Southwark, Lambeth, Tower Hamlets, Greenwich] | 2–3 storeys (+ basement), **8–11 m** to ridge | ground 2.9–3.2; upper 2.7–3.0 | pitched slate, ridge parallel to street, party-wall stacks | **two-storey bay windows** with slate or lead roofs, sash windows 1.0 × 1.6–2.0 m, **polychromatic brick** bands (red, yellow), arched lintels, stone or terracotta keystones, **porch**, front garden 2–4 m with low wall and railings; plot 4.5–6 m |
| **Edwardian mansion block / terrace** `edwardian` (1890–1914) | ~4 % | **5–8 storeys, 18–28 m** | 3.0–3.3 | steep clay tile, gables, tall stacks | **red brick with Portland stone bands**, terracotta dressings, **bay windows stacked**, balconies, arched entrances, Flemish gables; Victoria St, Cheyne Walk, Kensington, Marylebone |
| **Portland-stone institutional** `portland` (1700–1930) | ~2 % (Whitehall, Bank, Strand, Somerset House, ORNC, St Paul's, museums) | 4–7 storeys, **18–35 m** | 4.5–6 (piano nobile 6+) | lead/slate, balustrades, domes | classical orders, **rusticated base**, round-arched windows, pediments, colonnades |
| **Victorian Gothic and stone palaces** `gothic` | <0.5 % | 4–6 storeys + spires | 5+ | slate + spires | Parliament (limestone), St Pancras, Law Courts, Natural History Museum |
| **Post-war estates** `estate` (1945–1980) | **~8 %** of buildings, more of the area | 4–20 storeys, **12–60 m** | 2.7–3.0 | flat with parapet | **buff/yellow brick slabs with balcony decks** (Churchill Gardens, Dolphin Square), precast concrete panel towers, **Barbican: bush-hammered concrete ridges**; window bands, walkways |
| **Modern glass (City, Canary Wharf, Bankside, Nine Elms)** `glass` (1985–today) | 1.5 % of buildings, but **the skyline** | **50–300 m** (108 buildings ≥ 50 m) | **3.9–4.2** offices, 3.0–3.3 flats | flat, crowned | full curtain wall, fins, bands; dark glass `#2e3744`, blue-green `#7c818c–#afb8c0` (sampled); stainless steel and granite at Canary Wharf |
| **Modern residential (2000+)** `modern` | ~8 % | 6–40 storeys | 3.0–3.2 | flat | render, terracotta, metal panels, glass balconies (Wapping: curved balconies, glass), 8–40 storeys |
| **Warehouses and converted docks** `warehouse` (1800–1900) | ~1 % (Butlers Wharf, Shad Thames, Wapping, Tobacco Dock, Bermondsey) | 5–7 storeys, **20–30 m** | 3.3–4.0 | low slate/flat, hoist hoods | **brown London stock brick (sooted)**, iron loading balconies, arched and segmental-headed openings, hoist doors, cast-iron catwalks; Shad Thames lane is **10 m** facade to facade |
| **Converted power stations and industry** `industrial` | <1 % | 20–50 m | 6–8 | flat; chimneys 99–103 m | Battersea PS (dark brick, glazed roof garden, four white-grey chimneys), Bankside/Tate (brown brick, 99 m chimney) |
| **Shops and pubs at ground** `shopfront` | ground floors of 4.7 % commercial | 3.5–4.5 m | | | fascia signs, awnings, stallrisers, pubs with tiled and ornate fronts |
| Civic, schools, churches | 1.5 % (school 596, university 353, church 326, hospital 132, station 120, castle 49) | 12–40 m | 4–6 | slate/lead | brick Victorian board schools (red), Gothic churches in stone/flint |

### 5.2 Palettes (hex; sampled on Commons photos, pulled toward albedo where noted)
| Style | Wall colours | Photo samples (mid 40–90 %, p25 / p50 / p90) |
|---|---|---|
| **London stock brick (Georgian, Victorian)** | clean yellow `#c4b08a`, `#b89f74`, `#b5a07c`, `#a8957a`; grey-brown sooted `#9c8a72`, `#8a7c68`, `#70675b`; dark black-grey soot `#5a544a`; Georgian red brick (Queen Anne) `#a0583f`, `#9c5f42`; brick dressings `#c9a68a` | **Cowley St (Westminster) mid #a48e77, p25 #6f5944, p50 #807e6f, p90 #dcc8ad**; **Ada Rd (Southwark) mid #b89f74, p50 #a88766**, p25 #8b6759; Russell Sq (shade) mid #5f584a / stock + red dressings sunlit #907568 (p50 #7f6250, p90 #b49382); wiki: "air pollution... turning the bricks greyish or even black" (London stock brick) |
| **Georgian / Regency stucco (white, cream)** | white `#d8d3cb`, cream `#d9cfb5`, pale buff `#c9bfa3`, painted pastels (Pimlico: pink `#d9b8aa`, blue-grey `#a9b4b8`, cream) [believed] | **Belgravia mid #d8d3cb, p25 #d3ccc2, p50 #d9d3c5, p90 #dfddce** |
| **Victorian polychrome** | yellow brick `#b89f74` with red bands `#9c5f42` and cream `#d0c4a8` dressings | Ada Rd p90 #edeac7 (window frames), mid #b89f74 |
| **Edwardian red brick + stone** | red `#be7e54` lit, `#9c5f42` mid, `#622b24` shade; stone `#cdbca3`; terracotta `#b9684a` | **Cheyne Walk mansion block mid #be7e54, p50 #9c5f42, p25 #622b24, p90 #f49464 (sunlit orange)** |
| **Portland stone (sunlit, overcast, sooted)** | sunlit `#cdbca3`, overcast `#b2ac9d`, weathered `#a59984`, sooty `#7d705e`, black crust `#594c44` | **Old War Office (sun) mid #cdbca3, p90 #e3dbc6**; **FCO (overcast) mid #b2ac9d, p50 #88806d**; **Bank of England (soot) mid #7d705e, p25 #594c44**; ORNC Greenwich mid #aa9a93 (p90 #e6d0bb) |
| **Parliament (Anston-type limestone)** | honey-sand `#d3c0a6`, sunlit gold `#c9b48e`, shade `#8a7b64`, soot | Palace of Westminster sunlit mid **#d3c0a6**, p50 #bd9a74, p25 #5f595b |
| **Post-war estates** | buff/yellow brick `#a8a19c`–`#ac8b68`, concrete `#c8c5bd`, brown-red brick `#8a4a44`, dark window bands `#2b3038` | Churchill Gardens slab mid **#a8a19c**, p50 #ac8b68; low block mid #aea199; Barbican concrete mid **#baa994**, p50 #a3927e, p25 #57422f (stained) |
| **Modern glass** | dark `#2e3744`, blue-grey `#585e6f`, teal `#5d7d8c`, silver `#afb8c0`, green-grey `#6c7f86`; stainless `#c5cfce` | Canary Wharf dark tower **#2e3744** (p25 #121a25); blue tower mid #afb8c0 (p90 #f1f2f7); Whitehall roofs show Treasury stone p90 #c5cfce |
| **Warehouses, docklands** | brown stock `#b89f78`, `#a0825c`, dark soot `#474842`; iron black `#1c1c1e` | **Butlers Wharf mid #b89f78, p50 #a0825c, p25 #474842, p90 #d4bd9d** |
| **Power stations and Victorian industry** | dark red-brown `#7a4a3a` lit (shade sample Battersea mid #4a4243, p90 #554d4b; **brick reads very dark in shade**); Tate brown-black brick mid #3b3a35 (p90 #41686f with glass) | |
| Ironwork/details | railings and balconies black `#1c1c1e`; doors black, dark green `#2c3d33`, navy, red `#8a2a2a`; sash windows white `#e8e6de`, black-brown frames; shopfronts dark green/black/cream/burgundy | |
| Roofs | §4.3 | |

### 5.3 Classification rules from the data (proposal for M2 `building_kind()` / M4 `facade_styles()`)
**Which open data can tell these types apart (what it contains, verified in this session):**
| Source | What it gives | Limits |
|---|---|---|
| **OSM building tags** | `building` (house/terrace/apartments/commercial/retail/office/industrial/warehouse/school/church), `building:levels` (42 %), `roof:shape` (10 %), `building:material` (8 %, brick 83 %), `building:colour` (5 %), `start_date` (0.5 %), `building:architecture` (0.1 %), `heritage` (0.6 %), `name`, `historic=*` | `start_date` is almost empty: **no construction date** in open data for London |
| **Shared-wall adjacency (computed from footprints)** | terrace vs semi vs detached (59 / 22 / 19 %), plot width/depth, run length | footprint splitting depends on the mapper; OSM's 'house' is near-fully attached here |
| **Carbon & Place heights** (`height_max`, ODC-By, 2 m DSM − DTM) | roof apex height for 97 % of OSM buildings (measured: 97.8 % matched); +2 m over eaves | older than the newest towers (Wood Wharf, 8 Bishopsgate etc. low) |
| **Historic England listed buildings** (planning.data.gov.uk `listed-building`, **382,270 points**, OGL v3; CSV 90 MB: `https://files.planning.data.gov.uk/dataset/listed-building.csv`, also GeoJSON and parquet; updated 2026-09-30) | **9,067 in the area: Grade I 390, II* 748, II 7,846**; `name` text (e.g. "TERRACE" 165, "CHURCH" 467, "BRIDGE" 161, "STATION" 108, "WAREHOUSE" 42, "MANSION" 15, "statue" 125, lamps 315, railings/walls 1,144, gates 509, phone/post boxes 185); `listed-building-grade`, `start-date` (= listing date, **not** build date) | a point, not a footprint: match to the footprint under or within ~15 m; one entry may cover a terrace or a lamp standard |
| **Conservation areas** (planning.data.gov.uk `conservation-area`, **9,696 polygons**, OGL v3; GeoJSON 65 MB) | **317 intersect the area, covering 44.4 km² (42 %) of the 106 km² box**; names carry the period: Bloomsbury, Belgravia, Pimlico, Mayfair, Marylebone (Harley St, Portman Estate, East Marylebone), Soho, St James's, Covent Garden, Whitehall, Westminster Abbey and Parliament Sq, Regent Street, Strand, Barbican and Golden Lane, Churchill Gardens, Dolphin Square, Lillington Gardens, Hallfield, Boundary Estate, Peabody Estates, Wapping Pierhead, Wapping Wall, West India Dock, St Saviours Dock, Tooley St, Bermondsey St, Narrow St, Albert Embankment, Millbank, Kennington, Stockwell Park, Roupell St, Lower Marsh... | no dates in the dataset; ~40 % of the area uncovered |
| **Overture `class`/`num_floors`/`roof_shape`** | same OSM tags with hierarchy, 9 % Microsoft ML footprints (no heights) | |
| **OS OpenMap Local `ImportantBuilding`** | polygon type for institutions (FEATCODE) | no height |
| Not open / blocked | construction dates (Colouring London/Britain: click-through 7.9 GB, no geometry), EA 1 m lidar (403 from here), EPC age bands (registration), VOA property ages | |

**Decision order (first match wins) for London's `building_kind()`:**
1. **Landmark/named** (`landmarks_london.csv`, 127 rows) → its own style.
2. **Tower** `height ≥ 50 m` (OSM `height`, else lidar `height_max`, or `building:levels ≥ 14`) → `glass` (Canary Wharf, City, Nine Elms, Bankside) or `estate_tower` if the footprint is in an estate conservation area (Barbican, Churchill Gardens, Balfron Tower).
3. **Civic/institution:** OSM civic list (church, cathedral, school, university, hospital, station, townhall, castle, museum) or a Grade I/II* listed point inside the footprint with a civic word in the name → `portland`/`gothic` by district (Whitehall, Strand, the City → `portland`; Parliament, St Pancras → `gothic`).
4. **Warehouse/industrial:** `building=warehouse|industrial|service`, or a `historic=*` building in **Wapping Pierhead, Wapping Wall, St Saviours Dock, Tooley St, Bermondsey St, West India Dock** conservation areas with brick and height 15–32 m → `warehouse`; power stations and breweries from the landmark list.
5. **Terrace:** `building=house|terrace|residential` with ≥ 2 shared walls, footprint 25–120 m², levels 2–5 (or lidar 8–16 m):
   - **`georgian`/`regency`** inside the conservation areas **Bloomsbury, Belgravia, Pimlico, Mayfair, Marylebone (Harley St, Portman, East Marylebone), Fitzroy Sq, Soho, St James's, Covent Garden, Kennington, Stockwell Park, Roupell St, Greenwich (Gloucester Circus), Trinity Church Sq, Smith Sq, Vincent Sq, Whitehall** [believed mapping], or with a listed `TERRACE`/`SQUARE`/`CRESCENT` point in the name; stucco where `building:colour=white` or the conservation area is Belgravia/Pimlico/Regent St (Regency);
   - otherwise **`victorian`** (Southwark, Lambeth, Tower Hamlets, Greenwich: 35 % of buildings).
6. **Mansion block:** `building=apartments|residential`, 5–8 levels (lidar 18–30 m), footprint 500–2,000 m², attached ≥ 1, brick, in Westminster, Kensington, Marylebone, Pimlico, Victoria → `edwardian`.
7. **Estate:** `building=apartments`, 4–16 levels, footprint ≥ 300 m², in or next to the estate conservation areas (Churchill Gardens, Dolphin Square, Barbican and Golden Lane, Lillington Gardens, Hallfield, Boundary Estate, Peabody Estates, Latchmere, Pullens) or `building:architecture=brutalism|modernism` → `estate`.
8. **Modern residential/offices:** flats/office of any other height; `glass` when lidar ≥ 30 m and footprint ≥ 500 m² in the City/Canary Wharf/Nine Elms/Bankside/Greenwich Peninsula, else `modern`.
9. **Shops and pubs:** `retail|commercial|pub` ground floors → `shopfront` over the row style.
10. Remaining untagged (`yes`, 32 %) inherit the neighbour by the same grid cell rule as Paris (`neighbours 150 m`).

### 5.4 Colour sampling method
- **Photos:** Wikimedia Commons 960 px thumbnails (`action=query&prop=imageinfo&iiurlwidth=960`), polite User-Agent, 2 s
  pause, 46 photos; each was viewed on a 5 × 5 fraction grid before boxes were chosen; boxes over plain wall/roof
  (windows and shadows remain, so **use the mid 40–90 % lightness median**, not the mean); sky pixels dropped
  where `b > r + 25 and b > g + 8`; white/black clipping excluded. Script `lr/samp.py` in the session scratchpad.
- **Trust:** exposure and sun angle dominate. The Cowley Street and Ada Road brick values come from two frames
  each; several "p90" values are window frames and sky-lit stucco. Night boxes did not land on lit surfaces
  (sky blue mid #526a9d), so **no night colour is sampled**; night tones are read by eye from the photos (§6).
- Commons file licences (CC BY, CC BY-SA, OGL for the FCO photo, public domain for one) are in the index at the end.

### 5.5 Preset: Paris now → London needs
| Table | Paris now | London |
|---|---|---|
| `[buildings.kinds]` | haussmann, faubourg, interwar, hbm, postwar, modern, tower, house, civic, factory, shed (APUR fields) | **georgian, regency, victorian, edwardian, portland, gothic, estate, modern, glass, warehouse, industrial, shopfront, civic, shed**, tower; **no APUR**: kinds from §5.3 using OSM tags, shared-wall adjacency, lidar height, Historic England points and conservation areas |
| `[buildings.osm_kind]` | house/detached/semi/villa/bungalow/**terrace → house** | **`house`/`terrace` → `victorian`/`georgian` (terraced), `detached`/`semidetached_house` → `house` (rare: 81 and 530 ways)**; `warehouse`/`industrial` → `warehouse`; `apartments` → by §5.3 rules; school/church/hospital → `civic` (keep) |
| `[buildings] tower_h` | 50 m | 50 m (108 buildings ≥ 50 m in the area); `tower_form_h` drop |
| `[buildings] reconcile` | OSM height vs APUR | **Carbon & Place `height_max` joins by spatial join** (97.8 % of OSM buildings; `osm_id` is only 0.45 % filled): eaves = 0.8 × `height_max` for pitched/parapet roofs; towers: landmark list and OSM `height` (12 of the 82 landmarks ≥ 100 m are missing or low in the lidar epoch) |
| `level_h` | 3.3 / 3.0 / 2.9 by period | **3.2 (≤ 6 levels), 3.4 (> 6), offices 4.0–4.2**; Georgian piano nobile 4.2 m |
| `[facade.styles.*]` | haussmann (3.3 limestone), faubourg (3.0), house (2.9), limestone, concretepanel, brickstone, hbm, postwar, modern, glass, civic, factory, shed, plain, spire + landmark styles | **`georgian` (floor 3.3, palette stock brick `#c4b08a #b89f74 #b5a07c #a8957a #9c8a72 #8a7c68 #70675b`), `regency` (floor 3.5, stucco `#d8d3cb #d9cfb5 #c9bfa3`), `victorian` (2.9; stock `#b89f74 #a88766 #9c8a72` + red `#9c5f42`), `edwardian` (3.1; red `#be7e54 #9c5f42` + stone `#cdbca3`), `portland` (4.8; `#cdbca3 #b2ac9d #a59984 #7d705e`), `gothic` (5.0; `#d3c0a6 #c9b48e`), `estate` (2.8; `#a8a19c #ac8b68 #c8c5bd #8a4a44`), `warehouse` (3.6; `#b89f78 #a0825c #8a7a62 #474842`)**; keep `glass` (dark `#2e3744 #585e6f #7c818c #afb8c0`), `modern`, `civic`, `shed`, `plain`, `spire`; **remove** haussmann, faubourg, hbm, interwar |
| `[facade.osm_style]` | factory = industrial...; modern = retail... | factory → `warehouse` for brick, `industrial` for sheds; retail → `shopfront` |
| Balconies / details | continuous wrought-iron balconies on floors 2 and 5 | **Georgian: iron balcony (juliet) on the 1st floor, area railings and basement lightwell; Victorian: two-storey bays, porch; Edwardian: stacked bays and balconies** |
| Ground floor | shops 4–5 m with awnings, porte cochère | **doors up steps** over a basement lightwell (terraces), **shopfronts with fascia** (high streets), pubs |
| `facade.acUnits` | 0.03–0.15 | 0.03 (terraces), 0.15 (modern), 0.1 (glass): UK homes seldom have AC [believed] |
| `facade.refugeShare` | 0 | 0 |

---

## 6. Night

### 6.1 Street lighting (src: council pages and press via search; no London-wide inventory was found)
Unlike Paris (165,581 lamps as open data) **no borough publishes a lamp inventory that I could find**; OSM has only
**3,100 `highway=street_lamp` nodes** in the area (`lamp_type`: led/LED 325, "electric" 264, SON (high-pressure sodium)
139, gaslight 8, high_pressure_sodium 8; `support=pole` 170) against an estimated ~40,000 real lights [believed]:
use the OSM nodes only for special lamps (gas, dolphin), not for the street grid. What is sourced:
- **City of Westminster** (src: *Lighting Design Guide*, news via search): **3,000 K LED is the "Westminster standard"**;
  heritage lanterns **2,200–2,700 K** "to match gas"; **~14,000 street lights**, of which **about 300 are gas**;
  **6,500 heritage lanterns are being retrofitted with 3,000 K dimmable LED, 80 % of them the "Grey Wornum" type**;
  the council halted a plan to convert 174 gas lamps (138 Grade II listed) in Nov 2022 and will convert only **94 non-listed
  gas lamps** to "honey"-glow LED with replica mantles; heritage groups asked for < 2,500 K (src: ianvisits, ITV,
  Energy Live News via search). London has > 1,000 gas lamps overall (Covent Garden, the Temples, Westminster,
  Mayfair) [src search summary].
- **City of London Corporation** (src: DW Windsor case study, City Matters via search): **all street lights were
  converted to LED** and run through a Central Management System ("Urban Master"; a £4 M lighting strategy, 2018;
  carbon/energy cut by at least 50 %); **CCT 4,000 K on main highways, 3,000 K on minor roads, 2,700 K for places of
  interest and heritage lighting**; the 2023 Lighting SPD recommends a **3,000 K limit** for new lighting.
- **Other boroughs:** Greenwich: all 20,000 lights to LED (programme 2021, src); Lambeth: a programme converting
  8,500 of 15,000 units (57 %); the GLA counts five boroughs fully LED by 2024 and the last (Ealing) by 2035
  (src: London Assembly via search). **Area LED share [believed] ~80–90 %** (the City and Westminster high; a
  remainder of high-pressure sodium 2,000 K orange on older borough streets, less than Paris's 8 % sodium).
  Sodium is now a minority: use `ground.sodium` arterial 0.04, street 0.03.
- **Heritage types and pole heights** [believed unless noted]: **Westminster "Grey Wornum" lantern on a cast-iron
  column (1950s, ~5–6 m)**; Victorian **dolphin lamp standards** (Victoria Embankment, 1870: cast-iron column with
  intertwined dolphins, fluted shaft, opaque glass globe crown, on a granite plinth, ~4.5–5 m; Timothy Butler and
  George Vulliamy) (src: Wikipedia via search: "Two stylised dolphins ... supporting a fluted column bearing electric
  lights in an opaque white globe"); **gas lamps ~4 m** with a ladder bar and flickering mantle (Covent Garden, Savoy,
  Temples); modern **steel columns 6–10 m** with cobra-head LED luminaires on arterials, spacing **25–35 m**;
  **wall-mounted fixtures** in narrow lanes; **bollard lights** in squares and estates.
- **Emissive colours** (blackbody approximations as in Paris's file): LED 4,000 K main roads in the City
  **#ffd6a8**; LED 3,000 K **#ffc48a**; heritage LED 2,700 K **#ffb872**; 2,200 K **#ffa653**; high-pressure sodium
  2,000 K **#ffa040**; gas lamp ~1,900–2,000 K **#ff9a3a** with flicker.
- **Sky glow / Bortle:** London is Bortle class 8–9 (central city) [believed]; horizon warm grey-orange
  `#5a4638` fading to `#1a1f33`; the LED conversion has reduced the orange cast compared with sodium days [believed];
  `night.skyGlow` [0.05, 0.043, 0.04] linear (between Paris's neutral and warm) [believed].

### 6.2 Curfews and schedules
- London has **no national-style shop-window curfew** like France's 01:00 rule; **shops, offices and theatres stay lit
  late** (West End theatres until ~23:00; offices leave lights on, which is why the City glows) [believed].
  Landmark floodlights generally run **dusk to about 02:00–midnight** [believed]; the Greenwich meridian laser
  is **on each evening after the Observatory closes until 23:00**, most visible on winter evenings (src: RMG
  via search). The "Illuminated River" artwork (Leo Villareal, 15 bridges from Lambeth to Tower Bridge, LED, 2019–)
  runs dusk to ~2am [src: Signify press 2018 via search; hours believed].
- 10 October: sunset 18:19 BST, civil dusk 18:52, astronomical dusk 20:10: evening rush hour (17:00–19:00) is in
  twilight, **lamps on before 18:30** (photocell), fully lit streets by 19:00.
- **Night preset** (`city.json night.schedule`): `feature` curve reaches ~1.0 by **19:00 BST** (not Paris's 19:45);
  offices 55 % at 20:00 and 40 % at 23:00, landmarks 100 % until 23:30 [believed].

### 6.3 Monuments and landmarks (src unless marked)
- **Houses of Parliament:** warm golden floodlight on the Anston-type limestone (photo `night_parliament.jpg`: the
  palace reads orange-gold), river-front uplights; **Elizabeth Tower clock faces: 228 luminaires, over 55,000 LED
  chips, "a mixture of green and white lights creating a familiar yellow glow"**; the **Ayrton Light** above the
  clock is lit whenever Parliament sits (LED); the Victoria Tower is uplit. **Westminster Bridge: the arch soffits
  glow green** (photo: bright teal-green arches) plus white globes on the piers.
- **Tower Bridge:** 2012 colour-changing LED system by Citelum/GE (src: GE press, london-se1): **2 km of LED linear
  lights, almost 1,000 projectors, 1,000 junction boxes, 5,000 m of cable, 40 % less energy**; normally white/warm white
  on the towers and cool white on the suspension chains, colour shows on events; the upper walkway is lit.
- **St Paul's Cathedral:** floodlit since the 1980s (warm white); the City Corporation is replacing the 1980s
  floodlights with LED for a "warm wash of light" (src: City Matters / options appraisal); sampled photo tones of the lit
  west front: cool-neutral mid #93a6b3 (sky-lit) [dusk photo; low trust].
- **Shard:** the spire carries **LED "Shard Lights" (white/colour shows)**, the glass facade reads as a pale
  pyramid; aircraft warning red/white on the tip [believed; the-shard.com page returned nothing useful].
- **Canary Wharf:** One Canada Square's pyramid has a **white flashing aviation light**; towers' floors lit cool white
  (4,000 K) in a grid; the Crossrail Place roof garden and the Jubilee Park have warm bulbs [believed].
- **Battersea Power Station:** lit brick and the four chimneys (white/grey, lit from below), glass atrium, riverside
  Christmas-style lights [believed].
- **Others** [believed]: Nelson's Column and the National Gallery floodlit warm; **Piccadilly Circus "Piccadilly
  Lights"** (an LED screen of ~790 m², Landsec 2017; inside the area); Leicester Square screens; Covent Garden
  piazza fairy lights; the **London Eye** (LED-lit capsules, colour schemes, white default), the **O2** (yellow
  masts lit, white dome), **BT Tower** (LED ring, off-white), the **Royal Observatory green laser** (continuous
  green beam, 0° meridian, north), Cutty Sark and the Royal Naval College floodlit warm, HMS Belfast lit (white),
  Tower of London walls lit warm. **Christmas lighting** (Regent St, Oxford St) starts in November: not on 10 Oct.
- **Windows:** terraces warm 2,700–3,000 K `#ffb870–#ffd9a0` with 10 % TV blue `#b8d0ff`; shop windows brighter, whiter
  (`#ffe2b0–#fff1d8`); **offices cool white 4,000 K `#e9f1ff–#fff3dc`, about 50–60 % of floors lit at 20:00**,
  fewer after 22:00; **pub windows amber**; buses' interiors white-yellow; black cabs' TX roof sign yellow when vacant.
- **Boats:** Thames Clippers/Uber Boat and tourist boats lit white with coloured deck lights; HMS Belfast in the
  Pool of London; barges with small running lights (red port, green starboard, white stern) [believed].
- **Water at night:** the Thames reflects the lamps as long gold streaks (photos), near-black body `#0b1418`; the river
  reads dark blue-brown, **not green**.

### 6.4 Preset: Paris now → London needs
| Table | Paris now | London |
|---|---|---|
| `ground.sodium` | arterial 0.10, street 0.06 | arterial **0.04**, street **0.03** (LED share 80–90 %) |
| Lamp colour/warmth | warm LED 3,000 K dominant, 2,200 K quays, sodium minority | **LED 3,000 K `#ffc48a` Westminster standard; City main roads 4,000 K `#ffd6a8`; heritage LED 2,700 K `#ffb872`; gas lamps 2,000 K `#ff9a3a` in Westminster/Covent Garden/Temples; sodium ~3 %** |
| Pole height / spacing | 7 m, spacing 20–25 m staggered | **6–10 m steel columns, spacing 25–35 m**, post-top 4–5 m in squares, Grey Wornum 5–6 m in Westminster, **dolphin lamps ~4.5 m at 20–30 m spacing along Victoria/Albert/Chelsea Embankment** |
| Times Square signs | none | **Piccadilly Lights screen** (790 m², inside) and Leicester Sq screens; billboards.js on in Piccadilly/Shaftesbury only |
| Landmarks | Eiffel gold + sparkle, monuments | **Parliament gold, Elizabeth Tower clock green-white, Tower Bridge white + colour events, St Paul's warm white, Shard LED spire, Canary Wharf flashing pyramid light, London Eye colours, Westminster Bridge green arches, Greenwich green laser north**; `floodlit`/`crowned` styles |
| Office lights | Paris 50 % at 20:00, 25 % at 23:00 | City/Canary Wharf **55 % at 20:00, 40 % at 23:00** (UK offices leave lights on; no 1 h rule) [believed] |
| Curfew | monuments off 22:00, Eiffel 23:45 | **no curfew**: landmarks lit dusk to late (Meridian laser off at 23:00) |
| `night.schedule feature` | ~1.0 by 19:45 | **~1.0 by 19:00 BST** |

---

## 7. Water

### 7.1 The tidal Thames
- **Tide (src, PLA Tide Booklet 2026 via search snippet; Wikipedia "Tideway"; tidetimes.org.uk):** the tide rises and
  falls twice a day by **up to 7 m**; at **London Bridge (Tower Pier)** the PLA booklet lists (m above chart datum)
  mean sea level **3.2**, MLWS **0.5**, MLWN **1.5**, MHWN **5.9**, MHWS **7.1**, highest astronomical **7.6**
  [my reading of a single-line search snippet "3.20 0.5 1.5 5.9 7.1 7.6"; the labels are inferred]. So **mean spring
  range 6.6 m, mean neap range 4.4 m**. A tidetimes.org.uk day showed HW 6.86 and 7.18 m, LW 0.88 and 0.76 m. The rise
  takes 4–5 h, the fall 6–9 h; high water at Putney is ~30 min after London Bridge. **Chart datum ≈ 3.2 m below mean
  sea level**, i.e. ~ −3.2 mODN [believed]; so MHWS is about +3.9 mODN and MLWS −2.7 mODN.
  **10 Oct 2026 is a new moon [believed], so spring tides ~11–12 Oct**: HW about 7 m CD, LW about 0.5 m CD (range
  ~6.5–7 m). Time the viewer's tide by the clock: HW London Bridge ~ 05:00 and 17:30 BST on those days [believed; the
  `water` model should take a tide phase].
- **Width:** bridge lengths (Wikipedia, [believed]): Westminster Bridge 252 m, London Bridge 269 m, Tower Bridge
  244 m, Blackfriars 281 m, Vauxhall 250 m; so the river is **about 250–300 m wide through Westminster and the City**,
  wider downstream. **Measured from OS OpenMap Local (tidal water + foreshore union), width across the flow (PCA of the
  polygon):** Battersea PS **239 m**, Vauxhall **279 m**, Millennium Br 248 m, Wapping/Rotherhithe **357 m**, Limehouse
  Reach (Canary Wharf) **345 m**, Greenwich/Isle of Dogs 368 m, Blackwall Reach/O2 **454 m**, Cutty Sark 318 m. **Central
  London values (Westminster 126, Waterloo 142, London Bridge 121, Tower Br 132 m) came out too small and contradict
  the bridge lengths: the polygons or my transects there are wrong; I do not trust them.**
- **Area and foreshore (measured, OS OpenMap Local `TidalWater` + `Foreshore`, OGL):** river (water + foreshore union)
  **7.04 km²** in the area box, **foreshore (intertidal mud/shingle) 1.20 km² = 17 %** (116 polygons). At low water
  the foreshore is exposed along both banks: shingle/"beaches" under the embankment walls (Bankside, Oxo,
  Greenwich, Wapping) and mud; "there is a window of about two hours either side of low tide" to walk on it (src:
  thetidalthames/mudlarking pages via search). OSM has `natural=mud` and tidal wetland on only ~40 ways: **use the OS
  Foreshore polygons** (already in `demos/data/london/raw/os_openmap_local/TQ_Foreshore.shp`), not the OSM
  `mudflat` tag list.
- **Colour** (sampled, photographs): **Limehouse Reach from the air #877b62 (tan-olive-brown), sunlit Albert
  Embankment #664f31 (mid; brown), under a blue sky at Canary Wharf #6d665b, Bankside under cloud #5b6271 (sky
  reflection), Westminster in low sun #8b8a96, aerial Tower reach #696a71, Shadwell reach #61605f**; foreshore mud/
  shingle mid **#786f69–#877b6f** (photo). So the Thames is **brown-tan when lit and turbid, grey-blue when it
  mirrors cloud**: a **base albedo ~`#5d5446`** with strong Fresnel; **not** Paris's dark green (#3b4a41). The water is
  turbid (visibility ~0.2 m) [believed]. **Current:** flood tide flows upstream, ebb downstream at 1–2.5 m/s
  [believed].
- **Dock water (Canary Wharf, Millwall, Limehouse Basin):** impounded, **not tidal**, level constant; West India
  Docks: North Dock "30 acres (120,000 m²)" and Middle/Export Dock 24 acres (97,000 m²), connected by locks at
  Blackwall and Limehouse Basins; "buildings built out over the water", the Canary Wharf station inside the Middle
  Dock (src: Wikipedia West India Docks). **Sampled dock water from the air: #585e6f (mid), darker #4a4e59** — blue-grey
  dark, calm (little wave action). Regent's Canal (Limehouse Basin, Mile End) is at the north-east edge: OSM has 77
  `waterway=canal`, 36 `waterway=dock`, 23 `lock_gate`, 32 `weir`, 56 `river` ways in the area.

### 7.2 Embankments, walls, piers, boats
- **Embankment walls (src: Wikipedia/victorianlondon via search):** **Victoria Embankment (1865–70, Bazalgette)**,
  Albert Embankment (1866–69) and Chelsea Embankment (1871–74) are **granite-faced walls on Portland-cement concrete
  foundations "32.5 ft below high water"**, a **moulded granite parapet 3 ft 6 in (1.07 m) high**, the roadway "4 ft
  above high water, rising to 20 ft at the extremities" (so the road is 1–1.2 m above the spring high tide at the
  Embankment; the river wall face 5–7 m high at low water). **Granite river stairs**, **dolphin lamp standards every
  20–30 m**, plane trees (44 % plane in the Embankment box, §3.2), **Cleopatra's Needle (1878)**, bronze sphinxes.
  Sampled photo tones: granite kerb `#989690–#a2a5a3` (sunlit `#b5b7b5`); the Albert Embankment parapet and footway
  read grey-brown in the photo (`albert_emb_view.jpg`, not sampled).
- **Other banks:** Bankside/South Bank promenade (concrete, Queen's Walk), **Butlers Wharf and Wapping: brick
  warehouse wharf walls**, Canary Wharf quay walls, Greenwich: the brick river wall under the ORNC with a beach and
  the **Cutty Sark (64.6 m, in a dry dock, glass skirt)** [believed]. **Piers:** OSM `man_made=pier` **390 ways**
  (many are landing stages), floating pontoons with gangways that rise 7 m with the tide (Westminster, Embankment,
  London Eye, Tower, Greenwich, Canary Wharf piers); `man_made=bridge` 392, `embankment` 20, `groyne` 11.
- **Boats:** **HMS Belfast** (187 m × 19 m, grey, moored in the Pool of London by Tower Bridge) [believed];
  **Uber Boat by Thames Clippers** (fast catamarans ~35–40 m, navy/blue-white) and tourist cruisers (white, glass
  canopies, 25–40 m) [believed]; cargo/refuse **lighters and barges** (brown/grey, 40–60 m) and tugs; houseboats/
  working boats (114 OSM `houseboat` buildings, `ship` 34); rowing skiffs; the IFS Cloud Cable Car (Greenwich
  Peninsula ↔ Royal Docks, towers 60 m, in the landmark list).
- **Bridges (in the area), west to east** [believed]: Albert, Battersea (west edge), Chelsea, Vauxhall (1906, nine
  steel arches), Lambeth (red, matching the House of Lords' benches), Westminster (green,
  matching the Commons' benches), Hungerford/Golden Jubilee, Waterloo, Blackfriars (road + rail), Millennium (steel foot bridge),
  Southwark, Cannon Street rail, London Bridge, **Tower Bridge** (1894; two 65 m towers, bascule span 61 m; dark blue
  steel with white and blue painting [believed]), then the Greenwich Foot Tunnel, the Rotherhithe/Blackwall tunnels
  (no surface) and the **Emirates/IFS cable car** at the east end.
- **No wind waves**: the Thames has chop from wind (fetch 300 m) and boat wakes; `water.windFrom 225` (SW) fits
  London's prevailing wind [believed].

### 7.3 Preset: Paris now → London needs
| Table | Paris now | London |
|---|---|---|
| `[shores] coast_type` | quay (Seine's stone quays, inland) | **`quay` for the Embankments/Thames walls, `tidal` for the river**: granite wall face 5–7 m at low water, stairs and pontoons |
| `mudflat*` | (none: inland) | **add `mudflat` from the OS Foreshore polygons** (1.2 km² in the area); OSM `natural=mud` is only ~40 ways; `mudflat_min_area` 500 m² |
| `city.json water.sea` / `coast` | unused, `coast=false` | `coast=false`; **a tide model** (range 4.4–6.6 m; HW ~05:00/17:30 BST) raising the river surface 7 m over 6 h; foreshore and pier gangways follow |
| `water.inland.river` | `[0.03, 0.042, 0.034]` linear (#3b4a41 green) | **brown-tan `[0.11, 0.095, 0.072]` linear (≈ #5d5446)**; strong sky reflection; in low sun lighter `#877b62`; docks **blue-grey `[0.085, 0.10, 0.125]` (≈ #585e6f)** |
| Rooftop boats | péniches (38.5 × 5 m) at the lower quays | **HMS Belfast (187 × 19 m), Clippers (~38 × 9 m) and tourist cruisers at floating piers; barges (45 × 7 m) and tugs midstream; houseboats at Chelsea/Wapping** |
| Bridges | | landmark list has the big ones; **Westminster green, Lambeth red, Vauxhall arches, Tower Bridge blue-white**; `night`: Illuminated River on the 15 bridges |

---

## 8. Sun and season

Location **51.5074° N, 0.1278° W** (Charing Cross; the area's centre ~51.50, −0.10 differs by less than 1 min),
time zone **BST (UTC+1)**; British Summer Time ends **Sun 25 Oct 2026** (clocks back), so 10 October is still BST. Computed
with the NOAA/Meeus solar algorithm in my script `lr/sun.py` (same algorithm as Paris's; refraction −0.833° for
sunrise/sunset; civil/nautical/astronomical at −6/−12/−18°).

| Date (2026) | Declination | EoT | Solar noon (BST) | Noon alt. | Sunrise | Sunset | Civil dusk | Nautical | Astronomical |
|---|---|---|---|---|---|---|---|---|---|
| Oct 5 | −4.83° | +11.6 min | 12:49 | 33.7° | 07:08 | 18:30 | 19:03 | 19:42 | 20:21 |
| **Oct 10** | **−6.74°** | **+13.0 min** | **12:48** | **31.75°** | **07:16** | **18:19** | **18:52** | 19:31 | 20:10 |
| Oct 12 | −7.49° | +13.5 min | 12:47 | 31.0° | 07:20 | 18:14 | 18:48 | 19:26 | 20:05 |

Sun on 10 Oct (altitude / azimuth from north, clockwise): 09:00 BST 14.3° / 120.9°; 10:00 21.6° / 134.5°; 11:00 27.4° /
149.6°; 12:00 30.9° / 166.2°; **13:00 31.7° / 183.6°**; 14:00 29.7° / 200.8°; **15:00 25.2° / 216.8°**; 15:15 ~23.5° /
~220°; **16:15 (Paris's start) 16.8° / 234.7°**; 17:00 10.7° / 244.4°; 18:00 1.9° / 256.5°; 19:00 −7.3° / 268.2°;
20:00 −16.6° / 280.1°; **21:30 −29.8° / 299.8°** (dark). Day length **11 h 02 min**. The sun sets at azimuth ~259° (WSW).
Greenwich and Battersea differ by < 1 min (noon 12:47 and 12:48).

**What to set in London's `city.json`** (derived from Paris's): `location 51.5074, -0.1278`; `sun.date "10-10"`;
`time.utcOffset 1`, `zone "BST"` (**not** CET/GMT); `time.start` **15.25** (15:15 BST, sun 23.5°, about Paris's 24.6°, an equally warm low-angle
afternoon look: 16.25 would give 16.8°, too low and orange); `presets.Day 15.25`; `Dusk: null` (computed from sunset 18:19);
`Night` **21.5** (sun −29.8°, deeper than Paris's −23.5°; astronomical dark since 20:10). `city.toml [sun] latitude 51.51,
declination −6.7`. **Sun azimuth path is nearly identical in shape to Paris's, but everything is ~53 min earlier in clock time**.
Climate context [believed]: mean October afternoon ~15 °C, cloud cover ~65–70 %, rain in ~15 days of the month, wind ~4–5 m/s from the
SW–W; Thames haze brown-grey: **overcast diffuse light is the London norm**, the clear low-sun look is a fair-weather day.

---

## 9. Driving side
**LEFT-hand traffic**, right-hand-drive vehicles (driver on the right), overtake on the right, **roundabouts clockwise**,
give way to the right on roundabouts; buses and taxis stop at the **left kerb**, bus lanes are on the nearside (left)
with contraflow lanes also on the left in the direction of the bus; cyclists on the left; **right turns cross
oncoming traffic**; no turn on red (a green arrow filters; no "right on red" concept). Parking is allowed either side
in one-way streets, but **not against the flow at night** (parked facing the direction of traffic) [believed].
Pedestrians look right first ("LOOK RIGHT" legend at tourist crossings). Bus doors (3 on the New Routemaster) are on the
left; the rear platform is on the left rear. Emergency vehicles (blue lights, sirens) and the usual two-way shapes are unchanged.
**Engine consequence:** flip the lane offset, turn geometry, bus/taxi stop side, parked-car orientation and cycle
lane side; **the engine has no `drive_side` setting** [not checked in the code]: this is an engine change, not just a preset
(see `.agents/skills/build-3d-city/references/porting-checklist.md` "Driving side").

---

## What I could not verify
1. **Tide constants:** the PLA booklet PDF (403 from here; the URL is `https://pla.co.uk/sites/default/files/2025-12/PLA-Tide-Booklet-2026.pdf`) was
   read only as a search snippet ("3.20 0.5 1.5 5.9 7.1 7.6"): the labels (MSL, MLWS, MLWN, MHWN, MHWS, HAT) and the chart-datum offset are my reading;
   the new moon on 10 Oct 2026 is from memory.
2. **River width in central London** (Westminster → Tower Bridge): my OS polygon transects gave 120–170 m against bridge lengths of 244–281 m; I quote
   bridge lengths [believed] and only the widths downstream of Limehouse.
3. **Hex of TfL red**, LEVC TX roof-light behaviour, TX door layout, the Enviro400 and Wrightbus dimensions, UK car dimensions (from memory of Wikipedia pages,
   not fetched), Santander bike livery and count source (search snippet), Lime/other hire bike colours, bus fleet double-deck share.
4. **Stop line, STOP and junction give-way widths/dash (TSRGD 1001/1002/1003A)**, zig-zag width, the pelican/puffin studs: not read (chapter 6 tables were only partly read).
5. **Whether TfL's bike tracks still use blue Cycle Superhighway paint**, which bus lanes are red (no dataset; the two photos show red on one road and plain asphalt on another).
6. **Street lighting:** no inventory; LED share in the area (80–90 %) is an estimate from three boroughs; Westminster's "14,000" and "300 gas" come from press snippets;
   the Shard's external lighting, Canary Wharf's warning light colours, Battersea's lighting and the Piccadilly Lights area are not sourced; no night photo colours were sampled.
7. **Street-tree data completeness:** Kensington & Chelsea (4,433 total), Hammersmith & Fulham (9,351), the City (1,623) look thin; `girth_dbh` meaning (DBH vs girth) uncertain;
   I did not look for borough-own tree portals (Tower Hamlets, Westminster).
8. **Construction dates:** none open (OSM `start_date` 0.5 %, Colouring London blocked by a click-through); the style shares in §5.1 are my estimates
   (marked [believed]) built from tags, adjacency and conservation areas, not counts of Georgian/Victorian/Edwardian buildings; the conservation-area → period mapping
   (§5.3) is my knowledge of London, not a dataset.
9. **Roof colours** are from oblique or street-level photographs, not orthophotos; clay tile colour not sampled; chimney and pot counts are typical values.
10. **Kerbside parking shares and car ownership** (Census 2021) are estimates; OSM parking tags cover 13 % of streets.
11. **Pavement widths** by class are my estimate from TfL/City guidance and the measured gaps; no London pavement-width dataset was read.
12. **Whether `city3d` needs engine changes** (left-hand traffic, double-deck bus type, bike units, tides, dolphin lamps, Belisha beacons, zig-zags): I read the preset and the
    porting checklist only, not the viewer code.

---

## Sources
- **DfT Traffic Signs Manual**, chapter 3 (regulatory signs: waiting restrictions §13, bus lanes §9, red routes §16), chapter 5 (road markings: tables 2-1, 2-2, 2-3, 2-5, box junctions §8, colours §12.5),
  chapter 6 (pedestrian crossings §15–§22): https://assets.publishing.service.gov.uk/media/5c78f895e5274a0ebfec719b/traffic-signs-manual-chapter-03.pdf ;
  https://assets.publishing.service.gov.uk/media/5c4ace6ded915d38a0611abc/traffic-signs-manual-chapter-05.pdf ; https://tsrgd.co.uk/pdf/tsm/tsm-chapter-06.pdf
- **City of London Public Realm Technical Manual (2016)** (York stone 600 mm, granite kerbs 300 × 200 × 900, setts 300 × 150): https://www.cityoflondon.gov.uk/assets/Services-Environment/public-realm-technical-manual-2016.pdf ;
  **City Streets 2025 Summary Report** (cycle share 39 %/56 %): https://www.cityoflondon.gov.uk/assets/Services-Environment/City-Streets-2025-Summary-Report.pdf
- **DfT road traffic statistics** (AADF by region, `dft_aadf_region_id_6.csv`): https://roadtraffic.dft.gov.uk/ ; storage.googleapis.com/dft-statistics/road-traffic/downloads/aadf/region_id/dft_aadf_region_id_6.csv
- **London Datastore "London Public Realm Trees"** (OGL v3): https://data.london.gov.uk/dataset/local-authority-maintained-trees/ ; **Historic England listed buildings and conservation areas**
  (OGL v3): https://www.planning.data.gov.uk/dataset/listed-building ; https://files.planning.data.gov.uk/dataset/listed-building.csv ; https://files.planning.data.gov.uk/dataset/conservation-area.geojson
- **Carbon & Place (Univ. of Leeds) Building Heights**: local cut `demos/data/london/raw/carbon_place/` (ODC-By 1.0; README there); **Overture Maps buildings** 2026-09-23.1 (ODbL); **OS OpenMap Local** (OS OpenData) TidalWater/Foreshore;
  **OSM** (BBBike London extract 2026-09-26, ODbL).
- **TfL / GLA:** Bus fleet audit 31 March 2025 (8,797 buses; via search, PDF 403); taxi and PHV numbers (London Assembly answers, Feb 2025); Santander Cycles (visitlondon, Santander press); LEVC
  (levc.com); Wikipedia "LEVC TX" (4,857 × 1,874 × 1,888 mm), "New Routemaster" (11.23 × 2.52 × 4.39 m), "London stock brick", "Tideway", "West India Docks", "Dolphin lamp standard".
- **SMMT** colours 2025/2024 (https://www.smmt.co.uk/grey-in-the-fast-lane-as-green-powers-up-in-britains-top-new-car-colours/); **motcheckup.co.uk** fleet colours; UK best-sellers 2025 (carwow/SMMT via search).
- **Street lighting:** Westminster City Council lighting design guide (PDF, text not extracted); press on gas lamps (ianvisits, ITV, Energy Live News); City of London lighting (DW Windsor case study, City Matters, ukauthority);
  GLA "LED street lighting"; GE/Citelum Tower Bridge LED (GE press, london-se1); UK Parliament (Ayrton Light, Elizabeth Tower lighting); RMG "Green laser in the sky"; Signify press 2018 (Illuminated River).
- **PLA** Tide Booklet 2026 and tidetimes.org.uk (London Bridge Tower Pier); Wikipedia "Tideway".
- **Wikimedia Commons** photos (46, in `region_refs/`; licences CC BY, CC BY-SA 2.0/3.0/4.0, OGL 2 (FCO), public domain (one)); method §5.4.
- Earlier London notes: `data_sources.md`, `landmarks_london.md`, `landmarks_london.csv` (now in `demos/london/data/`).
- Scripts and scratch (not in the repo): `<scratch>/lr/` (`osmstats.py`, `widths.py`, `trees.py`, `trees2.py`,
  `hist.py`, `calib.py`, `attach.py`, `thames.py`, `samp.py`, `sun.py`, `cq.py`, `dlimg.py`, `osmstats.json`, `widths.json`).

### Image index (`demos/data/london/research/region_refs/`, 960 px JPEG thumbnails of Wikimedia Commons files)
Facades: `georgian_cowley_st` (1 Cowley Street, Westminster), `georgian_greenwich` (1 Gloucester Circus), `georgian_bedford_sq` (lamp post, brick in the corners: not useful),
`stucco_belgrave` (11a Belgrave Square), `victorian_ada_rd` (Ada Road, SE5), `mansion_cheyne` (Cheyne Walk mansion block), `portland_old_war_office`, `portland_fco`, `parliament`,
`bank_of_england`, `greenwich_orn` (Old Royal Naval College), `barbican`, `churchill_gardens`, `butlers_wharf`, `wapping` (modern riverside flats, not a warehouse), `canary_wharf`,
`bankside_tate`, `battersea_ps`. Roofs/aerials: `roofs_russell` (Russell Square mansards and stacks), `roofs_city`, `whitehall_from_eye`, `aerial_2009_a/b/c`, `aerial_2018_lcy`, `aerial_2018_iod`,
`aerial_lhr_03/05`, `aerial_city_1024`, `greenwich_qh_view`, `albert_emb_view`. Water: `thames_canary`, `thames_bigben`, `thames_bankside`, `thames_foreshore`. Night: `night_parliament`, `night_tower_bridge`,
`night_stpauls`, `dolphin_lamp`. Street: `street_bus_lane` (red lane), `street_redroute`, `street_double_yellow`, `red_double_yellow_meet`, `cab_tx`, `newroutemaster`, `santander_dock`. Commons titles, authors and
licences are in `lr/imgmeta.json` / `imgmeta2.json` (scratchpad).
