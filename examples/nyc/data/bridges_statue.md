# Brooklyn Bridge, Manhattan Bridge, Statue of Liberty: dimensions for procedural models

Conventions:
- Heights are metres above mean high water (MHW) for the bridges. For the statue they are metres above the ground at its base (Liberty Island grade).
- "(est.)" means an estimate or a value derived by me, not a published figure.
- Colour method: I searched the Wikimedia Commons API, fetched each file's thumbnail at 1280 px width, and computed PIL `ImageStat` mean and median over a box. Boxes are given as percentages of the image (x0,y0,x1,y1) plus the pixel box. "Non-sky median" means the median of the pixels in the box after removing sky pixels (B > R+40, or for tan steel keeping only R > B). The tools are `sheet.py`, `grid.py` and `sample.py` in this folder, and the images are `photos/b_*.jpg`.
- Sources:
  - Wikipedia articles "Brooklyn Bridge", "Manhattan Bridge" and "Statue of Liberty" (fetched 2026-09-28; plain-text extracts are in `raw/b/`).
  - The NPS "Statue Statistics" page (https://www.nps.gov/stli/learn/historyculture/statue-statistics.htm).
  - OSM through Overpass (2 queries; raw results are in `raw/b/osm.json` and `raw/b/osm2.json`).

## Positions (CSV-ready)

`name_zh,name_en,height_m,height_type,floors,status,year,lat,lon,source,notes,feature,use_height`

```
Brooklyn Bridge Manhattan Tower,Brooklyn Bridge Manhattan Tower,84.8,tip,,completed,1883,40.707269,-73.998334,Wikipedia Brooklyn Bridge; OSM way 1255363983,"tower top 278.25 ft = 84.81 m above MHW; OSM height 82.9; footprint 43x18 m at high water (OSM rect 42.8x16.6); 2 gothic arches 36 m tall x 10.29 m wide, arch floor 36.35 m above mean water; span 486.3 m; bridge axis bearing ~316 deg (Brooklyn->Manhattan)",structure,False
Brooklyn Bridge Brooklyn Tower,Brooklyn Bridge Brooklyn Tower,84.8,tip,,completed,1883,40.704104,-73.994354,Wikipedia Brooklyn Bridge; OSM way 317352708,"as Manhattan tower; OSM rect 42.8x16.7 m; OSM height 82.9",structure,False
Manhattan Bridge Manhattan Tower,Manhattan Bridge Manhattan Tower,106.7,tip,,completed,1909,40.708812,-73.991488,Wikipedia Manhattan Bridge; OSM way 1255353996,"cable tops 330 ft = 100.6 m above MHW; finials 350 ft = 106.7 m; OSM height 102 (colour tag #8eb4d2); OSM footprint rect 36.3x7.7 m; main span 1470 ft = 448 m (infobox says 1480 ft/451 m); bridge axis bearing ~337 deg",structure,False
Manhattan Bridge Brooklyn Tower,Manhattan Bridge Brooklyn Tower,106.7,tip,,completed,1909,40.705115,-73.989436,Wikipedia Manhattan Bridge; OSM way 317352033,"as Manhattan tower; OSM height 102",structure,False
Statue of Liberty,Statue of Liberty,93.0,tip,,completed,1886,40.689253,-74.044530,NPS Statue Statistics; Wikipedia; OSM ways 433053921 (statue 46.9-93 m) 32965412 (Fort Wood star 0-10 m) 229651145 (pedestal 23-46.9 m),"ground to torch 305 ft 1 in = 92.99 m; ground to top of pedestal 154 ft = 46.94 m; statue base-to-torch 46.05 m; heel to top of head 33.86 m",structure,False
```

Checks:
- The distance between the two Brooklyn Bridge tower points computes to about 485 m. The published main span is 486.3 m.
- The distance between the two Manhattan Bridge tower points computes to about 444 m. The published main span is 448 to 451 m.
- Every point above is the centroid of its OSM polygon, and I checked that each centroid lies inside the polygon.

---

## 1. Brooklyn Bridge (1883; John A. and Washington Roebling)

### Overall geometry
| Item | Value | Source |
|---|---|---|
| Main span (tower to tower) | 1,595.5 ft = 486.3 m | WP |
| Side spans (tower to anchorage) | 930 ft = 283.5 m each | WP |
| Total length incl. approaches | 6,016 ft = 1,834 m (Park Row to Sands St) | WP |
| Approach ramps | Manhattan 1,567 ft = 478 m; Brooklyn 971 ft = 296 m. Masonry Renaissance-style arches, infilled with brick walls with small windows | WP |
| Deck width | 85 ft = 26 m | WP |
| Navigational clearance, midspan | 127 ft = 38.7 m above MHW. Varies by ±2.7 m with temperature and load | WP |
| Stiffening trusses | 33 ft = 10 m deep, running parallel to the roadways. 4 today (6 originally, 2 removed in the late 1940s) | WP |
| Promenade | Central, pedestrian only, 5.5 m above the roadways and 3.0–5.2 m wide. It runs about 1.2 m below the truss crossbeams except around the towers, where it rises and meets balconies overhanging the roadways | WP |
| Axis bearing | about 316° (Brooklyn tower to Manhattan tower, NW) | computed from OSM |

### Towers (granite and limestone masonry, neo-Gothic)
- Height: **278.25 ft = 84.81 m above MHW** (tower top). The WP infobox says 272 ft, while the body text and the task figure say 84.3 to 84.8 m; use 84.8 m. OSM `height` is 82.9.
- Footprint at the high-water line: **140 × 59 ft = 43 × 18 m**, with the long side across the bridge. OSM polygons measure 42.8 × 16.6 m.
- Arches: **2 pointed Gothic arches per tower**, one over each roadway. Each opening is **117 ft = 35.7 m tall × 33.75 ft = 10.29 m wide**. The arch floor sits 119.25 ft = 36.35 m above mean water, which is also the roadway level where the deck passes through the tower. The arch apex is therefore about 72 m above water, and the solid masonry band above it about 12.8 m.
- Tower top is 159 ft = 48.5 m above the arch floor.
- Piers (est. from the frontal photo `b_bb_4`, scaled to the 42.8 m width): outer piers about 8.3 m and central pier about 6.8 m wide, with the arches 10.3 m wide. These add up to 42.8–44 m.
- Upper part: the piers continue as flat pilaster strips up to a heavy stepped cornice. Each pier ends in a small gabled or stepped cap. The main cables pass over saddles near the top of the piers (saddle height about 81–83 m, est.).
- The faces have a slight batter. There are no published top dimensions; taper the footprint by about 5–10 % to the top (est.).
- Below the deck, the tower is solid masonry from the waterline to the arch floor (36 m).
- Caisson and foundation are under water and do not need modelling. The Manhattan caisson is 52 × 31 m, the Brooklyn one 51 × 31 m.

### Cables
- **4 main cables**, each 15.75 in = 0.40 m in diameter (5,282 wires in 19 strands). **2 run outside the roadways, over the outer piers, and 2 run in the median, over the central pier, either side of the promenade.**
- Main-cable sag: about 39 m (est. This is the commonly cited 128 ft, which I could not verify in the fetched sources). The cable low point at midspan is roughly at the top of the trusses, about 43–49 m above MHW (est.).
- **Vertical suspenders:** 1,088, 1,096 or 1,520 in total (sources differ), 2.4 to 39.6 m long. The spacing is about 2.3 m (est.; about 7.5 ft is commonly cited, unverified).
- **Diagonal stays: 400**, 42 to 137 m long. They fan out from the tower tops down to the trusses, reaching roughly 130 m into each span on both sides of each tower (est. from the maximum stay length). Stays and suspenders cross to form the bridge's signature diamond web.
- Night: "necklace" LED lights (24 W fixtures) run along the main cables, and the towers are floodlit (56 LED lamps on the towers, per WP).

### Anchorages
- Trapezoidal limestone blocks, set slightly inland.
- Base 129 × 119 ft = **39 × 36 m**; top 117 × 104 ft = 36 × 32 m.
- Height about 27 m (est.; about 89 ft is commonly cited, unverified).

### Colours
- The stone is granite (Vinalhaven, Maine) and limestone (Clark Quarry, Essex Co., NY). In photos it reads as warm pale grey-beige.
- NYCDOT says the steel was originally painted "Brooklyn Bridge Tan" and "Silver", and today reads as tan-beige. Other accounts say "Rawlins Red".

| Surface | Hex (mean / median) | Photo, box, conditions |
|---|---|---|
| Tower stone, sunlit face | **#c8b5a7 / #d2bfb0** | [File:Brooklyn-side tower … from Brooklyn Bridge Park](https://commons.wikimedia.org/wiki/File:Brooklyn-side_tower_of_the_Brooklyn_Bridge_from_Brooklyn_Bridge_Park,_New_York_City.jpg), 1280×853, box 46,25,56,45 % (px 588,213–716,383). Taken 2026-04-17 13:02, clear blue sky, midday sun |
| Tower stone, sunlit lower pier | #c8b4a4 / #d2bdac | same file, box 42,70,56,85 % |
| Tower stone, side in partial shade | #b2a298 / #c4aea5 | same file, box 41,30,44,45 % |
| Tower stone, shaded (back-lit) face | **#766455 / #7b6858** | [File:New York City - Brooklyn Bridge - Manhattan-side tower - 0025.jpg](https://commons.wikimedia.org/wiki/File:New_York_City_-_Brooklyn_Bridge_-_Manhattan-side_tower_-_0025.jpg), 1280×854, box 25,30,35,45 %. Taken 2012-04-30 17:11 from the promenade, tower face in shadow, hazy blue sky #919dc4. The central pier (box 47,62,53,85) gives #705d50 / #725f50 |
| Deck truss steel ("tan"), sunlit | **#ad9183** non-sky median (mean #ad9285) | Brooklyn-side file above, px box 330,455–530,492 (truss and fascia), keeping only pixels with R > B and R+G+B > 250 (3,267 of 7,400 px). The plain box means were #7f675c and #846d63 because sky shows through the lattice |
| Cables and suspenders | **not sampled**. They are too thin at 1280 px. Use #b9ad9c (est.), tan-grey matching the steel, or #8a8a86 (est.) for the galvanised wire where unpainted | — |
| Sky reference | #0061a3 (sunlit shot) | box 60,5,75,15 % |

Recommended albedos:
- Masonry #c9b8a8 (est., a slightly desaturated version of the sunlit median).
- Steel #b09584 (est.).

Reference photos:
- https://commons.wikimedia.org/wiki/File:Brooklyn-side_tower_of_the_Brooklyn_Bridge_from_Brooklyn_Bridge_Park,_New_York_City.jpg
- https://commons.wikimedia.org/wiki/File:New_York_City_-_Brooklyn_Bridge_-_Manhattan-side_tower_-_0025.jpg
- https://commons.wikimedia.org/wiki/File:Brooklyn_Bridge_Tower_and_Cables.jpg (cable web, looking up)

---

## 2. Manhattan Bridge (1909; Leon Moisseiff)

### Overall geometry
| Item | Value | Source |
|---|---|---|
| Main span | **1,470 ft = 448 m** (body text). The infobox gives 1,480 ft = 451 m, and the OSM tower-centre distance is about 444 m | WP |
| Side spans | 725 ft = 221 m each | WP |
| Total length incl. approaches | 6,855 ft = 2,089 m | WP |
| Deck width | 120 ft = 37 m | WP |
| Clearance, midspan | 134–135 ft = 40.8–41.1 m above MHW | WP |
| Axis bearing | about 337° (Brooklyn tower to Manhattan tower) | computed from OSM |

### Two-deck structure (build as a box truss)
- **4 Warren stiffening trusses**, 24–26 ft = 7.3–7.9 m deep, each directly under one main cable.
  - Truss and cable centrelines: the inner pair is 40 ft = 12.2 m apart, and each outer truss is 28 ft = 8.5 m outboard of an inner one.
  - That puts the lines at **±6.1 m and ±14.6 m from the bridge centreline**.
- **Upper level** (on top of the trusses): 2 roadways with 2 lanes each (4 lanes in all). The Brooklyn-bound roadway on the west side is 6.9 m wide; the Manhattan-bound roadway on the east side is 7.3 m. Both narrow to 5.8 m at the anchorages.
- **Lower level** (on the bottom chords, floor beams 0.94 m deep):
  - Centre: a 3-lane Manhattan-bound roadway, 10–11 m wide.
  - Flanking it: **4 subway tracks, 2 under each upper roadway**, between the inner and outer trusses.
  - Outermost: the walkway on the south/west side and the bikeway on the north/east side, 3.0–3.7 m each, outside the outer trusses.
- Deck top at midspan is about 41 + 7.6 ≈ 48.5 m above MHW (est.).

### Towers (steel)
- Height: cable saddles (tops of the cables) at **330 ft = 100.6 m** above MHW. The **ornamental spherical finials reach 350 ft = 106.7 m**. OSM tags 102 m and gives the tower polygon as 36.3 × 7.7 m.
- **4 columns in a row across the bridge**, one under each cable (±6.1 and ±14.6 m from the centreline). Each column is 5 ft = 1.5 m wide across the bridge. Along the bridge, each column tapers from 32 ft = 9.8 m at the pedestal to 10 ft = 3.0 m at the top, which gives the elongated tapered-leg silhouette.
- Columns are braced by diagonal steel lattice. The centre of each tower reads as a "great open arch" between the two inner columns, over the lower roadway.
- Iron cornices sit just below the tops. Iron-and-copper hoods cover the walkway and bikeway where they pass the towers.
- Piers: masonry, 68 × 134 ft = **21 × 41 m**, rising 23 ft = 7.0 m above MHW. Each pier top tapers to a steel pedestal 18 × 43 ft = 5.5 × 13.1 m, from which the columns rise.
- Caissons are 24 × 44 m, 28 m below MHW (not visible).

### Cables
- **4 main cables**, 20.75–21.25 in ≈ 0.53 m in diameter, each 983 m long (9,472 wires in 37 strands).
- Saddles are fixed on the tower tops.
- **1,400 vertical suspenders**, about 0.13 m in diameter. There are **no diagonal stays**, which is the visual difference from the Brooklyn Bridge.
- Suspender spacing about 4.6 m (est.; the published count divided over the cable lengths).
- Main-cable sag about 50 m (est., derived: saddle 100.6 m minus the truss top of about 48.5 m at midspan). No published value was found.

### Anchorages
- Stone-faced concrete, **72 m long × 55 m wide × 41 m tall**, with sloping side buttresses. Each is topped by a 12 m colonnade of five bays (the "Egyptian" masses).
- Arch through the base: Cherry Street passes under the Manhattan anchorage, Water Street under the Brooklyn one. Each arch is 14 × 14 m.
- Manhattan approach plaza: an arch and colonnade in white Hallowell granite by Carrère & Hastings, at Canal St and the Bowery. The arch opening is 11 m tall × 12 m wide, and the colonnade is 12 m tall with Tuscan columns in pairs.

### Colours
The steel today reads as pale blue-grey or teal-grey (OSM mappers tagged `colour=#8eb4d2`). Both usable photos had strongly tinted light, so treat the sampled values with care:

| Surface | Hex | Photo, box, conditions |
|---|---|---|
| Tower column, sunlit, below deck | **#afb2ad** mean / #b5b8b1 median; non-sky median #b5b9b1 | [File:Manhattan Bridge tower, Dumbo, Brooklyn, New York.jpg](https://commons.wikimedia.org/wiki/File:Manhattan_Bridge_tower,_Dumbo,_Brooklyn,_New_York.jpg), 1280×2048, box 56,65,64,82 %. Taken 2026-04-17 06:13, **low sunrise sun (warm cast)**, clear sky #4798db |
| Tower lattice above deck, sunlit | non-sky median **#aaaba1** (plain mean #879494) | same file, box 56,15,61,45 % |
| Tower lattice, shaded side | non-sky median #837f72 (mean #737674) | same file, box 42,20,48,45 % |
| Masonry pier, sunrise-lit | #b08050 / #ad7946 | same file, box 35,88,70,91 %. Strongly orange from the dawn light; a neutral stone value would be about #b9ab94 (est.) |
| Tower at distance, back-lit / shaded | #243644 / #1e3445 (lower column); lattice #717e81 | [File:Manhattan Bridge and One Manhattan Square from Brooklyn Bridge, 20231005 0939 2164.jpg](https://commons.wikimedia.org/wiki/File:Manhattan_Bridge_and_One_Manhattan_Square_from_Brooklyn_Bridge,_20231005_0939_2164.jpg), 1280×1325, boxes 78,72,80.5,82 % and 80,51,81.5,62 %. Taken 2023-10-05 09:39, clear sky #84b3e2, tower on its shade side |

Recommended albedo for the steel: **#9fb0b6** (est., pale blue-grey between the sampled sunlit neutral grey and the OSM tag #8eb4d2). Use the same for the cables (est.).

Night:
- The main cables carry "necklace" lights along their curves. This is widely seen in photos but I did not verify it in the fetched text.
- Towers are floodlit (est.).

Reference photos:
- https://commons.wikimedia.org/wiki/File:Manhattan_Bridge_tower,_Dumbo,_Brooklyn,_New_York.jpg
- https://commons.wikimedia.org/wiki/File:Manhattan_Bridge_and_One_Manhattan_Square_from_Brooklyn_Bridge,_20231005_0939_2164.jpg
- https://commons.wikimedia.org/wiki/File:Manhattan_Bridge_and_One_Manhattan_Square,_New_York_City,_20231002_0915_1578.jpg

---

## 3. Statue of Liberty (1886; Bartholdi / Eiffel; pedestal by R. M. Hunt)

Position: **40.689253, -74.044530**. This is the centroid of OSM way 433053921, the copper statue part tagged `min_height=46.9`, `height=93`, `colour=#92C7BD`. The pedestal (way 229651145) and the fort outline (way 32965412) are concentric with it to within 1 m. Liberty Island (OSM relation 9791559) is 5.96 ha. The statue faces **south-east**, aligned with Fort Wood (NPS).

### Vertical stack (NPS / WP, metres above ground)
| Level | Height | Published |
|---|---|---|
| Ground (island grade) | 0 | — |
| Top of Fort Wood star walls | about 10 m (OSM `height=10`; est.) | — |
| Top of concrete foundation (stepped terraces inside the fort) | **19.81 m** (65 ft "height of foundation") | WP |
| Top of pedestal (statue base) | **46.94 m** (154 ft ground to pedestal); pedestal itself 27.13 m (89 ft) | NPS, WP |
| Top of head | 46.94 + 33.86 = **80.8 m** (heel to top of head 111 ft 1 in) | derived |
| Tip of torch | **92.99 m** (305 ft 1 in); statue base to torch 46.05 m (151 ft 1 in) | NPS |

### Plan dimensions for the loft (from OSM building parts, measured in local metres)
| Element | z range (m) | Footprint | OSM id |
|---|---|---|---|
| Fort Wood, 11-pointed star | 0–10 | star, 34 vertices. Inner (re-entrant) radius about **34.6 m**, point radius about **52 m**. The minimum rectangle is 96 × 94 m | way 32965412 |
| Foundation terraces (16 stepped rectangles) | 10.5–18 (0.5 m steps) | from about **47 × 52 m** at 10.5 m to about **21 × 27 m** at 18 m | relations 3079001–3079016 (bounds only) |
| Foundation blocks | 10–14 / 14–18 / 18–26 | 40.2 × 39.6 / 25.6 × 25.1 / 18.9 × 17.9 m | ways 229651147 / 229651143 / 229651144 |
| Pedestal shaft | 23–46.9 | 15.9 × 15.0 m | way 229651145 |
| Pedestal cornice / observation balcony | 45–46.9 | 17.3 × 16.4 m | way 229651146 |
| Statue (copper figure) | 46.9–93 | about 13.4 × 12.6 m envelope | way 433053921 |

The published pedestal is a truncated pyramid, **62 ft = 18.9 m square at the base and 39.4 ft = 12.0 m at the top**, all four sides identical. It has:
- a Doric portal on each face;
- a row of 10 discs above each door;
- a balcony framed by columns (a loggia) on each side, near the top;
- the observation platform just under the statue.

The OSM 15.9 m shaft is a simplified middle value.

### Figure dimensions (NPS)
- Head, chin to cranium: 5.26 m. Head width: 3.05 m. Eye width: 0.76 m. Nose: 1.37 m. Mouth: 0.91 m.
- Right arm (raised): 12.80 m long, 3.66 m thick.
- Waist thickness: 10.67 m.
- Hand: 5.00 m. Index finger: 2.44 m.
- Tablet in the left arm: 7.19 × 4.14 × 0.61 m, inscribed "JULY IV MDCCLXXVI".
- Crown: **7 rays and 25 windows**. Ray length about 2.7 m (est.; not in the fetched sources).
- Torch: the 1986 replacement, copper covered in 24k gold leaf. Floodlights light it by reflection at night.
- Copper skin 2.4 mm thick. A broken chain and shackle at the feet is not visible from below.

### Colours
| Surface | Hex (mean / median) | Photo, box, conditions |
|---|---|---|
| Copper verdigris, sunlit robe (close, frontal) | **#9ac7c8 / #addfdd** | [File:Statue of Liberty frontal 2 crop.JPG](https://commons.wikimedia.org/wiki/File:Statue_of_Liberty_frontal_2_crop.JPG), 1280×1931, box 40,45,60,65 %. Taken 2008-05-28, clear deep-blue sky #375684, full sun (slightly bright exposure) |
| Verdigris, robe folds in partial shade | **#6e9b98 / #699793** | same file, box 30,70,38,85 % |
| Verdigris, side of robe | #7caaa6 / #9ac9c4 | same file, box 60,70,67,85 % |
| Verdigris, whole figure at distance | #4a908c / **#358a87** | [File:Statue of Liberty, NY.jpg](https://commons.wikimedia.org/wiki/File:Statue_of_Liberty,_NY.jpg), 1280×960, box 48,25,54,45 %. Taken 2007-11-13 12:34, sun with scattered cloud, sky #93b4da. The box includes a few sky pixels between the arm and the body |
| Pedestal (Stony Creek pink granite), sunlit, with windows and shadow | **#74685a / #7b6959** | same file, box 44,55,56,70 % |
| Fort Wood granite wall, sunlit | **#87785f / #8a7b61** | same file, box 18,81,30,87 % |
| Fort Wood wall, shaded face | #3f4346 / #394046 | same file, box 62,81,80,87 % |
| Upper terrace / foundation parapet, sunlit | #a7957d / #b29e84 | same file, box 33,76,44,79 % |
| Torch flame (gold leaf) | not sampled (box too small) → **#d4a53c** (est.) | — |

Recommended albedos:
- Statue: **#6fa9a3** (est., between the close sunlit value and the distant value; OSM mappers use #92C7BD).
- Pedestal granite: #8f7f6c (est., the sampled value lifted to remove the shadowed windows).
- Fort walls: #8f806a (est.).

Night:
- The statue and pedestal are floodlit from within the Fort Wood walls. The 1986 metal-halide scheme is aimed at specific parts of the statue and pedestal; there may be later LED upgrades, which I did not verify.
- The torch glows gold by reflected light.

Reference photos:
- https://commons.wikimedia.org/wiki/File:Statue_of_Liberty,_NY.jpg (whole statue, pedestal and fort)
- https://commons.wikimedia.org/wiki/File:Statue_of_Liberty_frontal_2_crop.JPG
- https://commons.wikimedia.org/wiki/File:Liberty_Island_photo_Don_Ramey_Logan.jpg (aerial view of the star fort and island)

---

## Open gaps
- **Brooklyn Bridge:**
  - Main-cable sag (39 m) and suspender spacing (2.3 m) are commonly cited values I could not verify.
  - The tower's taper, pier widths (from photo proportions) and saddle height are estimates.
  - Anchorage height (about 27 m) is unverified.
  - I could not sample the cables' colour at the available resolution.
- **Manhattan Bridge:**
  - Main span: 448 m vs 451 m (two WP figures).
  - Sag (about 50 m) and suspender spacing are derived estimates.
  - Both usable photos had tinted light (sunrise, or the tower on its shade side), so the recommended pale blue-grey #9fb0b6 is partly estimated. The OSM tag #8eb4d2 is mapper-supplied.
  - Necklace lighting is not confirmed from text.
- **Statue of Liberty:**
  - Fort Wood wall height (10 m) comes from the OSM tag only.
  - The foundation terrace outlines are known only from relation bounding boxes, because Overpass returned no member geometry.
  - Crown ray length is not in the sources.
  - The torch colour was not sampled.
  - The current night-lighting technology is not verified.
  - The ground elevation of Liberty Island above MHW is unknown (about 3 m, est.).
- I did not reach any HAER (Library of Congress) measured drawings for either bridge, so no values from measured drawings were used.
