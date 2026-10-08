<!-- M4 landmark research (helper r-tk-m4l for b-tk-m4l, 7 Oct 2026): the sources of scripts/m4l_structures.py and data/landmark_facades.csv. Photos it sampled were kept outside git (demos/data/tk-m4l-photos/). -->

# Tokyo M4 landmark figures: research for b-tk-m4l (by r-tk-m4l, 7 Oct 2026)

Conventions: (sampled: Commons file + box + conditions) = PIL median over a box (box in the 1280-px-wide Commons thumbnail
unless stated; "mask" = only pixels passing a colour test inside the box, so lattice gaps do not pull the median to the sky).
(est.) = my estimate, no measurement. OSM ids are from the local Overpass (snapshot 2 Oct 2026). Centroid = mean of outline
vertices (lat,lon) to 6 decimals; "bbox WxH m" is the lon/lat-aligned bounding box (a rotated outline reads larger than its
sides). Photos live in <project>/demos/data/tk-m4l-photos/ (git-ignored).
IMPORTANT ABOUT OSM bbox NUMBERS: Overpass 'bbox' is axis-aligned, so a rotated rectangle reads up to 1.4x too wide. Where it matters I recomputed the true minimum-area rectangle ("true W x D", measured from the OSM vertices, rotation given as the bearing of one side). Numbers marked 'bbox' in the text below are the lon/lat-aligned ones; always prefer the 'true' figures (they are in the per-landmark text where I re-measured, and in the table at the end of this file, 'TRUE SIZES').
Heights are above ground unless "asl" is said. Tokyo Tower's ground (G.L.) is T.P.+18 m.

IMPORTANT cross-source trap: the marketing "150 m / 250 m" deck heights of Tokyo Tower are ASL-ish; above ground the Main Deck is 120-~135 m and the Special/Top Deck 217-251 m (OSM and photo agree, see 1).

---------------------------------------------------------------------------------------------------------------

## 1. Tokyo Tower  (35.658588, 139.745447 = OSM centre of the Main Observatory; tower relation centroid 35.658472,139.745498)

### (a) geometry
- Total 332.9 m (EN wiki), published "333 m"; 351 m asl (JA). Lattice, steel, 1958. Architect Naito Tachu.
- Plan: four legs; the tower is rotated: its square faces run along bearings 56 deg / 146 deg (i.e. 34 deg off the N-S axis), so every OSM "bbox" of a tower part is ~1.38x its true side (bbox = side x (cos34+sin34)). TRUE (min-area rectangle) values below. Leg footprints (4 OSM buildings, h 7 m: ways 1244967004-1244967007, centres (35.658703,139.746105) (35.659100,139.745316) (35.658497,139.744826) (35.658083,139.745569)), each ~6.5 m square: leg centre-to-centre spacing 83.8, 80.4, 81.4, 84.3 m (mean ~82.5 m); outer face to outer face ~ 89 m, which matches JA wiki's "塔脚の間隔 88.0 m" (so 88 m = overall base width; c/c ~ 82 m; a square plan of ~ 82 m sides, mapping errors +-2 m).
- Leg arch: the four legs are joined at 40 m by arches (JA: アーチ最上部 h40). OSM has the 40 m "roof" ways (skillion, #ff0000, ways 1244967008, 1244967009, 1245318714-1245318743) for the arches.
- Taper profile (OSM relation stack of pyramidal "roof" parts; the ring of each part is the SQUARE at the BASE of the segment, so side = true min-rect; segments run from base to the stated top; I measured them):
  | segment (m above ground) | true square side at the segment base (m) | OSM relation | roof:colour |
  | 0-40 (legs + arches)  | c/c 82.5 at ground (outer 89) | legs 1244967004-07 | |
  | 40-53  | 52.2 | 17133572 | #ff0000 |
  | 53-66  | 41.5 | 17133573 | #ff0000 |
  | 66-77  | 33.6 | 17133574 | #ff0000 |
  | 77-88  | 30.8 | 17133575 | #ff0000 |
  | 88-97  | 28.1 | 17133576 | #ff0000 |
  | 97-106 | 25.2 | 17133577 | #ff0000 |
  | 106-120| 22.5 | 17133578 | #ff0000 |
  | 120-130| Main Observatory 29.5 x 29.5 (overhangs the shaft) | way 313815246 | white |
  | 130-161| 19.4 | 17133569 | #ff0000 |
  | 161-188| 15.3 | 17133570 | #ffffff |
  | 188-217| 11.9 | 17133571 | #ff0000 |
  | 217-251| Special Observatory zone, 12.4 m square (ways 1244966979 8.3 m 217-241 white; 1244966986 12.4 m 224-227 white; 313815247 12.4 m 241-246; 1244966985 12.4 m 246-251 #ff0000) | | |
  Above 251 m the tower is a ~3-4 m gain tower (OSM ways 1244966987 251-274 #ff0000, 1244966988 274-301 #ffffff, 1244966989 301-311 #ff0000, 1244966990 311-332.6 #ff0000; true widths ~3 m and ~1 m, bbox 4x4 and 1x1).
  Taper changes: at 40 m (arch top; the legs lean strongly below), a kink at 66-77 m (width falls 33.6 -> 30.8, nearly straight above: 30.8, 28.1, 25.2, 22.5 over 77-120 m = a straighter shaft), 130-217 m concave again (19 -> 12), and the antenna section above 251 m. In the photo the profile is concave throughout.
- Main Observatory (大展望台): OSM way 313815246 "大展望台", centre 35.658588,139.745453, 29.5 m square (rotated 56 deg; bbox reads 35 m), min_height 120, height 130, 2 levels, building:colour white; a relation 3915931 (building=buffet) is its cafe. An OSM "height 150, min 20, white" way 1245337010 (13x15 m) is the lift core/stair tower. So the deck block is ~29.5 x 29.5 m (square, rotated with the tower) and 10 m tall, floors 120-130 m (JA: 地上120 m より上の2階構造; the 150 m in brochures is asl: 125 m floor + 18 m + ...). Photo: its facade is a white band of windows, 1 m tall mullion bands, about 10 m high, corbelled out: the deck block is 29.5 m wide while the shaft below it is ~22.5 m.
- Special / Top Deck (特別展望台, "Top Deck" since 2018): OSM way 313815247 12.4 m square, 241-246 m (a ring of glass), way 1244966979 11x11 241 (217-241, white lower), way 1244966986 12x12 (224-227 white), way 1244966985 12x12 (246-251 #ff0000 orange cap). JA: floors 223.55 m, "250 m" asl. Top Deck is ~12 m wide, circular in plan per Japanese sources (floor ~160 m2 ~ circle of 14 m diameter); in the photo it is a white cylinder with an orange cap, 217-251 m.
- The digital antenna: cylinder of diameter 13 m and height 11 m on top of the Special Observatory (JA wiki; the orange drum visible in the photo at ~250 m); above it the gain tower 4 m wide (OSM) to 311 m and the thin white/red antenna up to 333 m (mast top 332.6 per OSM). "STアンテナ" 25 m long, 0.37 m dia was removed in 2012 and replaced by a square steel pole.
- Band pattern (measured on the photo, see colours): from the top of the Main Deck (130 m) to the tip (333 m) there are 7 equal bands of 29 m, starting and ending with orange:
  orange 130-159, white 159-188, orange 188-217, white 217-246, orange 246-275, white 275-304, orange 304-333. Count above the deck = 4 orange + 3 white. (JA wiki: 7 equal bands since 1986, 11 before (6 orange + 5 white); my pixel scan of Tokyo_Tower_during_daytime.jpg puts the transitions at ~156, ~185, ~216 m, ~277 and ~311 m, consistent with 29 m bands within a few metres.) Below the deck: orange all the way (since 1998 the Main Deck's sides are white). OSM mapping agrees: 130-161 #ff0000, 161-188 #ffffff, 188-217 #ff0000.
  Note: in the lattice the white bands show as white diagonals/horizontals only; the verticals of the corner legs stay thicker. Whole lattice members are painted, there is no panel.
- FootTown (base building, 5 storeys incl. the roof use): OSM relation 4247313 (height 20 m, 4 levels, flat roof, roof:colour grey, building:colour #AB6B83 - an OSM guess; JA wiki: wall colour changed to "dark brown" at the 2005 FootTown opening). Footprint: true min-rectangle 52.7 x 76.7 m (rotated 56 deg; the same outer ring as the tower relation 4247312), centred ~ (35.658472,139.745498): the building sits under/between the four legs and extends towards the front (the legs' roof-level footprints stand on its roof; the tower legs rise from its roof; JA: ground floor = G.L. = FootTown floor 1, roof ~20 m high with a glass plaza/playground; stair from roof to Main Deck, 590 steps). 
- Aircraft-light and antennas: radio masts on Main Deck sides (white dishes, many); lift shafts in the leg.

### (b) daylight colours
- Orange lattice: #e05023 (sampled: Commons "File:Tokyo Tower during daytime.jpg" (Jan 2011, low winter sun, clear), mask r>170,g<140,b<100 inside displayed box 320-480 x 1300-1500 of the 852-px view (scale 1.5); median of 23,901 pixels); also #d9572e (same file, 130-159 m band), #d76233 (upper orange 253-277 m).  Official paint: 黄赤 "international orange"; reasonable model value #e8501f-#ff5a1f; keep lit side #e05023.
- White lattice and Main Deck facade: #f2ece1 (sampled: same file, white band 159-188 m, mask min>170), #faf5ed (Main Deck facade band, same file). Use #f4efe6.
- Sky behind: #d7e6e6 (same file, hazy winter).
- FootTown: dark brown (JA wiki, est. #5a4034); OSM guess #AB6B83 should not be used.

### (c) night
- Landmark Light (since 1 Jan 1989, designer Ishii Motoko): 180 floodlights (JA: 12 on the gain tower, 16 above the Special deck, 40 between Special and Main deck, 16 under the Main deck, 84 from FootTown roof to Main deck, 12 at the leg bases), from sunset to midnight; direct light on the steel, no outline bulbs. Sodium lamps (orange, ~#ff9a3c lit-steel look) 2 Oct-6 Jul; metal halide (white, ~#fff4e0) 7 Jul-1 Oct. The whole shaft glows orange/white evenly, the Main Deck windows warm white.
- "Diamond Veil" (since 1 Dec 2008, 20:00-22:00): 17 rings of seven-colour LEDs. Special lights (Christmas, pink 1 Oct etc.).
- Photo: File:Dramatic View of Illuminated Tokyo Tower.jpg (Jun 2025), a worm's-eye shot in the orange (sodium) season: (sampled, 1280-px thumb) lit lattice median #b04f0d (mask r>120 & r>b+60, box 150,700-1100,1500), brightest lit members #da7319 (mask r>200, box 300,900-900,1300), the Main Deck underside and glazing wash lit yellow-white #cb9430 (mask r>150, box 420,440-880,640), orange/gold top drum #aa7a21 (box 570,100-700,200); the shaft is dark between lit members, the deck windows are dark blue-black (deck glazing unlit from outside). So: night lattice = orange-gold #b04f0d-#da7319, deck belly #cb9430, background black.

### (d) OSM
- Tower relation 4247312 (name 東京タワー, height 333, man_made=tower, multipolygon); centroid 35.658472,139.745498; bbox 89x86 m. FootTown relation 4247313. Main Observatory way 313815246 (35.658588,139.745453, true 29.5 m square, 120-130 m); Special Observatory way 313815247 (12x12, 241-246 m); parts as tabled. Pyramidal roof relations 17133569-17133578, 4247312-linked parts as listed. Tower label node 11436145877 (35.659280,139.744767).

### (e) Commons
- https://commons.wikimedia.org/wiki/File:Tokyo_Tower_during_daytime.jpg (straight on, telephoto, bands visible)
- https://commons.wikimedia.org/wiki/File:Tokyo_Tower_2023.jpg ; night: https://commons.wikimedia.org/wiki/File:Dramatic_View_of_Illuminated_Tokyo_Tower.jpg

---------------------------------------------------------------------------------------------------------------

## 2. Tokyo Skytree  (35.710051, 139.810713 OSM tower way centroid)

### (a) geometry
- 634 m (including the gain tower), JA wiki; observation floors Tembo Deck 350 m (floors 340/345/350; the lift lands at floor 340; OSM part 290-350), Tembo Galleria 445-451 m (floor 450; H450; the spiral tube slope ~110 m long between 445 and 450), floor H458 top of lift; transmitter room H360; core cylinder (reinforced concrete, "shinbashira") 8 m dia up to H375; gain tower starts at 497 m (final height of the steel frame 497 m, JA timeline) and rises to 634 m: outer dia ~6 m (gain tower) and ~8 m at the antenna section (JA wiki); FM antennas ~550 m.
- Base: equilateral triangle of side ~68 m (JA wiki: 一辺約68メートル; foundation triangle, one side parallel to Kita-jikken river); the section turns rounder with height and is a CIRCLE at H320 (JA wiki: H320で円). Steel tubes up to 2.3 m dia, 10 cm wall. Total steel frame weight ~41,000 t.
- OSM: tower way 288269147 (name 東京スカイツリー, height 634, roof:shape cone, true 56.6 x 56.6 m (rot 24 deg), area 2,511 m2, centre 35.710051,139.810713 = the footprint of the lower tower: a rounded triangle (inscribed in a ~57 m square; the JA 68 m side is the outer triangle of the foundation/ground floor, the 2,511 m2 area is consistent with a rounded triangle of ~ 55-60 m circumdiameter)); part 362351415 (290-350, pyramidal, true 35.2 x 35.3 m (rot 88), centre 35.710043,139.810707: the Tembo Deck block, a 35 m diameter drum incl. its flaring roof); part 288269148 (410-450, pyramidal, true 26.6 x 26.5 m, centre 35.710039,139.810709: Galleria block); part 362351414 (5.7 x 5.7 m, to 634, centre 35.710045,139.810716: gain tower). Podium parts 557938593/557938595 (true 57.3 x 65.3 m, layers 2, around the tower, centre 35.710128,139.810699) and 362351420 (226x88 m, 5 levels, 35.709952,139.809677), 362351413 (82x75 m, 7 levels, 35.710229,139.811979).
- SILHOUETTE MEASUREMENT (my own, from two Commons photos taken from the Sumida's west bank at Asakusa, ~1.7 km away, near-orthographic: File:Tokyo_Skytree_@_Asakusa_(11625269163).jpg and File:Tokyo_Skytree_@_Sumida_River_@_Asakusa_(12326146143).jpg; row-by-row extent of non-sky pixels, scale calibrated on tip = 634 m and Tembo Deck centre = 345 m, i.e. 1.66 and 1.31 px/m; both photos agree within 2 m; accuracy +-3 m, view direction ~ WSW):
  | height (m) | silhouette width (m) |
  | ~95 | 58 (lower shaft; the 68 m triangle side is at ground; this is the triangle seen obliquely) |
  | ~185 | 50 |
  | ~246 | 44 |
  | ~276 | 41.5 |
  | ~303-306 | 38.5-39 (the section is a circle from H320; diameter ~38 m) |
  | 306-366 | TEMBO DECK bulb: flares from 38.5 m at 306 m to 46 m (318), 54 (330), 63 (342), max 67-69 m at ~348-355 m, top at ~366 m (59 m at the roof edge, then 36 m just above); i.e. a ~60-m-tall "pot" with max diameter ~68 m (est. +-4) centred on floors 340-350 |
  | 372-430 | shaft between the decks: 36 m at 372, 31-33 m at ~430 (hourglass, narrowest under the Galleria) |
  | ~440-455 | TEMBO GALLERIA bulb: ~43 m max (est. +-3), floor at 445-451 m; the glass tube ring |
  | 460-493 | collar/steel cylinder above the Galleria: 22-25 m |
  | 497-600 | gain tower ~ 7-8 m wide (JA: outer dia ~6 m; antenna casing ~8 m) |
  | 600-634 | antenna head (the stacked broadcast antennas) ~ 12-13 m wide, topped by the lightning rod (a thin needle) |
  The OSM building:part numbers (35.2 m "290-350" and 26.6 m "410-450") are the cores of the decks, not their outer diameters: use the silhouette values for a figure. Published deck diameters: none found (Wikipedia EN/JA, Obayashi/Tobu pages searched via the search tool).
- Cross-section along the height (use the silhouette table above; the circular section from H320 is ~38 m diameter, the ground triangle has a 68 m side with the 57 m rounded-triangle outline in OSM).
- Visual structure: lattice of diagonal tubes in each face; "mukuri" concave curve. Elevator shaft grey inside.

### (b) daylight colours
- "Skytree White" (スカイツリーホワイト, JA wiki): an original colour from the traditional bluish white 藍白 (aijiro; traditional colour list value #EBF6F7, est. - from the Japanese colour dictionary, not measured by me). Elevator shaft grey; observation decks metallic; top (gain tower) bright white (JA wiki, 9 Feb 2009).
- Sampled: #eef7fe (File:20240117_Tokyo_Skytree_10.45.01.jpg, sunlit Tembo Deck band, box (570,320)-(690,420) of the 1125-px view x1.14, mask min>175, clear sky, winter morning); lattice in sky-lit shade #c0cee6 / #c4d2e8 (same file, boxes (500,560)-(580,760) and (460,740)-(560,880) x1.14, mask min>175, strongly blue-sky tinted); #cde1ea on a shaded steel tube (File:Tokyo_Skytree_(53081432570).jpg, box (850,200)-(1150,600), 1280-px original, indoor shade). Use #e6eef2 as base with the sky's blue coming from the sky irradiance; do not use pure white.
- Galleria: #d8e2f9 (same photo, few pixels).

### (c) night
- Photo (File:The_Might_Sky_Tree_(28019362551).jpg, May 2016, long exposure; sampled): an "Iki" night: lit lower shaft cyan-blue #0a98d3 (box 805,552-866,841 mask max>110) with brightest #08b3e8; Tembo Deck ring warm olive-gold #878253; upper shaft/Galleria/gain tower warm gold #e1c166 (box 817,308-854,430). The warm gold on the upper part is the standard white/ gold deck-floodlighting, and the blue is saturated by the long exposure (true Iki is paler #8fd3f0-ish; est.).
- Three alternating nights (JA wiki): "Iki" (粋): light blue "Sumida-river water" #8fd3f0-ish (est.) on the central shaft / core, the lattice lit blue-white; "Miyabi" (雅): Edo purple (江戸紫, ~#7a4ea0 est.) with gold-leaf-like glints (#e8c36a est.); "Nobori" (幟, since 17 May 2017): tachibana orange (橘, ~#f08a2b est.) in vertical lines splitting the tower in three faces. LED, 2,362 fixtures (2020); gain tower is full colour. The deck rings are lit warm white from within.

### (d) OSM
- Tower way 288269147 (35.710051,139.810713); parts 362351415, 288269148, 362351414 (centroids above).

### (e) Commons
- https://commons.wikimedia.org/wiki/File:20240117_Tokyo_Skytree_10.45.01.jpg
- https://commons.wikimedia.org/wiki/File:Tokyo_Skytree_(14044461369).jpg

---------------------------------------------------------------------------------------------------------------

## 3. Rainbow Bridge  (centre of main span ~35.636569,139.763152 from the two tower centres; relation centroid 35.636326,139.765538)

### (a) geometry
- Official name Tokyo Port Connector Bridge (東京港連絡橋). JA Wikipedia infobox (cites the 1994 bridge yearbook): type = 3-span, 2-hinge stiffened-girder suspension bridge (3径間2ヒンジ補剛桁吊橋); span split 111.5 + 570.0 + 111.5 m = 793 m between the anchorages (total length 798.0 m quoted; the "918 m" suspension part counts 60 m anchorage blocks); width 29.0 m on the suspension part and 49.0 m at the tower foundations; tower height 126 m above T.P. (the towers are 119.0 m (Shibaura tower) and 117.366 m (Daiba tower) above their foundation tops); girder soffit (桁下) T.P. +51.266 m (the ~52 m clearance); girder weight 45,425 t; towers are portal frames (ラーメン構造), not trussed, painted white; limit TP +150 m (Haneda). (EN Wikipedia gives main span 570 m in its infobox but 580 m in the text: use 570.0.) Approach: Shibaura side 1,465 m (439 m land + 1,026 m loop), Daiba side 1,367 m. Double deck: upper deck = Shuto Expressway Route 11 Daiba (4 lanes), lower deck = Yurikamome (centre, 2 tracks), Tokyo Route 482 (2+2 lanes, one each side of the track) and walkways outside (north/south). Builder: Kawasaki HI / IHI / Nippon Steel etc. JVs.
- Tower positions from OSM pylon parts: 
  Shibaura tower: legs at (35.637366,139.760156) and (35.637637,139.760285) (ways 1348279698, 1348279700, each true 4.9 x 5.0 m (rot 69 deg), h 126); upper cross beam way 1348279701 (117-126 m, true 27.8 m long x 5.0 m thick) and lower cross beam way 1348279699 (27-31 m); centre of the pair 35.637502,139.760220.
  Daiba tower: legs (35.635502,139.766019) and (35.635773,139.766149) (ways 1348279695, 1348279696, 4.9 x 5.0 m, h126); upper beam way 1348279694 (117-126 m), lower beam way 1348279697 (27-31 m); centre 35.635637,139.766084.
  Leg centre spacing across: ~32.4 m (computed); tower centre to centre 568.7 m on bearing ~111 deg (ESE). Leg section ~5.0 x 4.9 m square (OSM true min-rect; legs are hollow box columns ~5 m). Upper cross beam 9 m deep (117-126 m) x 5 m thick x 27.8 m clear length between the legs; lower cross beam 4 m deep (27-31 m) also 27.8 m long. The lower cross beam (27-31 m) lies well below the girder soffit (51.3 m), so the girder passes between the legs without touching them (the photo shows the girder running through the portal).
- Anchorages: Shibaura side: ways 540211904 (true 45.4 x 68.7 m, rot 69 deg, 0-30 m), 1348272539 (45.4 x 47.4, 30-45 m), abutment/ramps 1348272540 and 1348272541 (26x14 and 25x14 bbox, 45-60 m); centre ~35.637927,139.758917. Daiba side: ways 1348279690 (true 68.8 x 45.5 m, rot 158 deg, 0-30), 1348279691 (46.9 x 45.4, 30-45), 1348279692/1348279693 (abutments 45-60 m); centre ~35.635176,139.767481 (the anchorage is a massive white cuboid with a sloped front, rust-brown cable cover visible on the slope; Daiba anchorage is built in the sea by pneumatic caisson).
- Main cable: sag/span ratio not found in any source I could reach (est. 1/10 => ~57 m sag; cable top at the tower saddle ~126 m T.P., so the lowest point mid-span ~ 69 m T.P., ~ 17 m above the girder top (~52 m); in the photo the cables dip to meet the truss's top chord only at mid-span). Two cable planes, one per tower leg, ~32.4 m apart centre to centre (a bit wider than the 29 m girder; the hangers lean slightly inward). Vertical hangers every ~ 15 m, thin white-grey ropes. 
- Deck: two-storey stiffening truss (upper deck on top of the truss, lower deck inside the truss), truss depth ~ 12-13 m (est., from the photo: ~0.1 of the tower height); girder soffit at T.P. 51.27 m => lower deck road at ~ 52-53 m, upper deck road at ~ 63-64 m (est.), top-chord of the truss ~ 64-65 m; the repo's M3 notes use 46/55 m only because of grade limits.
- OSM bridge ways: relation 18497742 (name レインボーブリッジ, man_made=bridge, centroid 35.636326,139.765538, bbox 1663x400 m) has ways 508040808 (bridge=viaduct, bridge:structure=cable-stayed (wrong), the outline polygon, 1599x369 m) plus the pylon/abutment parts. Roads: upper deck motorway ways 316305907/316305908 (東京港連絡橋, two carriageways, 860x329 m, layer 4), 4847506, 316305910 (Shibaura approach), 202805895, 316305909 (Daiba approach); Yurikamome ways 275936305, 749205417 (Shibaura side viaduct, layer 3), 172368551, 749205421 (Daiba approach, layer 2), 500180268/749205420 (loop).

### (b) colours
- Towers and girders: painted white (EN wiki: towers white to harmonise with the skyline from Odaiba). Sampled (File:Rainbow_Bridge,_Tokyo,_South_view_from_Odaiba_20190419_1.jpg, 1280-px thumb, overcast haze): lit top face of the Daiba tower's beam #cccdd1 (box 760,115-790,125); vertical tower faces in shade #78808c (box 585,140-600,330), #737d89 (box 745,140-758,330); girder underside #3f4750 (box 300,500-500,520); truss web #7f848c (box 300,465-480,480); anchorage wall #71747a (box 700,520-900,600); rust-pink cable cover slope #9a8f8c (box 720,470-790,520); sky #ced1d4. Model: tower white (est. #e6e8ea), girder light grey (#b8bec4), underside darker (#7a828a), anchorage white-grey (#d0d2d4).

### (c) night
- Sampled (File:Rainbow_Bridge,_Tokyo_at_Night.jpg, 1280-px thumb, night, overcast): tower legs floodlit cool white-green #c0c9c4 (mask max>150, box 540,310-556,530) and top beam #c6cbc1; far (Shibaura) tower #b2bbaf; the Daiba anchorage block is lit yellow-green #759449 (box 600,470-720,535, mask max>100); the main cables carry strings of small green lamps (EN wiki: red / white / green solar lamps, one colour per night); sodium-orange street lamps along the upper deck (est. #ffb35a), white lamps on the lower deck. Special rainbow nights.

### (e) Commons
- https://commons.wikimedia.org/wiki/File:Rainbow_Bridge,_Tokyo,_South_view_from_Odaiba_20190419_1.jpg ; https://commons.wikimedia.org/wiki/File:Rainbow_Bridge,_Tokyo_at_Night.jpg

---------------------------------------------------------------------------------------------------------------

## 6. Fuji TV headquarters (FCG Building), Odaiba  (OSM FCG outline way 287770734; sphere 35.626986,139.774658)

### (a) geometry
- Designed by Tange Kenzo (Kenzo Tange Associates), opened 10 Mar 1997. 123.45 m, 25 floors (OSM way 287770734: height 123, name FCGビル, 225x182 m bbox, 12,923 m2 for the whole low podium + towers, centre 35.626735,139.774301). Proportion of the elevation 16:9 (JA).
- Two high-rise blocks: Media Tower (west) and Office Tower (east), joined by "corridors" at floors 12, 18 and 24 (JA wiki: 12階・18階・24階). OSM has the corridor slabs as three layers of building:part relations, each with the same footprint (true 98.5 x 29.4 m, rot 34 deg, i.e. a ~98 m long x 29 m wide slab per level; centre 35.626815,139.774539): relation 3816597 (56-63 m), 3816598 (82-88 m), 3816599 (107-113 m); i.e. 7 m, 6 m, 6 m deep slabs at about 56-63, 82-88 and 107-113 m. Mega-columns (the "lattice" verticals): ~8 square columns 6x7 m, h 113 m (ways 287770759, 287770761, 287770764, 287770766, 287770770, 287770772 and others) at around (35.6268,139.7744) [west cluster] and (35.6269-35.6270,139.7747-139.7748) [east cluster]; columns 287770759/287770770 have min_height 56 (they stop above the third floor).
  Tower relations (true min-rects, rot 34 deg): 3816594 (68.1 x 36.7 m, 120 m, centre 35.626375,139.773822, west tower); 3816590 (42.1 x 53.5 m, 124 m, centre 35.627242,139.775091, east tower) with 3816588 (32.0 x 42.2 m, 119 m) as the upper part; the tall vertical service/lift shaft between them (blue-grey, tallest piece) is ways 287770738 (4x4 m, 127 m) and 287770778 (10x13, 124 m) near (35.626871,139.774891), per the photo it stands on the right of the sphere; lower podium relations 3816595 (154x106, 25 m), 3816591 (115x77, 31 m), 3816589 (136x96, 38 m), 3816593 (53x39, 45 m).
- Sphere (はちたま): diameter 32 m, titanium-clad (JA: 新日鐵 TranTixx titanium), ~1,200 t; observation at the 25th floor (24th-25th floors "球体展望室"). OSM way 287906915 (dome, true 31.7 m diameter, min_height 96, height 130, centre 35.626986,139.774658): that gives a 34 m tall dome with centre ~113 m. Published observation floor height ~100 m. My best figure: centre at ~108 m (est.), i.e. bottom ~92, top ~124 (= the roofline). Position: at the top of the west lattice portion, NOT midway between the towers: from the photo (File:Fuji_Broadcasting_Center_and_Aqua_City_Odaiba...) it hangs left of centre, about 1/3 of the way from the west tower to the east, above the first big opening of the lattice, supported by four columns below.
- Plan: building long axis rotated ~ -20 to -30 deg from E-W; whole complex 225x182 m (OSM). Lower podium: 7 storeys, mint-green panel block (west low block with columns) 5 storeys.

### (b) colours
- (sampled: File:Fuji_Broadcasting_Center_and_Aqua_City_Odaiba,_Tokyo,_North_view_20190419_1.jpg, overcast spring, 1280-px thumb) tower frames/ribs (light precast): #c4c4c6 (box 160,110-360,300 mask min>150) and #c2c1bf (east tower, box 640,290-870,440 mask min>150); glass bays between ribs #6f828c (box 255,120-290,300, plain median); sphere: sunlit upper face #a8a5a5 (box 385,185-500,260, mask min>110), overall median #615f5d (box 385,185-500,300; the sphere is a dark satin bronze-grey, with a lighter band at the equator windows); lift core/blue-grey tower #60676e (box 582,240-616,380); mint low block #a6b5ae (box 110,365-730,420 mask min>150) / plain #949fa1; sky #dbdee7.
- Model: ribs #c4c4c6, glass #6f828c-#7f8d98, sphere satin titanium #8c8884 with a metallic roughness 0.35, mega columns/corridors #bdbcba.

### (c) night
- Sphere lit warm white from inside (observation windows at the equator) and the grid corridors lit in white/amber; the lift core is lit blue-white; the sphere has a seasonal/commercial lighting (est.).

### (d) OSM: as above (FCG way 287770734; sphere way 287906915; corridor relations 3816597-3816599).
### (e) Commons
- https://commons.wikimedia.org/wiki/File:Fuji_Broadcasting_Center_and_Aqua_City_Odaiba,_Tokyo,_North_view_20190419_1.jpg ; https://commons.wikimedia.org/wiki/File:20190322_Odaiba_Fuji_Television_Network_building.jpg

---------------------------------------------------------------------------------------------------------------

## 5. National Diet Building  (centre tower 35.675911,139.745051 (way 331852164); whole building relation 3361370 centroid 35.675911,139.744876)

### (a) geometry
- JA wiki: width (length) 206.36 m, depth 88.63 m; wings 20.91 m (69 shaku), central tower 65.45 m (216 shaku); steel-reinforced concrete clad in granite (3 kinds; mostly pink "Kurahashi-jima cherry granite" 桜御影 from Hiroshima, hence 議院石); floor area 52,165 m2. Built 1920-1936. Tower design said to derive from the Mausoleum at Halicarnassus (JA).
- Plan: a symmetric block; centre front porch with 6 columns (photo: colonnade 6 columns, ~ 20 m wide); two wings (House of Representatives east, Councillors west, each 2 courtyards), the central tower rising behind the porch.
- Tower (from OSM building:part ways + the frontal photo):
  - tower plinth block 30.8 x 30.8 m (true; bbox 37x37), to ~28 m (OSM relation 4657362: height 28, centre 35.675920,139.745001) - this is the wide block with the colonnade at its front and a pediment/frieze band;
  - upper stage 22.9 x 22.3 m (true; bbox 27x27) (OSM way 331852164, height 47 m, centre 35.675911,139.745051): square drum with a band of 7 round-headed windows (arched openings with granite mullions) on each face and a rich cornice; ~ 28-47/52 m;
  - STEPPED PYRAMID roof: base ~18.1 x 18.4 m (true; bbox 22x22) (way 331852176, height 63 m, roof:shape pyramidal), starts ~ 47-52 m, rising to ~ 60 m, then a small lantern block (~5-6 m square, with slit windows and a flat/stepped cap) up to 65.45 m. Step count from the photo (upscaled crop): about 15 narrow tread steps (fine stepped courses), each ~ 0.5 m high, i.e. a smooth "stepped" pyramid; I would model it as a pyramid with ~15 steps or a 4-sided pyramid with a stepped texture.
  - wings: OSM relation parts at 21-29 m (bbox values, not true sizes: e.g. relation 4657358 21 m (119x213 bbox, base all), 4657359 8 m, 4657357 25 m, 4657356 29 m gabled 65x167, 4657363 27 m 66x205, 4657365 27 m 108x205, 4657355 24 m 72x57, 4657354 22 m 24x38, 4657360 23 m 18x25), brought to ~21 m at the eave of the wings (JA 20.91 m) with the ridge/central blocks at 24-29 m.
- Whole building OSM bbox 127 x 213 m; true min-rectangle 101.9 x 207.4 m (long axis at bearing 13 deg, i.e. nearly N-S; which side is the front is not verified from OSM).
- Branch buildings (not part of the figure): way 135739169 (衆議院分館), 135739170, 135739171.

### (b) colours
- (sampled: File:Diet_of_Japan_Kokkai_2009.jpg, 1280-px thumb, clear midday sun from the front-left): wing walls (white granite) #e4e3e3 (box 320,535-440,560), shaded wing #d1d3d5 (box 840,545-935,565), centre porch wall #e9e8e8 (box 450,500-500,520); tower middle stage wall (warm pink-beige) #cdbdb1 (box 540,360-560,410) and upper stage #bbb3ac (box 560,285-580,310); lantern block #b4a89d; pyramid roof (pink granite steps) #e0ccc5 (box 595,235-685,270). Sky #2f63b8-ish.
- Model: wings #dddbd8, tower stages #cdbdb1, pyramid roof #d9c3ba (a pinker, slightly darker stone than the walls), lantern #b4a89d. Windows dark #2a2d33. The pyramid roof is STONE, not tile.

### (c) night: floodlit from the front in warm white (est.; the Diet is lit at night; the pyramid glows pale pink-white).
### (d) OSM: relation 3361370 (名 国会議事堂, National Diet Building); tower parts way 331852164, way 331852176; plinth relation 4657362; wings relations 4657354-4657366; annexes ways 135739169-135739171.
### (e) Commons: https://commons.wikimedia.org/wiki/File:Diet_of_Japan_Kokkai_2009.jpg ; https://commons.wikimedia.org/wiki/File:%E5%9B%BD%E4%BC%9A%E8%AD%B0%E4%BA%8B%E5%A0%82%E3%83%BC%EF%BC%91.JPG

---------------------------------------------------------------------------------------------------------------

## 4. NTT Docomo Yoyogi Building  (OSM way 137189971 centroid 35.684406,139.703128; the brief's point 35.684450,139.702880 is ~230 m west of it, in the park)

### (a) geometry
- 240 m (tower top), 272 m with the derrick (JA: 32 m derrick, 1.85 t). Designed like an Empire State. The "building" proper is ~ 25 floors / ~150 m (14 floors office + 11 floors machine rooms); above is a hollow stepped steel spire clad in metal panels, 50 storeys equivalent, reached by stairs only. Completed Sept 2000.
- OSM: way 137189971 (name ドコモ代々木タワー, height 153, 32 levels(!), true 35.5 x 44.5 m (rot 11 deg), area 1,402 m2, building:colour #AAA5A8) = the shaft. Stepped spire as OSM parts (centre ~35.684400,139.703105): way 380315128 (true 26.3 x 32.8 m, to 177 m, 37 levels), way 380315127 (26.4 x 26.3, to 192 m), way 380315126 (19.6 x 20.1, to 206 m), way 380315125 (13.3 x 13.3, to 221 m), way 380315124 (7.6 x 7.4, to 240 m, 50 levels); the OSM bbox values (31x36, 31x31, 23x24, 16x16, 9x9) are rotated-box artefacts (rotation 11-12 deg). Node 1655901181 (35.684393,139.703123) man_made=tower. From the photo (File:NTT_DoCoMo_Yoyogi_Building_2009_cropped.jpg) the profile is: shaft to ~150 m (with 3 corner pilaster tiers), clock stage ~150-176 m (width ~ 30), then steps at ~176, 191, 206, 217 m, top block 240 m (about 8 x 8 m), then a red/white lattice mast (~ 31 m) to ~272 m (the derrick). Spire is shifted: the steps are cut more on the east/west and the north face; chamfered corners.
- Clock: ONE clock, on the NORTH face (JA wiki: 北側に直径約15 mの大時計; the brief's "4 faces" is wrong), 15 m dia, Roman numerals, centre ~ 162 m (est. from the photo: the dial spans ~ 155-170 m), hands ~1 t each, installed Nov 2002. Was the tallest clock tower until Abraj Al-Bait (2011).
- Plan: roughly triangular site (JR freight yard); the shaft is ~ 40 x 45 m with chamfered corners and a vertical glass slot on the front.

### (b) colours
- (sampled: File:NTT_DoCoMo_Yoyogi_Building_2009_cropped.jpg, 1200-px view x1.07, warm low sun, clear blue sky) shaft front face #59463d (box 580,950-640,1500), sunlit side face #786b5e (box 690,1000-745,1400), shaded left #403737 (box 440,950-480,1400); spire cladding #8d7968 (box 500,500-560,560) and top block #9a816f (box 570,260-625,330) (both warm-lit grey metal; true cladding is neutral grey, est. #a5a29f); clock face #7e6c5d; sky #4f7ba7. OSM building:colour #AAA5A8.
- Model: shaft dark grey-brown stone/tile #5c4b43 with a darker vertical glazing slot; spire #a09d9a light metallic grey with thin lighter vertical mullions; mast red/white bands.

### (c) night: the spire is floodlit; the clock is lit and the building has coloured lighting (File:NTT_Docomo_Yoyogi_Building_clock_tower_at_7_pm_with_color_lighting...jpg downloaded as doc_night.jpg, colours est.). Mast has aviation lights.
### (d) OSM: ids above. PLATEAU outline: not checked (the repo notes that PLATEAU has a stepped solid to 240.6 m).
### (e) Commons: https://commons.wikimedia.org/wiki/File:NTT_DoCoMo_Yoyogi_Building_2009_cropped.jpg ; https://commons.wikimedia.org/wiki/File:NTT_Docomo_Yoyogi_Building_clock_tower_at_7_pm_with_color_lighting_Shibuya_Tokyo_Japan.jpg

---------------------------------------------------------------------------------------------------------------

## 7. Tokyo Station Marunouchi building  (relation 4856156 centroid 35.681203,139.766003; bbox 122 x 316 m)

### (a) geometry
- Tatsuno Kingo, 1914, restored to 3 storeys in 2012. Length 330 m (JA wiki) / 335 m (brief) / OSM outline 316 m long (relation 4856156 min-rect 316 x ~ 36 m (rot 73 deg); the building runs NNE-SSW, long axis at bearing ~ 17 deg east of north).
- Heights (OSM, unverified against surveys): main wings: gable part 22 m with 5 m roof => eave ~ 17 m, ridge 22 m (relation 4856157, #B22222 walls, black roof); hipped pavilions 22 m (relations 4856162, 4856165); pavilion pyramid roofs 28 m with 11 m roof (relation 4856158: ways 342276675 north pavilion true 37.9 x 29.1 m c 35.682235,139.766366; 342276676 south pavilion 36.8 x 29.5 m c 35.680532,139.765720; long sides along bearing 73 deg = the building's own axis, which runs ~ 17 deg east of north): i.e. pavilion eave ~ 17 m, roof top 28 m; domes: relation 4856159 height 36 m, roof 9 m (ways 342276671 north dome true 20.7 x 20.7 m centre 35.682220,139.766375, and 342276674 south dome 20.8 x 20.7 m centre 35.680515,139.765732): dome springs at ~27 m and tops at 36 m (plus the finial/cross to ~ 44 m: in the photo the lantern spire adds ~ 8 m, est.). Central entrance (皇室専用 pavilion, "車寄": relation 4856160, 10x9 m, 7 m high at 35.681411,139.765922). Centre round roofs relation 4856161 (13x27 m twice, h 23 m, roof:height 2, shape round) = barrel-vault central roof section at ~35.681294,139.766403 and 35.681339,139.766224; central gable block ~ 22 m.
- The domes: octagonal (the interior ceilings are octagonal, 8 zodiac reliefs; the exterior dome is also an 8-faced pointed dome on an octagonal drum with 8 dormers/oculus; the drum has window tiers), diameter at the base ~20.7 m (OSM true min-rect 20.7 m across).
- Facade: 3 storeys, red brick with white granite bands (Inada granite; central porch and ground course Kitagi granite), 15 mm facing bricks. The 3rd-floor pavilion tops are white granite with copper balustrades.
- The central pavilion (entrance): a double-height arched recess, mansard-gabled slate roof with a round oculus window in the pediment.

### (b) colours
- (sampled: File:Tokyo_Station_(Marunouchi_Building).jpg, 1280-px thumb, summer midday, partial cloud, frontal) brick (mask r>g+40): #955b4c (left wing box 100,480-480,600), #925442 (right wing box 1040,470-1260,600), #965947 (central pavilion box 705,430-770,540); white granite upper pavilion #bebcb6 (box 1040,320-1140,400, mask min>150); slate roof #565353 (centre box 660,310-780,350 mask max<140), #4b4445 (left wing box 240,395-490,420); cupola cap #847976 (box 1060,250-1120,275, plain median); sky #e1e7ee.
- (sampled: File:Tokyo_Station_Marunouchi_North_2012_09.jpg, backlit, deep shade) brick #482014-#50271c (shade), slate dome #1a1718, copper roof #2a1812: shade values only; the copper roofs in 2012 were brown (new) and will green over decades, so use dark red-brown #7b4a3a for the fresh copper (est.) or verdigris #6f9a8a if you want an aged look (est.).
- Model: brick #955b4c, bands/granite #cfc9bc (est.; sampled #bebcb6 in light shade), slate #4b4647, copper #6b3d30.

### (c) night: warm-white floodlit (the brick glows orange-gold #d9915a est.), domes lit, 3-D projection events; the 2007-12 restoration lit it with lamps ~ 2,700-3,000 K (est.).
### (d) OSM ids above (outline 4856156 with parts 4856157-4856165; way 145407027 49x159 m is the central wing mass; way 878600072 is Sapia/Yaesu(?) skip).
### (e) Commons: https://commons.wikimedia.org/wiki/File:Tokyo_Station_(Marunouchi_Building).jpg ; https://commons.wikimedia.org/wiki/File:Tokyo_Station_Marunouchi_North_2012_09.jpg

---------------------------------------------------------------------------------------------------------------

## 8. Sensō-ji  (OSM way ids; centre of hall 35.714656,139.796766)

### (a) geometry
- Five-storey pagoda (五重塔): OSM way 173154770 (name 五重塔, height 53.32, 5 levels, pyramidal, start_date 942, centroid 35.714120,139.796017, true 18.1 x 18.4 m (rot 84 deg), area 331 m2 = the platform/base). JA wiki: current tower rebuilt 1973 on the WEST side of the hall (the old one was east), RC with aluminium tile roofs (titanium tiles from June 2017), base platform ~5 m, tower itself ~48 m (so 53.3 m with platform; the sōrin finial is part of the 48 m: est. 10-12 m long gilt rings and a sphere top). Roof widths per storey (est. from the photo, plan ~ 17 m at the first roof): 17, 15.5, 14, 12.5, 11 m with eaves overhang 3.5 m each; the finial: a gilt sōrin of 9 rings/ "dew basin" and a ball (est. 11 m).
- Main hall Hondō (観音堂/本堂): OSM way 91008673 (name 本殿, Senso-ji Main Hall, height 29.4, building=shrine, start_date 1958, centroid 35.714656,139.796766, true 48.3 x 48.6 m (rot 84 deg), area 2,319 m2 including the porch/ 3-storey RC hall). Reinforced concrete, irimoya-zukuri (入母屋造) with a 向拝 porch, 3 x 8? bays: the hall body about 45 m x 45 m (est.), height 29.4 m to the ridge (OSM). Roof: titanium tiles (2009-10 re-roof, 3 colours, to look like clay: mottled dark grey #39373d to brown-grey). Walls vermilion, lanterns 4.5 x 3.5 m.
- Hōzōmon (宝蔵門): OSM way 573271561 (name 宝蔵門, height 21.7, 2 levels, gatehouse, start_date 942, centroid 35.713935,139.796641, true 31.4 x 18.1 m (rot 86 deg; includes the side wings/stairs), 568 m2) (node 10566912937 35.713821,139.796779); EN wiki: 22.7 m tall, 21 m wide, 8 m deep; irimoya two-storey nijūmon (1964 RC), titanium tile roofs (2007), Niō statues, 3 lanterns (centre 3.75 m x 2.7 m).
- Kaminarimon: OSM nodes 291756002 and 1691781729 (35.710868,139.796230 / 35.710855,139.796331), no outline in OSM; EN wiki: 11.7 m tall, 11.4 m wide, 69.3 m2 footprint (so ~ 11.4 x 6.1 m), 8-legged kirizuma (gabled) gate, RC 1960, lantern 3.9 m x 3.3 m (700 kg).
- Nakamise: 250 m approach between Kaminarimon and Hōzōmon, shop fronts 4-5 m high (RC, 1925).

### (b) colours
- Vermilion: (sampled: File:H%C5%8Dz%C5%8Dmon_and_five-story_pagoda.jpg, 1280-px thumb, clear sunny day) #c45947 (mask r>150,g<110,b<90,r-g>80, box 560,600-1280,960, lower gate level), #b55e51 (upper level, box 600,150-1280,560); true colour is a strong vermilion, model with #c8432b (est.); roof tiles (sampled) #393740 (Hozomon/foreground temple roof, box 120,770-480,880, mask max<150) and pagoda roof tiles #4a383b (box 60,300-380,370); white plaster panels ~ #e8e6e1 (est., sample was too small), green signboard (est. #2e6b5a), gilt finial (est. #d4a93c).
- The Hondō roof ~ dark grey-brown with a blue-ish sheen, ridge ends gilt. Walls: vermilion columns & eaves with white-plaster panels between.

### (c) night: all four (Hondō, pagoda, Hōzōmon, Kaminarimon) are floodlit warm by Ishii Motoko since 2003 (sunset-23:00): vermilion glows amber-orange (est. #ff9a50); Nitenmon changes red/blue/purple (LED, 2010).
### (d) ids above. 
### (e) Commons: https://commons.wikimedia.org/wiki/File:H%C5%8Dz%C5%8Dmon_and_five-story_pagoda.jpg ; https://commons.wikimedia.org/wiki/File:Kaminarimon1.jpg ; https://commons.wikimedia.org/wiki/File:Senso-ji_Temple_@_Asakusa_(13824517393).jpg

---------------------------------------------------------------------------------------------------------------

## 10. Tokyo International Forum glass hall  (OSM way 287736170 centroid 35.676777,139.763360; whole complex way 144508545 centroid 35.676814,139.763609)

### (a) geometry
- Rafael Vinoly, 1996/1997. Glass hall (ガラス棟): ship-shaped, curved to follow the Yamanote track curve; OSM building:part way 287736170: true min-rect 206.3 x 24.4 m (rot 75 deg; the hull is curved so the true max width is ~ 30 m and the chord ~ 206 m), height 61 m (so ~ 207-210 m long, ~ 30 m max beam: the OSM height 61 vs the quoted 57.7-60 m); east block (Halls B, C, D) ways 287736171 (47 m) and 287732855 (60 m, 116x175 m bbox); whole complex 137 x 223 m bbox area ~13,955 m2 (OSM 36 m "public" outline). Total building area 21,000 m2 (JA: 建築面積).
- Structure: two massive concrete "legs" (the end cores) support the boat-shaped hull: a 2-sided curved steel-truss ("keel") roof of two tapered steel masts (the large 'mast' columns) with suspended cables; roof truss as inverted-boat ribs of tubular steel; the glass facade with cable-braced glass ("ship-keel"); the roof's ridge is a bow-curved line (higher at the middle ~60 m, lower at the ends ~ 45 m: est.), an atrium with bridges at 3-4 levels.
- Photo (File:Tokyo-International-Forum_Glass-Building_Outside.jpg) shows the glass building's flank as a vertical glass wall with a sloping roof; white-painted truss.

### (b) colours
- (sampled: File:Tokyo-International-Forum_Glass-Building_Outside.jpg, 1280-px thumb, clear sky, sun low-ish) glass reflecting sky #89a7bd (box 560,170-820,300); lower glass seeing into the interior/trees #425153 (box 480,420-700,520); white truss/frames #eef6fb (box 480,100-800,350, mask min>200); the neighbouring precast tower (Hall block) #666c78 (box 120,300-330,600). Model: glass #7f9fb8 with 0.35 transmission, truss white #f2f4f6.

### (c) night: the glass hall is lit from within in warm white, the steel truss visible as a bright white skeleton (est.).
### (d) OSM ids above. ### (e) Commons: https://commons.wikimedia.org/wiki/File:Tokyo-International-Forum_Glass-Building_Outside.jpg ; https://commons.wikimedia.org/wiki/File:Interior_of_the_Tokyo_International_Forum_Glass_Building,_Japan.jpg

---------------------------------------------------------------------------------------------------------------

## 15. The two missing towers

### 15a. Tokyo Midtown Nihonbashi: "Nihonbashi Nomura Mitsui Tower" (日本橋野村三井タワー, "The Tower"), C block of 日本橋一丁目中地区
- Sources: JA Wikipedia (東京ミッドタウン日本橋, 日本橋野村三井タワー), Mitsui Fudosan / Nomura RE press release of 21 Apr 2026 (prtimes 000001038.000051782), Impress Watch 2103270.
- Height ~284 m, 52 floors above, 5 basement floors; completion end of September 2026 (the OSM site relation says opening_date 2026-09), grand opening autumn 2027. Address 日本橋一丁目5番1号. Developer Mitsui Fudosan + Nomura Real Estate; design Nikken Sekkei; builder Shimizu.
- Site C block ~15,560 m2; C-block total floor area ~374,800 m2; standard office floor ~1,370 tsubo (=~4,530 m2 rentable; 1,373 tsubo on floors 27, 37, 38; 955 tsubo on floor 26). My estimate of the tower footprint: ~65-75 m square-ish rounded rectangle, ~5,000-5,500 m2 (est., derived: 374,800 m2 / ~(52 floors + podium) ~ 5,500 m2 per floor; the photo shows a wide rounded-rectangle shaft with 2 large-radius corners). The shaft is NOT slender: width:height ~ 1:4.
- Program by floors (JA wiki): B1-3F retail (connects to the Nihonbashi 1-chome Mitsui Building "South"); 5-8F MICE (2 halls, 12 conference rooms); 10-20F and 22-38F offices (sky gardens open at 10F and 21F); 39-47F Waldorf Astoria Tokyo Nihonbashi (197 rooms); 48-51F Waldorf Astoria Residences (71 units; lounge on 50F); top at 52F/rooftop plant.
- Other blocks: A block (reconstructed Former Nihonbashi Nomura Building, 1930, OSM way 187598501 centroid 35.683740,139.775101, 50 x 22 m, 7 levels) rebuilt as 4 floors above / 2 below, ~33 m; B block "Nihonbashi Riverside Terrace" 7 floors, ~32 m (OSM construction polygon way 910717425, 151 x 34 m, area 3,896 m2, centroid 35.683726,139.775539); D block = existing Nihonbashi 1-chome Mitsui Building (way 187598470, 121 m, 20 levels, 117 x 86 m bbox, centroid 35.682527,139.774611).
- Position (est.): OSM multipolygon relation 15339753 "日本橋一丁目中地区市街地再開発" (landuse=construction, opening_date 2026-09, alt_name 東京ミッドタウン日本橋) has outers way 750976828 (218 x 128 m bbox, area 17,182 m2, centroid 35.683210,139.775207: the C-block + part of the site) and way 910717425 (B block). The tower is inside the first outer: use 35.683210,139.775207 as the tower position (+-30 m; the tower is not mapped in OSM; the precise footprint could not be determined from sources I could reach). In the Jul 2026 photo it stands NORTH of the Nihonbashi Expressway/river bank, just east of Chuo-dori.
- Form (from the 19 Jul 2026 Commons photo, seen from the south): blue-tinted reflective glass curtain wall with a fine 1.2-1.5 m (est.) vertical mullion grid; the lower ~1/3 of the shaft is the full-width rounded rectangle; at ~55-60% of the height there is a single big setback on the right/east face (the shaft narrows by ~ 1/5), then the top 20 floors ~ narrower with chamfered/rounded corners; a crown of dark horizontal louvre bands (plant floors) and an inclined (hipped/pitched) top silhouette; low podium of curved glass (B block wing) with a sloping roof, 7 storeys.
- Colours: (sampled: File:Tokyo_Midtown_Nihonbashi（Nihonbashi_Nomura_Mitsui_Tower,_July_2026）.jpg, 19 Jul 2026 07:04, clear-ish morning, sky-reflecting) tower face reflecting deep sky #335a84 (box 640,640-880,900), upper face #778fa8 (box 640,350-780,520), face reflecting white clouds #9bacbc (box 410,500-520,800), crown band #85a1d0 (box 430,220-560,320), podium glass #a9c1d2 (box 960,900-1100,1200); sky #7c9acc. Model: glass base #6f8fb0 (the photo is a morning reflection; mid-day tint is more neutral blue-grey #7f93a8, est.), mullions #9aa4ad.
- Commons: https://commons.wikimedia.org/wiki/File:Tokyo_Midtown_Nihonbashi%EF%BC%88Nihonbashi_Nomura_Mitsui_Tower,_July_2026%EF%BC%89.jpg (local copy nb_tower.jpg)

### 15b. Grand City Tower Tsukishima (グランドシティタワー月島)
- Height 197.65 m (max 199.45 m), 58 floors above / 2 below; 1,284 units (1,285 under the rules); site 10,076.42 m2; building area 6,743.49 m2 (all blocks); floor area 144,276.80 m2; RC with partial steel, viscous-damper seismic isolation; builder Penta Ocean; Sumitomo Realty + Tokyo Tatemono + Daiwa House + Shutoken Fuenken Kenchiku Kosha; project: 月島三丁目北地区第一種市街地再開発事業 (association-built); completed 7 May 2026 (skyskysky.net; Blue-style says April 2026; moving in from Dec 2026). A block: tower + retail + childcare (58F, 197.65 m); B-1 block 6F (group home + shops); B-2 block 7F (56 homes). 25 shops at the ground levels facing the monja street (Tsukishima Nishi-nakadori) and the Sumida terrace.
- Position: 35.663154, 139.779584 (Blue-style listing coordinates); OSM outline of the whole district way 1158707581 (name グランドシティタワー月島, 141 x 143 m bbox, area 9,859 m2, centroid 35.662761,139.779586) - a site polygon, the tower itself is not mapped; way 1158707583 (37x33 m, 650 m2, centroid 35.663019,139.778407) is a small part (a B-block?). The tower stands between the monja street and the Sumida River in the NORTH part of the site.
- Plan shape and podium (est.): not found in any source I could open. Using the site/GFA: a tower floor of ~2,000-2,300 m2 (1,284 homes / ~54 residential floors ~ 24 homes per floor), so ~ 45-50 m x 45-50 m, probably a squarish/Y plan with balconies (est.); retail podium ~ 2-3 storeys + parking ~ 15 m (est.).
- Colours (est.): a residential tower: white/light-grey precast and balcony panels with glass railings, warm grey-beige #cfc8bc and mid-grey bands #8c929a; no photo of it was found on Commons (nothing sampled).

---------------------------------------------------------------------------------------------------------------

## 9. Sumida river bridges  (OSM man_made=bridge outlines; road carriageways are separate ways)

All distances are my computations from OSM way ends (lat,lon). Kachidoki, Eitai and Kiyosu are national Important Cultural Properties (2007).

| bridge | OSM outline / ways | ends (west-or-north end to east-or-south end) | length |
|---|---|---|---|
| Kachidoki-bashi (勝鬨橋) | man_made way 549492916 (arch, centroid 35.662333,139.774841); road/footway ways 228050647, 286507872 | (35.663203,139.774187) Tsukiji end -> (35.661420,139.775818) Tsukishima end (way 286507872); ways 228050647: (35.663083,139.773987)-(35.661308,139.775623) | ~247 m (JA: 246 m) |
| Eitai-bashi (永代橋) | man_made way 1060000228 (arch, centroid 35.676368,139.787370); road ways 168663963 / 168663968 | (35.676545,139.786578) west (Shinkawa) -> (35.676129,139.788578) east (Fukagawa) | ~186 m (JA: 184.7 m; width 25.0 m) |
| Kiyosu-bashi (清洲橋) | man_made way 856821159 (name 清洲橋, suspension, centroid 35.682362,139.791966; 172 x 123 m bbox, 4,876 m2); road ways 157238663 (carriageway), 157238674 and 666718110 (footways) | (35.682867,139.791024) Nihonbashi-Hakozaki (west) -> (35.681957,139.792765) Fukagawa (east) | ~187 m (JA: 186.3 m; width 22.0 m) |
| Chuo-ohashi (中央大橋) | man_made way 633292488 (suspension? tagged; centroid 35.671989,139.784277), road ways 131156055, 157296567 | (35.670787,139.784635) -> (35.672887,139.783561) | ~253 m; cable-stayed with two A... pylons (the photo shows a single slim inclined-pylon pair; the pylon is ~ 42 m? est.) |
| Shin-Ohashi (新大橋) | man_made way 1055853349 (cable-stayed, centroid 35.687445,139.792004); roads 54786435, 157292797 | (35.686794,139.790781)-(35.687886,139.792921) | ~228 m; single H/inverted-Y pylon, cable-stayed (1977) (pylon height est.) |
| Ryogoku-bashi (両国橋) | way 553536165 (arch, centroid 35.694356,139.788684) | - | - |
| Kuramae-bashi (蔵前橋) | way 585439312 (arch) centroid 35.701022,139.793329; roads 91689539 / 156575072 | (35.701297,139.792646)-(35.700637,139.794388) | ~173 m |
| Umaya-bashi (厩橋) | way 585439311 (arch, centroid 35.704372,139.795152) | | |
| Azuma-bashi (吾妻橋) | way 554057521 (humpback centroid 35.710177,139.798844) | | |
| Kototoi-bashi (言問橋) | way 1013424064 (humpback, 35.714103,139.803563) | | |
| Sakura-bashi (桜橋) | ways 48808274, 48808289 (an X-shaped pedestrian bridge, humpback; centroid 35.717509,139.806822 / 35.717295,139.806656) | (35.717180,139.807600)-(35.718046,139.806073) and (35.717688,139.805776)-(35.716810,139.807277) | ~168 m each leg (the two legs cross in an X over the river) |
| Aioi-bashi (相生橋) | way 508041946 (humpback, 35.667049,139.788247); roads 131156078 / 655092021 | (35.667863,139.789454)-(35.666364,139.787499) | ~242 m |

- Kachidoki-bashi (JA wiki): bascule bridge (1940; the central span opens up to 70 degrees in ~70 s; bascule leaf weighs 950 t with a 1,050 t counterweight), flanked at both ends by steel arch (through-arch/tied) spans; four bascule piers/towers (OSM ways 665324852, 665324855, 665324857, 665324860, each ~10x12 m, h unknown, at (35.662558,139.774843), (35.662366,139.774570), (35.661960,139.774941), (35.662154,139.775213)). Spans (JA wiki infobox): movable span 51.6 m (Chicago-type double-leaf bascule), fixed spans 86.0 m (steel solid-rib tied arch) at both ends; width 22 m; total ~ 246 m. Arch rise ~ 15 m (est. from the photo: rise ~ 1/5.5 of the span). Colour: very light warm grey/white (sampled: File:Sumida_River,_Kachidokibashi_Bridge,_Tokyo.jpg, hazy morning aerial, 1280-px thumb, bright mask min>150: arches #bfbcb2 (box 410,480-600,525) and #c9c4b8 (box 770,515-950,550), piers #c2bbae). Lit from 1998.
- Eitai-bashi: central span a through steel TIED ARCH (JA: 中央径間 下路式スチールアーチ), the first Japanese bridge with a span >100 m (JA text: 径間長100 m超; the commonly quoted figure is 100.8 m, not in the sources I opened), modelled on the Ludendorff (Remagen) Bridge; 184.7 m long, 25.0 m wide; the side spans are girder/truss approaches (~ 42 m each, est.), arch rise ~ 20 m (est.). Colour: pale light-blue/blue-grey (est. #9db7d3; I could not obtain a useful sample); lit bluish-white from sunset to 21:00 (JA wiki). Commons: File:2019-09-04_View_from_Eitai_Bridge_(Tokyo).jpg (night, Chuo-ohashi in view).
- Kiyosu-bashi: self-anchored (自碇式) suspension bridge with eyebar chains (not wire cables), modelled on the Hindenburg Bridge in Cologne; 186.3 m long, 22.0 m wide; main span ~ 91.4 m (est. from memory) with two portal-frame steel towers ~ 25-27 m above the deck (est.) and 2 side spans ~ 45 m; blue paint: sampled lamp post #6280b6 (File:Kiyosu-bashi_01.jpg, box 370,150-410,620, mask b>r+40) and railing #748caf (box 990,440-1280,600); the steel members are painted a light "Kiyosu blue" (est. #7f9fcf, a lighter value than the lamp). Lit since 2 Aug 2020.
- Chuo-ohashi (中央大橋, 1993): 2-span continuous steel cable-stayed bridge, 210.7 m long, 25.0 m wide (JA wiki infobox); one A-frame/"Y" pylon per pier-line (est.), pylon height not found.

Commons file pages: Kachidoki https://commons.wikimedia.org/wiki/File:Sumida_River,_Kachidokibashi_Bridge,_Tokyo.jpg ; Kiyosu https://commons.wikimedia.org/wiki/File:Kiyosu-bashi_01.jpg ; Eitai https://commons.wikimedia.org/wiki/File:2019-09-04_View_from_Eitai_Bridge_(Tokyo).jpg

---------------------------------------------------------------------------------------------------------------

## 14. Named towers: facade table for the landmark-facade list
Method: where a Commons photo existed I sampled one box over the main tower face (the "body" box in a contact sheet, 400x600 px tiles; boxes converted back to the 1280-px thumbnails). All are plain medians (mixed glass + mullions, with whatever the glass reflected) unless a mask is named. Photo conditions: see the file. Module/bay widths: I did not find published bay widths for any of these in the sources I could reach; the values below are visual (est.) from the photos (count of mullion lines per tower width).
Contact sheet (git-ignored): <project>/demos/data/tk-m4l-photos/contact_towers.jpg

| tower (height, year) | facade system (from photos) | module (est.) | colour (sampled / est.) |
|---|---|---|---|
| Marunouchi Building ("Maru Biru" tower, 179.7 m, 2002) | grey-brown stone/precast piers and spandrels with continuous blue-green glass bands; a 3-4 floor crown of louvres/plant; stone podium (3 storeys, tan-brown) | ~ 1.35 m window module, vertical stone fins (est.) | stone side #7c7974 (sampled: File:Marunouchi_Building.JPG, midday, partly cloudy, box on the left stone piers); whole body median #798284; blue-green glass bands #728b95 (mask b>r+10) |
| Tokiwabashi Tower (212 m, completed 2021; NOT the 385 m Torch Tower still under construction) | rounded-rectangle shaft with a warm bronze-champagne metal-and-glass skin: closely spaced horizontal glass bands between bronze-grey spandrels and vertical fins on the long faces (fin lines visible all the way up); dark 4-storey rounded base with the lobby; crown with a slim parapet | est. 1.5 m, 4-floor groupings | body #889196 (sampled: File:Tokiwabashi_Tower.jpg, clear afternoon, 1280-px thumb, box 441,525-817,1330 of the original-scale thumbnail), shaded fin side #baacb5 (box 360,659-454,1330); (the east/west sun faces read warm bronze) |
| Toranomon Hills Mori Tower (247 m, 2014) | tall dark-blue-tinted low-reflection glass with fine WHITE vertical fins/mullions running full height (strong vertical stripes, about every 3 m); the plan chamfers/tapers inward near the top so the long faces slope; large glass-and-steel low "Glass Rock" base and a dark podium with the TORANOMON HILLS sign; thin horizontal floor lines | ~ 1.5 m glass bays, white fins ~ every 2 bays (est.) | glass body #3b4d66 (sampled: File:虎ノ門ヒルズ森タワー.jpg, Sep 2019, blue sky, looking up from the base, 1280-px thumb, box 276,331-993,1099), white fins #c8d8f3 (mask min>170) |
| Roppongi Hills Mori Tower (238 m, 2003) | cylinder-ish rounded rectangle plan with 2 big curved sides, silver-grey aluminium + glass in 4-floor horizontal banding; the roof is a stepped silver crown | est. 1.4 m | (est.) glass #9fb3c4 bands #b8bec4; far shot only (File:Tokyo_Tower_and_Roppongi_Hills_Mori_Tower_seen_from_Hamamatsucho.jpg), body reads silver-blue #a8bccb at 10 px so not sampled |
| Tokyo Midtown Tower (248 m, 2007) | grey-green mirror curtain wall with horizontal bronze/tan louver bands every 2-3 floors, and pale vertical aluminium fins; top slab with a roof of louvres | est. 1.5 m, bands every 4 floors | body #95999b (sampled: File:Midtown_Tower_from_Tokyo_Midtown.jpg, overcast, from below with sun glare; box 409,680-889,1480), tan louvres #9e8774 (mask r>b+25) |
| Tokyo Metropolitan Government Building No.1 (243.4 m, 1991) | Gothic stepped masses: base block, a mid block, the buildings split into TWIN TOWERS above ~130 m (OSM: 4 towers' stacks: north tower centre 35.689785,139.691640, south tower 35.689222,139.691781, each true 46.5 m square to 176 m, 43.5 m to 207 m, 36.3 m to 243 m (bbox reads 48/44/44; rotated); the towers' centres are ~64 m apart; in the photo the notch between the towers starts at ~130 m (= 33rd floor), shoulder steps at ~165 and ~185 m, observation floors at 202 m (45F), roofs 243 m; each tower top is a square frame ~14 m thick around an open recess with a drum (antenna dishes, 4 small mast stumps with red/white lights) | granite-faced precast with 1.6 m x ~3.6 m module? (est.): window grid ~ 2 m, deep reveal | (sampled: File:Tokyo_Metropolitan_Government_Building_2012.JPG, clear sky, evening/morning side light) front block pale warm-grey #b6baba (box 480,1000-630,1500), lit stone mask #d2d4d0 (min>150), shaded side tower face #252d39 (box 860,800-980,1500), crown frame #6f7d95; OSM building:colour #CCCFDB; ids: way 89877471 (building, centroid 35.689491,139.691712, 61x112 m), parts 568387704-568387709 |
| Mode Gakuen Cocoon Tower (203.65 m, 2008) | white diagonal steel lattice (a "cocoon" diamond grid of ~ 2 floors per diamond) over blue-green glass, elliptical plan tapering at both ends, rounded top | diamond module ~ 8 m wide x 8 m high (est.; the lattice has ~ 5-6 diamonds around the visible half, ~ 20 diamonds in total vertically) | glass #5a6a6e / lit glass #52656c (sampled: File:Mode_Gakuen_Cocoon_Tower_2018.jpg overcast, box on the glass band; mask b>r+5), lattice white #e1e2e9 (mask min>205). The evening blue-sky photo (File:Mode_Gakuen_Cocoon_Tower_in_the_evening_with_blue_sky_Tokyo_Japan.jpg, downloaded as f_cocoon2.jpg) shows the glass a strong blue; use #3d6a91 for blue sky reflections (est.) |
| Shibuya Scramble Square East Tower (229.7 m, 2019) | trapezoidal/stepped body with big rounded SE corner; teal-blue reflective curtain wall in a 4-floor grid with dark horizontal spandrels; a notched crown with a rooftop SKY deck frame | est. 1.5 m, visible 4-floor horizontal dividers | #3085a6 (sampled: File:SHIBUYA_SCRAMBLE_SQUARE_East_Tower.jpg, clear blue sky, box 371,249-915,1305, plain median) |
| Dentsu Building (213 m, 2002) | Jean Nouvel's knife-edge wedge: very pale champagne-white glass with a fine horizontal grid; curved sail-like end faces; the tower top rises to a sharp ridge | est. 1.5 m, horizontal frit bands | #b8b8a0 body (sampled: File:Dentsu_Headquarters_Building_in_Shiodome,_Tokyo,_2019_-_868.jpg, overcast, sunlit highlight), highlight #b3bbca (mask min>150) |

Notes on the first row: I mislabelled the Marunouchi Building's year while drafting: it opened 2002 (tower 179.9 m, Mitsubishi Estate); the 2007 redevelopment was the Shin-Marunouchi Building. The photo sampled is of the 2002 tower.

---------------------------------------------------------------------------------------------------------------

## 12. Wako (Ginza 4-chome, Seiko House Ginza)  (OSM way 103509469, centroid 35.671552,139.765035)
- Designed by Watanabe Jin, completed 12 Jun 1932 (2nd Hattori clock tower building), neo-Renaissance; 7 storeys, OSM height 28 m, true min-rect 32.8 x 28.5 m (rot 138 deg), area 887 m2 (the lot ~ 900 m2). Clock tower: OSM building:part way 1341775164 ("Clock Tower", 6x6 m, 28-38 m), way 1341815191 (13 x 9 m, 28-30 m, tower base on the cornice), way 1341815951 (finial 38-40 m). So tower top 38 m, spire to ~40 m; clock face ~ 2.5-3 m dia (est.), dial at ~ 33-34 m. Plan: a quarter-circle/ rounded corner facing the 4-chome crossing (the crossing is SE of the building, bearing ~ 135 deg from the entrance? In the photo the curved front looks across the crossing, with the tall clock tower rising in the middle of the curved arc), two straight wings along Chuo-dori (north-west) and Harumi-dori (north-east ...).
- Elevation (photo): a rusticated 2-storey base (granite, darker #857765 in shade), 4 storeys of piers in cream stone with window rows, a deep cornice, and a top attic/colonnade of arched windows (the 7th floor under the cornice), then the tower (square stage with arched belfry louvre, clock at the top, a small pinnacle).
- Stone: pale cream-beige granite/marble-faced (sampled: File:Ginza_Wako_20241021.jpg, bright sunny noon, box 520,330-700,560 mask min>160) #fef6ea (very sunlit; plain median #f9eede; right wing #f7e7d5; clock tower #fbf3e8). Model: #e9dfcf (est.; the sun overexposure raises the sampled value), base #857765.
- Night: warm-white floodlighting of the facade and the clock face lit.
- Commons: https://commons.wikimedia.org/wiki/File:Ginza_Wako_20241021.jpg ; File:Wako_Ginza.jpg

## 13. Nikolai-do (Holy Resurrection Cathedral, Kanda-Surugadai)  (OSM relation 4080936 centroid 35.698036,139.765469)
- JA wiki: building area ~800 m2; 35 m high verdigris dome; Greek-cross plan with a central octagonal drum and dome; brick/stone; copper roof; completed Feb 1891 (design by the Russian architect Mikhail Shchurupov with Josiah Conder involved; JA says Conder's actual role is unclear); the bell tower collapsed in 1923 and the dome was damaged; rebuilt 1927-29 by Okada Shinichiro with a taller drum for the dome and a lowered bell tower.
- OSM parts: way 273258751 dome (true 15.8 m dia, top 30 m, roof:shape dome, centroid 35.698008,139.765536), way 273260342 drum (17.3 m square-ish octagon, 20 m, 35.698004,139.765533), way 273260343 body/mansard (18.9 m, 18 m, 35.698005,139.765527); bell tower dome way 553266118 (5x5 m, 23 m, centroid 35.698096,139.765305, the western tower), small dome way 553267628 (2x2, 7 m); relation bbox 44 x 36 m; chapel relation 7904409 (11x9 m, 35.697928,139.765286). The tallest point (cross) ~ 35 m (JA).
- Colours: sampled (File:Tokyo_Resurrection_Cathedral_March_2019.jpg, clear spring day, 1280-px thumb): dome verdigris #3f7267 (box 470,205-700,290 mask g>r+15), small dome #507f76; walls cream plaster #d6cec3 (box 420,560-780,720 mask min>150), dark brown/charcoal stone bands and cornice #35362e (mask max<110, box 405,360-750,400); drum brick-dark #453d34. Model: dome #4a8174 with ribs, walls #d8d0c4, bands #3d3a33, doors teal #2f7a6d.
- Commons: https://commons.wikimedia.org/wiki/File:Tokyo_Resurrection_Cathedral_March_2019.jpg

## 11. Masts
- Nippon Television Tower (日本テレビタワー, Shiodome): OSM way 151481850 (name 日本テレビタワー, height 192.8 m, 32 levels, 80 x 102 m bbox, centroid 35.664293,139.759900, 2003). From the photo (File:Nittele_tower_Shiodome_2007-3.jpg, downloaded as ntv1.jpg): a dark tinted-glass tower with fine horizontal louver lines; a huge exposed steel truss ("exoskeleton" bracing in the notch on the corner, round-tube chord members with K-bracing), a glass lift box at the base; the roof is crowned by a curved steel arch frame (a swoosh at the top), no tall antenna mast. Colours (sampled from that file by eye only; not measured): dark grey-green glass, chords dark grey #4a4d52 (est.).
- TEPCO head office (Uchisaiwaicho 1-1-3): no OSM tower and no height/antenna found in the sources I could reach (est.: ~ 120 m roof plus small mast; not verified).
- NHK Broadcasting Center: OSM says 36 m over 23,509 m2 (repo notes); not researched further.


---------------------------------------------------------------------------------------------------------------

## S. Supplement: published numbers from the JA Wikipedia infoboxes (wikitext of 6-7 Oct 2026)
- Tokyo Tower: official height 332.6 m (quoted 333; 351 m asl); site 15,577 m2, building area 4,470 m2 (the FootTown footprint), total floor area 24,875 m2, "60 floors" (the lattice's nominal count), built 29 Jun 1957-23 Dec 1958; coordinates 35 39 31 N, 139 44 44 E = 35.658611, 139.745556. The EN wiki gives the Top Deck at 249.6 m and the Main Deck at 150 m (those are the asl-ish brochure values; the floors above ground are 120-130 m and ~224 m).
- Tokyo Skytree: 634 m; site 36,844 m2 (whole complex), building area 31,833 m2, floor area 229,410 m2; 13 lifts; coordinates 35 42 36.5 N, 139 48 39 E = 35.710139, 139.810833 (the OSM centre 35.710051,139.810713 is 10 m south-west of that).
- Fuji TV HQ: height 123.450 m, 25 floors above, 2 basements, 1 penthouse; site 21,102 m2, building area 14,171 m2, floor area 141,825 m2; completed June 1996 (opened 10 Mar 1997); coordinates 35 37 37 N, 139 46 28 E = 35.626944, 139.774444 (which is the sphere/lattice, i.e. about the centre of the bridge between the towers). Designed by Tange Kenzo's office with Kobori Takuji Laboratory.
- National Diet: site 103,007 m2, building area 13,356 m2, floor area 53,464 m2 (JA infobox; the 52,165 m2 in the body text is an older figure); 3 floors above + 1 basement (central tower 4 floors, penthouse top = 9th); coordinates 35 40 33.2 N, 139 44 41.9 E = 35.675889, 139.744972.
- Docomo Yoyogi: 27 floors above, 3 below, 1 penthouse; 240 m; site 6,273 m2; building area 2,832 m2; floor area 51,122 m2; completed Sep 2000; design NTT Facilities; steel frame. Coordinates 35 41 6 N, 139 42 12 E (a rough value; the OSM shaft centre is 35.684406,139.703128).
- Tokyo International Forum: height ~60 m (Hall block + glass hall), site 27,375 m2, building area 20,951 m2, floor area 145,076 m2; hall block 11 floors above + 3 below + 1 penthouse; completed 31 May 1996.
- Kachidoki-bashi: movable span 51.6 m (Chicago-type double-leaf bascule), fixed spans 86.0 m (solid-rib tied arches), width 22 m (JA wiki). Eitai-bashi: central span through steel arch, side spans steel girders, width 25.0 m, length 184.7 m. Kiyosu-bashi: length 186.3 m, width 22.0 m, self-anchored eyebar-chain suspension. Chuo-ohashi: 2-span continuous steel cable-stayed, 210.7 m, 25.0 m wide.
- Rainbow Bridge: see section 3 (spans 111.5 + 570 + 111.5 m; width 29.0 m; tower 126 m TP; soffit TP 51.266 m).

## TRUE SIZES quick table (minimum-area rectangles of the OSM outlines, measured on the vertices; use these, not the bboxes quoted above)
| feature | OSM id | true W x D (m) | rot (deg) | h (m) |
|---|---|---|---|---|
| Tokyo Tower Main Observatory | way 313815246 | 29.5 x 29.5 | 56 | 120-130 |
| Tokyo Tower Special Observatory | way 313815247 | 12.4 x 12.4 | 2 | 241-246 |
| Tokyo Tower segment 40-53 / 53-66 / 66-77 / 77-88 / 88-97 / 97-106 / 106-120 / 130-161 / 161-188 / 188-217 (base side) | rels 17133572-78, 69-71 | 52.2 / 41.5 / 33.6 / 30.8 / 28.1 / 25.2 / 22.5 / 19.4 / 15.3 / 11.9 | 56 | |
| Tokyo Tower FootTown outline | rel 4247313 | 52.7 x 76.7 | 56 | 20 |
| Skytree outline (lower tower) | way 288269147 | 56.6 x 56.6 | 24 | 634 |
| Skytree Tembo Deck block | way 362351415 | 35.2 x 35.3 | 88 | 290-350 |
| Skytree Galleria block | way 288269148 | 26.6 x 26.5 | 178 | 410-450 |
| Skytree gain tower | way 362351414 | 5.7 x 5.7 | 72 | to 634 |
| Rainbow Bridge pylon legs | ways 1348279695/96/98/1348279700 | 4.9 x 5.0 | 69 | 126 |
| Rainbow Bridge pylon cross beams (upper 117-126, lower 27-31) | 1348279694/701, 1348279697/699 | 27.8 x 5.0 | 69 / 159 | |
| Rainbow Bridge Shibaura anchorage (0-30 / 30-45 m) | ways 540211904 / 1348272539 | 45.4 x 68.7 / 45.4 x 47.4 | 69 | 30 / 45 |
| Rainbow Bridge Daiba anchorage (0-30 / 30-45 m) | ways 1348279690 / 1348279691 | 68.8 x 45.5 / 46.9 x 45.4 | 158 | 30 / 45 |
| Fuji TV sphere | way 287906915 | 31.7 dia | | 96-130 |
| Fuji TV corridor slabs (3 levels) | rels 3816597/98/99 | 98.5 x 29.4 | 34 | 56-63, 82-88, 107-113 |
| Fuji TV west tower / east tower / east upper part | rels 3816594 / 3816590 / 3816588 | 68.1 x 36.7 / 42.1 x 53.5 / 32.0 x 42.2 | 34 | 120 / 124 / 119 |
| Diet plinth / upper stage / pyramid | rel 4657362 / ways 331852164 / 331852176 | 30.8 sq / 22.9 x 22.3 / 18.1 x 18.4 | 12 | 28 / 47 / 63 |
| Diet whole | rel 3361370 | 101.9 x 207.4 | 13 | |
| Docomo shaft / steps 177, 192, 206, 221, 240 | way 137189971 / 380315128, 127, 126, 125, 124 | 35.5 x 44.5 / 26.3 x 32.8, 26.4 x 26.3, 19.6 x 20.1, 13.3 sq, 7.6 x 7.4 | 11 | 153 / 177...240 |
| Tokyo Station north / south dome | ways 342276671 / 342276674 | 20.7 x 20.7 | | 27-36 |
| Tokyo Station north / south pavilion | ways 342276675 / 342276676 | 37.9 x 29.1 / 36.8 x 29.5 | 73 | 28 |
| Sensoji pagoda base / Hondo / Hozomon | ways 173154770 / 91008673 / 573271561 | 18.1 x 18.4 / 48.3 x 48.6 / 31.4 x 18.1 | 84 / 84 / 86 | 53.3 / 29.4 / 21.7 |
| Forum glass hall | way 287736170 | 206.3 x 24.4 (curved) | 75 | 61 |
| Wako | way 103509469 | 32.8 x 28.5 | 138 | 28 (+tower to 38-40) |
| Nikolai-do dome / drum / body | ways 273258751 / 273260342 / 273260343 | 15.8 / 17.3 / 18.9 | | 30 / 20 / 18 |
| TMG north & south towers (3 stacks each) | ways 568387704-709 | 46.5 / 43.5 / 36.3 sq | | 176 / 207 / 243 |
| Nippon TV Tower | way 151481850 | 35.1 x 105.0 (incl. podium) | 146 | 192.8 |
