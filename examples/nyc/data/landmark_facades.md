# Manhattan landmark facades: photo research

Companion to `landmarks_manhattan.csv`, the per-building heights and footprint points.

**Height conventions.** The CSV `height_m` is the extrusion height: the main roof, or the parapet of the main volume. Spires, masts and crowns are listed in the CSV `notes` and in the profiles below, so they can be modelled separately. The CTBUH Skyscraper Center is the height source. Where CTBUH, Wikipedia and OSM disagree, the entry says so.

**Colours.** Colours marked "sampled" were measured from Wikimedia Commons photos with PIL `ImageStat`: mean and median of a box, with the file page URL, the box in percent of the image, the image size and the conditions. Anything not measured is marked **(est.)**. The scripts are in this folder (`sample.py`, `split.py`, `grid.py`, `sheet.py`, `o_sheet.py`), the thumbnails are in `photos/`, and every box of the other-towers pass is logged in `o_samples.log`.

Sections:
1. Must-have landmark towers: 1WTC, ESB, Chrysler, 432 Park, Central Park Tower, One Vanderbilt, Steinway, 30 HY and Flatiron.
2. Other skyline-defining towers.
3. Manhattan facade palettes by building type, and rooftop clutter.
4. Open gaps: must-haves, then others. Bridges and the Statue of Liberty are in `bridges_statue.md`.

## Must-have landmark towers

### How these numbers were made

**Colours.** Colours marked "sampled" come from Wikimedia Commons photos: the search API, then the standard thumbnail at 1280 px wide (the original when it was smaller). For each box the scripts computed the mean and median with PIL `ImageStat` (`sample.py`). `split.py` also gave the mean of the brightest 30 % and the darkest 30 % of pixels by luminance. That separates the stone, frame or spandrel colour ("bright30") from the window or reflection colour ("dark30"). Boxes are given as percentages of the image, `x0,y0,x1,y1`, with the origin at top left. The scripts and thumbnails are in `landmarks/`: `sample.py`, `split.py` and `photos/`. The EXIF times on Commons are camera-local and sometimes wrong, so the lighting conditions below come from looking at each photo. Glass colour depends heavily on the sky it reflects and the angle it is seen from, so treat glass values as ranges. Anything not measured is marked **(est.)**.

**Heights.** Heights come from the CTBUH/Skyscraper Center export in `raw/ctbuh.json`: roof, architectural top, tip and highest occupied floor.

**Loft profiles.** The loft profiles come from the OSM `building:part` models in the parent's `raw/osm_60.json` (all parts ≥ 60 m in Manhattan), cut horizontally with shapely by `m_profile.py`. `scale` is sqrt(section area / reference area), taken about the centroid. W×D is the minimum rotated rectangle of each section. Paired entries at the same fraction are hard setbacks. Fractions are of the **roof** height given in each entry unless stated otherwise. OSM misses parts under 60 m tall, and its heights can differ from CTBUH, so the podium heights marked (est.) are not measured.

---

### One World Trade Center (285 Fulton St)
- **Heights (CTBUH):** roof (glass parapet) 416.97 m, highest occupied floor 386.5 m, architectural top with spire 541.3 m, tip 546.2 m. The observatory is at 1,268 ft (386.5 m) on floors 100–102 (Wikipedia).
- **Facade:**
  - Unitized glass curtain wall with cable-net glass walls at the lobby. Curtain wall made by Benson Industries, glass by Viracon.
  - Each curtain-wall panel is **13.33 ft (4.06 m) tall** (Wikipedia), which is the typical floor-to-floor height.
  - Panel width is about 1.5 m (5 ft) **(est.)**, not verified.
  - The base (floors 1–19, 185 ft / 56.4 m) is windowless concrete. It is clad in stainless-steel panels with angled glass fins, lit from behind by LEDs at night.
- **Colours (sampled):**
  - **Blue sky, midday sun:** left face mean `#495e7a` (median `#495c78`), right face `#315a84` (median `#2b5a87`). Photo: [One_World_Trade_Center_from_New_York_Harbor,_New_York_City.jpg](https://commons.wikimedia.org/wiki/File:One_World_Trade_Center_from_New_York_Harbor,_New_York_City.jpg), 1280×1920 thumb, boxes `42,32,49,55` and `51,32,58,55`, taken 2026-04-17 about 11:34 from the harbour, blue sky with cumulus.
  - **Overcast:** darker face `#52698a` (median `#516d94`), bright sky-reflecting face `#919aad` (median `#9ca7be`). Photo: [New_York_City_…_One_World_Trade_Center_--_2012_--_6566.jpg](https://commons.wikimedia.org/wiki/File:New_York_City_(New_York,_USA),_One_World_Trade_Center_--_2012_--_6566.jpg), 1280×2048 thumb, boxes `42,40,50,62` and `52,40,58,62`, taken 2012-07-30 around 09:06 under a flat grey sky. The building was topping out then, but the sampled boxes are on the finished glass.
  - **Suggested use:** base glass `#3f5f82`, sky-lit faces blending up to `#9aa6bc`. Base stainless panels `#9a9c9e` **(est.)**.
- **Massing / loft:**
  - The base is a **61 m (200 ft) square, 0–56.4 m (0–0.135 of roof)**, extruded straight.
  - From 56.4 m to the parapet at 417 m the corners are chamfered back into **eight tall isosceles triangles**, which makes an elongated **square antiprism**:
    - The bottom is the 61 m square.
    - The top (parapet) is a square **rotated 45°**.
    - Halfway up the section is a regular octagon.
  - The top square's side is ≈ 61/√2 ≈ **43 m** if its corners sit over the midpoints of the base edges, which matches the "8 isosceles triangles" description **(geometry derived, est.)**.
  - **Geometry recipe.** Each base corner B_i connects to the two adjacent top corners T_j. With s = (z−56.4)/(417−56.4), the section at height z is the octagon with vertices (1−s)·B_i + s·T_j.
  - **Equivalent uniform scale (heightFraction:scale):** `0:1.0, 0.135:1.0, 0.351:0.984, 0.568:0.935, 0.784:0.848, 1.0:0.707`. Rotation is needed to get the silhouette right; a plain scaled prism loses the faceted look.
  - OSM check: the tower part is 65×65 m to 417 m (way 713565776, parts 783285127–130).
- **Parapet, ring and spire:**
  - A glass parapet screen rises about 30 m above the top floor (386.5 → 417 m).
  - A circular support ring sits at 417–420 m, about 35.6 m across (OSM part 241029248, 995 m²).
  - Above it is the 408 ft (124.3 m) cable-stayed mast, sculpted by SOM with Kenneth Snelson. OSM models it as a pyramid with a 5.8 m base, from 420 to 541 m (part 241029247). Mast colour: light grey steel `#b8bcc0` **(est.)**.
- **Night:**
  - An intense vertical light beam shoots from the spire tip, reaching over 1,000 ft (Wikipedia).
  - The mast is lit white, or in colours for occasions **(colours not verified)**.
  - LEDs light the base from behind its panels. Office floors glow cool white.
- **Refs:** the two photos above, and [One_World_Trade_Center_and_Lower_Manhattan_skyline_from_the_harbor,_New_York.jpg](https://commons.wikimedia.org/wiki/File:One_World_Trade_Center_and_Lower_Manhattan_skyline_from_the_harbor,_New_York.jpg).

### Empire State Building (350 Fifth Ave)
- **Heights:**
  - Roof 381.0 m (1,250 ft, the top of the 102nd-floor observatory, which caps the mooring mast).
  - Top floor 373.1 m. Tip 443.2 m (1,453 ft 8 9/16 in).
  - The 86th-floor observatory is about 320 m **(est., commonly quoted 1,050 ft)**.
  - Only floors 1–85 are offices. Floors 86–102 form the "spire" (the mast), which has no intermediate levels.
- **Facade:**
  - Indiana limestone panels; granite at the ground floor.
  - Windows project slightly from the stone and sit in stainless-steel frames, with nickel-chrome steel mullions and aluminium spandrels between floors.
  - The tower bays alternate narrow and wide piers, with sets of one, two or three windows per bay (LPC 1981, via Wikipedia). There are 6,514 windows.
  - Floor-to-floor is about 3.7 m **(est.**: 381 m / 102 floors = 3.74 m).
  - Window pitch is about 1.5 m, with piers every 2–3 windows **(est.)**.
- **Colours (sampled):**
  - **Blue sky, low sun (≈19:11 in October, strongly warm):**
    - Lit face: mean `#999597`, median `#9e9b9f`; limestone (bright30) `#d2cec3`; windows and mullions (dark30) `#545364`.
    - Other face: mean `#8d8b8f`; bright30 `#d0ccc4`; dark30 `#454556`.
    - Sky `#144c94`.
    - Photo: [Empire_State_Building_From_Rooftop_2019-10-05_19-11.jpg](https://commons.wikimedia.org/wiki/File:Empire_State_Building_From_Rooftop_2019-10-05_19-11.jpg), 1280×2548 thumb, boxes `17,42,26,62` and `31,42,41,62`.
  - **Hazy afternoon, aerial:**
    - Sunlit face: mean `#928678`, median `#998977`.
    - Shaded side: `#646364`.
    - Photo: [Empire_State_Building_(aerial_view).jpg](https://commons.wikimedia.org/wiki/File:Empire_State_Building_(aerial_view).jpg), 846×1270 original, boxes `43,35,60,55` and `62,35,64,55`, taken 2017-09-25 around 15:02 in haze.
  - **Suggested use:**
    - Limestone `#cfc9bc` (sampled bright30, slightly warmed).
    - Window band `#4c4b58`.
    - Tower-average albedo at distance `#958f8c`.
- **Massing / loft:**
  - Reference footprint: the lot, 129×60 m (7,656 m², OSM way 34633854), with H = 381 m.
  - The **LPC lists setbacks at floors 5 (60 ft deep), 21, 25, 30, 72, 81 and 85**.
  - OSM sections (parts 137425125–145, 265932618), as W×D in m:
    - 5-storey base 129×60, 0–≈24 m **(est.)**
    - 94×50 to 75 m
    - 71×50 to 90 m
    - 68×41 to 115 m
    - 56×41 to 255 m
    - 52×37 to 290 m
    - 45×29 to 310 m
    - 43×27 to 320 m
    - 37×21 to 330 m
    - then the mast
  - heightFraction:scale: `0:1.0, 0.063:1.0, 0.063:0.745, 0.197:0.745, 0.197:0.652, 0.236:0.652, 0.236:0.586, 0.302:0.586, 0.302:0.519, 0.669:0.519, 0.669:0.475, 0.761:0.475, 0.761:0.409, 0.814:0.409, 0.814:0.386, 0.840:0.386, 0.840:0.316, 0.866:0.316`.
  - Mast (86th–102nd floors): `0.866:0.17, 1.0:0.11`. That is a stepped, faceted mast about 16 m wide at its base, narrowing to about 10 m at the 102nd-floor drum **(est.; OSM uses a 13 m pyramid)**.
  - The section is elongated, so scale X and Y separately (W×D above) rather than uniformly. The tower is centred on the lot (OSM centroid offsets are constant).
  - **Antenna:** 62 m (203 ft) from 381 m to 443.2 m. Base about 5 m, tapering to about 1 m **(est.; OSM gives an 8 m base)**. Colour: light grey `#c8c8c8` **(est.)**.
- **Night:**
  - Since 2012 the upper tower and mast (lit from the 72nd floor up) use about 1,200 computer-controlled LED fixtures with 16 million colours (Wikipedia).
  - Default is white; there are colour schemes for holidays and sports, and seasonal schedules. The 72nd–86th floor setbacks and the mast are floodlit.
  - The lower shaft shows only office windows.
- **Refs:** the two photos above, and [View_of_Empire_State_Building_from_Rockefeller_Center_New_York_City_dllu.jpg](https://commons.wikimedia.org/wiki/File:View_of_Empire_State_Building_from_Rockefeller_Center_New_York_City_dllu.jpg) (dusk, green lighting).

### Chrysler Building (405 Lexington Ave)
- **Heights (CTBUH):** roof 281.9 m (top of the crown), highest occupied floor 252.3 m, architectural top and tip 318.9 m. The visible needle above the crown is about 37 m (derived: 318.9 − 281.9). The often-quoted 185 ft (56 m) "vertex" includes the part hidden inside the crown **(not verified)**.
- **Facade:**
  - Steel frame with masonry infill. White brick with grey and black brick bands and zigzags at floors 24–27.
  - Black Shastone granite at the ground floor, white Georgia marble on floors 2–4.
  - The windows sit in a flush grid without sills. Floors 16–24 have vertical white-brick piers with aluminium spandrels.
  - The crown and needle are clad in "Nirosta" 18-8 stainless steel with triangular sunburst windows.
  - Ornaments: gargoyles and hood ornaments on floor 31, eagles on floor 61. 3,862 windows in total.
  - Floor-to-floor is about 3.7 m **(est.)**; window pitch about 1.4 m **(est.)**.
- **Colours (sampled):**
  - **Blue sky, high sun, shaft:** lit face mean `#b0ae9e`, median `#dcd9c2`; brick (bright30) `#f0eedf`; windows (dark30) `#403f36`. Other face mean `#bab8a6`, median `#dad8c3`. Photo: [Chrysler_Building_by_David_Shankbone_Retouched.jpg](https://commons.wikimedia.org/wiki/File:Chrysler_Building_by_David_Shankbone_Retouched.jpg), 1036×3055, boxes `36,45,48,62` and `52,45,64,62`. Note that this image is retouched.
  - **Blue sky, crown in partial shade:** stainless steel reflecting the sky reads `#6f7776` (median `#717a77`), same photo, box `44,18,56,27`.
  - **Warm late sun on the crown:** crown `#998b79` (median `#9a8870`); brick below `#83796a`; sky `#166180`. Photo: [Chrysler_Building_NYC-20090519-RM-094845.jpg](https://commons.wikimedia.org/wiki/File:Chrysler_Building_NYC-20090519-RM-094845.jpg), 1280×1819 thumb, boxes `40,33,55,45`, `30,65,45,80` and `80,10,95,30`.
  - **Hazy daylight, seen from the Empire State Building:** crown `#888a8f`, shaft `#909091`. Photo: [Chrysler_Building_-_05.jpg](https://commons.wikimedia.org/wiki/File:Chrysler_Building_-_05.jpg), 1280×1707 thumb, boxes `52,36,60,46` and `50,55,62,65`, taken 2012-07-29 around 13:38.
  - **Suggested use:**
    - White brick `#e6e3d4`.
    - Window grid `#403f38`.
    - Stainless crown: metalness about 1 with roughness about 0.3, base colour `#b8bcbd`. It reads `#707876`–`#9a8b79` depending on the sky.
- **Massing / loft** (reference is the section below 70 m, 52×51 m ≈ 1,985 m²; H = 282 m):
  - The lowest 16 floors rise from the lot line, with a U-shaped light court above floor 4.
  - Wikipedia gives setbacks at floors 16, 18, 23, 28 and 31, then none until floor 60, above which the plan becomes a Maltese-cross shape leading into the crown.
  - OSM sections:
    - 52×51 m to 70 m
    - 47×45 m to 80 m
    - 47×36 m to 91 m
    - shaft 35×28.6 m to 185 m, then 35×28.6 m / 866 m² to 199 m
    - eagles and transition 200–229 m, about 30×28 m
    - square crown core 22.2 m, 229–282 m
  - heightFraction:scale: `0:1.0, 0.248:1.0, 0.248:0.908, 0.284:0.908, 0.284:0.75, 0.323:0.727, 0.323:0.708, 0.656:0.708, 0.656:0.668, 0.706:0.668, 0.706:0.59, 0.812:0.587, 0.812:0.496`.
  - Crown: seven concentric terraced arches (a cruciform groin vault) narrowing from the 22 m square to about 5 m: `0.87:0.42, 0.93:0.31, 0.97:0.20, 1.0:0.10` **(est. from the photo silhouette)**.
  - Each terrace carries rows of triangular windows, so a sunburst texture is advisable.
  - OSM crown parts: 260904072 (core, pyramidal) and 260904081–096 (the rounded arches).
  - **Needle:** 282 → 319 m, about 2 m at its base down to a point **(est.)**, OSM part 196647417.
- **Night:** White V-shaped (chevron) fluorescent tubes outline about 120 triangular crown windows (added 1981, part of the original design), plus coloured floodlights for special schemes. The needle is dimly lit. The crown is dark during Audubon "Lights Out" migration periods.
- **Refs:** the three photos above.

### 432 Park Avenue
- **Heights (CTBUH):** roof 416.3 m, top floor 392.1 m, architectural top 425.7 m (the top parapet and mechanical screen; OSM 425.5, way 463593207). 85 storeys, numbered up to 96.
- **Facade:**
  - Exposed **white-cement cast-in-place concrete lattice**, a regular grid of **10 ft (3.05 m) square windows**.
  - Each elevation has six windows per floor. The floor plate is a **93 ft (28.35 m) square**, so the bay module is **4.72 m**.
  - **Floor-to-floor is 15 ft 6 in (4.72 m)**, so each bay is a square module of 4.72 × 4.72 m (all from Wikipedia).
  - The tower is divided into **12-storey blocks separated by open double-height mechanical windbreaks**. Each windbreak has two tiers of six unglazed openings per side, with lit concrete mechanical cylinders visible inside.
- **Colours (sampled):**
  - **Evening sun (≈18:36 in July):**
    - Lit face mean `#a09888`; concrete (bright30) `#e9d8c5`, warm from the low sun; windows (dark30) `#444138`.
    - Shaded face mean `#5f656d` (median `#555e6c`).
    - Photo: [432_Pk_Av_2020-07_jeh.jpg](https://commons.wikimedia.org/wiki/File:432_Pk_Av_2020-07_jeh.jpg), 1280×2275 thumb, boxes `47,20,56,45` and `37,20,46,45`.
  - **Bright overcast / high haze:**
    - Face mean `#838f91`; concrete (bright30) `#d9e1e0`; windows (dark30) `#313d41`.
    - Sky `#bfd0e1`.
    - Photo: [432_Park_Avenue_August_2024.jpg](https://commons.wikimedia.org/wiki/File:432_Park_Avenue_August_2024.jpg), 1280×576 thumb, box `56,10,65,90`, taken 2024-08-03 around 11:54.
  - **Suggested use:** concrete `#dcdcd6`, glass `#353f44`, with about 65 % concrete by area at a distance (3.05 m windows in a 4.72 m grid means about 42 % glass).
- **Massing / loft:**
  - A pure square prism, 28.5 m square (OSM 28.8×28.1), from grade to the roof: `0:1.0, 1.0:1.0`.
  - The retail podium to the east is low (a few storeys), with a tinted glass facade.
  - The windbreaks are double-height (about 9.4 m) open bands where the facade is recessed and dark (see-through). There are 5 of them, spaced every 12 storeys plus 2 (≈ 66 m ≈ 0.159 H), at about `0.21, 0.37, 0.53, 0.69, 0.85` of H **(est. positions; verify on a photo before using)**.
- **Night:** A permanent nightly illumination scheme, since 14 November 2016, lights the windbreaks: the open mechanical floors glow as white bands every 12 storeys. The apartments are sparsely lit.
- **Refs:** the two photos above, and [432_Park_Avenue_November_2024_006.jpg](https://commons.wikimedia.org/wiki/File:432_Park_Avenue_November_2024_006.jpg).

### Central Park Tower (225 West 57th St)
- **Heights (CTBUH):** roof 461.9 m, top floor 431.8 m (1,417 ft), architectural top and tip 472.4 m (1,550 ft). 98 storeys, numbered to 136. About 300 ft of the height is mechanical space.
- **Facade:**
  - Aluminium and glass unitized curtain wall (Permasteelisa, about 12,000 panels), divided vertically by **flush stainless-steel "fins" arranged like pinstripes**.
  - Satin-finish horizontal spandrel bands at each floor **(est.)**.
  - The base (Nordstrom) on 57th and 58th Streets has fluted, laminated glass panels in a serpentine "wave" pattern.
  - The east face, over the Art Students League, is clad in **zinc** to cut glare; it weathers to matte.
  - Floor-to-floor about 4.3 m for apartments **(est.)**; bay about 1.5 m **(est.)**.
- **Colours (sampled):**
  - **Hazy blue sky, early afternoon (distant, from Rockefeller Center):**
    - Lit face `#889dba` (median `#8aa0bf`); other face `#637692` (median `#5d7290`).
    - Fins and spandrels (bright30) `#a1b4cf`; glass (dark30) `#536682`.
    - Sky `#9cc1ef`.
    - Photo: [Central_Park_Tower_April_2021.jpg](https://commons.wikimedia.org/wiki/File:Central_Park_Tower_April_2021.jpg), 1280×2276 thumb, boxes `44,15,48.5,35` and `50,15,55,35`, taken 2021-04-24 around 13:31.
  - **Overcast:**
    - Faces `#858e9c` and `#556274`; bright30 `#98a0ae`; dark30 `#3a485b`.
    - Sky `#aeb5c4`.
    - Photo: [Billionaires'_Row_2020_(4to3).jpg](https://commons.wikimedia.org/wiki/File:Billionaires%27_Row_2020_(4to3).jpg), 1280×1708 thumb, boxes `46,15,50,45` and `51,15,55,45`, December 2020.
  - **Close-up worm's-eye view under a blue sky** (mostly reflected sky, so do not use for distant views): `#447dcd`. Photo: [Central_Park_Tower_November_2024.jpg](https://commons.wikimedia.org/wiki/File:Central_Park_Tower_November_2024.jpg).
  - **Suggested use:** glass `#5f7390` (overcast `#4a586b`), with pale pinstripe fins `#a8b4c6`.
- **Massing / loft** (reference is the OSM outline of the whole lot, 3,401 m², way 261509934; H = 461.9 m). OSM sections:
  - Podium, full lot, to about 37 m **(est.; retail floors 1–7)**.
  - Tower 41.5×37.9 m to 89 m.
  - **Cantilever**: 89–163 m, the tower pushes about 8.5 m (28 ft) east over the Art Students League. Wikipedia says the cantilever starts about 290 ft (88 m) up, set back 80 ft from the street. The section grows to 1,311 m² (38×50 m).
  - Main shaft about 30.9×29.5 m, 163–433 m, with small steps at 237, 332 and 342 m.
  - Top, 433–466 m: 29.6×22.5 m, stepped back on one side.
  - Crown screen and spire to 472 m. OSM relation 14745243 / way 1107961665 (glass) and a metal part (way 1107961667) at 471 m.
  - heightFraction:scale: `0:1.0, 0.08:1.0, 0.08:0.56, 0.193:0.56, 0.193:0.62, 0.275:0.62, 0.275:0.576, 0.353:0.576, 0.353:0.515, 0.719:0.50, 0.937:0.482, 0.937:0.428, 1.0:0.428`. Then the crown screen to 1.022 (472 m).
  - The shaft centroid is offset about 17 m east of the CTBUH point. Use the OSM part polygons rather than scaling the lot outline.
- **Night:** Crown lighting is **not verified**. Photos show only lit apartment windows and a dim crown; add a subtle white crown glow at most.
- **Refs:** the three photos above.

### One Vanderbilt (1 Vanderbilt Ave)
- **Heights:** roof 392.6 m (CTBUH; Wikipedia gives 1,301 ft / 396.5 m), highest occupied floor 330.1 m, spire tip 427.0 m (1,401 ft). OSM glass parts reach 397 m and the spire 427 m (way 1470380434).
- **Facade:**
  - Unitized glass curtain wall (Permasteelisa: 8,743 pieces in 1,060 shapes) with floor-to-ceiling vision glass up to **22 ft (6.7 m)** on the tall trading floors.
  - **Ventilated glazed terracotta spandrels** between storeys: 34,845 tiles by Boston Valley Terra Cotta, cream and white in homage to Grand Central's Guastavino tile.
  - A wedge-shaped void at the base (the lobby ceiling slopes 50–110 ft).
  - Typical floor-to-floor about 4.5 m **(est.)**; bay about 1.5 m **(est.)**.
- **Colours (sampled):**
  - **Afternoon sun (≈16:02 in April, from Top of the Rock):**
    - Shaded face mean `#5d6676` (median `#666e7f`); spandrels (bright30) `#868fa0`; glass (dark30) `#2d3543`.
    - Lit face mean `#7e8691`; terracotta spandrels (bright30) `#c7ccd2`; glass (dark30) `#363f4d`.
    - Photo: [One_Vanderbilt_April_2023.jpg](https://commons.wikimedia.org/wiki/File:One_Vanderbilt_April_2023.jpg), 1280×1920 thumb, boxes `41,35,48,60` and `50,35,58,60`.
  - **Partly cloudy, close-up:** mean `#66788e` (median `#577190`). Photo: [One_Vanderbilt_007.jpg](https://commons.wikimedia.org/wiki/File:One_Vanderbilt_007.jpg), 1280×2847 thumb, box `30,50,70,80`, taken 2024-09-19 around 13:27.
  - **Suggested use:** glass `#34404f`, horizontal spandrel bands `#c8ccd0` (terracotta has a slight warm tint in sun, about `#d6d2c8` **(est.)**), distant average `#6e7786`.
- **Massing / loft** (reference is the lot outline, 3,864 m², way 265875648, about 65×60 m; H = 392.6 m):
  - The shaft is four interlocking volumes whose faces **taper continuously inward** as they rise; OSM models these as slanted-roof glass slivers. At the top is a cluster of glass pavilions at different heights, from the 60th-floor main roof to just above the 66th floor.
  - Up the east and west sides of the crown are **C-shaped screens**: exposed diagonal steel beams with aluminium strips, and terracotta on the horizontal beams of the east side.
  - Estimated loft: `0:1.0, 0.10:0.97, 0.50:0.80, 0.80:0.62, 0.84:0.50, 0.89:0.36, 1.0:0.27` **(est.: 0–0.8 read from the photo silhouette, top part from the OSM sections 48×50 m below 330 m, 41×36 m below 350 m and 17×17 m below 397 m)**.
- **Spire:** from the roof to 427 m, about 34 m tall, about 2.5 m square at its base (OSM), light grey `#d3d3d3`.
- **Night:** The crown and pavilions are lit, and the Summit observatory glows. Colour lighting schemes are **not verified**.
- **Refs:** the two photos above, and [One_Vanderbilt_42_Street.jpg](https://commons.wikimedia.org/wiki/File:One_Vanderbilt_42_Street.jpg).

### Steinway Tower (111 West 57th St)
- **Heights:**
  - Roof slab 1,257 ft 6 in = **383.3 m** (SHoP filing via Wikipedia; CTBUH 383.28).
  - Top floor 345.5 m.
  - Pinnacle 1,423 ft 7 in (433.9 m); architectural top 435.3 m (1,428 ft).
  - The width-to-height ratio is about 1:24 (Wikipedia; commonly also quoted as 1:23 or 1:24).
- **Facade:**
  - **North and south faces:** large glass curtain walls with slightly projecting **bronze mullions**. Above the top floor, the north face has reflective glass over the pinnacle's concrete walls.
  - **East and west faces:** narrow windows between vertical **glazed terracotta piers** in a wave-like extruded profile. The terracotta comes in 6 tones of white and beige and complements the limestone of Steinway Hall. Between the piers are bronze filigree mullions shaped like feathers.
  - Each terracotta pier stops at one of the pinnacle's setbacks. There are glass parapets above each setback.
  - At the base is the 16-storey limestone and brick **Steinway Hall** (1925), with a copper pyramidal campanile.
  - Floor-to-floor about 4.2 m **(est.)**; pier pitch about 1.5 m **(est.)**.
- **Colours (sampled):**
  - **Afternoon sun (≈16:18 in April), seen from Top of the Rock (south, glass face):** `#7a8fa7` (median `#86a5c3`) and `#728093`. Photo: [111_West_57th_Street_from_Top_of_the_Rock.jpg](https://commons.wikimedia.org/wiki/File:111_West_57th_Street_from_Top_of_the_Rock.jpg), 1262×4318, boxes `45,12,52,40` and `53,12,58,40`.
  - **Overcast (February, ≈12:09), close-up of the east face:**
    - Glass `#788193` (median `#8892a4`); frame (bright30) `#919bad`; glass (dark30) `#485162`.
    - Terracotta pier edge: mean `#8f8c88`, median `#a5a29e`, bright30 `#c2c0bc`.
    - Photo: [111_West_57th_Street_008.jpg](https://commons.wikimedia.org/wiki/File:111_West_57th_Street_008.jpg), 1280×2847 thumb, boxes `35,55,60,80` and `84,30,92,55`.
  - **Suggested use:**
    - Terracotta piers `#d8d2c4` in sun **(est., warmed from the sampled overcast `#c2c0bc`)**.
    - Bronze mullions `#6b5a45` **(est.)**.
    - Glass `#6d7c90`.
    - Steinway Hall limestone `#c9c1b0` **(est.)**.
- **Massing / loft:**
  - Steinway Hall (OSM way 265147970, 67 m tall) forms the base. The tower above is about **18.1 m wide (E–W, along 57th Street) × 24.9 m deep (N–S)** (OSM; Wikipedia gives the site as about 59×75 ft).
  - **The north face rises straight. The south face steps back** about every 15 m from about 200 m up.
  - Depth by height, from the OSM parts (1158813428–1158813432 …): 24.9 m (to 200 m), 23.1 (248), 21.4 (283), 19.7 (308), 18.2 (328), 16.2 (343), 14.5 (358), 12.8 (373), 11.1 (383), 9.4 (393), 7.7 (405), 6.0 (417), 4.3 m (435).
  - This is not a uniform scale. Keep the width at 18.1 m and the north face fixed, and move the south face. As depth fractions against height fractions of 435.3 m: `0.46:1.0, 0.57:0.93, 0.65:0.86, 0.71:0.79, 0.75:0.73, 0.79:0.65, 0.82:0.58, 0.86:0.51, 0.88:0.45, 0.90:0.38, 0.93:0.31, 0.96:0.24, 1.0:0.17`.
  - Above 383 m the setbacks form a stepped "feathered" pinnacle, with no occupied floors.
- **Night:** The pinnacle has a lighting scheme by L'Observatoire International (Wikipedia). It is a soft warm-white wash on the setbacks **(appearance est.)**.
- **Refs:** the two photos above, and [111_West_57th_Street_November_2024.jpg](https://commons.wikimedia.org/wiki/File:111_West_57th_Street_November_2024.jpg).

### 30 Hudson Yards
- **Heights (CTBUH):** roof 379.2 m, highest occupied floor 342.1 m, architectural top and tip 387.1 m. OSM tags the crown at 395 m (ways 1485848980–982), which does not agree with CTBUH. The **Edge** sky deck is at 1,100 ft (335 m) on the 100th floor.
- **Facade:**
  - KPF-designed unitized glass curtain wall. The top is sheared at a slant, and the glass facets fold toward it.
  - Vertical striation mullions **(est.)**; bay about 1.5 m **(est.)**; office floor-to-floor about 4.3 m **(est.)**.
  - Wikipedia has no facade specification for this building.
- **Colours (sampled):**
  - **Clear blue sky, noon (≈11:59 in October), looking west:**
    - The sun-facing face mirrors bright sky: `#d1dee9` (median `#d7e2eb`).
    - The shaded face is deep blue: `#355979` (median `#2a5070`); bright30 `#5e86a8`; dark30 `#183652`.
    - Edge soffit and deck, in grey shade: `#54626d`.
    - Photo: [Hudson_Yards_from_Hudson_Commons_(95131p)_(30_Hudson_Yards).jpg](https://commons.wikimedia.org/wiki/File:Hudson_Yards_from_Hudson_Commons_(95131p)_(30_Hudson_Yards).jpg), 1280×2416 thumb, boxes `36,25,48,55`, `52,25,64,55` and `40,13,55,18`.
  - **Overcast:** not sampled. Use about `#5d6c80` **(est., by analogy with Central Park Tower and One WTC under overcast)**.
- **Massing / loft** (reference is the OSM outline including the shops podium, 6,159 m², way 264656626; H = 379.2 m). OSM sections:
  - Podium full lot to about 0.1 H **(est.)**.
  - Tower 79×57 m to 140 m, then 74×57 m to 310 m.
  - 67×45 m from 310 m to the top.
  - The **Edge** deck, 335–340 m: a triangular cantilever that juts **80 ft (24 m)**, south per Wikipedia. It has 2.7 m glass walls leaning 6.6° outward and a 20.9 m² glass floor. The OSM section grows from 1,920 to 2,564 m² there.
  - heightFraction:scale: `0:1.0, 0.10:1.0, 0.10:0.82, 0.37:0.82, 0.37:0.806, 0.82:0.806, 0.82:0.558, 0.884:0.558`. Edge: `0.884:0.645, 0.897:0.645`, then `0.897:0.558, 1.0:0.558`.
  - The top is a **slanted (skillion) crown**: the roof plane falls from the 387 m tip to about 345 m on the opposite corner **(slope direction est.; check with a photo)**.
- **Night:** The Edge deck and the soffit under the triangle are lit **(est.)**. The office floors glow cool white.
- **Refs:** the photo above, [Pier_66_and_Hudson_Yards_(01473)p.jpg](https://commons.wikimedia.org/wiki/File:Pier_66_and_Hudson_Yards_(01473)p.jpg) and [30_Hudson_Yards_November_2024.jpg](https://commons.wikimedia.org/wiki/File:30_Hudson_Yards_November_2024.jpg).

### Flatiron Building (175 Fifth Ave)
- **Heights (CTBUH):** roof 86.9 m, architectural top 93.6 m. 22 storeys: the original 20, plus the penthouse and upper floor added later. OSM outline is way 264768896, 86 m, 1,002 m².
- **Status:** Renovation into 36–38 condominiums. **The scaffolding came off in early 2026.** In August 2025 the Landmarks Preservation Commission approved permanent night-time facade lighting.
- **Facade:**
  - The 3-storey base is **limestone**; the upper floors are **glazed terracotta** in Renaissance Revival style.
  - The facade has three parts like a column (base, shaft, capital), with a heavy cornice.
  - Bays are arranged in pairs: **18 bays each on the Fifth Avenue and Broadway sides, 8 bays on the 87 ft (26.5 m) 22nd Street end**, so the bay pitch is about 3.3 m.
  - The corners are rounded. The prow at 23rd Street has three sash windows per floor. There are oriel windows.
  - Floor-to-floor about 3.9 m **(est.)**.
- **Colours (sampled):**
  - **Winter sun, seen from the Empire State Building (lit west face):** mean `#aa9c8e` (median `#baa997`); terracotta (bright30) `#efe2cf`; windows (dark30) `#554842`. The shaded east face is `#898181`, with bright30 `#ada7a5`. Photo: [Edificio_Fuller_(Flatiron)_en_2010_desde_el_Empire_State_crop_boxin.jpg](https://commons.wikimedia.org/wiki/File:Edificio_Fuller_(Flatiron)_en_2010_desde_el_Empire_State_crop_boxin.jpg), 1280×2422 thumb, boxes `32,30,50,60` and `58,30,68,60`, January 2010.
  - **Backlit, late afternoon (after renovation, 2026-04-17 around 17:39):** mean `#646a73`; bright30 `#beb9bb`; dark30 `#222730`. Photo: [Flatiron_Building,_Fifth_Avenue,_Manhattan,_New_York.jpg](https://commons.wikimedia.org/wiki/File:Flatiron_Building,_Fifth_Avenue,_Manhattan,_New_York.jpg), box `45,20,58,40`.
  - **Midday from above, mostly shade:** mean `#69676b`. Photo: [New_York_City_…_Blick_auf_Flatiron_Building_--_2012_--_6459.jpg](https://commons.wikimedia.org/wiki/File:New_York_City_(New_York,_USA),_Empire_State_Building,_Blick_auf_Flatiron_Building_--_2012_--_6459.jpg), box `38,20,48,45`.
  - **Suggested use:** terracotta `#e2d6c2`, limestone base `#d6cdbb` **(est.)**, windows `#3a3634`, cornice shadow line `#6d6259`. OSM tags `building:colour=#CBC7AC`.
- **Massing / loft:** A **triangular prism** on the full lot outline: 26.5 m wide at the south (22nd Street) end, narrowing to a rounded prow about 2 m wide at 23rd Street **(prow width est.)**.
  - `0:1.0, 0.93:1.0` (cornice at about 81 m, overhanging by about 1 m), then `0.93:0.95, 1.0:0.95`.
  - A penthouse storey is set back on the upper roof: `1.0:0.6` up to 93.6 m **(est.)**.
  - The low one-storey "cowcatcher" retail wing sits at the north tip.
- **Night:** Previously there were only window lights. The facade washlighting approved in 2025 means a warm-white uplight on the terracotta **(installed state not verified)**.
- **Refs:** the three photos above.

---

### Open gaps (must-have towers)
- **Bay widths:** Curtain-wall panel widths for One WTC, Central Park Tower, One Vanderbilt, 30 Hudson Yards and Steinway are estimates (about 1.5 m). Only One WTC's panel height (4.06 m) and 432 Park's full grid (4.72 m bays, 3.05 m windows) are published values.
- **Floor-to-floor heights:** For the Empire State Building, Chrysler, Central Park Tower, One Vanderbilt, Steinway, 30 Hudson Yards and the Flatiron these are estimates (average height divided by floor count, or typical values).
- **One WTC geometry:** The top-square side (≈ 43 m) is derived from the "8 isosceles triangles" description, not from a published dimension. The parapet screen height of about 30 m is derived as roof minus top floor.
- **Empire State mast and antenna:** Widths are estimates. OSM's crude model disagrees with photos. The 86th-floor height (≈ 320 m) is the commonly quoted value and was not verified here.
- **Chrysler:** The crown terrace scale steps come from the photo silhouette. The base lot size is unknown because OSM has no Chrysler outline with a height tag. The 185 ft vertex figure is not verified.
- **432 Park windbreak heights:** These are estimates. Count them on a photo before using them.
- **One Vanderbilt taper:** Estimated from one photo. The OSM skillion slivers could not be sectioned correctly by the simple max-height method.
- **30 Hudson Yards:** The direction of the slanted-crown slope is unverified. OSM gives 395 m against CTBUH's 387.1 m. No overcast colour was sampled.
- **Night lighting:** Central Park Tower's crown lighting, One Vanderbilt's colour schemes and the Edge lighting are not verified. The Empire State lighting and 432's windbreak lighting are documented; the Chrysler crown lighting is documented except for how the needle is lit.
- **Flatiron:** The OSM building:part (463 m²) is smaller than the outline (1,002 m²), which looks like an incomplete part model. Use the outline. The post-2026 facade lighting is not confirmed as installed.
- **Terracotta warmth:** The Steinway terracotta in sun and the One Vanderbilt terracotta warmth are estimates. Only overcast or cool-light samples were taken.

---

## Other skyline-defining towers (short entries)

### How the colours were made (other towers)

- **Method.** I searched Commons through the API (`o_sheet.py`, a gentler copy of `sheet.py` that backs off on HTTP 429) and fetched each image at the standard 1280 px thumbnail width (1000 px or 1024 px when the original was smaller). I laid a 20×20 grid over each photo, picked boxes on the facade, and took the mean and median with PIL `ImageStat`.
- **Box notation.** Boxes are given as `x0,y0,x1,y1` in **percent of the image**. The full log of every box, including its pixel coordinates and standard deviation, is in `o_samples.log`.
- **Mean vs median.** The mean includes window/mullion/spandrel texture. On a gridded facade, the median is closer to the dominant surface (the stone, or the glass pane).
- **Estimates.** Anything marked "(est.)" is a judgement, not a sample.
- **Glass colour depends on the sky.** The same curtain wall reads about #4b72b0–#6b7da0 under a blue sky and about #7b7e83–#818a8d under overcast (see 35 HY, 53W53).

- **Heights.** These are the Wikipedia list values (architectural) unless another value is given. "roof" means the main roof, where Wikipedia's infobox has one. The parent CSV is the authority on heights; these are only for context.
- **Profiles.** A profile is a list of `heightFraction:scale` pairs about the footprint centroid. heightFraction is measured to the **main roof**, and scale is relative to the base footprint of the tower shaft. Everything in them is **(est.)**: I read them off photos and the setback floors published on Wikipedia, not from drawings.

---

### 35 Hudson Yards (SOM / David Childs, 2019; 305 m, 72 fl)
- **Facade:** A unitized glass curtain wall with **pale stone-clad vertical piers/fins**. The stone appears in the photos as thin light verticals over the glass; the stone type is unverified. The shaft steps back several times, and the top is a rounded, chamfered crown with a notch (two lobes). No module was published; from the photos it looks like ≈1.5 m (est.).
- **Colour, sampled:**
  - [35_Hudson_Yards_037.jpg](https://commons.wikimedia.org/wiki/File:35_Hudson_Yards_037.jpg) (2024-08-10 12:10, clear blue sky, 1280×2847):
    - sunlit face, box 50,55,68,80: mean #6b7da0, median #4f6693
    - other face, box 25,55,45,80: mean #607dab, median #4b77b8
    - sky: #4f7aba
  - [35_Hudson_Yards_033.jpg](https://commons.wikimedia.org/wiki/File:35_Hudson_Yards_033.jpg) (2024-08-02 12:27, bright overcast):
    - glass, box 30,55,60,80: mean #7b7e83, median #7c8087
    - sky: #b8c5d6
- **Profile (est.):** `0:1.0, 0.25:0.95, 0.45:0.88, 0.65:0.80, 0.85:0.72, 0.97:0.66, 1.0:0.60`. The top is rounded in plan, and the crown notch is ≈ the top 3 % of the height.

### 53W53 (Jean Nouvel, 2019; 320 m to the tip of the tallest spire, 77 fl)
- **Facade:** An exterior **concrete diagrid**; in the photos it reads as light grey-white members. Between the diagrid is a glass curtain wall of **5,747 triple-glazed panels** with aluminum frames and ventilation grates. The north and south faces **slope inward** to a sharp apex. The east and west faces are vertical.
- **Spires:** Five steel spires, above floors 21, 24, 73, 83 and 86 (Wikipedia).
- **Colour, sampled:**
  - [53_W53_fr_57_St_2020_jeh.jpg](https://commons.wikimedia.org/wiki/File:53_W53_fr_57_St_2020_jeh.jpg) (2020-05-22 08:40, blue sky, 1280×2276): glass, box 55,40,65,65: mean #3c5679, median #33537c
  - [53W53_August_2021_001.jpg](https://commons.wikimedia.org/wiki/File:53W53_August_2021_001.jpg) (2021-08-21 13:06, overcast, 1280×1707): glass + diagrid, box 45,33,60,50: mean #818a8d, median #788082; sky #ecf1f7
  - Diagrid members: ≈ #c9cbcc (est.)
- **Profile (est.):** Scale applies to the **N–S depth only**; E–W stays 1.0. `0:1.0, 0.25:1.0, 0.5:0.85, 0.7:0.65, 0.85:0.4, 0.95:0.15, 1.0:0.03`. That is a blade-like wedge ending in 2–3 thin spires. The diagrid diamonds are ≈ 10–12 floors tall (est.).

### 3 World Trade Center (Rogers Stirk Harbour, 2018; 329 m flat roof, 80 fl)
- **Facade:**
  - Glass is double-glazed low-e, with ≈10,000 annealed panels running floor to ceiling. The cable-net lobby wall uses panels 5 ft × 10 ft (1.52 × 3.05 m). A **bay module of 1.52 m** is plausible for the tower (est.).
  - **Stainless-clad K-bracing** runs on the east and west elevations over the lower two-thirds.
  - The roof is flat, with no spires; four corner spires were dropped from the design.
- **Colour, sampled:**
  - [3_World_Trade_Center_150.jpg](https://commons.wikimedia.org/wiki/File:3_World_Trade_Center_150.jpg) (2024-08-20 11:46, overcast, 1280×2847): glass, box 50,20,74,45: mean #5d6d84, median #607087; sky #a7a8af
  - Blue-sky glass ≈ #4f6f9f (est.)
  - K-brace stainless ≈ #b8bcc0 (est.)
- **Profile (est.):** `0:1.0, 0.62:1.0, 0.63:0.88, 0.80:0.88, 0.81:0.76, 1.0:0.76`. These are the notched setbacks where the K-bracing ends; the bracing is visible in photo 150.

### 4 World Trade Center (Fumihiko Maki, 2013; 298 m, 72 fl)
- **Facade:**
  - The curtain wall uses highly **reflective glass** in panes **5 ft wide × 13 ft tall**, which gives a bay of 1.52 m and a floor-to-floor of ≈4.0 m. Mullions are minimal, so the tower reads as a mirror.
  - The lobby is clear glass. The obtuse corners have deep vertical grooves.
  - The plan is a parallelogram in the lower tower and changes to a trapezoid on the upper floors.
- **Colour, sampled:**
  - [Four_World_Trade_Center_2015.jpg](https://commons.wikimedia.org/wiki/File:Four_World_Trade_Center_2015.jpg) (2015-04-25, blue sky with cloud, 1280×1920): glass, box 37,20,63,65: mean #7e96bc, median #8198be. It reflects the sky almost 1:1.
  - [4_World_Trade_Center_030.jpg](https://commons.wikimedia.org/wiki/File:4_World_Trade_Center_030.jpg) (2024-08-12 13:54, hazy bright): box 20,30,80,90: mean #818a97, median #848f9c
- **Profile (est.):** `0:1.0 (parallelogram), 0.75:1.0, 0.76:0.82 (trapezoid, one acute corner removed), 1.0:0.82`. The podium is ≈7 floors.

### 7 World Trade Center (SOM / David Childs, 2006; 226 m roof, 52 fl)
- **Facade:**
  - The glass is ultra-clear **low-iron**, with **stainless-steel (Type 316) spandrels behind it**. Upper panes are 13.6 ft (4.15 m) high, which gives the floor-to-floor.
  - The base encloses a Con Ed substation behind **stainless-steel louvers**, with a LED light wall by James Carpenter.
  - The plan is a trapezoid prism with no setbacks.
- **Colour, sampled:** [Wtc7-2006-0911.jpg](https://commons.wikimedia.org/wiki/File:Wtc7-2006-0911.jpg) (2006-09-11, deep blue sky, 1280×1707)
  - west face, box 33,10,48,40: mean #365b8d, median #2f558a
  - other face, box 52,10,62,40: mean #2b5186, median #284f85
  - Overcast ≈ #8a929c (est.)
- **Profile:** `0:1.0, 1.0:1.0`, a straight extrusion with a flat roof.
- **Night:** The base curtain wall has **220,000 blue and white LEDs**, so the base glows blue/white. The lobby has Jenny Holzer's LED text wall.

### 8 Spruce Street (Frank Gehry, 2011; 265 m, 76 fl)
- **Facade:**
  - About **10,500 brushed stainless-steel panels** ripple over three elevations. The south face is flat.
  - Windows are rectangular but vary in width, forming bays.
  - The podium is 6 storeys of **reddish-tan brick**. The plan is T-shaped.
- **Colour, sampled:** [8_Spruce_Street_(01030p).jpg](https://commons.wikimedia.org/wiki/File:8_Spruce_Street_(01030p).jpg) (2020-08-20 17:38, blue sky, 1280×3309)
  - box 38,25,48,50: mean #86a3ac, median #88a9b4
  - box 52,25,62,50: mean #7c97a2, median #85a2ac
  - This is steel reflecting sky, so it is blue-grey. Overcast ≈ #a8acae (est.).
- **Profile (est.):** Setbacks forming terraces are at floors 7, 24, 40 and 52 of 76. `0:1.0 (podium), 0.08:0.85, 0.31:0.85, 0.32:0.78, 0.52:0.78, 0.53:0.72, 0.68:0.72, 0.69:0.66, 1.0:0.66`. Add a low-frequency ripple (≈ ±1.5 m amplitude, est.) to the E, N and W faces.

### Bank of America Tower (Cook+Fox, 2009; roof 288 m / 945 ft, architectural 366 m / 1,200 ft)
- **Facade:**
  - An insulated glass curtain wall of **8,644 panels**, fritted and clear. The **faceted, sloping planes** (a crystal form) make the upper mullions run slightly diagonal.
  - The base is 7–8 storeys and covers the whole plot.
- **Spire:** ≈78 m (1,200 − 945 ft), a slender mast. Its base is ≈3–4 m (est.).
- **Colour, sampled:** [Bank_of_America_Tower_at_One_Bryant_Park,_Manhattan.jpg](https://commons.wikimedia.org/wiki/File:Bank_of_America_Tower_at_One_Bryant_Park,_Manhattan.jpg) (2019-10-04 15:42, blue sky with cumulus, 1280×960)
  - box 47,40,57,70: mean #556674, median #3f5668
  - box 58,40,62,70: mean #637d9b, median #597282
- **Profile (est.):** `0:1.0, 0.1:0.9, 0.5:0.85, 0.75:0.72, 0.9:0.55, 1.0:0.4`. The facets are sheared rather than stepped.
- **Night:** The crown and spire are lit with LED, usually white; it changes colour for events.

### 220 Central Park South (Robert A.M. Stern, 2019; 290 m, 70 fl)
- **Facade:**
  - **Alabama "Silver Shadow" limestone**, installed as a curtain wall because hand-set stone was not feasible at that height. It has **punched windows** in vertical bays with metal-framed recesses, a decorative rooftop crown, and several upper setbacks.
  - An 18-storey "Villa" wing sits on Central Park South.
  - Six mechanical storeys are 18–24 ft tall (Wikipedia).
- **Colour, sampled** (both photos show the **shaded** face, so they are sky-lit and blue-cast; see gaps):
  - [220_Central_Park_South_001.jpg](https://commons.wikimedia.org/wiki/File:220_Central_Park_South_001.jpg) (2025-01-17 12:39, blue sky, north face in shade): box 42,35,58,70: mean #7b93b4, median #889fbb
  - [220_Central_Park_South_September_2024.jpg](https://commons.wikimedia.org/wiki/File:220_Central_Park_South_September_2024.jpg) (shade, underexposed): stone, box 30,75,55,95: #636061
  - Sunlit stone ≈ #d6d0c4 (est.)
- **Profile (est.):** `0:1.0, 0.85:1.0, 0.88:0.86, 0.94:0.72, 1.0:0.58`. The crown has a stepped parapet.

### 30 Rockefeller Plaza / Comcast Building (Raymond Hood, 1933; 259 m roof, 70 fl)
- **Facade:**
  - **Indiana limestone** with a granite base and continuous vertical piers. About 6,000 windows sit between **aluminum spandrels**, which read as dark verticals.
  - It is a slab under the 1916 zoning. The N and S elevations rise straight for 33 storeys and then step back gradually, with three setbacks each on the N, S and E.
- **Colour, sampled:**
  - [GE-Bldg_30-Rockefeller-Plaza_NYC_2012.jpg](https://commons.wikimedia.org/wiki/File:GE-Bldg_30-Rockefeller-Plaza_NYC_2012.jpg) (2012-05-11, blue sky, 1280×1707): box 25,30,45,60: mean #828486, median #918f87
  - [Rockefeller_Plaza_-_Comcast.jpg](https://commons.wikimedia.org/wiki/File:Rockefeller_Plaza_-_Comcast.jpg) (2019-06-13 15:25, hazy/partly cloudy, from Top of the Rock): box 25,25,55,70: mean #8d8d8a, median #a6a6a0
- **Profile (est.):** The long E–W axis steps; the N–S depth is ≈ constant. `0:1.0, 0.5:1.0, 0.55:0.88, 0.7:0.78, 0.85:0.68, 1.0:0.6`.
- **Night:** The "Comcast" sign at the top is lit. The Top of the Rock terraces are lit, and there is the seasonal tree below.

### 40 Wall Street (H. Craig Severance, 1930; 283 m architectural, 71 fl)
- **Facade:**
  - **Limestone base**, then **buff brick** above with buff terracotta, flat Art Deco piers, and recessed spandrels (darker on upper storeys).
  - Setbacks on Wall St are at floors 17/19/21, 26, 33 and 35. Pine St has setbacks at 12, 17, 19, 23, 26, 28 and 29.
  - Above ≈floor 36 a square tower carries a **copper (verdigris) pyramid with dormers**, topped by a spire.
- **Colour, sampled:** [40_Wall_Street_(cropped).jpg](https://commons.wikimedia.org/wiki/File:40_Wall_Street_(cropped).jpg) (2005-12-19, sunny winter, blue sky, 1280×2046)
  - buff shaft, box 38,30,62,65: mean #a29884, median #a89d85
  - **copper pyramid**, box 45,12,58,18: mean #99bec4, median #99cbc6
- **Profile (est.)** (fractions of architectural height):
  - `0:1.0, 0.12:0.85, 0.3:0.7, 0.42:0.58, 0.45:0.5 (tower), 0.83:0.5`
  - pyramid `0.83:0.5 → 0.93:0.15`
  - spire `0.93:0.05 → 1.0:0.01`

### Woolworth Building (Cass Gilbert, 1913; 241 m, 57 fl)
- **Facade:**
  - Cream/white glazed **architectural terracotta** over a limestone lower portion. It is neo-Gothic, with continuous vertical piers and dense windows.
  - The base is U-shaped, 155 ft (47 m) on Broadway × 200 ft (61 m), up to ≈30 storeys. The square tower above ends in a copper roof with Gothic tracery and three layers of pyramid (≈62 ft / 19 m) plus a spire. There is an ogee-arch canopy at the 27th floor.
- **Colour, sampled:** [Woolworth_Building_9494.JPG](https://commons.wikimedia.org/wiki/File:Woolworth_Building_9494.JPG) (2010, sunny, blue sky, 1280×960)
  - tower face, box 43,15,60,45: mean #aaadaf, **median #cecdcc** (the terracotta)
  - the buff pre-war tower to its left (unidentified, probably 225 Broadway), box 12,30,24,50: median #a49b91
- **Profile (est.):** `0:1.0 (base), 0.36:1.0, 0.37:0.5 (tower ~26 m square, est.), 0.85:0.5, 0.88:0.42, 0.93:0.28, 0.98:0.08, 1.0:0.02`.
- **Night:** The crown is floodlit warm white/gold. Historically lamps increased in intensity with height.

### 70 Pine Street (Clinton & Russell, 1932; 290 m architectural, roof ≈259 m / 850 ft infobox, 67 fl)
- **Facade:**
  - Indiana limestone lower storeys over a Minnesota granite water table. The upper storeys are **four shades of buff brick that darken toward the top**.
  - Setbacks are placed so their tops form a diagonal line, alternating N–S and E–W. The shaft runs from floor 32 to floor 54–56, where the corners taper.
- **Spire:** **124 ft (37.8 m)**, made of a 27 ft (8.2 m) glass lantern and a 97 ft (29.6 m) stainless-steel pinnacle. The lantern is ≈5 m across (est.).
- **Colour, sampled:** [American_International_Building3.JPG](https://commons.wikimedia.org/wiki/File:American_International_Building3.JPG) (2009-04-13, blue sky, 1280×1597)
  - sunlit face, box 36,35,45,60: mean #948d89, median #928b88
  - box 46,35,52,60: median #b2ada8
- **Profile (est.)** (to the 259 m roof): `0:1.0, 0.12:0.85, 0.3:0.62, 0.8:0.58, 0.86:0.45, 0.92:0.33, 0.97:0.24, 1.0:0.2`. The lantern and spire sit on top.
- **Night:** The glass lantern is lit (it was a beacon historically). The current lighting colour is unverified.

### MetLife Building (Emery Roth & Sons / Gropius / Belluschi, 1963; 246 m, 59 fl)
- **Facade:**
  - One of the first **precast concrete** curtain walls in NYC. The panels have a quartz-aggregate finish, with **vertical concrete mullions projecting 13 in (0.33 m)** and the windows recessed.
  - **Recessed mechanical bands at floors 21 and 46** read as dark stripes.
  - The plan is an elongated octagon. The N and S faces are divided into 3 segments.
- **Colour, sampled:** [MetLife_Building_September_2024_004.jpg](https://commons.wikimedia.org/wiki/File:MetLife_Building_September_2024_004.jpg) (2024-09-19 13:24, hazy blue sky, 1280×2847): box 15,25,75,60: mean #909291, median #8c9a9c
- **Profile (est.):** `0:1.0 (base block to ~10 fl), 0.17:0.82, 1.0:0.82` (octagon prism).
- **Night:** **LED "MetLife" letters** on the N/S faces at the top and globe logos on the E/W faces (replaced by LED in 2017). They are lit white/blue.

### Citigroup Center / 601 Lexington (Hugh Stubbins, 1977; 279 m, 59 fl)
- **Facade:**
  - Silver **anodized aluminum and reflective double-glazed glass** in continuous horizontal bands, with flush aluminum spandrels.
  - The square tower (≈48 m, est.) stands on **four ≈114 ft (35 m) stilts at the mid-sides**.
  - The top is **sloped at 45°** facing south.
- **Colour, sampled:** [Citigroup_Center_2015.jpg](https://commons.wikimedia.org/wiki/File:Citigroup_Center_2015.jpg) (2015-04-26 16:52, blue sky, seen from Rockefeller Center, 1280×1920)
  - box 38,30,60,55: mean #7b8795, median #8895a7
  - This mixes the aluminum bands and glass. The sunlit aluminum alone is lighter, ≈ #c8ccd0 (est.).
- **Profile (est.):**
  - `0–0.12:` only the core and 4 stilts
  - `0.12:1.0 … 0.86:1.0`
  - then along N–S, the depth goes linearly to `1.0:0.1`, following the 45° slope
- **Night:** The sloped crown is washed in white light.

### 56 Leonard Street (Herzog & de Meuron, 2017; 250 m, 57 fl)
- **Facade:** Floor-to-ceiling glass between **exposed white/light-grey slab edges**. The floor plates shift and cantilever irregularly ("Jenga"), increasingly so toward the top. The base has an Anish Kapoor sculpture.
- **Colour, sampled:**
  - [56_Leonard_Street_007.jpg](https://commons.wikimedia.org/wiki/File:56_Leonard_Street_007.jpg) (2024-12-21 13:35, overcast, 1280×2847): box 30,62,52,90: mean #505b66, median #4f5965; sky #afb3bb
  - [56_Leonard_Street_010.jpg](https://commons.wikimedia.org/wiki/File:56_Leonard_Street_010.jpg) (2024-12-23 13:22, deep blue sky, sunlit): box 35,45,65,80: mean #98a4ae, median #9ba9b2
- **Profile (est.):** The base scale is 1.0. For each floor, add a random ±(0.03–0.12) offset per edge, growing toward the top 30 %, and a stacked-box crown.

### One57 (Christian de Portzamparc, 2014; 306 m, 75 fl)
- **Facade:** A Permasteelisa unitized wall of 8,200 pieces. The glass comes in vertical stripes of **dark and light blue, pewter and silver** (Klimt-inspired). The south (57th St) face has curved cascading setbacks, and the curved roof tapers to 60 ft (18 m) wide.
- **Colour, sampled:** [One57_November_2024_003.jpg](https://commons.wikimedia.org/wiki/File:One57_November_2024_003.jpg) (2024-11-13 13:15, blue sky): box 20,30,60,80: mean #5373a9, median #5875af. The pixel mix is a checker of ≈ #2e3f6a and #8aa4cf (est. from the visible pattern).
- **Profile (est.):** N–S depth only. `0:1.0, 0.55:1.0, 0.62:0.9, 0.72:0.8, 0.82:0.68, 0.92:0.55, 1.0:0.4`, with a curved (barrel) roof.

### 15 Hudson Yards (Diller Scofidio + Renfro / Rockwell, 2019; 279 m, 70 fl)
- **Facade:** A glass curtain wall. The tower rises as a rectangular block and then transforms, through a **quilted/"tulip" transition**, into a narrower rounded crown with open-air "Skytop" terraces.
- **Colour, sampled:** [15_Hudson_Yards_045.jpg](https://commons.wikimedia.org/wiki/File:15_Hudson_Yards_045.jpg) (2024-08-10 12:13, blue sky): box 20,35,80,80: mean #5f8fc9, median #5e92d1. It reflects the sky strongly. Overcast ≈ #7d848c (est.).
- **Profile (est.):** `0:1.0, 0.6:1.0, 0.72:0.88, 0.85:0.74, 0.95:0.68, 1.0:0.66`. The upper part is rounded/lobed.

### The Spiral (BIG, 2022; 314 m, 66 fl)
- **Facade:** A glass curtain wall with a continuous chain of **landscaped terraces spiralling up** the tower as stepped setbacks. It is a tapering prism.
- **Colour, sampled:** [The_Spiral_019.jpg](https://commons.wikimedia.org/wiki/File:The_Spiral_019.jpg) (2025-02-01 13:46, blue sky): box 10,55,90,95: mean #4b72b0, median #5178b7
- **Profile (est.):** `0:1.0, 0.2:0.95, 0.4:0.9, 0.6:0.84, 0.8:0.78, 1.0:0.72`. Each step is on a different face, rotating 90° per step (the spiral). Put green terrace strips ≈3–5 m deep at each step.

### 270 Park Avenue (JPMorgan Chase HQ, Foster + Partners, 2025; 423 m, 60 fl)
- **Facade:**
  - Glass curtain wall with **expressed vertical piers**, which read bronze-grey in the photos, and horizontal louver bands.
  - **24 fan/diagonal columns** carry the tower over an 80 ft (24 m) lobby.
  - Setbacks to the W and E create **seven rectangular masses** tapering to a pinnacle.
- **Colour, sampled:** [270_Park_Avenue_2025_004.jpg](https://commons.wikimedia.org/wiki/File:270_Park_Avenue_2025_004.jpg) (2025-01-23 14:13, clear blue sky, 1280×2847)
  - glass + pier, box 24,30,34,60: mean #7e8da5, median #8093ab
  - box 12,30,20,70: mean #6d84a2
- **Profile (est.)** (W–E width; N–S constant): `0:1.0, 0.35:1.0, 0.36:0.82, 0.55:0.82, 0.56:0.64, 0.75:0.64, 0.76:0.46, 0.9:0.46, 0.91:0.3, 1.0:0.3`, plus a mast/pinnacle.
- **Night:** Linear light fixtures run up the sides for ≈750 ft (229 m) from the 29th floor to the spire. The facades above the top two setbacks are covered in lights.

---

## Manhattan facade palettes by building type

The values are sampled where a box and a Commons file are given. They are **(est.)** otherwise. For the generic city, the engine should jitter each palette by roughly ±8 % in lightness and ±5° in hue per building.

| Type | Wall colour | Trim / secondary | Floor-to-floor | Window grid | Notes |
|---|---|---|---|---|---|
| **Brownstone / rowhouse** (UWS, Harlem, Chelsea, Village) | sunlit brownstone piers **#6b564a / #735d4a (mean)**, shaded band **#514038 (median)** | window glass ≈ #3c4148 (est.); cornice painted dark brown/black ≈ #2b2622 (est.) | 3.4–3.8 m parlour floor, ≈3.0–3.3 m above (est.) | 3 bays on 20–25 ft (6.1–7.6 m) lots, window ≈1.0 × 2.0 m, 4–5 storeys + stoop | Sampled from [Lenox_123_rowhouses_jeh.jpg](https://commons.wikimedia.org/wiki/File:Lenox_123_rowhouses_jeh.jpg) (2011-03-03, sunny), crop of the left half, y 25–95 %; piers at crop boxes 13,30,18,45 and 29,30,35,45. Harlem/Striver's Row also has yellow-buff brick and red-brick variants. |
| **Pre-war brick apartment** (12–16 fl, UWS/UES, 1905–1931) | brick + windows mean **#7a6d6a**, median #7a6964 (rust/brown brick) | limestone base 2–3 fl ≈ #cfc6b6 (est.); terracotta/stone cornice | 3.0–3.2 m (est.) | 1.2–1.5 m windows, bays ≈3 m, grouped 2–3; double-hung 6/6 | [450_West_End_Avenue_2021_jeh.jpg](https://commons.wikimedia.org/wiki/File:450_West_End_Avenue_2021_jeh.jpg) (2021-06-12, soft light), box 20,25,90,70. The palette ranges from buff/tan (#b09a7c, est.) through orange (#a56a4a, est.) to dark brown (#6a4a3c, est.). |
| **Cast-iron loft** (SoHo/Tribeca, 1850–1890) | painted cast iron, cream: mean **#99958e**, median **#a09e94**; painted pink/red: median **#97828b**; buff: median **#918b83** | black fire escapes ≈ #1e1e1e (est.) | 4.0–4.6 m (tall loft floors) (est.) | columns/arches ≈2.5–3 m wide, tall 2-over-2 windows ≈1.3 × 3 m, 5–6 storeys, cornice | [72_Greene_Street_from_south.jpg](https://commons.wikimedia.org/wiki/File:72_Greene_Street_from_south.jpg) (2012-06-20, overcast-bright), box 20,20,80,60. [Cast_Iron_Buildings_-_SoHo_Historic_District.jpg](https://commons.wikimedia.org/wiki/File:Cast_Iron_Buildings_-_SoHo_Historic_District.jpg) (2015-06-05), boxes 5,10,48,55 (pink) and 55,10,85,55 (buff). Fire escapes on the facades are a strong cue. |
| **1920s–30s setback office tower** (limestone/brick/terracotta) | buff brick **#a89d85** (40 Wall), **#928b88** (70 Pine); limestone **#918f87–#a6a6a0** (30 Rock); white terracotta **#cecdcc** (Woolworth); a shaded buff tower reads **#545153** | copper roofs weathered **#99cbc6** (40 Wall pyramid); dark spandrels ≈ #4a4744 (est.) | 3.7–4.0 m (est.) | narrow vertical bays ≈1.5 m separated by continuous piers; spandrels recessed | 1916-zoning wedding-cake setbacks. Shaded sample: [Four_World_Trade_Center_2015.jpg](https://commons.wikimedia.org/wiki/File:Four_World_Trade_Center_2015.jpg), box 5,45,28,80 (unidentified pre-war tower in shade). |
| **Post-war glass/metal box** (1950s–80s) | Seagram bronze + tinted glass (overcast) mean **#6c6c72**, median #757780; Citicorp aluminum/glass median **#8895a7**; MetLife precast median **#8c9a9c** | black/dark bronze mullions ≈ #2e2a26 (est.) | 3.7–4.0 m (est.) | 1.4–1.6 m module (est.), continuous ribbon or full-height glazing; mechanical band floors | [Seagram_Building_(35098307116).jpg](https://commons.wikimedia.org/wiki/File:Seagram_Building_(35098307116).jpg) (2017-06-07, overcast), box 43,20,59,75. Flat roofs with large mechanical penthouses. |
| **2000s+ glass tower** | blue sky **#4b72b0–#6b7da0** (Spiral, 35 HY, One57); deep sky reflection **#2b5186–#365b8d** (7 WTC); overcast **#5d6d84–#818a8d** (3 WTC, 35 HY, 53W53) | silver mullions ≈ #b0b5ba (est.) | 4.0–4.2 m office (7 WTC 4.15 m); ≈3.3–3.8 m residential (est.) | 1.5 m module (3/4 WTC: 5 ft panes) | Model glass as reflective, with the tint pulled from the sky. The flat-colour fallback is the overcast values. |
| **NYCHA public housing** (1940s–60s, 6–21 fl) | tan/red-buff brick, sunlit: mean **#a39686**, median **#b1a18d** (Fulton Houses); darker red-brown brick in other estates ≈ #8a5a44 (est.) | window frames white/aluminium; many through-wall AC units | ≈2.6–2.8 m (est.) | small windows ≈1.2 × 1.4 m, irregular pairs; no cornice, flat parapet | [NYCHA_Fulton_Houses_001.jpg](https://commons.wikimedia.org/wiki/File:NYCHA_Fulton_Houses_001.jpg) (2022-04-20 14:40, blue sky), box 55,20,95,80. Cruciform or X plans set in "tower-in-the-park" lawns; rooftop elevator bulkheads. |

### Rooftop clutter
- **Wooden water towers.** These sit on nearly every pre-war building of 6+ storeys, and on many post-war loft and residential buildings too.
  - **Tank:** a cedar or redwood cylinder ≈3–4.5 m in diameter and 3–6 m tall, bound with steel hoops, under a conical roof with a finial.
  - **Stand:** a steel stand 3–6 m tall on the roof.
  - All dimensions are (est.); they are typical of Rosenwach/Isseks tanks.
  - **Colours, sampled** from [Rooftop_water_towers_in_SoHo,_Manhattan.jpg](https://commons.wikimedia.org/wiki/File:Rooftop_water_towers_in_SoHo,_Manhattan.jpg) (2016-03-09 13:37, sunny, 1280×905):
    - **weathered grey-brown tank**, box 18,16,26,34: mean **#8a7760**, median #948063
    - **new/fresh cedar tank** (sunlit), box 38,48,47,64: median **#f3debe** (mean #bfb29d, which includes shadow)
    - red-brick parapet (sunlit), box 5,72,45,95: mean **#8b6847**, median #865940
  - The steel stand is dark ≈ #2a2a2a (est.).
  - More views: [Rooftop_water_towers_on_New_York_apartment_buildings.jpg](https://commons.wikimedia.org/wiki/File:Rooftop_water_towers_on_New_York_apartment_buildings.jpg) and [Rooftop_water_tower,_160_5th_Ave,_Manhattan.jpg](https://commons.wikimedia.org/wiki/File:Rooftop_water_tower,_160_5th_Ave,_Manhattan.jpg).
- **Other clutter:**
  - **Elevator/stair bulkheads:** brick boxes ≈3–4 m tall covering ≈10–15 % of the roof (est.).
  - **Mechanical:** HVAC units and cooling towers on post-war and modern roofs, grey ≈ #8c8f91 (est.). Large mechanical screens sit on office towers.
  - **Tar roofs:** dark grey ≈ #4a4a4a, or light/white "cool roof" coatings ≈ #cfd2d2 (est.). Parapets are ≈1 m.
  - **Parks and plazas:** rooftop gardens and terraces on setbacks.

---

### Open gaps (other towers and palettes)
- **Profiles:** Every `heightFraction:scale` profile is an estimate from photos and published setback floors. No drawings or elevations were consulted, and no footprint dimensions were checked against OSM (the parent has OSM).
- **Stone in sun:**
  - 220 CPS stone was only sampled in shade (sky-lit, blue cast). The sunlit value is an estimate.
  - 30 Rock and 40 Wall stone and brick were sampled in sun, but their window and spandrel texture shifts the mean. Use the medians for the stone.
- **Missing weather conditions:**
  - No overcast sample for 7 WTC, 8 Spruce, BoA, One57, 15 HY, Spiral or 270 Park.
  - No blue-sky sample for 3 WTC.
- **Unpublished or unconfirmed data:**
  - 35 Hudson Yards pier material is unconfirmed.
  - Bay modules are unpublished for most towers. Only 3/4 WTC (5 ft panes) and 7 WTC (13.6 ft panes) come from Wikipedia text.
  - Floor-to-floor heights for the building types are estimates.
- **Night lighting:** Current schemes for 70 Pine, 40 Wall and Woolworth are not verified in detail.
- **Photo checks:**
  - The "unidentified pre-war tower" samples (left of Woolworth; left of 4 WTC) were not identified.
  - For 40 Wall, the second photo ([40_Wall_Street_001.JPG](https://commons.wikimedia.org/wiki/File:40_Wall_Street_001.JPG)) sample, box 30,15,60,40, is sky-contaminated and was discarded.
- **Water towers:** The dimensions are typical values, not surveyed.
- **Useful for bridges_statue.md (parent):** [Gehry_8_Spruce_Street_Brooklyn_Bridge.jpg](https://commons.wikimedia.org/wiki/File:Gehry_8_Spruce_Street_Brooklyn_Bridge.jpg) (2010-09-02, sunny) shows a Brooklyn Bridge tower close up. It is already downloaded as `photos/o_8spruce_3.jpg` but not sampled.

### Open gaps (landmarks_manhattan.csv)
- **Where the heights come from.** Tall-building heights come from the CTBUH Skyscraper Center page (JSON embedded in the NYC city page, fetched 2026-09-28). Where CTBUH gives a roof and the top of the main volume reaches the CTBUH architectural height (architectural − roof ≤ 15 m, and the OSM full-footprint part is at the architectural height), `height_m` is the parapet (architectural) height. Examples are 432 Park, 270 Park, The Spiral and 4 WTC. In every other case it is the CTBUH roof. The notes say which was used.
- **Buildings with only an architectural height.** About 35 buildings have no CTBUH roof value, so they use the architectural height (`height_type=architectural`). These include 3 WTC, 520 Fifth, 35/50/10 HY, One Manhattan West, 30 Park Place, 125 Greenwich, 262 Fifth, Woolworth, 500 Fifth, New York Life, 570 Lexington and One Wall Street. For buildings with a crown, the prism will overshoot the crown volume.
- **Empire State Building.** Its `height_m` is 381 m (top of the mooring-mast floors), as requested. The main shaft ends near 320 m at the 86th floor.
- **Low-rise heights from OSM only.** Grand Central (45.8), NYPL (35), St Patrick's roof (42) and Madison Square Garden (45) use OSM tags. They are unverified, so `use_height=False`.
- **Trinity Church.** The spire height of 85.6 m is from Wikipedia. OSM does not model the spire, so `use_height=False`.
- **Buildings not yet complete.** 520 Fifth, 262 Fifth, 8 Carlisle (111 Washington), Casoni and 450 Eleventh are marked topped out but not complete (CTBUH UCT/STO). One Seaport (161 Maiden Lane) and 45 Park Place are marked topped out but on hold. None of these statuses was checked against site photos.
- **Excluded towers.** The Torch (740 8th Ave), 2 WTC and 343 Madison are excluded as still under construction. OSM already carries their planned heights.
- **Wrong heights in OSM.** OSM heights disagree with CTBUH for Monogram (OSM 183 m, CTBUH 138 m) and The Maybury (OSM 185 m, CTBUH 159 m). Neither is in the CSV.
- **Salesforce Tower.** The "reclad 2008" note is unverified.
