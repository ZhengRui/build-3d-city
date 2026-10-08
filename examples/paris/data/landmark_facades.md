# Paris landmark facades: photo research

Companion to `landmark_facades.csv` (152 rows, the columns of New York's: `name, facade, tint, module, variant, profile, whole, notes`) and to `landmarks_paris.csv`, the per-building heights and points. Written for M4 (facade styles): the builders take the row values and the numbers here, the critics take the reference photos in `demos/data/paris/refs/` (git-ignored; `refs/index.md` lists every file, its Commons page, licence, author, date and what it shows: aerial, street, day, dusk, night).

**Coverage.** Every must-have has a row (Tour Eiffel, Arc de Triomphe, Notre-Dame, Sacré-Cœur, Louvre Pyramid and Louvre Palace, Tour Montparnasse, Panthéon, Dôme des Invalides and the Hôtel des Invalides, Opéra Garnier, Grande Arche), every tower of 100 m or more in the landmark list (La Défense, Front de Seine, Italie 13, Olympiades, Belleville and Flandre, the rest) and the big monuments (Grand Palais, Pompidou, BnF towers, Chaillot, Orsay, Hôtel de Ville, Madeleine, the churches, Saint-Jacques, IMA, Géode, Maison de la Radio). Eight lesser La Défense towers under 100 m have no row (Europe, Enedis, Prisma, Pascal, Pacific, Gémeaux, Voltaire, Exaltis); they take the district palette. The Eiffel Tower and the Front de Seine chimney are structures: no building of that name exists, so `06_tiles` prints "no building named ..." for those two rows; the rows carry the colours for their `[[structures]]`.

**Sections.**
1. Must-have landmarks (photo-sampled colours, dimensions, what the table holds, gaps).
2. La Défense: 17 towers with sampled-box table, palette by generation.
3. Big monuments, churches, the 1960s-70s towers, the bridges.
4. Standard AREA views: what the critic compares in each photo set, and the measured palette of Paris (stone, zinc, slate, asphalt, water, foliage).
5. Engine gaps and NEW STYLE proposals.

## How the rows are read by the engine (checked against `stages/tiles.py` and the built `buildings.gpkg`)

- `name` = `name_zh` in `landmarks_paris.csv`. **The row applies to every row of `buildings.gpkg` with that name**: I ran the engine's own `landmark_facades()` on the real table (Paris venv, no stage run, memory well under 2 GB): 150 of the 152 names hit 410 building rows with no error (the two misses are the structures above); all `profile`, `crown@` and `module` values parse.
- `profile` is ignored for a landmark whose rows are OSM `building:part`s (`part_of` set) unless `whole=true` merges them into one outline; the four `whole=true`/profile combinations are noted per row. `crown@<m>:<profile>` (Sacré-Cœur, Panthéon) cuts the tallest non-spire body at `<m>` and lofts the piece above as a spire-style body (no windows, hard-coded grey `#b8bcc0`); tested for parsing only.
- The 06 stage maps `facade` through `STYLE_ID`: **a NEW STYLE name must exist in `[facade.styles]` of `europe-west.toml` and in `facade.js` (in the same order) before 06 runs**, or the pack stage fails on an unknown style.
- `tint` on the glass-wall styles (`glass`, `fins`, `bands`, `piers`) is the glass colour; on `stone`, `limestone`, `concretepanel`, `floodlit` it is the wall colour (sRGB hex, sampled or estimated as each note says).

## What the table actually holds for the landmarks (important for M4)

Checked in `demos/data/paris/buildings.gpkg` on 2026-09-30:
- `min_h` is 0.0 on every part of every landmark (OSM's `min_height` is lost in M2's flattening): raised parts, arches and voids extrude from the ground. So the Arc de Triomphe's vaults are solid; the **Grande Arche is a filled block** (its 108 x 104 m roof-slab footprint runs 0 to 104 m) with one 112 x 19 m wall; Notre-Dame's nave and towers and the domes are stacked solid prisms.
- Unnamed parts of a named landmark do not get its row: Notre-Dame's two 69 m towers (unnamed rows 128141/128142/128190-2) keep the default style.
- The domes are cylinders: Invalides' dome is a 28 x 28 m cylinder to 72 m, Panthéon's 25 x 25 m to 74.5 m; the tallest non-spire part is not always the dome (Invalides, Opéra), so `crown@` only works for Sacré-Cœur and Panthéon.
- `landmarks_paris.csv` heights above the dalle at La Défense come out 6-8 m lower in the table (`h_src = landmark@slab`): The Link 235.6 m vs 242, Saint-Gobain 170.1 vs 178.

## NEW STYLE proposals (palettes from the sampled photos)

| Style | Used by | Wall palette (sRGB) | Floor / bay | What it draws | Parent for the per-style tables |
|---|---|---|---|---|---|
| `limestone` | Louvre Palace, Hôtel des Invalides, Opéra Garnier, Madeleine, Chaillot, Orsay, Hôtel de Ville, Grand Palais, 14 churches and belfries, Saint-Jacques, the clock tower (21 rows) | `#d6ccb6 #cfc4ab #c8bca2 #d9d0bc #e0d8c6` (region_research) and the sampled `#cdbfa1 #b3a78f #cfc4a8 #c6bda9` | 4.5 m floor, 3.4-3.6 m bay | tall punched openings (about 0.35 x 0.55 of a bay), a deep cornice band, a 3 m plinth, no glass wall | `stone` |
| `concretepanel` | 49 towers of the 1960s-70s: Italie 13, Olympiades, Front de Seine, Flandre, Ourcq, Chapelle, Bagnolet | `#c1c4c8` (Italie 13 pale), `#b9b0a8` (Olympiades beige-pink), `#a9acb3`, `#9d6550` (red-brown), `#858279` (grey-brown), `#c9c5b8` (Flandre cream), `#6b6a63` (dark ribbon) | 2.9 m floor, 2.4-2.7 m bay | continuous window strips 45 % of the floor height with dark spandrels (`#4f4249`), glass `#3f3f4a`; the pier colour is the tint | `residential` |
| `gothic` (optional) | Notre-Dame, Sainte-Chapelle, Saint-Eustache: tall lancet openings in a stone wall | limestone palette | 6 m bay | pointed tall windows, dark glass | `limestone` |
| `zincmansard` | none of these rows; kept for the generic Haussmann roofs | zinc `#909390` sunlit, `#777e83` shade; slate `#292930` shade, `#7f888d` sun | | | |

Existing styles used: `glass` (36 rows), `bands` (18), `panel` (12), `floodlit` (5: the monuments without windows, night floodlight), `lattice` (4: Louvre pyramid, Eiffel, Pompidou, Tour D2), `stone` (3), `plain` (2), `fins` (1), `piers` (1).


## Must-have landmarks

Photos are in `demos/data/paris/refs/<slug>/` (index: `refs/index.md`); "refs/x/NN" below is the file number in that folder. Colour boxes are fractions of the 800 px image, `x0,y0,x1,y1`, origin top left. Every number marked "(sampled)" was measured with `samp.py` (mean, median, and the mean of the brightest 30 % of pixels, `bright30`) on the box named; "(est.)" is a judgement. Dimensions come from Wikipedia EN/FR (fetched 2026-09-30) unless another source is named, and from the OSM parts in `demos/data/paris/osm_parts.gpkg`. What the buildings table (`buildings.gpkg`, after M2) actually holds is stated per landmark, because it differs from OSM: **every part has `min_h = 0`** (OSM's `min_height` is lost), so arches, voids and raised drums are extruded solid from the ground, and unnamed parts of a named landmark (Notre-Dame's towers) are not reached by name-based rows.

### Tour Eiffel (330 m to the antenna tip; STRUCTURE)
- **Heights and plan:** decks at 57.63 m (about 70 x 70 m), 115.73 m (about 42 x 42 m) and 276.13 m (about 16.5 x 16.5 m); legs on a 129.2 m square; 330 m to the antenna tip (300 m top platform roof); OSM's ten stacked solid prisms are wrong and excluded (landmarks_paris.md).
- **Facade:** puddled wrought-iron lattice, 7,300 t of ironwork, repainted every seven years in three shades of "Eiffel brown", darkest at the base and lighter towards the top. Cross-braced pier lattices, open arches with ornamental spandrels under the first deck, solid riveted arch ribs.
- **Colours (sampled):**
  - Sunlit north pier, blue sky: lit arch face box `0.44,0.30,0.50,0.85` median `#9b8060`, mean `#897a62`, bright30 `#e0d7ba`; shaded pier `0.20,0.2,0.235,0.9` median `#28201d`. Photo eiffel-tower/04, [Structure_Tour_Eiffel_pilier_nord.jpg](https://commons.wikimedia.org/wiki/File:Structure_Tour_Eiffel_pilier_nord.jpg).
  - First-floor belt girder in shade (eiffel-tower/05, box `0.14,0.605,0.86,0.645`): mean `#50453a`, median `#41362e`; sunlit arch ribs (box `0.30,0.68,0.70,0.72`) median `#94826b`, bright30 `#ebd7bd`. [Tour_Eiffel_-_20150801_13h44_(10613).jpg](https://commons.wikimedia.org/wiki/File:Tour_Eiffel_-_20150801_13h44_(10613).jpg).
  - Row tint `#7a6a58` is the mean of sunlit and shaded ironwork; against sky the tower reads mostly as its dark side (`#41362e`).
- **Night:** golden light since 1985 from 336 sodium projectors (region_research §6.3); sampled lit lattice (eiffel-tower/07, box `0.44,0.10,0.56,0.33`): mean `#9d6c26`, bright30 `#f4cc48`, so lit steel `#e8b23c` on a `#0d1f3a` blue-hour sky; the arch underside and the first-floor belt stay dark (mean `#624a2f`). Sparkle 5 min per hour; a beacon on the top; the Olympic rings between decks since 2024.
- **Engine:** cannot: an open lattice as a building (the row would be a filled block, and there is no building of this name, so 06_tiles prints "no building named Tour Eiffel"). It needs a `[[structures]]` figure (four tapering legs as tubes on the 129.2 m square, arches to about 57 m, decks as boxes, a tapered shaft, the antenna), or a `lattice` cut-out figure. The row keeps colour, lattice module (about 4 m diamond cells at the base, est.) and night colour for it.
- **Refs:** eiffel-tower/01-10: full tower blue sky, from the Champ de Mars, structure detail, night and dusk, aerial from Trocadéro side.
- **Open gaps:** the exact current paint tone (the 2019-2025 repaint is a lighter yellow-brown than the older bronze-brown, not verified in a dated photo); LED vs sodium projectors at night not verified.

### Arc de Triomphe (49.54 m)
- **Heights and plan:** 49.54 m high, 44.82 m wide, 22.21 m deep; main vault 29.19 x 14.62 m (through the avenue axis), transverse vaults 18.68 x 8.44 m (Wikipedia EN). OSM outline way/226413508 is 50 x 28 m (base and steps included); parts: body 47 x 24 m to 47 m, attic corners 49 to 50 m, four 6 m bollard pieces.
- **Facade:** ashlar limestone, no windows; four groups of sculpture (Rude's Marseillaise on the east front), a frieze of soldiers under the attic, 30 shields on the attic; a deep cornice. The interior of the vaults is coffered.
- **Colours (sampled):** arc-de-triomphe/01 ([Arc_de_Triomphe_de_l'Étoile_in_July_2011.jpg](https://commons.wikimedia.org/wiki/File:Arc_de_Triomphe_de_l%27%C3%89toile_in_July_2011.jpg), blue sky, noon sun): sunlit front wall box `0.485,0.6,0.525,0.8` median `#bfbfbc`, bright30 `#c9cac8`; the wall beside the left sculpture `0.28,0.61,0.31,0.78` median `#c8c9c5`, bright30 `#dbdad4`. The stone reads cool neutral grey-white under blue sky; a warm-cast photo would read `#cfc7b4` (est.). Row tint `#c4c1b6` (est., slightly warmed).
- **Massing / the table:** the buildings table holds six parts of the Arc (47, 49, 50 m and three 6 m), all from 0 m: the vaults are solid. The main vault (29.19 m high, 14.62 m wide) and the four transverse vaults must be cut by hand: a `[[structures]]` figure of four piers (each about 15 x 22 m in plan), a lintel body from 29.2 m to 44 m, and the attic 44 to 49.5 m, or `min_h` kept for the parts (the OSM parts w226413509/514 carry min_height 38 and 32).
- **Night:** warm golden floodlighting (region_research §6.3: `#ffd6a0` to `#ffc080`, no technical source); the flame under the vault; the twelve avenues' street lamps (sodium) ring the Étoile.
- **Refs:** arc-de-triomphe/01-08: three day views, blue-hour and night, detail of attic and vault, an orthophoto (2018) of the Étoile star and an oblique aerial.
- **Engine:** `floodlit` (no windows, floodlit at night) is the right existing style; cannot: the arches.

### Cathédrale Notre-Dame de Paris (96 m spire)
- **Heights and plan:** length 128 m, width 48 m (Wikipedia EN); west front two towers 69 m, each about 18 x 17 m in plan (OSM parts: unnamed, 69 m, areas 186 and 108 m2); nave and choir ridge 45 m (parts 93 x 15 and 48 x 14 m), aisles and chapels 33 m; the rebuilt spire 96 m (part way/1299835416, 5 x 5 m prism, roof pyramidal in OSM); transept flèche base on the crossing ridge. The reopening in December 2024 restored the spire and the roof (oak, lead).
- **Facade:** limestone (Lutetian), cleaned 2019-24 so it is lighter than its old soot-grey; the west front has three portals, a gallery of kings at about 20 m, the rose window, an open arcade, and two towers with paired lancet louvres (dark). Roof and spire lead: mid grey with a blue cast, dark at the ridge.
- **Colours (sampled):** notre-dame/01 ([Cathédrale_Notre-Dame_de_Paris,_20_March_2014.jpg](https://commons.wikimedia.org/wiki/File:Cath%C3%A9drale_Notre-Dame_de_Paris,_20_March_2014.jpg), evening light): left tower shaft `0.13,0.2,0.21,0.42` mean `#a89c8b`, median `#afa28e`, bright30 `#d7d0c3`; the left buttress `0.10,0.62,0.13,0.9` `#a2a8a0` (bluish shade); the lower wall between portals in shade `#868477`. Lead roof and spire (notre-dame/07, box `0.6,0.47,0.75,0.55` and `0.505,0.15,0.535,0.45`): `#929d9f` and `#aeb9c5` median, bright30 `#dfe3e7` (sky reflections), dark side `#444446`. Row tint `#bdb29e` (est.: between the sampled mean and bright30, since the restored stone is pale); lead `#8d9298` (est.).
- **Massing:** the table holds five named parts (96, 45, 45, 45, 33 m) plus unnamed 69 m tower parts and two degenerate 78 m parts: a blocky cross with two square towers and a prism spire. Profile row left empty: `tops@` would stack the two zero-area 78 m parts before the 96 m spire (the spire would run 78 to 96 m only) and `crown@` cuts the tallest named body (45 m). Proper spire: a tapering octagon from the 45 m ridge to 96 m (base about 8 m across, about 2 m under the tip), a structure or a `tops@` that skips parts under 0.2 m2.
- **Night:** LED lighting since reopening, 1,400 projectors, 2200-5000 K range, 3000-3500 K normally (region_research §6.3): suggested `#ffd9a8` on the west front.
- **Refs:** notre-dame/01-10: west front, east end and spire, Seine dusk, dusk lit front, aerials and the nadir orthophoto of the Cité.
- **Open gaps:** the towers' names in the table (not matched), the current spire's geometry.

### Basilique du Sacré-Cœur (83 m)
- **Heights and plan:** total 83 m; central dome about 21 m in outer diameter (OSM part w226727341 21 x 18 m, roof dome 23 m over a 50 m base); four small domes at 46 m; campanile 91 m incl. cross (Wikipedia FR; not in the table); hill 130 m a.s.l.; Greek-cross plan with a long west-east extent (OSM base 87 x 50 m).
- **Facade:** Château-Landon lacustrine limestone that exudes calcite in rain and stays white; scale-like ribbed domes, a portico of three arches, equestrian statues (verdigris bronze).
- **Colours (sampled):** sacre-coeur/03 ([Basilique_du_Sacré-Cœur_de_Montmartre,_Paris_18e_140223_2.jpg](https://commons.wikimedia.org/wiki/File:Basilique_du_Sacr%C3%A9-C%C5%93ur_de_Montmartre,_Paris_18e_140223_2.jpg), blue sky, February sun): main dome sunlit `0.38,0.32,0.60,0.44` mean `#b1a99f`, median `#beb6aa`, bright30 `#e4dcd0`; left small dome in shade `0.17,0.60,0.27,0.72` median `#c5bdb1`; portico wall `0.32,0.87,0.65,0.90` mean `#998c83`. The stone is warm ivory, not blue-white. Row tint `#cfc8bb` (est. near median-to-bright30).
- **Massing:** row profile `crown@50:dome:0` cuts the 73 m central dome part (21 x 18 m) at 50 m and lofts a quarter-ellipse dome to 73 m (untested; it becomes a grey spire-style body). The 83 m lantern (10 m2 part) is not in the table. The four 46 m small domes are cylinders from 0.
- **Night:** floodlit warm white, a little cooler than the other monuments (`#ffe2b8` est.; sacre-coeur/08-10 show cool white on blue hour).
- **Refs:** sacre-coeur/01-10: day fronts, gardens below the butte, dome views from the top, three dusk/night.

### Pyramide du Louvre (21.6 m)
- **Dimensions:** 21.6 m high, 34 m square base (OSM 35.42 m), sides at 51.52 degrees; 673 panes: 603 rhombic and 70 triangular (Wikipedia EN); stainless steel rods and cables; extra-clear laminated glass (from memory, not re-verified). Three sunken pools with fountains (Cour Napoléon) and three small pyramids.
- **Colours:** the glass takes the sky: overcast `#6d6f74` mean over a dark-lattice background, the rhombs over blue sky `#889dd1` (sampled, louvre-pyramid/03, [Louvre_Pyramid_and_Cour_Napoléon,_Paris.jpg](https://commons.wikimedia.org/wiki/File:Louvre_Pyramid_and_Cour_Napol%C3%A9on,_Paris.jpg), boxes `0.30,0.40,0.36,0.50` and `0.62,0.55,0.9,0.58`; the second box is the sky, the first the dark lattice/glass). Interior seen through the glass is warm cream (the Louvre stone). Row tint `#7f93a8` (est.). The surrounding Louvre stone: Denon/Sully facade `0.75,0.62,0.94,0.70` mean `#615345` in shade, bright30 `#8a7c6b` (sampled, shade); the roofs slate `#645e61`.
- **Massing:** profile `0:1 1:0.03` scales the square footprint linearly from 100 % to 3 % over the 21.6 m, giving faces at about 52 degrees: correct for a pyramid. Style `lattice` is a diamond lattice with glass/panel infill (module 1.9 m est.). The table holds the pyramid alone (h 21.6 m, landmark).
- **Night:** interior warm uplight; wings gold `#e8b25a` (est.); neutral `#e6f0ff` for the glass (region_research); pools mirror it.
- **Refs:** louvre-pyramid/01-14: day views, dusk and night, aerials of the courtyard.

### Tour Montparnasse (210 m)
- **Dimensions:** 209 m to the roof, 210 m with the 2.9 m glass screen, 59 floors + 6 basements, almond plan 50 x 32 m with triangular notches at both ends (Wikipedia FR), 7,200 windows on 40,000 m2 of facade; 56th-floor observatory at 200 m and a roof terrace; OSM outline way/16406633 is 62 x 39 m.
- **Facade:** dark smoked-bronze glass with dark grey-brown steel piers: reads near black in shade, dark grey-brown under haze. Sampled (tour-montparnasse/01, [Manifestation_Internes_14oct2007_(4).jpg](https://commons.wikimedia.org/wiki/File:Manifestation_Internes_14oct2007_(4).jpg), hazy morning, seen from above): the left face `0.10,0.03,0.20,0.33` mean `#595d5a`, median `#575a56`, bright30 `#7e807a`; the darker right face `0.23,0.03,0.33,0.33` `#4e5353`, median `#464c4d`. Row tint `#454a4a` (est., below the hazy mean since sun-lit views read darker and warmer).
- **Massing:** a straight prism with a plain top; no setbacks. The almond plan is the OSM outline and needs no profile. Module 1.35 m is derived (about 122 windows per floor around a 164 m perimeter).
- **Renovation:** a bioclimatic double-skin facade by Nouvelle AOM (competition 2017) with transparent glazing, planned from 2026; height up to 220 m: the dark facade is the state to model unless the work is complete (not checked).
- **Night:** offices lit, bright top; the base by the station.
- **Refs:** tour-montparnasse/01-08: the tower from Rue de Rennes, the Luxembourg garden, the Seine, an autumn view, night; the views FROM the tower are in `area-paris-overview-from-montparnasse/`.

### Panthéon (83 m)
- **Dimensions:** length 110 m, width 84 m, height 83 m (Wikipedia EN); Corinthian portico with 22 columns of about 19 m; the drum with a 32-column peristyle; a triple dome; a lantern and cross. OSM parts: portico blocks 70 x 24 and 104 x 24 m to 32.4 m; dome part 25 x 25 m to 74.5 m (roof dome 13 m, so the drum top is at 61.5 m); drum block 35 x 35 m to 59.8 m; lantern 83 m (5 x 5 m).
- **Facade:** limestone with blind side walls (the windows are walled up), garlands in the frieze. The dome is lead-covered, blue-grey.
- **Colours (sampled):** pantheon/01 ([Panthéon_de_Paris_in_July_2022_(2).jpg](https://commons.wikimedia.org/wiki/File:Panth%C3%A9on_de_Paris_in_July_2022_(2).jpg), evening sun): flank `0.62,0.57,0.80,0.75` mean `#b1926a`, median `#bf9e73`, bright30 `#cead83` (warm, low sun); dome `0.50,0.20,0.58,0.27` `#8c8d91` (sunlit lead). pantheon/02 ([Pantheon_of_Paris_007.JPG](https://commons.wikimedia.org/wiki/File:Pantheon_of_Paris_007.JPG), golden hour): flank `0.66,0.68,0.84,0.84` median `#e8ba73`, bright30 `#fbd689` (too orange). pantheon/03 ([Le_tambour_et_le_dôme_du_Panthéon,_Paris_2021.jpg](https://commons.wikimedia.org/wiki/File:Le_tambour_et_le_d%C3%B4me_du_Panth%C3%A9on,_Paris_2021.jpg), blue sky): dome `0.46,0.32,0.62,0.48` mean `#748397`, bright30 `#becddb`. Row tint `#c9bb9b` (est. neutral light, between the sunlit and shaded samples); dome lead `#8c8d91` to `#748397`.
- **Massing:** crown row `crown@61.5:dome:0` (untested) cuts the 74.5 m dome part at 61.5 m and lofts the 13 m dome; the lantern is an existing 83 m spire part. The drum colonnade is a solid cylinder.
- **Night:** warm floodlight on the stone, dome lit cooler; pantheon/07-09.
- **Refs:** pantheon/01-09.

### Dôme des Invalides (107 m) and Hôtel des Invalides
- **Dimensions:** dome church 107 m with the lantern, dome 90 m (Wikipedia EN), gold leaf 12.65 kg on the dome (Wikipedia EN); two nested domes. OSM parts: base cross block 31 x 26 m to 34.2 m, block 32 x 24 m to 48.1 m, a 28 x 28 m circular part to 72 m (roof dome 16.8 m, so a drum to 55.2 m), a 9 x 9 m part to 77.6 m, 5 x 5 m to 85.6 m, a 1 m2 spire part to 100 m (the real spire tip is about 107 m). The Hôtel: 274 x 256 m outline, wings 30 m (parts).
- **Colours (sampled):** invalides/04 ([Dôme_des_Invalides,_Paris_10_October_2010.jpg](https://commons.wikimedia.org/wiki/File:D%C3%B4me_des_Invalides,_Paris_10_October_2010.jpg), low sun): dome `0.58,0.31,0.70,0.40` mean `#9b8d71`, bright30 `#e8d7ac`; invalides/01 ([South_facade_of_Dôme_des_Invalides.jpg](https://commons.wikimedia.org/wiki/File:South_facade_of_D%C3%B4me_des_Invalides.jpg), sunset light): dome `0.44,0.335,0.53,0.40` mean `#88764d`, bright30 `#d2bb7e`; drum `0.41,0.47,0.55,0.52` `#796141`; the stone body was in shade in every box (median `#8c8068`, `#706753`): stone tint is est. `#c6b998`. Gilding as a wall tint: `#c8a94f` (est.); gold under a warm floodlight reads `#ffc24a` (region_research).
- **Massing:** OSM stops at 100 m and builds the dome as a 28 m cylinder: at distance a silo. A figure spec from the parts and the photos (est.): drum radius 13.4 m, `y 48.1 to 55.2 m` cylindrical with a colonnade; dome from 55.2 to 72 m, quarter ellipse to the ring at radius 4.5 m; lantern 72 to 85 m (radius 4.5 to 2.5 m); the spire 85 to 107 m (radius 2.5 m to 0.3 m, gilded). `crown@` cannot do it (the tallest non-spire part is the 77.6 m shaft).
- **Night:** gold floodlighting (`#ffc24a`, region_research; invalides/07, 08 show it).
- **Refs:** invalides/01-09: front and side views, aerials, dome floodlit, courtyard at dusk.
- **Engine:** cannot: a gilded wall colour on a dome (the crown style is hard-coded grey `#b8bcc0`), the drum's colonnade.

### Opéra Garnier (Palais Garnier, 58 m stage house)
- **Dimensions:** 154.9 x 70.2 m at the lateral galleries; 32 m to the top of the facade block and 56 m to the flytower (Wikipedia EN; landmark CSV 70 m is OSM's outline height incl. the dome and statues); OSM parts: stage house 59 x 38 m to 58 m, auditorium dome part 35 x 31 m to 51 m, facade block 128 x 59 m to 35 m, pavilions 15 x 15 m with copper domes at 36.5 m; an APUR footprint (55 x 39 m, 63.6 m) sits unnamed beside them.
- **Facade:** 17 kinds of stone and marble; front of paired columns on a loggia with round windows, gilded bronze groups on the side pavilions (Apollo group on the stage house), a copper dome patinated green, a pale beige stone.
- **Colours (sampled):** opera-garnier/06 ([Palais_Garnier_façade_nord_Paris_1.jpg](https://commons.wikimedia.org/wiki/File:Palais_Garnier_fa%C3%A7ade_nord_Paris_1.jpg), afternoon sun): left pavilion `0.22,0.47,0.29,0.72` mean `#937769`, median `#967a65`, bright30 `#b9b5aa`; gable wall `0.38,0.30,0.52,0.42` mean `#847762`, bright30 `#a99c84`. opera-garnier/01 ([Palais_Garnier,_Paris.jpg](https://commons.wikimedia.org/wiki/File:Palais_Garnier,_Paris.jpg), overcast): dome `0.36,0.22,0.54,0.27` mean `#8fa396`, bright30 `#acc3b6`; the columns `0.13,0.50,0.16,0.68` median `#989693`; a gilded group `0.19,0.15,0.24,0.24` bright30 `#e7e6d2` (overexposed). Row tint `#b3a78f` (est.: warm beige toward bright30); copper dome `#8fa396`; gilded statues `#c9a63e` (est.).
- **Massing:** OSM parts already give the stepped mass. `crown@` cannot dome the 51 m part (the tallest named non-spire body is the 58 m stage house).
- **Night:** floodlit warm gold facade with the domes lit (opera-garnier/07, night `#ffd6a0` est.).
- **Refs:** opera-garnier/01-08.
- **Engine:** cannot: 17 stones, the columns, the green dome tint (roof shapes take one tint).

### Grande Arche de La Défense (110.9 m)
- **Dimensions:** 112 m (along the axis) x 106.9 m x 110.9 m high (Wikipedia FR); prestressed concrete frame, foundations 30 m deep, 300,000 t, turned 6.3 degrees from the Louvre-Étoile axis (EN says 6.33); the void 68.9 m wide (106.9 - 2 x 19, est. from OSM wall thickness 19 m) and about 100 m high (Wikipedia gives only that it could shelter Notre-Dame and is as wide as the Champs-Élysées); the roof slab about 10.9 m thick (est.); a PTFE-fibreglass membrane canopy ("le Nuage") in the void; panoramic lifts; 12 pillars. The side walls' outer face is glass (2.5 ha, 5 cm thick) and marble (3.5 ha).
- **Facade:** Carrara marble panels on the axis faces, replaced with Bethel White granite from Vermont in 2010-17 after freeze damage (Wikipedia EN); joints in a grid of about 2 m panels (grande-arche/06, est.), glass slot windows and mirror glass on the inner faces of the walls (grande-arche/07: dark mirror glass).
- **Colours (sampled):** grande-arche/01 ([Grande_Arche,_France_-_April_2011.jpg](https://commons.wikimedia.org/wiki/File:Grande_Arche,_France_-_April_2011.jpg), hazy midday, seen small from the parvis): sunlit side face `0.42,0.62,0.45,0.72` median `#f2f4f5`, bright30 `#f6fafc` (overexposed); top beam `0.34,0.58,0.44,0.62` median `#969494` (underside). The granite is a very light grey; row tint `#e0ded8` (est.); glass `#3e4a5c` (est. from grande-arche/07 sky-reflecting dark blue).
- **Massing / the table:** the table has 9 parts at 104.2 m: a 108 x 104 m block (area 9,752 m2, the roof slab's footprint), one 112 x 19 m wall and slivers, all from 0 m. So the void is filled by the roof slab's footprint extruded from the ground. Fix: keep `min_h` (OSM parts w225694300/304/310/313/319/321/332 have min_height 101-108 m and 110 m top) or build a `[[structures]]` figure: two side walls 112 x 19 m x 110.9 m, a roof slab 112 x 106.9 m from 100 to 110.9 m, a floor slab, and the inner void. The `whole=true` option cannot make a hollow shape (one outline).
- **Night:** the faces lit white/cool (`grande-arche/04`); the opening framed against La Défense.
- **Refs:** grande-arche/01-11: from the axis, the Esplanade car park (framed), night, aerial at dusk, marble detail. Exterior daylight close-ups are scarce on Commons for this cube (most files are of the rooftop and the steps).

### What the current engine can and cannot do for these (summary)
- Can: `floodlit` monuments with a sampled tint (no windows), `glass`/`lattice` on the Louvre pyramid with a pyramid profile, a curtain-wall tower (Montparnasse) with a derived bay, `limestone` (NEW STYLE) for palaces.
- Cannot: solid-from-the-ground parts (arches, the Grande Arche void, lantern gaps): `min_h` dropped in M2; an open lattice (Eiffel); domes with their own tint (the crown style is grey `#b8bcc0`, hard-coded in `tiles.crown()`); a dome part that is not the tallest non-spire body (Invalides, Opéra); unnamed parts of a named landmark (Notre-Dame's towers); `tops@` with zero-area 78 m parts (Notre-Dame spire); sculpted stone (Arc frieze, gothic tracery).


## La Défense and its towers

#### How the La Défense numbers were made

**Photos.** Wikimedia Commons, scripted (search API and categories, contact sheets, 800 px files in `demos/data/paris/refs/<slug>/`, `refs/index.md` lists each file page, licence and author). Commons has few finished-tower photos of the 2019-2026 towers (Hekla, Link, Trinity, Alto, Saint-Gobain and Carpe Diem are mostly construction shots; Eqho and Duo have almost nothing), so tints of the new towers come from the Jan 2023 skyline shot from the Arc (`tour-hekla/05_...janv.jpg`) and from close-ups of the glazing.

**Colours.** "Sampled" = `samp.py`: mean, median, mean of the brightest 30 % and darkest 30 % (luminance) of a box given as image fractions `x0,y0,x1,y1` (origin top left) in the 800 px file, drawn back on the image to check. Glass values are sky-dependent (blue sky vs overcast), so tints sit between the two. Anything else is **(est.)**. Identification in the skyline photo was done by bearing from the Arc (tower lat/lon in `landmarks_paris.csv`, the Arc at 48.8738, 2.2950; about 69 px per degree in the 960 px image), so those samples carry an identity risk.

**Heights.** `buildings.gpkg` gives some heights lower than the landmark list by 6-8 m (The Link Arche 235.6 vs 242, Saint-Gobain 170.1 vs 178, Hopen 159.5 vs 167, Michelet 109.8 vs 117): `h_src = landmark@slab`, height measured above the dalle (the deck is about 7 m over the boulevard). That is consistent; the rows below quote both.

**Which towers are built of OSM parts** (their `profile` would be ignored, `whole` left blank): Tour First (parts 231, 234, 190, 173, 170 m), Coupole (relation parts to 187), Eqho (4 relation parts, 130 m), Europlaza, Hyatt. Every other tower here is one footprint, so its profile applies.

### Sampled boxes (all La Défense rows)

| File (refs/) | Box | Conditions | mean / median / bright30 / dark30 |
|---|---|---|---|
| tour-areva/01 (Areva beside a newer tower) | 0.66,0.25,0.90,0.70 | shaded face, blue sky | #1d2127 / #16171c / #363f49 / #0d0f14 |
| tour-areva/02 (April 2011) | 0.22,0.15,0.38,0.50 | hazy afternoon | #525353 / #545352 / #63625f / #3f444a |
| coeur-defense/01 | 0.28,0.25,0.48,0.75 | blue sky, low sun | #adaa8d / #cec8a5 / #efebcb / #474b36 |
| the-link/01 (Jun 2025) | 0.24,0.25,0.42,0.60 and 0.50,0.35,0.70,0.60 | blue sky | #59779a / #527398 and #577ba5 / #577ea9 |
| the-link/02 (Oct 2025) | 0.28,0.25,0.50,0.60 | low warm sun | #796e63 / #746b63 |
| the-link/03 (Seine tower in cladding) | 0.20,0.30,0.45,0.60 | blue sky, cloud | #6b8094 / #678899 |
| tour-majunga/01 (Unsplash, dusk) | 0.72,0.35,0.87,0.85 | dusk overcast | #4c5155 / #484e53 / #7a7a7e / #242b30 |
| tour-majunga/04 (close-up) | 0.12,0.15,0.50,0.50 | day | #747e7f / #66777e / #b1b6b2 / #474e4d |
| tour-alto/06 | 0.35,0.55,0.60,0.85 | overcast HDR | #5c676a / #647375 / #909fa5 / #1e2020 |
| tour-alto/01 | 0.25,0.50,0.75,0.80 | Oct 2018, mixed light | #51524e / #50524e |
| tour-d2/01 | 0.02,0.10,0.30,0.60 | blue sky | #414c57 / #2e3a4a / #8796a3 / #13181f |
| tour-carpe-diem/01 | 0.30,0.52,0.65,0.80 | Mar 2012, partly glazed | #455c62 / #3d5f62 / #798e99 / #1a2826 |
| tour-saint-gobain/02 | 0.30,0.40,0.60,0.75 | overcast | #68737c / #707c86 / #a1acb6 / #252c33 |
| tour-saint-gobain/03 | 0.45,0.75,0.75,0.95 | overcast, white top glass | #d5d5d3 / #f3f6f6 |
| tour-trinity/02 | 0.08,0.72,0.40,0.95 | blue sky, low frame | #768699 / #627a99 / #cbd1d5 / #36475e |
| tour-first/01 | 0.11,0.10,0.25,0.25 | crown glass, blue sky | #7a93aa / #537ca5 / #cbd4da / #2f5276 |
| tour-triangle/01 | 0.30,0.50,0.70,0.75 | blue sky, sunlit | #6aa6be / #6aa8c0 / #98cee0 / #427f9b |
| tour-triangle/02 | 0.35,0.35,0.55,0.55 | overcast, backlit | #39414b / #373f4a |
| tribunal-de-paris/01 | 0.31,0.12,0.45,0.40 (tower); 0.60,0.50,0.85,0.68 (low glass); 0.02,0.45,0.25,0.75 (podium cladding) | blue sky | #a9b7c3 / #b1becf; #698ebb / #6991c1; #33435e / #334461 |
| tours-duo/02 | 0.37,0.06,0.50,0.35 | grey day, far | #46505d / #485768 |
| tour-hekla/05 (Arc, Jan 2023) | Hekla 0.17,0.34,0.20,0.50; Coupole 0.735,0.33,0.775,0.50; T1 0.835,0.36,0.855,0.50; Areva 0.675,0.42,0.70,0.58; First crown 0.615,0.38,0.645,0.50; CB21 or SG 0.565,0.36,0.595,0.50; Trinity area 0.63,0.45,0.66,0.58 | overcast, 4.8 km | Hekla #838c99 / #6d7b91; Coupole #7a8798 / #6f7f92; T1 #76808d / #5f6a7c; Areva #627083; First #b0babf (sky glare); CB21 #65757d / #607078; Trinity area #b4bcbd |
| la-defense-other-towers/06 | 0.30,0.40,0.55,0.80 (Ariane); 0.80,0.15,0.98,0.50 | blue sky, from below | #6f7d76 / #707d75 / #a4b0a4 / #3b4b4b; #84959b / #708489 |
| la-defense-other-towers/09 | 0.12,0.25,0.26,0.70 (pale 1970s tower); 0.41,0.40,0.52,0.75 (slanted-top green tower); 0.70,0.35,0.80,0.65 | hazy blue sky | #71787a / #7a8284; #4c5c5d / #45595b; #858e94 / #82909a |
| la-defense-other-towers/04 | 0.30,0.20,0.45,0.65 (curved blue-glass tower, Place des Pyramides) | blue sky | #718c94 / #678993 / #d1dcdc / #1c3f4d |
| tour-areva/03 (photo5) | 0.42,0.42,0.57,0.70 (rounded tower judged Eqho); 0.88,0.25,0.99,0.60 (EDF glass tower) | cloudy, bright | #737a78 / #78807e; #687b89 / #5c7586 |

### The towers

#### The Link (Arche, 242 m; Seine, 178 m) (Philippe Chiambaretta, 2025)
- **Heights:** Arche 242 m, 52 floors; Seine 178 m, 35 floors; 35 "link" platforms join them (Wikipedia EN, FR list). Table: 235.6 m (above the dalle). Duplex floors of about 6,000 m2 across both.
- **Facade:** double-skin insulating façade with photovoltaic panels, concrete structure, "neo-futurist". Glass reads clear blue in blue sky; in the Oct 2025 photo the Arche face is amber (low sun): not a tint.
- **Colours:** Arche `#5a7590` (blue-sky mean #59779a, sky-lit face #577ba5), Seine `#4e6b8c` (darker in every photo: dark30 #11305a). Sources: `the-link/01, 02, 03`.
- **Massing:** Arche footprint 1,728 m2 (65 x 52 m box), Seine 1,719 m2. Two parallel towers of unequal height, linked by platforms every 5 floors or so: the platforms are not in OSM, not modelled.
- **Night:** floors lit, the link platforms read as lit bands (no photo yet).
- **Engine:** can do the glass tower; cannot do the sloped crown or the platforms. **Gaps:** finished-day close-ups with neutral light.

#### Tour First (Pierre Dufau 1974; KPF and SRA 2007-11)
- **Heights:** 231 m (arrow), 225 m roof, 203 m last floor, 55 floors, +50 m added in the renovation.
- **Facade:** ventilated double-skin glass (KPF); blue-grey mirror with a tapering crystalline glass crown (photo `tour-first/01`); the 1974 tower was a three-branched star at 120 degrees around a core, and the plan still reads as a lobed form.
- **Colours:** sunlit crown glass mean `#7a93aa`, median `#537ca5`; sky-glare face `#b0babf` (Jan 2023, overcast). Tint `#5d7691`.
- **Night:** the crown is lit in colours that indicate tomorrow's weather (FR Wikipedia).
- **Massing:** OSM parts (231, 234, 190, 173, 170 skillion roofs, one 259 m pyramid tip of 0 x 2 m): profile would be ignored; the landmark cap holds it at 231 m (rows `landmark_cap`). **Engine gap:** the crown's skillion cuts come from the parts only.

#### Tour Hekla (Jean Nouvel, 2022)
- **Heights:** 220 m, 48 floors (51 levels with technical spaces), floors 1,700 m2, ceilings 3 m, 76,000 m2 (Wikipedia FR, Paris La Défense).
- **Facade:** glass and metal prismatic silhouette, terraces or loggias on every floor (2,518 m2), a rooftop hanging garden.
- **Colours (est. from overcast only):** the Jan 2023 face reads mean `#838c99`, median `#6d7b91` reflecting cloud; the tower is darker than the skyline around it. Tint `#5f6d84`, `bands` with variant 0.35.
- **Massing:** faceted, leaning, chamfered top; single OSM outline (2,269 m2, 48 x 81 m). **Engine cannot:** lean or chamfer (a uniform loft scales about the centroid). **Gaps:** no finished close-up on Commons.

#### Tour Majunga (Jean-Paul Viguier, 2014)
- **Heights:** 194 m roof (CTBUH), 45 floors, floors 1,350-1,550 m2, 67,200 m2.
- **Facade:** three adjoining planes, one with a wave-like bevel; stepped garden loggias on every floor; bioclimatic façades, opening windows.
- **Colours:** dusk `#4c5155`; day close-ups mean `#747e7f`, median `#66777e`. Tint `#5c6c74`.
- **Massing:** outline 867 m2, 51 x 46 m. The notch and stepping are not modelled. `tour-majunga/01` shows the tower's notched top well (right of frame).

#### Tour Trinity (Cro&Co, Jean-Luc Crochon, 2020)
- **Heights:** 167 m with spire, roof 151 m, 33 floors, 49,000 m2, floors 1,600 m2 on average, a decentred core; terraces, loggias, 3,500 m2 plaza.
- **Colours:** `tour-trinity/02` box: mean `#768699`, median `#627a99` (blue sky, cladding not finished). Tint `#6c7f96`, `bands` variant 0.6.
- **Massing:** 2,150 m2 plan, 37 x 87 m (very elongated): stepped terraces not modelled. (The English Wikipedia "Trinity Tower" page describes another tower; not used.)

#### Tour Alto (IF Architectes and SRA, 2020)
- **Heights:** 160 m from the street, 150 m from the dalle, 38 floors above ground; 51,200 m2.
- **Facade:** rounded plan, curved glass between pale concrete slab edges; floors grow 12 cm per level, from 700 m2 at the base to 1,500 m2 at the top (FR Wikipedia).
- **Colours:** overcast glass mean `#5c676a`, median `#647375`; dusk `#51524e`. Tint `#5d686c`, `bands` variant 0.9 for the pale slab edges.
- **Massing:** profile `0:0.78 1:1` (est.; assumes the footprint is the top plate). Night: `tour-alto/05` shows the curved glass with irregular lit offices.

#### Tour Carpe Diem (Robert A. M. Stern with SRA, 2013)
- **Heights:** 166 m with spire (162 m from the boulevard, roof 154.3 m from the platform), 34 floors, 5 terraces, 47,100 m2, LEED Platinum.
- **Colours:** mean `#455c62`, median `#3d5f62` (blue-green mirror, part-glazed in `carpe-diem/01`). Tint `#46606a`.
- **Massing:** stepped terraces and a pointed crown, not modelled; outline 1,702 m2 (49 x 65 m).

#### Tour D2 (Anthony Béchu with Tom Sheehan, 2015)
- **Heights:** 171 m in the list (OSM 175), 37 floors, 50,000 m2.
- **Facade:** asymmetric "avocado" volume (elongated Paris face, soft curved back) wrapped in a steel diagrid over dark glass. Sample: mean `#414c57`, median `#2e3a4a`, bright30 `#8796a3`.
- **Engine:** `lattice` (diamond members, tint = glass, variant = share of white panels): a fair match; the curved plan comes from the OSM outline (624 m2).

#### Tour Saint-Gobain (Valode and Pistre, 2019)
- 178 m (roof; 177.95 from the ground), 44 floors, 48,900 m2, replaced the Tour Generali project (265 m). Pale blue-grey glass: overcast mean `#68737c`; the top floors read white `#d5d5d3`. Tint `#6f7b84`. Table height 170.1 m above the dalle.

#### Tour Areva / Framatome (SOM with Roger Saubot and François Jullien, 1974)
- **Heights:** 184 m (178 in one list); 44 floors; 54.56 x 42.64 m prism.
- **Facade:** dark granite with tinted windows that widen towards the top, "the 2001 monolith". Sampled `#1d2127` (shaded), `#525353` (hazy).
- **Engine:** `bands`, tint `#2b3038`, variant 0.05. Cannot do the widening windows.

#### Tour CB21 (Wallace K. Harrison and Max Abramovitz with J. P. Bisseuil, 1974)
- 180 m roof, 187 m with antennas (list 179), 42 floors, Greek cross plan, 64,500 m2; ex Tour Gan; new glazing 2009-10. Tint `#5b6f78` (est.).

#### Cœur Défense (Jean-Paul Viguier, 2001)
- Two 161 m towers of 40 floors, three low blocks of 9, 350,000 m2; two-tone façade, rotunda-shaped ends. Sampled sunlit `#cec8a5`, bright30 `#efebcb`. Style `stone` (punched dark windows), tint `#cbc5a6`, module 1.35. Night: warm lit windows (`coeur-defense/02, 03`).

#### Tour Eqho (Willerval, Urquijo, Macola, 1988; ex Tour Descartes)
- 131 m, 40 floors, 77,000 m2, a parallelepiped with an extruded half-cylinder, no corner windows (pillars). Table: 130 m from four OSM relation parts. Colours from an unverified photo (`tour-eqho/01`): grey-green `#737a78`.

#### Tribunal de Paris (Renzo Piano, 2018-20)
- **Heights:** 160 m, 38 floors, 120,000 m2 net; a 5-8 storey podium follows the site, three stacked parallelepipeds shrink upward, about 10,000 m2 of planted terraces between them.
- **Colours:** white-glass tower mean `#a9b7c3`, median `#b1becf` (blue sky); lower glass `#698ebb`; dark grey-blue podium panels `#33435e`. Tint `#8fa3b8`.
- **Massing:** profile est. from `tribunal-de-paris/01, 02`: `0:1 0.36:1 0.36:0.82 0.68:0.82 0.68:0.64 1:0.64`. The podium is not in the tower outline (1,473 m2): build it as its own building or leave the OSM podium (8 levels).

#### Tour Triangle (Herzog and de Meuron, topped out 2026)
- **Heights:** 178 m roof, 180 m with spire (H&dM: 583 ft = 178 m), 42 floors (FR Wikipedia says 44), 162 m long, 54 m wide at the base, footprint 5,562 m2, 95,503 m2 GFA; about 16 m wide at the top.
- **Facade:** ventilated bioclimatic glass, photovoltaic recesses on the south face. Sunlit `#6aa6be`, backlit `#39414b`: tint `#5b8ba5`, light horizontal banding visible in `tour-triangle/01`.
- **Engine:** profile `0:1 1:0.2`; the OSM outline is `building=construction` (needs an override) and the real taper is asymmetric: gap.

#### Tours Duo (Jean Nouvel, 2021)
- Duo 1: 180 m, 38 floors, double skin of reflective scale-like panels with cantilevered glass fins; Duo 2: 122 m, 27 floors, single-skin reflective metal panels, enamelled glazing, stainless sun-breakers; 108,000 m2. Seven of eight faces lean up to 5 degrees.
- Colours: mean `#46505d` (a grey-day far shot); sunset silhouettes in `tours-duo/01` give the crowns' shapes. **Engine cannot:** lean.

#### CNIT (Camelot, de Mailly, Zehrfuss; Jean Prouvé façades, 1958)
- Triangular vault, 250 m sides, span 218 m, crown 46.3 m, 6 cm reinforced-concrete double shell on three buttresses tied by 44 steel cables; white, restored 2009; glass and metal end façades. Stand-in `plain` with `dome:0.1`.

#### Other towers (one CSV row each; most are ribbon-window or glass towers, colours (est.))
Chassagne and Alicante (167 m, Société Générale), Granite (184 m, silver-white, Portzamparc 2008), Coupole/TotalEnergies (187 m, 1985, dark blue-grey mirror glass), T1/Engie (185 m, 2008, curved hood), Ariane (152 m, grey-green glass with pale frames, sampled), Dexia/CBX (142 m), Europlaza (135 m, 1972), Défense 2000 (134 m, 1974), Aurore (131 m, renovated 2023), Les Poissons (130 m), France (126 m), Franklin (120 m), Séquoia, W, Michelet, CGI, Neptune, Manhattan, Ève, Initiale, Atlantique, Gambetta, Emblem, Opus 12, Allianz One. Tint families come from the generation palette below; refine when a photo is sampled.

#### La Défense facade palette
| Generation | Look | Style | Tint family (from the skyline photos) |
|---|---|---|---|
| 1960s-70s ribbon towers (Areva, Europlaza, Franklin, CGI, Manhattan) | dark or grey concrete and granite piers, continuous window ribbons | `bands`, module 1.6-3 m | black granite `#1d2127`-`#2b3038` (Areva); grey `#6a7176`-`#7d7f7c` (pale 1970s tower `#71787a`, `#7a8284`) |
| 1980s postmodern (Cœur Défense 2001, Eqho 1988, Coupole 1985) | cream stone-look or dark mirror glass, rounded corners, hoods | `stone`, `glass` | cream `#cec8a5`; dark mirror `#5f6a7c`-`#6f7f92` |
| 2000s glass (Granite, T1, Dexia, Ariane, Alicante) | silver, blue-grey or grey-green curtain wall | `glass` | `#6f7d76` (Ariane) to `#8a97a2` |
| 2010s+ (Majunga, Alto, Carpe Diem, D2, Saint-Gobain, Trinity, First, Hekla, Link) | loggias, diagrid, curved glass, terraces, double skin | `glass`, `bands`, `lattice` | `#3d4c5c` (D2), `#46606a` (Carpe Diem), `#5d7691` (First), `#5a7590` (Link) |
| Skyline average from 5 km (Jan 2023, overcast) | sky-lit cool grey-blue | | `#6d7b91`-`#8e939a`; distant towers `#b4bcbd` (glare) |
| Esplanade paving | pale grey-beige stone | | `#b5ada0` (est.) |

#### Engine gaps found (La Défense)
1. A profile scales the actual footprint about its centroid: no lean (Duo, Hekla), no notch (Majunga), no asymmetric taper (Triangle), no podium plus tower (Tribunal).
2. A profile is ignored for towers made of OSM parts (First, Coupole, Eqho, Europlaza): `whole` would merge them but lose the crown cuts.
3. Roofs cannot take a colour of their own (Coupole dome, T1 hood, Triangle glass roof): the wall shader's roof colour is shared.
4. Two-tone façades (Cœur Défense cream over dark glass) have no style; `stone` is the closest. Areva's windows widen with height.
5. The Link's 35 platforms, the D2 diagrid's curvature and the CNIT's triple-curved vault need structures or a mesh.

#### Open gaps (La Défense)
No finished-day photo: Hekla, Eqho and the Duo façades. Colours (est.) for about 30 lesser towers. Which OSM footprint is Duo 1. First's crown parts above 231 m. Night lighting of the newest towers (no photo). No architect/year check for the 1970s towers beyond the FR/EN Wikipedia lists.

## Big monuments, churches, 1960s-70s towers and bridges

#### How the colours in this part were made

Photos are 800 px Commons thumbnails in `demos/data/paris/refs/<slug>/` (index in `refs/index.md`). Two methods:

- **Boxes (towers, glass, panels):** `samp.py` gives mean, median, bright30 and dark30 (mean of the brightest and darkest 30 % of pixels by luminance) of a box in image fractions `x0,y0,x1,y1` (origin top left); the box was placed on plain wall after reading a 10 % grid overlay, away from sky and foliage. Boxes are quoted with the file.
- **Auto (stone monuments):** `auto.py` takes the middle 70 % x 70 % of the photo, drops sky (b > r+12), foliage (g > r+8 and g > b) and clipped pixels, and reports `mid` = median of the 40th-90th luminance percentile (wall without window shadows), `p90` = mean of the 88th-94th percentile (the sunlit wall) and `dark` = darkest 25 %. Sunlit values read brighter than albedo, shaded ones darker.
- Tints for stone are the sunlit p90 nudged toward the mid value; tints for glass are between the overcast and blue-sky samples (buildings-and-landmarks.md "Tint caveats"). Anything not measured is marked **(est.)**. Identification of a tower in a skyline photo by position is also marked (est.) where two towers look alike.

Styles: `limestone`, `concretepanel` are **NEW STYLE** proposals (below); everything else exists in `facade.js`. `whole` is blank everywhere: no profile depends on merging OSM parts except La Géode's sphere, which needs a single outline (see its section).

**NEW STYLE proposals**

| Style | Use | Palette (sampled) | Floor / bay | Windows |
|---|---|---|---|---|
| `limestone` | Monuments: Madeleine, Orsay, Hôtel de Ville, Louvre, Chaillot, churches | #d0c6b0 #cfc4a8 #c9bfa9 #c4beb2 #cdbb95 #c4bfb2 #bdb8aa #c6bfae #c9bfa4 #d0c6a8 #cbc4b6 #d0cabb (all in the csv) | 4.5 m floor, 3.6 m bay | tall punched openings (0.35 x 0.55 of a bay), a deep cornice band at the top, plinth band 3 m; parent `stone` so the per-style tables of `stone` apply until the shader learns it |
| `concretepanel` | 1960s-70s precast towers (Italie 13, Olympiades, Front de Seine, Ourcq, Flandre) | #b9b0a8 (Olympiades beige), #c1c4c8 (Italie 13 white-grey), #a9acb3, #9d6550 (red-brown), #858279 (brown-grey), #98a1a2 | 2.9 m floor, 2.4-2.7 m bay | continuous window strips 45 % of the floor height with dark spandrel bands; the pier colour is the tint, the window glass is dark (#3f3f4a) |
| `zincmansard` | not used in this part (no row needs it) | | | |

### Big monuments

#### Grand Palais (Avenue Winston-Churchill)
- **Heights and size.** Nave about 240 m long (paris.fr and Wikipedia FR quote 200 m x 50 m clear span plus paddock; 240 m overall is the commonly quoted length), 45 m to the dome ridge, roof glass about 17,500 m2, 6,000 t of steel (Wikipedia FR, paris.fr). CSV 45 m.
- **Facade.** Cream limestone front with a 200 m Ionic colonnade, mosaic frieze and bronze quadrigae at the corners (1900); the barrel-vaulted glass roof is rendered as a grey-green glass and steel skin.
- **Colours (sampled).** Sunlit p90 #beb8aa (grand-palais/04, blue sky, Seine side), #aba49e (02, CC0, shade), mid #8b7e73 (02). Tint `#c6bda9` (sunlit p90 warmed a little).
- **Night.** No technical source; the glass roof glows warm white from inside during events (grand-palais/06 shows the lit dome).
- **Engine.** Can: limestone box to 45 m. Cannot: the glass roof (a skin of glass and steel over the nave; use `panel`/`lattice` on a part or a structure) or the quadrigae.
- **Refs.** grand-palais/01-06.

#### Centre Pompidou (rue Saint-Martin)
- **Size.** 166 m x 60 m x 42 m (centrepompidou.fr); Piano and Rogers, 1977. Closed for renovation 2025-2030 (Commons has a "construction works" category).
- **Facade.** Exposed white steel truss frame with diagonal bracing, glass infill on the piazza side; escalator tube in red on the west facade; ducts colour-coded blue (air), green (water), yellow (electricity), red (circulation) and white (ventilation).
- **Colours (sampled).** Whole west facade box 0.05,0.10,0.95,0.60 of centre-pompidou/04 (overcast): mean #686868, median #5a5757, bright30 #b2b4b3. White ducts #d0cac4 (05). Tint `#9a9b9c`.
- **Engine.** Cannot: the tubes and the escalator (they are elements, not a wall). Proposal: NEW STYLE `exposedframe` (open steel bays with coloured ducts) or a box row of thin structures.
- **Refs.** centre-pompidou/01-07.

#### Louvre Palace
- **Facade.** Renaissance and classical facades in cream-honey stone with dark slate/zinc mansards; the Richelieu wing and Pavillon de Flore have tall mansard pavilions; the Cour Napoléon holds the glass pyramid (a must-have row of the other part).
- **Colours (sampled).** Richelieu wing p90 #dbcba4 (louvre-palace/03, storm light), #d7ccb1 (04); Cour Carrée cooler p90 #cecac2, mid #9e978d (05). Tint `#cfc4a8`. Mansard slate #4f5966 (region_research.md).
- **Night.** Facades floodlit warm gold; the Cour Carrée at dusk (06) shows the sodium-like yellow #d1b592 p90.
- **Engine.** Can: limestone body with the OSM relation's heights. Cannot: the mansard roofs' colour differs from the wall (no roof-colour channel for landmark rows).

#### Madeleine
- **Size.** 108 m x 43 m, 30 m high; peristyle of 52 Corinthian columns 20 m tall; no dome outside and no bell tower (paris.fr). The CSV says 30 m (OSM gives 36).
- **Colours (sampled).** p90 #d2c9b6 (madeleine/01), #d8cdba (02), mid #b4aa9a; tint `#d0c6b0`.
- **Engine.** Cannot: the columns and pediment relief (a box in limestone reads correctly from far away).

#### Palais de Chaillot, Musée d'Orsay, Hôtel de Ville
- **Chaillot (30 m).** Two curved wings of 1937 in cream limestone facing the Seine; p90 #e0e2e3 under bright overcast (palais-de-chaillot/02), mid #8f877d. Tint `#cec6b6` (est.). Night: floodlit warm white; the Eiffel Tower behind.
- **Orsay (35 m).** 1900 station: cream stone front with tall arched windows, clock windows and a glass vault; west facade p90 #f3ebdd (clipped), Seine side p90 #cac1af (musee-d-orsay/01). Tint `#c9bfa9`. Dusk: warm yellow through the vault (05, 06).
- **Hôtel de Ville (50 m).** Neo-Renaissance (1882), central clock tower, statues in niches, slate mansards; p90 #d6d3cd/#dddad3, mid #b2a89f. Tint `#c4beb2`. Dusk photo hotel-de-ville/04.
- **Engine.** Can: limestone bodies. Cannot: mansards and dormers on landmark rows.

#### Churches and belfries (one row each)
Saint-Sulpice (twin towers 73/70 m), Sainte-Chapelle (spire 75 m, rebuilt 1853), Saint-Eustache, Sainte-Clotilde (twin spires 69 m), La Trinité (tower 65 m), Saint-Augustin (dome 25 m across, more than 80 m, 100 m long; Baltard 1871, iron frame under a stone skin), Val-de-Grâce (dome over a 16-window drum, 1663), Saint-Vincent-de-Paul (Ionic portico, two towers), Saint-Germain-des-Prés (Romanesque tower), Saint-Germain-l'Auxerrois (belfry), Notre-Dame-de-la-Croix (spire 78 m), Saint-Jacques Tower (52 m to the balustrade, 54 m with the statue of Pascal), Gare de Lyon clock tower (67 m).

| Landmark | Stone samples (file) | Tint |
|---|---|---|
| Saint-Sulpice | mid #e4ca92 golden light (01); dusk lit #e08c13 | #cdbb95 (est.) |
| Sainte-Chapelle | p90 #cdc9be, mid #989187 (02) | #c4bfb2 |
| Saint-Eustache | p90 #c5c1b3, mid #817d77 (01) | #bdb8aa |
| Sainte-Clotilde | p90 #ccc5bc, mid #9a9590 (01) | #c6bfae |
| La Trinité | p90 #d2c9b0, mid #a89f87 (01) | #c9bfa4 |
| Saint-Augustin | p90 #dcd3b4, mid #a9a18a (01); night lit (03) | #d0c6a8 |
| Val-de-Grâce | p90 #cab9a6, mid #85776a (01) | #c4b59f |
| Saint-Vincent-de-Paul | p90 #d8d2c6/#cec8c1 (01, 02) | #cbc4b6 |
| Saint-Germain-des-Prés | p90 #dacfc0, mid #716e6a (01) | #bfb5a2 (est.) |
| Saint-Germain-l'Auxerrois | p90 #c5bca3, mid #9b917f (01) | #bdb39b |
| Notre-Dame-de-la-Croix | p90 #e7e3d5, mid #a39e98 (01) | #d0cabb |
| Saint-Jacques Tower | overcast mid #948c82 (02); golden #e1c59a (03) | #c9b998 |
| Gare de Lyon clock tower | p90 #cbc2bb, mid #86817d (02) | #bfb6a8 |

- **Night.** Notre-Dame-type warm floodlighting is a tradition, no technical source found for these; Saint-Eustache and Saint-Sulpice photographs show warm gold (`saint-eustache/02`, `saint-sulpice/02`: p90 #bfa77d and #f7ac1b in the photo).
- **Engine.** Cannot: spires, campaniles, domes and lanterns on landmarks made of one OSM outline. A `crown@<m>:<profile>` could carve a spire from a tower row once the tower height under the spire is known (Saint-Jacques' crown starts about 47 m; not measured here), so no profile was written.
- **Open gaps.** The spire heights above are the CSV's, not measured; no profile was justified for any church.

#### La Géode
- **Size.** Sphere 36 m across, 6,433 polished stainless equilateral triangles on a 2,580-bar tube frame (Adrien Fainsilber, 1985; pariszigzag.fr, timeout.fr). Height in the CSV 36 m.
- **Colours (sampled).** Mirror: box 0.42,0.25,0.58,0.45 of la-geode/01 (blue sky): mean #768185, median #71829a, bright30 #cacdcb. It mostly reflects the sky and the park, so the tint `#8d989c` is a neutral chrome (est.).
- **Profile.** `0:0.5 0.05:0.5 0.1:0.6 0.2:0.8 0.3:0.917 0.4:0.98 0.5:1 ...` is r/R = sqrt(1-(2f-1)^2) with f the height fraction; it is right only when the OSM outline is the 36 m circle (check the area, about 1,018 m2) and the outline is one polygon (no `whole` needed then). The bottom scale of 0.5 stands for the sphere meeting its plinth.
- **Night.** Lit blue-white; not verified.
- **Refs.** la-geode/01-03.

#### Institut du monde arabe
- Nouvel, 1987: south facade of about 240 aluminium diaphragms with photo-electric irises behind glass; north facade plain glass. Box 0.30,0.12,0.90,0.75 of institut-du-monde-arabe/03 (blue sky): mean #9cb2be, median #aec7d5, dark30 #465864. Tint `#7d93a0` (est.). The diaphragm grid (bays about 1.2-1.5 m, floors 3.5 m) is not modelled; `bands` gives horizontal lines only. Night: the photo institut-du-monde-arabe/01 shows backlit diaphragms.

#### Maison de la Radio
- Henry Bernard, 1963: round building of 500 m circumference and a central 68 m tower, 25,000 m2 (Cité de l'architecture and paris.fr). Concrete and glass; the Seine side shows ribbon windows. Sample p90 #9b9c8f to #d4d5d1 (maison-de-la-radio/01, /03); tint `#b5b5ae` (est.). The ring plan is OSM's; the row applies `concretepanel`.

### BnF, Hyatt, Zamansky, Pullman

#### BnF towers (Laws, Numbers, Times, Letters)
- Four L-shaped glass towers 79 m (Dominique Perrault 1995) around a garden on a 60,000 m2 ipe-wood esplanade (Wikipedia FR and pariszigzag.fr). Glass grey-blue: boxes 0.27,0.12,0.42,0.38 mean #515b6e and 0.60,0.12,0.72,0.38 mean #676c75 (bnf/03, blue sky, the two towers of the north-south row). Tint `#5f6772`, module 1.5 (est.). At night the towers glow amber in the corners (bnf/04, 05).
- Engine: the OSM parts give the L plan and the 79 m height; the wooden shutters and the deck are not modelled. Note: the deck is the whole 60,000 m2 esplanade, not a 60 x 8 m strip (the brief's figure was wrong).

#### Hyatt Regency Paris Étoile (Concorde Lafayette)
- Cylindrical tower 137 m (137 m real; OSM says 174 m), ribbed by cream piers about 0.6 of each bay with dark glazing; box 0.45,0.35,0.75,0.9 of hyatt-regency-etoile/01 (deep blue sky): mean #8e8c90, median #948684, bright30 #dddfdf, dark30 #313443. Style `piers` with the tint the glass `#3a3d4c`, module 2.4 (est.), variant 0.6. Rooftop antennas exist, not modelled.

#### Zamansky (Jussieu), Pullman, Super Montparnasse, Pitard
- Zamansky: glass tower 90 m, box 0.38,0.12,0.5,0.3 of zamansky-jussieu/02 (overcast): mean #5c727d, bright30 #8aa1ab; tint `#6a808b`.
- Pullman (116 m) and Super Montparnasse (90 m): dark shaft and dark-brown balconied slab from pullman-super-montparnasse/01 (box 0.82,0.2,0.96,0.5 mean #404348 in shade); tints est.

### 1960s-70s towers

#### Olympiades (Tokyo, London, Antwerp, Helsinki, Sapporo, Mexico, Athens, Cortina)
- Eight towers of 104 m (Michel Holley, delivered 1972 and 1976): Sapporo, Mexico, Athènes in 1972, Helsinki, Cortina, Tokyo in 1976; Londres and Anvers are the social-housing pair (Wikipedia FR and paris-promeneurs). Prefabricated concrete panels with a hyperbolic-paraboloid relief (Wikipedia FR).
- Colours (sampled): piers bright30 #c0bbb8 and #c2bbb5, spandrels dark brown #4f4249, pale window frames (olympiades/01 detail, boxes 0.29,0.05,0.34,0.95, 0.05,0.05,0.28,0.95, 0.40,0.05,0.60,0.95); at dusk the pink cast reads #b0a0a0 (07). Tint `#b9b0a8`, module 2.4 (est.).
- Per-tower colour was not verified, all eight share the family value.

#### Italie 13 (Ferrare, Ancône, Bologne, Palerme, Ravenne, Mantoue, Atlas, Verdi, Puccini, Rimini, Capri, Abeille, Bergame, Chambord, Super-Italie)
- About 30 storeys each, 1969-77, precast panels, white-grey with dark window strips (Wikipedia FR "Italie 13"); Super-Italie (Novarina 1974) is the only round tower. Chambord stands alone on Boulevard Kellermann.
- Colours (sampled, italie-13-towers/01, blue sky): white towers median #d1d4d8, bright30 #f1f3f5 (box 0.90,0.44,0.95,0.6); banded tower median #4f4f54, bright30 #c1c0c1 (0.24,0.28,0.36,0.6); Super-Italie median #6d7079 bright30 #c5c7cd. Tint `#c1c4c8` for the family, `#a9acb3` for Super-Italie; `variant` varies the window seed 0.1-0.9.

#### Chéops, Mykérinos, Chéphren, Antoine et Cléopâtre, Nouveau Monde, Béryl, Jade, Onyx, Rubis, Périscope, Albert
- 13e-14e 1970s towers; Chéops, Chéphren, Mykérinos stand on Boulevard Vincent-Auriol with slightly pyramidal bases; Périscope (Novarina 1971) is a 20-storey bar. No sample of these towers: family default `#b6b3ad` (est.).

#### Orgues de Flandre, Ourcq, Boucry, Chapelle, Bagnolet
- Orgues de Flandre IV: cream precast; mean #d2cdb4, median #e6e1c5 in warm evening light (tours-belleville-ourcq-flandre/01, box 0.68,0.28,0.76,0.5), tint `#c9c5b8`.
- Boucry (99 m): ribbon windows, overcast mean #4d4c47, bright30 #8b8a81 (03); tint `#6b6a63`, style `bands`.
- Prélude, Fugue, Cantate and the unnamed Ourcq tower: not identified in a sampled photo; family default.
- Super-Chapelle and La Sablière: Porte de la Chapelle towers, samples #95a0a1 and #7a8485 (05); identification est.
- HT1: box 0.48,0.2,0.58,0.6 of tours-porte-de-bagnolet-montreuil/01: mean #838a8c, bright30 #d1d3d0; a blue curved-glass neighbour (0.08,0.2,0.3,0.6) reads mean #728395. Giralda and Saint-Blaise: est.

#### Front de Seine (Cristal, Perspective 1-2, Novotel, Adagio, Mars, Seine, Totem, Avant-Seine, Reflets, Rive Gauche, Keller, Évasion 2000, Espace 2000) and the chimney
- 1970s towers of 92-98 m over the Seine (Beaugrenelle sector). Photos show grey-blue glass towers (mean #797e7f, front-de-seine/01), pale grey-white panel towers (median #939496, #a5a4a5 in 02), a brown-grey banded tower (median #84847d, 04), a red-brown tower (median #9d6550, 04), a twisted grey tower with ribbed bands (mean #606969, 03).
- The mapping of a colour to a named tower is by position and is (est.); the rows say so. The chimney (130 m) is a structure: the OSM box should be replaced by a thin tube.

### 1960s-70s tower palettes and the bridges

**Palettes for the 60s-70s towers (for the generic `concretepanel` and `residential` tables):** pale precast `#c1c4c8` (Italie 13), beige-pink `#b9b0a8` (Olympiades), grey-brown `#858279`, red-brown `#9d6550`, cream `#c9c5b8` (Flandre), dark ribbon `#6b6a63` (Boucry), blue-grey `#98a1a2` (Chapelle); window glass dark `#3f3f4a` to `#313443`; spandrel brown `#4f4249`.

**Bridges (reference photos only; no rows, for M3 deck builders):**
- **Pont Alexandre III (pont-alexandre-iii/01-06).** Single steel arch 107.5 m, lifted with gilt bronze: four 17 m pylons in pale stone with gilded Renommées (Pegasus groups) on top, 32 bronze candelabras in dark green-bronze with warm lamps (lit #ffd08a at dusk, photo 06), stone balustrades, nymph and lion groups; the arch ribs read pale blue-grey at dusk (photo 01, est.). Colours to use: pylon stone #cfc4a8, gilded #d9a441, lamp standards #2f3b32, arch steel #8e9aa3 (est.).
- **Pont Neuf (pont-neuf/01-06).** Stone bridge of 12 arches over both arms (238 m, 20.5 m wide), pale blond stone with dark cornice and carved mascarons under the cornice, hemicycle bays with benches over the piers, dark lamp posts. Stone #c9bfa4 (est. from pont-neuf/01, /03).
- **Pont de Bir-Hakeim (pont-bir-hakeim/01-06).** Two-level bridge: the roadway at quay level and Metro Line 6 on a steel viaduct above on a row of slender steel columns; masonry piers with a colonnade of the Île aux Cygnes; dark green painted steel (#3d4a3f est.) with pale stone piers; the Metro cars are white and green. Night: the viaduct lit by uplights (photos 05, 06).

#### Open gaps
- No exterior photo of Sainte-Clotilde's spires at dusk; no night photo of Hôtel de Ville/Louvre in daylight-lit condition beyond the dusk ones.
- Only one Hyatt photo; no photo of Chéops/Mykérinos/Chéphren, Béryl/Jade/Onyx/Rubis, Antoine et Cléopâtre, Nouveau Monde, Périscope, Albert, Giralda, Prélude/Fugue/Cantate, Pitard: tints est.
- Tower-by-tower colours for Front de Seine and Italie 13 depend on position only.
- Institut du monde arabe: no night exterior photo; diaphragm bay module est.
- Heights of the church spires are the landmark list's; no separate measurement.

## Standard AREA views: what the critic compares


All colours are sRGB hex sampled with `samp.py` (PIL: mean / median / bright30 = mean of the brightest 30 % of pixels / dark30) from the 800 px Commons photos in the folders named, boxes as fractions `x0,y0,x1,y1` of the image, top-left origin. Photographed tones depend on exposure and sky: sunlit values are read brighter than albedo, shaded ones darker. Anything not sampled is (est.). 191 images in 22 `area-*` folders; all daylight unless the tag says dusk or night. Light in most photos is spring or autumn, not late-September noon; the autumn folder is October-November.

#### area-paris-overview-from-montparnasse
Eight views from the observation deck (day, hazy, dusk and night). The critic's target for the whole-city overview: Paris is a low, even carpet of 18-25 m blocks with zinc-grey roofs and cream walls, the Haussmann avenues cut straight diagonals through it, La Défense and the Eiffel Tower are the only things standing up. Roof-and-wall mix in 02 (box 0.3,0.6,0.7,0.9): mean #574f43, bright30 #a99d8b (sepia light, low sun). Photos are hazy: contrast falls off fast with distance, the horizon is milky-blue.

#### area-paris-from-eiffel-tower
Ten oblique aerials from the 2nd/3rd platform. 06 (sunlit blocks, boxes 0.1,0.33,0.35,0.5): sunlit cream stone wall mean #8b816f, bright30 #dfd2b1; a mansard slope in shade box 0.05,0.62,0.3,0.7: median #4c4c44. The 21/22 shots (golden light) show that roofs read as a mix of zinc-grey (#8c8f90) and dark slate with lighter orange-tan walls. Trees fill the courtyards and the avenues; shade in the courtyard trees is very dark (#1e2116 median).

#### area-haussmann-boulevards
Boulevard Haussmann and neighbouring boulevards. 01 is the one aerial-like view (from a Printemps/Lafayette roof): zinc-grey mansard roofs (box 0.3,0.03,0.7,0.2: mean #a7afb8, bright30 #dde3e8, hazy blue-white), asphalt in shade (box 0.55,0.62,0.7,0.8: #34384a, blue-cast shadow), and a cream facade sunlit at the right (bright30 #dedad1). The street shots show 6-7 storeys, continuous balcony line at the 2nd and 5th floors, ground-floor shops with dark frames, a zinc mansard over a stone cornice, plane trees on both sides.

#### area-marais
Place des Vosges (brick pavilions with stone quoins, steep blue-grey slate roofs, arcades) and the Francs-Bourgeois streets (narrow, 8-12 m, stone hotels, low dormers). Place des Vosges 01 (boxes 0.32,0.31,0.55,0.38 slate: mean #889094 median #7f888d; 0.55,0.42,0.7,0.5 brick: median #c59a7f, bright30 stone #f1e8d6; lawn 0.1,0.86,0.5,0.96: mean #44502f). One dusk shot (09) shows warm window light on stone.

#### area-latin-quarter
Boulevard Saint-Michel and Rue Mouffetard. 05/06 give the October tree colour (yellow-olive: box 0.05,0.15,0.3,0.45 mean #65583f in 05; box 0.6,0.5,0.9,0.6 mean #49422a in 06) and the asphalt (05 box 0.3,0.7,0.7,0.9: #5b5656; 06 box 0.35,0.75,0.65,0.95: #656368). The streets are 25-30 m wide with pavement, trees, stone facades.

#### area-montmartre
Rue Saint-Vincent, Rue de l'Abreuvoir wall, Place du Tertre, the ivy-covered villas, a cobbled lane at dusk. Lower, smaller houses (2-4 storeys), plaster walls, stone retaining walls, cobbles, green shutters, red awnings. Sunlit rubble stone from the analogous side-street set: #9a8a6c median, bright30 #d7caac (side-street 05). No good day aerial of the butte was found on Commons in this pass; the Sacré-Cœur folder (F1/me) and zinc-roofs 05/06 give the skyline.

#### area-ile-de-la-cite-aerial
Seven pictures: oblique and vertical aerials (18, 4, 5, 1, 13: the Cité as a boat-shaped island, roofs continuous to the quay wall, two Seine arms, dense grey-cream) and the Notre-Dame blue hour. The vertical ones are lower resolution and have a colour cast.

#### area-champs-elysees-axis
Aerials from the Arc (20, 19, 14, 37, 15) and eye-level (7, 9, 39, 34). Axis is about 70 m between building lines, 8 carriageway lanes plus two tree rows (chestnuts and planes) each side; facades 21-25 m, cream stone and grey zinc. Asphalt from the aerial 01 (box 0.47,0.65,0.58,0.9): mean #55555a median #4d4c51; roof and facade zone box 0.6,0.15,0.75,0.3: #707277 (hazy).

#### area-street-rue-de-rivoli
Rivoli terrace facades, arcades with stone piers and lamps, corner blocks. Uniform 6-storey pale stone, continuous arcade at street level, shops behind it. 39 is an aerial of Rivoli and the Tuileries.

#### area-street-haussmann
Rue de Rome, Boulevard Saint-Germain, Place Saint-Michel and Rue de Châteaudun: the reference for a 20-30 m Haussmann street. 01 (Rue de Rome, blue sky, sunlit): stone box 0.6,0.1,0.85,0.5 mean #a59d8f median #b7b0a3 bright30 #f2ead9; box 0.42,0.3,0.55,0.55 mean #a39d94 bright30 #f4eddf; road in shade 0.15,0.8,0.5,0.95 mean #474f5c (bluish). 02 (open shade, Blvd Saint-Germain) facade box 0.3,0.28,0.5,0.34 mean #c1beb7 median #c1bbb1. 03 plane-tree canopy in leaf (box 0.15,0.05,0.7,0.4): mean #516d39 median #45622e bright30 #8baa6b (green summer foliage). 07 (low golden sun): sunlit wall mean #74634c bright30 #c6aa81, the other side in shade mean #8e8375 bright30 #c5bdac, asphalt #737372. 08, 09 are suburban (Ivry, Boulogne): asphalt and road markings only. 06 is the dusk shot with warm lit windows.

#### area-zinc-roofs
Ten roof views. 01 close on zinc: sunlit mean #7f8280 median #909390 bright30 #adb1b0; in shade box 0.05,0.7,0.35,0.95 median #777e83 (blue-grey). 03 (from Beaubourg): pale zinc slopes mean #959699 (box 0.35,0.28,0.6,0.42) next to near-black slate (median #292930 in box 0.02,0.65,0.3,0.85, shaded); chimney stacks in white-cream stone, 1-2 m wide, dormers with white windows every 3-4 m. 04-06: roofs at distance grey #8c8a8a with orange-tan walls. Mansards are 2 storeys, 45-70 degrees, top flat zinc terrace.

#### area-seine-water-level
Ten views from the river: bateaux-mouches, the Louvre wing from the water, Pont Neuf arches from the quay, houseboats and barges. Water colour: blue sky day box 0.75,0.72,0.95,0.9 (02): mean #415261 median #354859 (bright30 #879fb6); flat light day 01 box 0.05,0.8,0.5,0.95: mean #686b68 median #636867 (grey-green). Quay walls are pale stone, 5-6 m above the water, with a flat tow-path and plane trees on the upper quay.

#### area-street-side-street
Nine views of 10-14 m streets in the 11e (Rue Amelot, Oberkampf, Pelée, Pihet, Ternaux). 01: asphalt sunlit-shade mean #4e4e4e median #4d4d4d, bright30 #636463; 05 (very narrow): sunlit rubble wall box 0.02,0.2,0.4,0.55 mean #95886d median #9a8a6c bright30 #d7caac, shaded wall box 0.85,0.15,0.98,0.55 mean #585148, road box 0.35,0.86,0.75,0.95 median #5d584f (asphalt with light patches). Shop blinds in red, dark green, white; cycle lanes; 6-storey plaster and stone walls, plane trees sparse.

#### area-trocadero-eiffel
Trocadéro fountains, terrace, Champ de Mars from above and two night views (gold Eiffel). Symmetric pale-stone Chaillot wings in 16. Gravel and lawn in the gardens; the Eiffel Tower is warm brown-grey against blue sky (`#6d5a4a` to `#8b7355` per region_research).

#### area-tuileries-louvre
Cour Napoléon and pyramid, Carrousel, Tuileries alleys (gravel #b8ad98-like, not sampled), Cour Carrée facades and two dusk views (lit pyramid, fountains). Louvre facades: pale limestone, blue-grey slate mansards with tall dormers, gilded details.

#### area-paris-skyline-night
Thirteen night/dusk views: high aerials of the lit axes with the Eiffel beacon, the Seine at night, Notre-Dame and Pont Neuf blue hour, a lit Haussmann block, street shopfronts. Street lighting is warm (sodium-like #ffb070 in old photos, LED white-warm today); monuments are floodlit gold; the sky glow is orange-brown at the horizon.

#### area-paris-autumn
Eight views: Luxembourg orange and yellow trees, plane-tree boulevards, Champs-Élysées chestnuts. Blvd Auguste-Blanqui 03: canopy box 0.05,0.05,0.4,0.4 mean #6f6c53 median #5f5b3d bright30 #bdbca8; pavement box 0.4,0.75,0.7,0.95: mean #bfb7a7 median #cac1b0 (pale paving). Luxembourg leaf litter on gravel box 0.3,0.8,0.6,0.95 of 01: median #a77746. (Photos are late October to November; late September is greener.)

#### area-quais-bouquinistes
Green bouquiniste boxes on the parapet, plane trees, stone quay, Notre-Dame and Palais de Justice. Quay pavement (03, box 0.05,0.8,0.5,0.95): mean #858171 median #8d8975 bright30 #c2bcaa (sunlit gravel/stone). Parapet stone 03 box 0.6,0.62,0.95,0.75: mean #6e6d67 (in shade). Boxes are dark green (#3a4a3e-like, box 04 not sampled).

#### area-place-des-vosges, area-rue-mouffetard, area-canal-saint-martin, area-batignolles-13e
Six, six, eight and five photos respectively. Place des Vosges: red brick #c59a7f (median), stone quoins #f1e8d6, slate #7f888d, trimmed limes, lawn #44502f mean (Marais 01). Mouffetard: narrow 6-8 m cobbled market street, 4-5 storey plaster facades in cream, ochre and pale green, awnings. Canal Saint-Martin: 25-27 m canal between stone quays, plane-tree rows, iron footbridges. Batignolles/Bercy: only five photos, mostly construction cranes and the Bercy Village warehouses; a good modern zinc/glass Batignolles set was not found.

#### Area palette summary
| Item | Value | Evidence |
|---|---|---|
| Haussmann stone, sunlit, blue sky | mean `#a59d8f`, median `#b7b0a3`, bright30 `#f2ead9`; albedo suggestion `#d6ccb6` | street-haussmann/01, box 0.6,0.1,0.85,0.5 |
| Stone in open shade | `#c1bbb1` median (overcast-like) | street-haussmann/02, box 0.3,0.28,0.5,0.34 |
| Stone at golden hour | sunlit bright30 `#c6aa81`, shaded side `#c5bdac` | street-haussmann/07 |
| Shaded rubble/plaster wall (narrow street) | `#585148` mean | side-street/05 |
| Sunlit rubble stone | `#9a8a6c` median, `#d7caac` bright30 | side-street/05 |
| Zinc roof, sunlit | median `#909390`, bright30 `#adb1b0` | zinc-roofs/01 |
| Zinc roof in shade | `#777e83` median (blue-grey) | zinc-roofs/01 |
| Pale zinc slopes at distance | `#959699` mean | zinc-roofs/03 |
| Slate roof | dark, median `#292930` in shade (near black); sunlit blue-grey `#7f888d` | zinc-roofs/03; marais/01 Vosges |
| Brick (Place des Vosges) | `#c59a7f` median sunlit | marais/01 |
| Pavement (quay gravel/stone) | `#8d8975` median, `#c2bcaa` bright30 | quais-bouquinistes/03 |
| Asphalt, in shade | `#4e4e4e` (median `#4d4d4d`) | side-street/01 |
| Asphalt, sunlit | `#737372` | street-haussmann/07 |
| Asphalt on the Champs-Élysées, from above | `#55555a`, median `#4d4c51` | champs-elysees-axis/01 |
| Seine, blue sky | mean `#415261`, median `#354859` | seine-water-level/02 |
| Seine, flat light | `#686b68` mean, `#636867` median | seine-water-level/01 |
| Tree foliage in leaf (Blvd Saint-Germain, summer green) | mean `#516d39`, median `#45622e`, bright30 `#8baa6b` | street-haussmann/03 |
| Lawn | `#44502f` mean | marais/01 |
| Autumn plane canopy (Nov) | mean `#65583f`, `#6f6c53` | latin-quarter/05, autumn/03 |
| Leaf litter on gravel | `#a77746` | autumn/01 |

## M4 landmark massing (the `profile`, `take` and `roof` columns)

The engine now reshapes landmarks made of parts in 06_tiles (directives, see the engine README "Landmark facades
and massing"). What each row does, from the parts listed above and the photos in `refs/`:

| Landmark | Cell | Why (photos, dimensions) |
|---|---|---|
| Tour Triangle | `long:0:1:1 1:0.1:0.6`, `bands` 0.7 | tour-triangle/01-05: a trapezoid on the long face (162 m base, about 16 m at the top) with a slim end; the old uniform `0:1 1:0.2` made a square pyramid. Floor bands are visible in every photo |
| Dôme des Invalides | `crown@55.2-72:dome:0` gilt `#c4a45c`, lantern `crown@72-77.6`, `tops@77.6` (lantern shaft, spire to 100 m) | the 28 m cylinder (48.1-72 m) is now drum to 55.2 m and a gilt dome; invalides/02, /05: from afar the dome reads gold (est. between the sampled #9b8d71 mean and #e8d7ac bright30). The spire tip is 100 m in OSM (107 m real) |
| Panthéon | `crown@61.5-74.5:dome:0` lead `#8a8e95`, `tops@74.5` lantern | pantheon/03, /04: lead dome over the colonnaded drum (the drum stays a solid cylinder) |
| Sacré-Cœur | `take=8`, `crown@59-73` (a 23 m dome from 50 m read as a bullet) and `crown@38-46` domes, campanile `crown@70-80`, white `#dcd6ca`; APUR's 40-44 m dome duplicates `h@..=30` | sacre-coeur/01: travertine white main dome and four small domes; the campanile's OSM parts were unnamed |
| Notre-Dame | `take=10` (the two 69 m towers, unnamed OSM parts, now stone, no apartment windows), nave roofs `crown@33-45:long:...` lead `#80868c` gables, `tops@45` spire tapering 45-96 m | notre-dame/05, /08: lead ridge roofs at 45 m, thin lead spire. The parvis in front is paving (ground: M5) |
| Arc de Triomphe | `h@47=49.5` (attic), corners 49/50 to 49.5 | 49.54 m (Wikipedia); `floodlit` is windowless stone |
| Grande Arche | `h@104.2=110.9`, `lid@93` | 110.9 m from its parvis; OSM's lid is 1 m stacked slices (the "step strips"): now one 18 m lid over the void |
| Tour Duo 1 | `wing@83:w1130750788` | APUR's 4,130 m² roof-plan outline held the tower (OSM 2,799 m²) and a 1,222 m² wing at the tower's 180 m; the wing takes APUR's median 83 m (est.). The lean is not modelled |
| Cœur Défense (tour 1) | `take=8`, `h@97.6=161`, `h@155.2=161` | the 240 m² and 61 m² joining pieces notched the twin 161 m towers |
| Tour First | `crown@225:0:1 1:0.8` glass `#7a93aa` | roof 225 m, crystalline crown to 231 m (tour-first/01) |
| Tour Areva | `h@184=178` | the brief's roof height 178 m (Wikipedia FR list); 184 m in OSM/CTBUH is kept in landmarks_paris.csv |
| Tour T1 | `crown@169:0:1 1:0.7` glass `#6b7a8e` | 185 m with the curved glass hood, roof about 169 m |
| Opéra Garnier | `take=2` (APUR's 63.6 m flytower piece inside the stage walls), `h@63.6=58`, stage roof `crown@52-58:long` gable `#6f8a80`, dome `crown@44-51:dome:0` copper `#8fa396` | opera-garnier/01: verdigris dome; the flytower gable. Statues not modelled |
| Hôtel de Ville | `h@22.5=28`, `crown@22.5-28:0:1:0 1:1:4` slate `#4f5966` | APUR h_med 28.1 m; slate hipped pavilion roofs over 22.5 m walls. The 50 m campanile has no part: not modelled |
| Grand Palais | nave vaults `crown@25-42:long:...` (a barrel across each 42 m part), dome `crown@30-45:dome:0.15`, glass-and-steel grey `#929c9e` | grand-palais/03, /04: grey glass barrel vaults and dome over the stone ranges (the green of the dome's flanks is not modelled) |
| Val-de-Grâce | `crown@41-52.8:dome:0` lead `#6f767e`, `tops@52.8` lantern | val-de-grace/01 |

Not done (no part to shape or no generic feature yet): the Sorbonne chapel and the Institut de France (one flat
APUR footprint each), The Link's sky bridges, Duo's and Hekla's leans, the Hôtel de Ville campanile.

## Engine gaps found (all parts, for the M4 and M5 plan)

1. **`min_h` lost in the buildings table**: arches (Arc de Triomphe), the Grande Arche's void, raised drums and lanterns are solid from the ground. Fix in 04/M2 (keep OSM `min_height`, cut stacked parts) or model those as `[[structures]]` figures.
2. **A profile scales the actual footprint about its centroid**: no lean (Tours Duo, Hekla), no notch (Majunga), no asymmetric taper (Triangle), no podium plus tower (Tribunal de Paris), no lens plan (Montparnasse: the OSM outline supplies it).
3. **Towers made of OSM parts ignore `profile`** (First, Coupole, Eqho, Europlaza, all monuments); `whole=true` would lose crown cuts and cannot make hollow shapes.
4. **`crown@` is grey and takes the tallest non-spire body**: the tint is hard-coded `#b8bcc0` (gilded Invalides, lead Panthéon, green copper Opéra domes cannot have their colour); Invalides and Opéra have a taller non-dome part.
5. **Roofs take no colour of their own** (domes, mansards, Coupole hood, Triangle's glass roof); `tops@` stacks parts sequentially and would take Notre-Dame's zero-area 78 m parts into the spire.
6. **Unnamed parts of a named landmark** (Notre-Dame's towers) get no row.
7. **An open lattice** (Eiffel Tower, D2's diagrid, Pompidou's truss, the Link's platforms, CNIT's shell) needs a structure, a mesh or an alpha-cut style.
8. **No two-tone facade style** (Cœur Défense cream over dark glass, Areva's windows widening with height); no stone-relief styles (Arc frieze, Notre-Dame tracery, Opéra's 17 stones).
9. **Photo evidence is thin for**: Hekla, Eqho, Duo and Trinity finished facades; Saint-Sulpice, Saint-Eustache, Val-de-Grâce, Saint-Germain-des-Prés, La Trinité (1-2 photos); Grande Arche daylight exteriors on Commons (mostly rooftop and steps); early-autumn foliage (all tree photos are summer or November); Batignolles/Bercy modern facades; a dedicated dusk for Trinity, Hekla, Eqho.

## Open gaps (whole file)

- Wikipedia-only dimensions: the Panthéon's 22 portico columns of about 19 m and the 32-column peristyle, the Louvre pyramid's glass make-up, the Grande Arche's void size (68.9 m x about 100 m derived from OSM wall thickness), Notre-Dame's vault height and roof ridge (not re-verified in this pass).
- Montparnasse's renovation status (the dark facade is modelled; the 2026+ double-skin facade is not).
- Night colours are from `region_research.md` §6.3 where no photo exists (Arc, Panthéon, Louvre pyramid: judgement, not measured).
- Colour of the current Eiffel paint (2019-25 repaint); LED vs sodium projectors.
