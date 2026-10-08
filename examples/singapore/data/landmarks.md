# Singapore landmark list: method, sources, disagreements

Files: `landmarks.csv` (55 rows, columns as Berlin and Shenzhen: `name_zh,name_en,height_m,height_type,floors,status,
year,lat,lon,source,notes,feature,use_height`) and `places.csv` (9 areas for camera views: `name,lat,lon,kind,note`).
Written 2026-10-06 by w-sg-lm for b-sg-m1. `name_zh` is the English display name; the Chinese name is the first
sentence of `notes` where known.

## Method

1. The 37 Phase 0 landmarks (`demos/data/singapore/phase0/research.json`) were split: 9 areas went to
   `places.csv`, the other 28 became 40 rows (MBS 3 towers, Gardens' two domes, the Esplanade's two halls, the Pinnacle's
   seven blocks, Reflections' three tall towers) and 15 towers were added (rows whose notes start "added (not in
   Phase 0)"): 55 rows.
2. Second height source for every tower: CTBUH Skyscraper Center. `https://www.skyscrapercenter.com/city/singapore`
   embeds the data of all 363 Singapore records (height architecture / roof / tip, floors, status, completion year,
   source remark) as JSON in the page; read once with curl. Third source: the English Wikipedia "List of tallest
   buildings in Singapore" (raw wikitext) and the building articles (infobox). For the non-towers: Wikipedia articles
   and web search summaries (see "weak" below).
3. Footprints and coordinates: OpenStreetMap API 0.6 `map` calls on nine small boxes (CBD, Marina Bay, Esplanade,
   Anson/Duxton, Gardens, Orchard, Keppel Bay) plus `way/<id>/full` for 8 ways and 2 relations (about 25 calls in all;
   no Overpass). A point is the centroid of the tower's own OSM footprint (a part for towers mapped in parts), or
   the Phase 0 coordinate when that already lies inside it. Each use_height=True point was tested: it lies inside
   the polygon named in `source`.
4. The 280 m CBD height limit is stated above mean sea level (URA, as reported on skyscrapercity), and CTBUH takes
   heights from architects' drawings above the street. That explains most gaps of 2-7 m between "official" figures
   (280, 290, 245, 235, 218...) and CTBUH: where they differ and the drawing-based CTBUH figure is explained, CTBUH is
   used. If you want the official figures back (and the notes say which they are), edit the number.

## Heights that changed against Phase 0 (and why)

| Row | Phase 0 | Now | Reason |
|---|---|---|---|
| Guoco Tower | 290 | 283.7 | CTBUH amended 290 to 283.7 from SOM drawings (2019); the Wikipedia list's own table says 283.7, its lead/infobox 290 (AMSL approval). OSM: body 180 + Wallich part to 290. |
| One Raffles Place (Tower 1) | 280 | 277.75 | CTBUH section drawing; Wikipedia/OSM 280/283. |
| Republic Plaza | 280 | 276.25 | CTBUH; OSM tower part 275 + crown parts 280-282; Wikipedia 280. |
| CapitaSpring | 280 | 276 | CTBUH from the 2023 drawings (grade +104.0 m); developer/Wikipedia/OSM 280. |
| UOB Plaza One | 280 | 280 | CTBUH, Wikipedia and OSM's top part agree. |
| MBFC Tower 3 | 245 | 239.65 | OSM's 245 is Tower 2's height; CTBUH, Wikipedia list and OSM's own parts say 239. |
| MBS towers | 194 (one row) | 198 (three rows) | CTBUH roof 198; OSM 193 + SkyPark (separate building, 207, min 193). |
| ION Orchard tower | 218 | 210.9 | CTBUH 210.9; 218 is "above sea level" per some sources (Wikipedia, OSM, ION Sky). |
| Reflections at Keppel Bay | 180 (one row, point off the towers) | 174.15 (three rows) | CTBUH from drawings; Wikipedia 160, list 178. |
| National Stadium | 82 | 83 | Wikipedia infobox 83 m; Arup-derived pages 80, another 85. |
| Pinnacle@Duxton | 156 (one row) | 156 (seven rows) | Official 156 (HDB/Wikipedia/OSM parts) kept; CTBUH 159.66 (163.03 for 1C). |
| Flower Dome / Cloud Forest | 58 (one row) | 38 / 58 (two rows) | Separate buildings; OSM tags both 30 m. |
| Esplanade | 35 (one row) | 35 / 35 (two rows) | OSM dome parts; the Phase 0 point was on the low podium. |
| Fullerton | 37 | 36.6 | Wikipedia wall height; OSM 25/30. |
| Sri Mariamman | 15 | 20 (gopuram) | Weak: search summaries say about 20 m; OSM body 10 m. |
| Raffles Hotel, Lau Pa Sat, Sultan Mosque, Istana, VivoCity | blank | blank | No height source found; position records only (use_height False). |

Unchanged and confirmed: Supertrees 50 (tallest; range 25-50, Wikipedia), Merlion 8.6 (Wikipedia/NLB), Flyer 165
(Wikipedia, OSM), Buddha Tooth 30 (OSM only), Victoria Theatre clock tower 54 (Wikipedia), ArtScience 60 (see below).

## Rows with use_height False and why

Structures (feature=structure): Supertree Grove, Merlion, Helix Bridge (no height), Singapore Flyer.
Shells and roofs that a box would ruin: Flower Dome, Cloud Forest, Esplanade Concert Hall and Theatre, National Stadium,
ArtScience Museum (OSM already has its fingers as parts).
Needle on a larger footprint: Victoria Theatre (clock tower), Sri Mariamman (gopuram).
Monuments without a firm height or a reliable footprint: Fullerton, National Gallery, Buddha Tooth, Raffles Hotel,
Lau Pa Sat, Sultan Mosque, Istana, VivoCity. If `[buildings.landmarks] cap = true`, the rows with a height cap and name
their buildings (monuments); without it they are not applied at all (rows without height never are).
The other 35 rows (towers) are use_height True.

## Disagreements and doubts

- **Guoco Tower 283.7 or 290**: see above; the biggest judgement call. 290 is the figure people know.
- **Official versus CTBUH on the CBD towers**: One Raffles Place, Republic Plaza, CapitaSpring, IOI West Tower
  (237.93 vs 245), Frasers Tower (230.85 vs 235), ION (210.9 vs 218): CTBUH used, the official figure is in `notes`.
- **MBS**: the three tower rows are inside the SkyPark polygon (w116800998, one 12,467 m2 building, 193-207 m) as well as
  their own footprints. With match "nearest" the SkyPark could take the row's height (a 193-198 m slab); check
  `checks/buildings.md`, or use match = "best".
- **Towers on podiums**: for Marina Bay Suites, One Raffles Place, Guoco, Republic, CapitaSpring, ION, Swissotel and
  most of the added towers, the point also lies inside a larger low podium polygon. Prefer `match = "best"` (height
  closest to the listed one) or the `podium` option.
- **Marina One** (two office towers, OSM 207 m, 30 floors; CTBUH 225.45 m; Wikipedia 225; a search says 200 m) was not
  added: unresolved.
- **ArtScience Museum**: 60 m (tourist/architecture pages, "tallest finger") against OSM parts topping at 26 m; Safdie's
  own page and Wikipedia give no height. Kept 60 but the row is use_height False.
- **Weak second sources** (single or search-summary only): Flower Dome 38 and Cloud Forest 58 (OSM 30), Esplanade domes
  35 (OSM only), Buddha Tooth 30 (OSM only), Sri Mariamman 20, National Gallery 25 (OSM), Fullerton 36.6 (OSM 25/30).
- Pinnacle block letters 1A-1G follow the order along the chain; the footprint-to-letter pairing is approximate (no
  effect on heights, all 156).
- Chinese names given where well known; the added towers' names are English only.
- Raffles Hotel's point is the Phase 0 OSM node; its footprint was not fetched.

## Coordinates moved

Republic Plaza (the Phase 0 point was on the 4-storey podium w171999304; now on the tower part w407705571), CapitaSpring
(base part to the tower part w1157548672), Guoco Tower (into the Wallich part w393100848, which is also inside the
body part), ION Orchard (mall podium to the tower part w231917896), Reflections (the Wikidata point was off the
towers; three points on the stacked parts). Split rows (MBS towers 1 and 3, Gardens domes, Esplanade halls, Pinnacle blocks)
have new points inside their own footprints. Everything else keeps the Phase 0 coordinate (checked inside).

## M4 figures (landmarks the building table can't draw; `scripts/m4l_structures.py`)

Photo research of 6 Oct 2026 (worker r-sg-m4l: Wikimedia Commons searches, contact sheets, PIL samples in boxes checked
by eye). All the photos were hazy or overcast tropical daylight, so sampled colours are what a camera saw; the figure
colours sit between the sample and a lit "paint" estimate. (src) = a published figure, (samp) = sampled, (est.) =
read off photos or assumed. Figures are `[[structures]]` in `generated/structures-m4l.toml`; the OSM pieces they replace
are excluded in `scripts/m2_heights.py` (`M4L_EXCLUDE`, the stadium's `PART_DROP_IN`); profiles are in
`landmark_facades.csv`.

| Landmark | How it is drawn | Numbers | Colours | Photos (Commons) |
|---|---|---|---|---|
| MBS towers | OSM outlines, `lean:` profile: the west leg straight, the curved east leg leaning in (Wikipedia: "a curved eastern leg leaning against the other") | 198 m (CTBUH roof); 61 m along the row x 51 m deep (OSM) -> ~39 m at the top; Tower 3 is only half mapped (31 m deep): a slight lean | glass #35566f (samp #204d69-#385a72 across the bay, overcast); white end cladding #d8d6d2 (est.) | Singapore_(SG),_Marina_Bay_Sands_Hotel_--_2019_--_4535.jpg, ..._4483.jpg |
| MBS SkyPark | figure: OSM outline w116800998 in 6 m slices along the row, the underside 190 m over the towers rising to a ~3 m bow at the 66.5 m north cantilever (src: Wikipedia), a convex belly 4 m deeper 7 m in from the edges; deck at 201 m, pool, rim planting, two pavilions | 340 x 38 m (src: Arup), 66.5 m cantilever | belly #8f989f (samp #4c657a-#565d6c, mirrors sky/water), sides #d9dcdd | ..._4754.jpg (underside) |
| Esplanade shells | OSM outlines with a `dome:0.04` profile, china-south's honeycomb style (the sunshades read as cells) | 97 x 63 m and 108 x 63 m (OSM), 35 m (OSM tag, no second source) | #8a8c89 (samp whole shell #797c79, sunlit sunshades #c4c3be): grey-silver, not tan | The_Esplanade_Concert_Hall,_Singapore_(54526628939).jpg |
| ArtScience Museum | figure: ten fingers lofted as tapering, out-curving horns round a bowl on a glazed ring base; three tallest to the north-east/east (the aerial photo) | tallest finger 60 m (src: Wikipedia); others 26-56 m (est.); bowl 17 m (est.) | #e2e0dc (samp lit #ece8e8, sky-lit #828e94) | ..._View_from_Marina_Bay_Sands,_ArtScience_Museum_--_2019_--_4714.jpg |
| Flower Dome, Cloud Forest | figures: a height field over the OSM outline (ridge along the long axis, cross-sections to the plinth), see-through glass gridshell (lattice mesh), white arches every ~13 m outside, 3 m plinth; Cloud Mountain inside | 38 m; 58 m (project figure, unverified); Cloud Mountain 42 m (src: Wikipedia) | arches #eceeee; glass members #a9bec2 (samp #98aeba-#b4c5cb from above) | Singapore_Flower-Dome-and-Cloud-Forest-in-The-Gardens-01.jpg |
| Supertrees | 15 figures (12 of the grove from OSM's ring parts, 3 by the Cloud Forest): flared planted trunk, an open canopy cone (lattice mesh) on six ribs; heights snapped to 25/30/37/42/50 m (src: greenroofs.com); canopy 0.62 x height across (est.); OCBC Skyway at 22 m along OSM w687915906 | 25-50 m | trunk #5a4152 (samp #3e2b39 overcast), canopy #3f3b57 (samp #414259), Skyway #b98a4e (est.) | OCBC_Skyway,_Supertree_Grove,_Gardens_by_the_Bay,_Singapore_-_20120617.jpg |
| Singapore Flyer | figure: 150 m wheel, hub 90 m (15 m clearance, src figures 165/150), trussed double rim, 28 outboard capsules, cable spokes, spindle between two pylons with two stays each (Arup summary); plane from OSM w230082125 | 165 m | rim #e6e8ea (samp #cdd3dd-#e5ebf6), capsules #59626a (samp #505458) | Singapore_(SG),_Singapore_Flyer_--_2019_--_4491.jpg |
| Helix Bridge | figure: two helices (r 5.2 / 4.6 m, pitch 18 m, est.) along OSM's S-bent deck ways, struts every 14 m; the deck is 05b_roads' | 280 m (src) | #aeb3b8 (samp #838990-#938f89) | Singapore_(SG),_Helix_Bridge_--_2019_--_4466.jpg |
| Merlion | figure: lofted body, spout, the blue-and-white basin; facing east (src: Wikipedia) | 8.6 m (src) | #e6e1d5 (samp #c2baab overcast) | Singapore_Merlion-at-Marina-Bay-01.jpg |
| Victoria clock tower | figure: square shaft, clock stage with four dials, octagonal bell turret, cupola | 54 m (src: Wikipedia) | white render #ecebe4, cupola #8a8f8c (est.) | Victoria_Theatre_and_Concert_Hall_Singapore.jpg |
| Old Supreme Court dome | figure over OSM's drum part (excluded): drum with attic, dome, lantern | top 45 m (est.: OSM 36/42 m, a photo's scale 50-60) | verdigris #8fb0a6 (samp #96b7bd sun) | Old_Supreme_Court_Building_and_City_Hall_from_the_Padang,_Singapore_-_20110205.jpg |
| Sultan Mosque | figure: onion dome (~15 m across, est.) on a black band over the prayer hall; the two east minarets' tops (OSM 17-29 m) | ~31 m (est.) | gold #bc9a4c (samp #85764d overcast), band #2b2b2b (samp near black) | Sultan_Mosque,_Singapore.jpg |
| Sri Mariamman gopuram | figure at the outline's east end: dark base, five tapering sculpted tiers, barrel crown with finials | ~18 m (est.; no published height) | mid multicolour (samp overall #70706b): tiers pink/teal/ochre | Gopuram_of_Sri_Mariamman_Temple_Singapore_2.jpg |
| Buddha Tooth Relic Temple | figure: deep-eaved hip roofs over OSM's hall (17.5 m) and centre tower (21 m), gilt finial | ~30 m (OSM tag) | roofs #3d2e2b (samp #361818) | Buddha_Tooth_Relic_Temple,_Singapore,_20240122_0810_2924_01.jpg |
| National Stadium | figure: a spherical cap on the OSM outline (its roof rings excluded), 16 ribs | 310 m span, 83 m (src: Wikipedia) | #d3d7da (samp #c8cacd lit, #a2a5aa shaded) | Singapore_Singapore-Sports-Hub-with-National-Stadium-01.jpg |

Not built (time box; Known issues): the Sultan Mosque's second dome and corner turrets, the Helix's four pods, the
stadium's retractable opening and vents, the Fairmont and National Library splits, Henderson Waves (1.27605 N,
103.8155 E, 274 m, 36 m over Henderson Road), the Mount Faber / Sentosa cable car (rope heights ASL: Faber 93 m,
Tower 1 80, HarbourFront 69, Tower 2 88, Sentosa 47; src: Wikipedia). Unverified: the MBS legs' join level, the
SkyPark's thickness, Supertree canopy sizes, Helix tube sizes, the Cloud Forest's 58 m, the shells' and domes' heights.
