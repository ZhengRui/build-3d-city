# Berlin landmark facades: photo research

Companion to `landmark_facades.csv` (140 rows, the columns the engine reads: `name, facade, tint, module, variant,
profile, whole, take, roof, notes, near`), to `landmarks_berlin.csv` (the heights and points) and to the reference photos in
`demos/data/berlin/refs/` (git-ignored; `refs/index.md` lists each file with its Commons page, licence, author and what it
shows). Written for Berlin M4 (facade styles and landmark massing), 2026-10-02, modelled on London's `landmark_facades.md`.
Method: Wikimedia Commons photos (refs/, 574 files at the time of writing), contact sheets with a 20 % grid viewed by eye,
colour sampling of boxes given as image fractions `x0,y0,x1,y1` (origin top left) with PIL (`mean`, `median`, `mid40-90` =
median of the 40-90 % lightness band, `bright30` = mean of the brightest 30 %; sky pixels dropped only where the note says
so); Wikipedia DE/EN and OSM for dimensions. Every value marked (sampled) was measured on the named file and box; (est.) is a
judgement from the photos; [believed] is recalled knowledge not checked against a source; nothing is invented as sampled.

**Coverage.** All 140 rows of `landmarks_berlin.csv` have a row. 43 rows carry a photo-sampled colour; the
others are family rows whose tints are estimates (their notes say [believed] or [est.]). Photos exist for the 14 must-haves
and most of the Museum Island, the Potsdamer Platz, Breitscheidplatz and Alexanderplatz rows; the Karl-Marx-Allee, Hansaviertel,
Treptow and Kreuzberg rows are the weakest (see refs/index.md for what the photo set has). Styles used: `floodlit` 35, `glass` 22, `monument` 21, `concretepanel` 18, `brickstone` 15, `panel` 11, `limestone` 8, `bands` 5, `stone` 3, `factory` 1, `house` 1.
Rows whose building does not exist (Covivio, Hines, M50) or that are structures/bridges/terrain document the look for
`[[structures]]` and the DEM; `06_tiles` will print 'no building named ...' for them.

## How the rows are read by the engine

Same as London's note: `name` = `name_zh` in `landmarks_berlin.csv`; `facade` holds only styles that exist in the preset
(glass, fins, bands, piers, lattice, panel, stone, monument, limestone, concretepanel, floodlit, brickstone, factory, house...);
new styles are proposed below, not used in the column. On the glass-wall styles `tint` is the glass colour, on the others the
wall colour. `profile` is ignored for landmarks made of OSM parts unless `whole=true` (none here: no Berlin tower needed it
yet; the Kollhoff profile is a proposal). `take` (m) joins unnamed parts to the named outline (Dom 4, the Gendarmenmarkt
domes 5, Humboldt Forum 5, Gedaechtniskirche ruin 4). Monument variants: 0.1 arcade, 0.3 palace, 0.5 gothic, 0.65 peristyle,
0.7 blank ashlar.

## NEW STYLE proposals (Berlin)

| Style | Used by | Wall palette (sRGB) | Floor / bay | What it draws | Parent |
|---|---|---|---|---|---|
| `clinker` | Rotes Rathaus, Kollhoff-Tower, Oberbaum bridge, Friedrichswerder church, Martin-Gropius-Bau, brick factories, Kaiserzeit civic brick | Rotes Rathaus `#b8573a` (orange-red, sampled over-orange `#e79a62`), Oberbaum `#a4523a` (sampled `#984f36`), Kollhoff `#8a5a48` (sampled median `#ab836c`, mean `#876b5b`) | 3.6 m (Rathaus), 4-5 m Kollhoff windows | deep-set windows with pale stone surrounds and bands; Kollhoff: tall narrow punched windows with projecting frames | `brickstone` |
| `ceramictile` | Karl-Marx-Allee blocks, Frankfurter Tor towers | cream/ivory `#e0d8c4` [believed; unsampled] | 3.0 m | smooth light tile cladding, stone base, regular windows, balconies | `limestone` |
| `staggerframe` | Upper West | frame `#e0e5e6` (sampled mid40-90), glass dark blue-grey | 3.3 m floor, 4 m bay | rounded shafts wrapped in a staggered white frame grid (windows cut out of it) | `bands` |
| `goldpanel` | Axel-Springer-Hochhaus, Philharmonie (dull gold anodised aluminium) | Springer `#b8a468`, Philharmonie `#86743f` (sampled) | 3.5 m | metal panels with a shaded joint grid, no window style | `panel` |
| `altbau` | Gruenderzeit blocks (see region_research) | cream `#d9cfb2`, ochre `#c9b07a`, grey `#b8b4aa` | 3.5 m ground, 3.2 m upper | stucco bands, vertical windows with lintels, 22 m cornice | `house` |

## 1. Must-have landmarks: what the row says (full numbers in the CSV notes)

Photos: `demos/data/berlin/refs/<slug>/NN_...`; 'slug/NN' is the file number in that folder.

### Berlin TV Tower (Fernsehturm)
- **Row:** facade `floodlit`, tint `#b9bdc1`, module 0, variant -, roof `#c8c8c4`.
- **Look, sampled colours, gaps:** STRUCTURE, build as a [[structures]] figure (the OSM prism is a 368 m column of the pedestal's width: do not extrude). Silver-grey sphere: sampled (sampled on refs/fernsehturm/02, box 0.30,0.45,0.70,0.58): mean #9ca0a4, mid40-90 #bbbec1, bright30 #edeeed: the skin is faceted pyramids that catch the sun, so the tint is the mid-high value #b9bdc1. Shaft: pale concrete grey #b8b8b4 with dark porthole bands (5 sections, DE) [est.]; the antenna above the sphere is a white/pale mast with a red top (fernsehturm/02 top: red-white banded cap) [seen, colours est. #c9c9c6 and #b8392f]. Dimensions from Wikipedia DE: shaft 16 m -> 9 m diameter, sphere 32 m centred at 213.78 m, foundation 42 m, 368.03 m total. Night: the sphere is lit warm white from inside at the deck band, the shaft is lit only at its foot; red aircraft-warning lights at the tip.

### Brandenburg Gate
- **Row:** facade `monument`, tint `#c8c2b0`, module 5.0, variant 0.65, roof `#7e9b88`.
- **Look, sampled colours, gaps:** Brandenburg Gate: Doric peristyle on a blank attic: variant 0.65 (peristyle, one free-standing column per bay on a podium; the Madeleine's setting), module 5 m (the bays are about 5 m; est. from refs/brandenburg-gate/01). Sampled (sampled on refs/brandenburg-gate/01, box 0.42,0.50,0.45,0.78 = a sunlit column): mean #c7c2b2, mid40-90 #cfcab9; attic frieze box 0.25,0.30,0.75,0.37 mean #9b9d91, bright30 #d3d2c2 (shade): tint #c8c2b0 (pale warm sandstone). Quadriga: green-patinated copper on top (roof #7e9b88, seen); the two Torhäuser (guard-house temples) at each side are separate low Doric blocks. Night: floodlit warm white (brandenburg-gate/03).

### Reichstag building with glass dome
- **Row:** facade `monument`, tint `#c8b690`, module -, variant 0.3, roof `#aebcc4`.
- **Look, sampled colours, gaps:** Reichstag: palace variant 0.3 (arched windows between pilasters, a central Corinthian-column portico) for the Wallot block; the Foster glass dome is not in any style: build it as a lathe of glass + steel (24 ribs, 38-40 m dia, 23.5 m high; roof #aebcc4 glass). Sampled (refs/reichstag/01, dusk sun, box 0.12,0.50,0.38,0.65) mean #ae9e7f, median #beae8a, mid40-90 #d8c4a1, bright30 #f1e0be; refs/reichstag/02 (golden hour, box 0.30,0.42,0.55,0.65) mean #9f7f5c, mid40-90 #c19a72: warm sand stone, tint #c8b690 (sampled neutral-ish). Four corner towers with low roofs; main roof flat metal. Night: dome lit warm from within; facade floodlit (reichstag/05).

### Berlin Cathedral
- **Row:** facade `monument`, tint `#7c7a74`, module -, variant 0.3, take 4, roof `#79948a`.
- **Look, sampled colours, gaps:** Berlin Cathedral: Neo-Renaissance/Baroque (monument variant 0.3 palace is the closest; 0.5 gothic is wrong). Sooty Silesian sandstone, dark grey: sampled (refs/berliner-dom/03, box 0.15,0.55,0.35,0.70, overcast shadow) mean #434848, mid40-90 #474b4b, bright30 #727878: tint #7c7a74 (the cleaned stone is lighter, est.). The domes are verdigris copper: sampled (refs/berliner-dom/05, box 0.45,0.30,0.65,0.45, sky dropped) mean #7c8f86, median #81958b, mid40-90 #8ca096, bright30 #9fb2ab: roof #79948a (grey-green teal; darker/bluer in shade, refs/berliner-dom/01 dusk), gold lantern with a cross (#c9a227, refs/berliner-dom/05). Four corner cupolas, a central drum with columns. take 4 for the corner-dome parts [est.]. Night: floodlit warm, the dome blue-green (berliner-dom/01).

### Red City Hall (Rotes Rathaus)
- **Row:** facade `brickstone`, tint `#b0643f`, module 3.6, variant 0.5, roof `#7d8f88`.
- **Look, sampled colours, gaps:** Rotes Rathaus: red clinker brick with terracotta bands. Sampled in neutral daylight (refs/rotes-rathaus/01, wing box 0.12,0.70,0.38,0.82) mean #9d6042, median #a66341, mid40-90 #ba6f4b, bright30 #cb8965; tower box 0.45,0.30,0.53,0.50 mean #88573f, mid40-90 #a76a4d; in refs/rotes-rathaus/02 (golden hour) the same brick reads #e79a62/#fc9f5c (too orange): tint #b0643f (the neutral mid value). Tall arched windows in three rows over a plinth, the square clock tower with a lantern and a small green copper roof (#7d8f88 est.); roofs flat/low. Night: lit windows (rotes-rathaus/04).

### Kollhoff Tower (Potsdamer Platz 1)
- **Row:** facade `brickstone`, tint `#8a5a48`, module 2.4, variant 0.6, profile `0:1 0.55:1 0.55:0.88 0.78:0.88 0.78:0.7 0.92:0.7 0.92:0.45 1:0.18`, roof `#7f6a5c`.
- **Look, sampled colours, gaps:** Kollhoff Tower: dark red-brown clinker, tall narrow punched windows with projecting frames. Close-up (refs/kollhoff-tower/03, box 0.2,0.35,0.8,0.80, oblique light) sampled mean #876b5b, median #ab836c, mid40-90 #ba9279, bright30 #cdaa94; seen from the square against the sun (refs/potsdamer-platz-area/02, box 0.38,0.25,0.44,0.60) the whole tower is a dark maroon-brown silhouette: mean #47434f, median #383848, mid40-90 #5a515a, bright30 #7a6d74: tint #8a5a48 (between). In refs/db-tower/04 the same tower reads pale beige in a backlit/hazy frame (sun glare on the pale mortar). Step-backs: profile est. from refs/potsdamer-platz-area/02 (a stepped crown with a pyramidal top: 0.55, 0.78, 0.92 of 103 m) [est.]; the 115 m tip is the lantern/mast in OSM. Module 2.4 m is est. (window bay).

### Bahntower (DB Tower, Potsdamer Platz)
- **Row:** facade `glass`, tint `#2c4a68`, module 1.5, variant -, roof `#8b98a6`.
- **Look, sampled colours, gaps:** Bahntower: dark blue glass, a cylindrical west face: sampled (refs/db-tower/04, box 0.10,0.10,0.40,0.55) mean #1f3853, median #173658, mid40-90 #254767, bright30 #43698a: tint #2c4a68 (a mirror of the sky; clearer glass reflects #43698a on bright sections). Glass fins with a stepped crown; DB logo lit at night (db-tower/05). Module 1.5 m est.

### Sony Center (tent roof)
- **Row:** facade `floodlit`, tint `#d6d3cb`, module 0, variant -.
- **Look, sampled colours, gaps:** Sony Center forum roof: STRUCTURE (a tent of PTFE-coated fibreglass on a steel ring: white-grey #d6d3cb by day, lit from within by coloured LEDs at night; refs/sony-center/02, /05). The wings are glass-and-steel office blocks (refs/sony-center/04). Cone height 67 m (DE).

### Kaiser Wilhelm Memorial Church, ruined old spire
- **Row:** facade `monument`, tint `#7c7a71`, module -, variant 0.5, take 4, roof `#5c5650`.
- **Look, sampled colours, gaps:** Ruined old tower: sooty grey-brown stone with ornate Neo-Romanesque detail and a broken, roofless top: sampled (refs/gedaechtniskirche/01, box 0.18,0.35,0.30,0.65, sky dropped) mean #68685f, median #595d58, mid40-90 #7c7a71, bright30 #c2b8a5: tint #7c7a71. Variant 0.5 (arches, buttresses, an octagonal stair turret). Night: floodlit warm (gedaechtniskirche/04).

### Kaiser Wilhelm Memorial Church, new octagon and bell tower
- **Row:** facade `floodlit`, tint `#85847a`, module 0, variant -.
- **Look, sampled colours, gaps:** New octagon and bell tower: by day grey concrete with tiny blue dots: sampled (refs/gedaechtniskirche/01, new church box 0.50,0.66,0.72,0.76, sky dropped) mean #818178, median #85847a, mid40-90 #95948b, bright30 #aaaaa5: tint #85847a for the day; at dusk/night the 21,292 stained glass inlays (predominantly blue; ruby red, emerald green, yellow, EN) glow: deep cobalt #46689f (est. from refs/gedaechtniskirche/04-05). Octagon 35 m dia x 20.5 m high, hexagonal bell tower 53.5 m, flat roofs. In the engine: floodlit style with the grey tint and an emissive blue at night.

### Victory Column (Siegessäule)
- **Row:** facade `floodlit`, tint `#5f5a4c`, module 0, variant -, roof `#d4aa3c`.
- **Look, sampled colours, gaps:** STRUCTURE (a column: build as a [[structures]] figure). Base: red/brown granite and dark bronze reliefs: sampled (refs/siegessaeule/01, box 0.12,0.88,0.40,0.95, in shade) mean #332f2b: the lit granite is a warm red-brown #8c4f40 [est. from the photo, the sample is shadowed]. Colonnade ring dark bronze-brown, shaft dark olive-bronze with three gilded cannon-barrel bands each (sampled shaft box 0.42,0.31,0.54,0.69 mean #63635a, bright30 #bdbcb0, the gilded bands brighter); Victoria gilded #d4aa3c (seen). 67 m (EN), Victoria 8.32 m and 35 t (DE).

### Berlin Hauptbahnhof (central station)
- **Row:** facade `glass`, tint `#8fa3aa`, module 1.5, variant 0.4, roof `#aab6bc`.
- **Look, sampled colours, gaps:** Hbf: glass, light blue-grey with white steel frames: sampled (refs/hauptbahnhof/02, box 0.22,0.30,0.45,0.62) mean #7f8c91, mid40-90 #98aab0, bright30 #c1cdd1: tint #8fa3aa. The two Bügel (46-48 m OSM parts) are curtain-wall slabs; the east-west hall a barrel-vault glass roof (321 m, DE) over the tracks, light blue-grey with white ribs: a profile cannot make a barrel vault: [[structures]] or a roof shape.

### Oberbaum Bridge
- **Row:** facade `floodlit`, tint `#a4523a`, module 0, variant -, roof `#8a4a3c`.
- **Look, sampled colours, gaps:** STRUCTURE (bridge): orange-red brick arcade and towers: sampled (refs/oberbaumbrücke/02, arcade box 0.60,0.70,0.90,0.78) mean #945038, median #984f36, mid40-90 #a55940; tower box 0.52,0.36,0.67,0.56 mean #8b665e (sky mixed), mid40-90 #a56355: tint #a4523a. Tower roofs: pointed conical, copper-red/rust (roof #8a4a3c, est.). Calatrava's central steel span: pale grey #c0c3c6 [est.]. U1/U3 trains run on top (yellow, refs/oberbaumbrücke/04).

### Humboldt Forum (Berlin Palace reconstruction)
- **Row:** facade `monument`, tint `#cdb68f`, module -, variant 0.3, take 5, roof `#6b7f72`.
- **Look, sampled colours, gaps:** Humboldt Forum: the baroque facades are warm ochre-cream plaster with sandstone-coloured pilasters: sampled (refs/humboldt-forum/04, baroque wing box 0.70,0.40,0.88,0.55) mean #a48b68, median #aa916f, mid40-90 #c2aa86, bright30 #e0c69c: tint #cdb68f; the modern east/north facade is a pale warm-grey stone grid with deep vertical window reveals, no ornament: (box 0.15,0.35,0.45,0.55) mean #7e746b, mid40-90 #aa9d90, bright30 #c1b6ac: tint #b9ada0 (grid ~ 2.4 m module est.). A copper-green dome over the west portal; low dark hipped roofs. refs/humboldt-forum/01 (dusk) reads far greyer: not used. take 5.

### Park Inn by Radisson Berlin Alexanderplatz
- **Row:** facade `bands`, tint `#6a7e94`, module 1.5, variant 0.4, roof `#b3b5b7`.
- **Look, sampled colours, gaps:** Park Inn: blue-grey glass with white vertical mullions and spandrel bands: sampled (refs/alexanderplatz-towers/01, box 0.30,0.30,0.65,0.70) mean #64788f, mid40-90 #7b8fa5, bright30 #a8bacd: tint #6a7e94. A lit rooftop 'PARK INN' sign, a small crown/mast, horizontal white band at the top (refs/alexanderplatz-towers/01).

## 2. Other rows (tint, style and the one-line look)

| Landmark | facade | tint | note |
|---|---|---|---|
| Atrium Tower (Daimler/debis Haus, Potsdamer Platz) | brickstone | #a8573f | Atrium Tower (Piano): terracotta-and-glass: terracotta tint #a8573f [est. from memory of the debis facade; refs/potsdamer-platz-area not sampled for this]; tapered wedge plan (82 m long). |
| Forum Tower (Potsdamer Platz) | glass | #6a7e94 | Placeholder (Forum Tower): height unknown; not used. |
| Beisheim Center (Ritz-Carlton and Marriott, Potsdamer Platz) | limestone | #d0cfcc | Beisheim Center: two pale white-grey stone slabs (sampled refs/potsdamer-platz-area/02, box 0.82,0.35,0.93,0.65: mean #bbbbb9, median #bebcba, mid40-90 #d6d5d3, bright30 #f2f2f0): tint #d0cfcc; regular punched windows, flat roofs. ~ 70 m. |
| Europa-Center (Breitscheidplatz) | panel | #a8a8a6 | Europa-Center: grey curtain wall panels with ribbon windows, a flat roof with the Mercedes star (roof #d0d3d6, black star lit) [est.]. |
| Zoofenster (Waldorf Astoria Berlin) | stone | #d4d0c4 | Zoofenster: cream-white stone/cladding with deep punched windows, topped by a dark glass crown. Seen in refs/zoofenster-upper-west/04 (right tower): sampled box 0.62,0.45,0.78,0.65 mean #b2b1ae, median #dad8d0, mid40-90 #efe8df, bright30 #f8f4ed: tint #d4d0c4 (sunlit pale cream-white); the dark top block (box 0.66,0.18,0.80,0.28... |
| Upper West (Motel One, Breitscheidplatz / Kantstraße) | bands | #e0e5e6 | Upper West: two rounded twin shafts wrapped in a staggered white frame grid (white diagonal 'brick-bond' frames with tall dark window cut-outs), refs/zoofenster-upper-west/04 (left tower): sampled box 0.17,0.15,0.37,0.50 mean #979ea3 (frames + dark glass mixed), mid40-90 #e0e5e6, bright30 #f7fcfc: the frame is near-white (#e0e5e... |
| Bikini Berlin (Bikinihaus) | concretepanel | #cfcdc6 | Bikini Berlin: refs/zoofenster-upper-west/06: a long off-white horizontal slab raised on pilotis with continuous ribbon windows and white spandrels; the open 'bikini' storey; sampled box 0.30,0.18,0.80,0.40 mean #929ba0 (sky glass mixed), mid40-90 #a3bcd6 (reflections): not usable as albedo; tint est. #cfcdc6. |
| Kudamm-Karree (Fürst Tower, Kurfürstendamm) | concretepanel | #b0aca4 | Kudamm-Karree 1974: precast panel slab [est.]; being converted to Fürst Tower. |
| Kranzler Eck (Café Kranzler) | glass | #7090a0 | Kranzler Eck: curtain wall with a round tower and rotunda [est.]. |
| Breitscheidplatz ensemble (Gedächtniskirche, Europa-Center, Zoofenster) | floodlit | #b0a898 | Breitscheidplatz ensemble row: see the church rows. |
| Berlin Zoo and Elefantentor (Zoo entrance) | floodlit | #a4392b | Elefantentor: red-painted pagoda gate with stone elephants [believed], tint est. |
| Berlin Philharmonie (Kulturforum) | floodlit | #86743f | Philharmonie: the roof/walls are dull-gold anodised aluminium panels: sampled (refs/philharmonie-kulturforum/01, box 0.35,0.20,0.75,0.40) mean #78683d, median #7b6a3d, mid40-90 #7d6d40, bright30 #827349: a dark mustard-olive gold, not bright yellow: tint #86743f (a little lighter than the shaded sample). The asymmetric tent with... |
| New National Gallery | glass | #3b4048 | Neue Nationalgalerie: black steel roof plate (#2b2b2e) over a glass box with thin dark mullions: glass tint #3b4048 [est.]; the granite terrace #8a8680. |
| Kulturforum: Gemäldegalerie and Kunstgewerbemuseum | brickstone | #b8a98a | Gemäldegalerie/Kunstgewerbemuseum: pale stone and brick, low [est.]. |
| Memorial to the Murdered Jews of Europe (Holocaust Memorial) | floodlit | #8a8a86 | Holocaust memorial: STRUCTURE (instanced grey concrete stelae, 0.2-4.7 m); concrete mid-grey #8a8a86 [est.]; a plaza #9a9690. |
| Altes Museum (Museum Island) | monument | #bdb6a6 | Altes Museum: 18 Ionic columns weathered grey-white, the wall behind the colonnade painted RED (a deep ochre-red, seen in refs/altes-museum/04), a long attic with an inscription; sampled attic box hit blue sky (0.1,0.22,0.9,0.29 median #567b85: invalid); colonnade stone est. #bdb6a6 (light grey, soot-streaked). Peristyle variant... |
| Neues Museum (Museum Island) | limestone | #b6ae9c | Neues Museum: pale cream-grey plaster and stone, tall windows, a colonnade wing: sampled (refs/neues-museum/01, box 0.55,0.30,0.85,0.48) mean #aeada1, median #b2ac9a, mid40-90 #c7c0b5: tint #b6ae9c (partly shaded). The corner pavilion has a Greek-style pediment on the top storey. |
| Alte Nationalgalerie (Museum Island) | monument | #cdb48f | Alte Nationalgalerie: a Corinthian temple front on a high podium with a double staircase; warm buff sandstone: sampled (refs/alte-nationalgalerie/01, box 0.15,0.64,0.40,0.74 = steps) mean #c3ab8c, median #d1b895, mid40-90 #ddc19f: tint #cdb48f. Colonnade back wall dark red-brown (the recess, seen). Apse on the north, flat roof, ... |
| Pergamon Museum (Museum Island) | limestone | #d0cabc | Pergamonmuseum: bright pale limestone, a blank central portal block flanked by two plain wings with pilaster-like vertical frames, the south wing front is a bare monumental facade: sampled (refs/pergamonmuseum/01, box 0.3,0.30,0.65,0.45) mean #d3cdc2, median #e3ded1, mid40-90 #e8e3d6, bright30 #f1ece0 (very light): tint #d0cabc.... |
| Bode Museum (Museum Island) | monument | #b0a48e | Bode Museum: stone grey-beige walls (sampled in shade refs/bode-museum/03 box 0.5,0.38,0.8,0.50 mean #796f63, mid40-90 #908478: tint #b0a48e brightened, est.), a drum with a dark green-grey copper dome (the dome box hit the sky: dome colour est. from the photo as dark grey-green #6f7f74). Round-arched arcade at the water, a pedi... |
| James-Simon-Galerie (Museum Island entrance) | concretepanel | #e8e8e2 | James-Simon-Galerie: slender white stone colonnade (thin square columns in a row, a flat roof slab, a wide stair); sampled (refs/james-simon-galerie/03, box 0.05,0.45,0.35,0.60) median #abacab, mid40-90 #ebebe5, bright30 #f5f6f0: tint #e8e8e2 (white-grey). |
| Zeughaus (German Historical Museum), Unter den Linden | monument | #c8b8a2 | Zeughaus: warm cream-pink sandstone with rich sculpture on the cornice, tall arched windows (refs/neue-wache-zeughaus/02: sampled box 0.20,0.40,0.60,0.62 mean #aa9888, median #b9a592, mid40-90 #e4ceba, bright30 #f8e6d4): tint #c8b8a2; flat roof hidden behind a balustrade with trophies. |
| Neue Wache (Unter den Linden) | monument | #c4b89a | Neue Wache: Doric portico (six columns) on a sandstone cube [est.]. |
| Berlin State Opera | monument | #d8b8a6 | Staatsoper: the plaster is a PINK-rose (salmon) with white pilasters/columns and a grey slate roof, clearly visible in refs/staatsoper-humboldt-uni/01 (sample box 0.30,0.45,0.70,0.60 mixes columns and shadow: mean #8c7965, mid40-90 #9d8c7c, bright30 #d7be9a): tint #d8b8a6 [est. from the photo's lit plaster]. Six Corinthian colum... |
| St. Hedwig's Cathedral | monument | #c0b196 | St Hedwig's: bright verdigris-green copper dome and warm buff sandstone walls with a six-column Corinthian portico (refs/st-hedwigs-cathedral/01). Sampled dome (box 0.35,0.12,0.65,0.25, sky dropped) mean #abe2d8, median #aae1d8 (very light mint in full sun): roof #7fbfae (toned darker for albedo); walls (box 0.30,0.58,0.55,0.72)... |
| Konzerthaus Berlin (Schauspielhaus, Gendarmenmarkt) | monument | #d4cdb8 | Konzerthaus: cream-grey plaster and sandstone, Ionic portico, pediment, slate-grey roof [est.]. |
| French Cathedral (Französischer Friedrichstadtkirche), Gendarmenmarkt | monument | #c8bea6 | French Cathedral: sandstone domed tower, copper-green cupola (roof est. #6e8c80). A tower row: take 5 for the dome parts. |
| German Cathedral (Deutscher Dom), Gendarmenmarkt | monument | #c8bea6 | German Cathedral: as the French Cathedral; mirror image. |
| Friedrichswerder Church (Schinkel) | brickstone | #a8573f | Friedrichswerder Church: neo-Gothic red brick, two square towers with crenellations [believed]. |
| St. Mary's Church (Marienkirche), Alexanderplatz | brickstone | #8f5a42 | St Mary's: refs/marienkirche-nikolaiviertel/01: a steep orange-red tile roof (sampled box 0.40,0.58,0.65,0.66 mean #c6735a, median #cc623e: roof #cc623e) over red-brown brick walls (box 0.30,0.77,0.60,0.84 mean #815a3d, mid40-90 #936846 in shade: tint #8f5a42), and a cream-ochre plastered west tower (box 0.20,0.40,0.27,0.58 mean... |
| St. Nicholas' Church (Nikolaikirche) | brickstone | #8a5b44 | Nikolaikirche: brick Gothic with two copper-green spires (the twin tower form, refs/marienkirche-nikolaiviertel/02 aerial) [believed colours; the St Mary's sampling next door shows the brick/roof colours: brick #8f5a42, tile roof #cc623e]. |
| Haus des Lehrers (Alexanderplatz) | bands | #d4dcd8 | Haus des Lehrers: refs/alexanderplatz-towers/03: a 12-storey curtain-wall slab with pale mint-white spandrel panels and light grey mullions (sampled box 0.30,0.25,0.55,0.50 mean #9fadad, median #c0c6c3, mid40-90 #dee3e1, bright30 #eef7f2: tint #d4dcd8) over a glazed ground floor on slender white columns, and the multicoloured Wo... |
| House of Travel (Haus des Reisens), Alexanderplatz | concretepanel | #9fa09f | Haus des Reisens: pale panels: sampled (refs/alexanderplatz-towers/05, box 0.35,0.30,0.65,0.60) mean #686768, mid40-90 #818184, bright30 #b0aca8 (the tower is in partial shade in the photo): tint #9fa09f. |
| Berlin Congress Center (bcc), former Kongresshalle | panel | #b8bcc0 | bcc: grey metal panels and glass; low saddle roof [est.]. |
| The Berlinian (Hochhaus am Alexanderplatz, ex-MYND) | stone | #8e8a82 | The Berlinian: stone-grey tiles and glass [est. from press; no photo yet]. Shell completed 2026 (topped out 14 Jan 2026). |
| Covivio Tower (Alexanderplatz, ALX) | glass | #7a8c9c | Covivio tower (not built). |
| Hines Alexander Tower (next to Alexa) | glass | #7a8c9c | Hines tower (not built). |
| Galeria Kaufhof Alexanderplatz (Kaufhaus) and the Alexa mall | stone | #d6ccb8 | Galeria Kaufhof Alexanderplatz: refs/alexanderplatz-towers/06 (2024) shows the renewed facade as a pale cream-beige stone cladding with vertical fins and tall glass bands (the old aluminium honeycomb facade is gone): sampled box 0.25,0.20,0.50,0.35 mean #a1a7ad (sky in the glass), mid40-90 #c9c5cc, bright30 #f1e9e0: tint #d6ccb8... |
| World Clock (Urania-Weltzeituhr), Alexanderplatz | floodlit | #b8b8b4 | World Clock: STRUCTURE. |
| Alexanderplatz station (S-Bahn Stadtbahn, U2/U5/U8) | panel | #a0a4a8 | Alexanderplatz station: steel and glass hall. |
| Federal Chancellery (Bundeskanzleramt) | concretepanel | #c9c4c1 | Kanzleramt: pale grey-white concrete cube with huge round-cornered cut-outs and glass behind (refs/kanzleramt/01): sampled (box 0.22,0.35,0.38,0.60 = pale wall with glass) mean #7d7c7b, mid40-90 #9b918b, bright30 #cac4c1: tint #c9c4c1 (the lit concrete). The glass front is dark blue-grey, a red-brown steel sculpture ('Berlin' by... |
| Paul-Löbe-Haus (Bundestag offices, Band des Bundes) | glass | #a8b4bc | Paul-Löbe-Haus: huge thin white flat roof plate cantilevering over a fully glazed hall (refs/paul-loebe-haus/02): roof/fascia white #e8e8e6 [est.; the sample box hit the blue sky: invalid], glass clear light blue-grey; tint est. #a8b4bc. |
| Marie-Elisabeth-Lüders-Haus (Bundestag library, Spree east bank) | glass | #a8b4bc | Marie-Elisabeth-Lüders-Haus: glass and pale stone; round tower 36 m [est.]. |
| Jakob-Kaiser-Haus (Bundestag offices) | brickstone | #b09c80 | Jakob-Kaiser-Haus: mix of old stone/brick and new glass [est.]. |
| House of World Cultures (HKW) | floodlit | #c4986c | HKW: the saddle shell is warm timber/copper-coloured panels (refs/haus-der-kulturen-der-welt/03: sampled box 0.45,0.40,0.75,0.60 mean #7d5c42, mid40-90 #ce9e6f, bright30 #dcac81: tint #c4986c) under a white concrete rim/roof edge (#e8e6e0 est.), glass hall below; the carillon pylon at the left. Not a window style: floodlit with ... |
| Bellevue Palace (Schloss Bellevue) | monument | #d8d6d0 | Schloss Bellevue: white-cream plaster with white pilasters and a low dark-grey hipped slate roof, seen in refs/schloss-bellevue/01 (sampled box 0.30,0.35,0.70,0.45 mean #85868a, median #878c91, bright30 #ced1d3 under a blue-sky shadow: tint #d8d6d0 est.). Three storeys, wings; clipped yew cones and a big lawn in front. |
| Bundesrat building (former Prussian House of Lords) | limestone | #b8ae98 | Bundesrat: grey sandstone, mansard roof [believed]. |
| Hamburger Bahnhof (Museum für Gegenwart) | monument | #d0c49a | Hamburger Bahnhof: pale yellow plaster, long glazed-brick hall at the rear [believed]. |
| Einz Tower (Heidestraße, Europacity) | glass | #7090a8 | Einz Tower [est.]. |
| Cube Berlin (Washingtonplatz) | glass | #4f6368 | Cube Berlin: a tilted all-glass cube with faceted, mirror-glass planes: sampled (refs/europacity-heidestraße/01, box 0.45,0.10,0.80,0.40, sky pixels dropped) mean #4f6368, median #475b5e, mid40-90 #51666b, bright30 #809499: dark teal-grey in the shade, light blue-white in reflections: tint #5f7a82. |
| Tour Total (Europacity) | glass | #7a8c9c | Tour Total [est.]. |
| Upbeat Berlin (Moabit) | glass | #7a8c9c | Upbeat [est.]. |
| Charite Bettenhochhaus (hospital tower) | concretepanel | #aeada6 | Charite tower: a wide pale-cream/grey 21-storey slab with a gold 'Charite' lettering on the parapet (refs/charite-bettenhochhaus/02; sampled box 0.30,0.20,0.60,0.38 in dusk light mean #7b7d82, mid40-90 #86888e: too dark; tint #aeada6 est.). |
| Axel Springer House (Axel-Springer-Hochhaus) | bands | #b8a468 | Springer House: golden-bronze anodised panels in a regular window grid (refs/axel-springer-hochhaus/02): sampled (box 0.30,0.30,0.65,0.55) mean #a69b82, median #a79980, mid40-90 #bdb296, bright30 #ddd7c0 (the window glass and strips pull the mean down): the panels read saturated gold-bronze in the photo: tint #b8a468 [est.]. A b... |
| Berlin Wall Memorial (Bernauer Straße) | floodlit | #7a4a38 | Wall memorial: rusted steel [believed]. |
| EDGE East Side Tower (Amazon Berlin) | glass | #6f93a0 | EDGE East Side Tower: green-blue glass with a stepped, offset floor plate pattern [est.]. |
| Stream Tower (Mercedes-Platz) | glass | #7c93a4 | Stream Tower [est.]. |
| Spreeturm (Warschauer Straße) | glass | #7c93a4 | Spreeturm [est.]. |
| Lux Tower (Lichtenberger / Friedrichshain Ostkreuz) | concretepanel | #b0aca4 | Lux-Tower [est.]. |
| Uber Arena (Mercedes-Benz Arena), Friedrichshain | panel | #4a4c50 | Uber Arena (refs/mercedes-benz-arena/01): a glass-and-steel lattice wall under a black roof ring with the logo, a white base ring (est.): dark grey #4a4c50 [est.], roof black #1d1d20. |
| Molecule Man (Jonathan Borofsky) | floodlit | #a8acae | Molecule Man: STRUCTURE (perforated aluminium, silver-grey). |
| Treptowers (Hochhaus Treptower) | glass | #8c95a0 | Treptowers: refs/treptowers/04: the 125 m tower is a grey-blue glass slab with horizontal metal bands (sampled box 0.09,0.22,0.20,0.60 mean #8b959f, median #8c95a0, mid40-90 #a0a8ad, bright30 #c2c7c9); the three lower wings (46 m) have pale cream-grey stone-and-glass facades with stepped tops (box 0.62,0.35,0.88,0.50 mean #99989... |
| East Side Gallery (Mauer, Mühlenstraße) | floodlit | #6a6f78 | East Side Gallery: the wall is dark blue-grey concrete with murals (refs/east-side-gallery/01: a 3.6 m wall with a rounded cap; the painted panels are multicoloured, base concrete est. #6a6f78); the Spree side is open. |
| Frankfurter Tor towers (Karl-Marx-Allee) | monument | #c9bba6 | Karl-Marx-Allee towers and blocks: sampled (refs/karl-marx-allee/01 = Strausberger Platz, box 0.10,0.45,0.35,0.60) mean #9a937e, median #b2a692, mid40-90 #bfb2a0, bright30 #d2c7b6: a warm cream-beige tile, tint #c9bba6; 8-9 storeys with a darker stone base and regular small windows, the tower end block has a lattice frame on the... |
| Karl-Marx-Allee Wohnbauten and Strausberger Platz | monument | #c9bba6 | Karl-Marx-Allee blocks: tint #c9bba6 (sampled cream-beige tile, see Frankfurter Tor row); 8-9 storeys, stone base, steep-ish flat roof with small attic; fountains in the Strausberger Platz roundel (refs/karl-marx-allee/01). |
| Café Moskau (Karl-Marx-Allee) | panel | #c0c4c8 | Café Moskau [believed]. |
| Kino International (Karl-Marx-Allee) | concretepanel | #d8d4c8 | Kino International [believed]. |
| Haus der Elektroindustrie (Karl-Marx-Allee) | panel | #a0a8b0 | Haus der Elektroindustrie [believed]. |
| Haus der Statistik (Alexanderplatz) | concretepanel | #b8a58a | Haus der Statistik: orange-brown/white panels [believed]. |
| Königstadt-Carree (Prenzlauer Allee/Mollstraße) | glass | #7c8c98 | Königstadt-Carree [est.]. |
| Neptunbrunnen and Marx-Engels-Forum (Fernsehturm park) | floodlit | #8a8a82 | Park: no facade. |
| Checkpoint Charlie (Friedrichstraße) | floodlit | #f0f0ee | Checkpoint Charlie: STRUCTURE (white hut). |
| Jewish Museum Berlin (Libeskind building) | panel | #8a9496 | Jewish Museum: Libeskind's zinc zigzag: sampled (refs/juedisches-museum/01, box 0.78,0.30,0.98,0.60) mean #7c8384, median #838c8e, mid40-90 #8d9698: tint #8a9496 (a grey with a blue-green cast); the old Baroque Kollegienhaus next to it is salmon-ochre plaster with white trim and an orange-red tile roof (box 0.15,0.40,0.50,0.60 m... |
| Tempelhof Airport terminal (outside the boundary) | limestone | #c8c0aa | Tempelhof terminal: limestone (outside the boundary). |
| M50 Hochhaus (Mehringplatz, Kreuzberg) | glass | #7a8c9c | M50: under construction. |
| America Memorial Library (AGB) | concretepanel | #c0bab0 | AGB [believed]. |
| Berlinische Galerie (Alte Jakobstraße) | panel | #b8bcc0 | Berlinische Galerie [believed]. |
| Topography of Terror and Martin-Gropius-Bau | brickstone | #b0584a | Martin-Gropius-Bau: terracotta-red brick/ceramic [believed]. |
| Anhalter Bahnhof portico ruin | brickstone | #a8856a | Anhalter portico: buff brick and terracotta, ruin. |
| German Museum of Technology (Gleisdreieck) | factory | #9a6a52 | Technikmuseum: brick halls [believed]. |
| Telefunken-Hochhaus (Ernst-Reuter-Platz) | bands | #4a5a6a | Telefunken-Hochhaus (TU): refs/tu-berlin-ernst-reuter-platz/02: a dark blue-grey grid facade with pale horizontal strips, a lit magenta T-logo (the telecom tenant) on top: sampled (box 0.40,0.25,0.60,0.60) mean #475562, median #435362, mid40-90 #516171, bright30 #707c88: tint #4a5a6a. |
| TU Berlin main building and Ernst-Reuter-Platz | monument | #c4b496 | TU main building: Neo-Renaissance sandstone [believed]. |
| Deutsche Oper Berlin (Bismarckstraße) | concretepanel | #cfc5b2 | Deutsche Oper (refs/deutsche-oper/01): a pale travertine-like wall slab with a glazed foyer side: sampled box 0.10,0.52,0.50,0.64 mean #c8beae, median #d0c6b4, mid40-90 #dfd3c1: tint #cfc5b2; a flat-roofed box with a taller stage house behind (~ 30 m [est.]). |
| Hansaviertel (Interbau 1957: Niemeyer-Haus, Punkthochhaus, Akademie der Künste) | concretepanel | #d0cbc0 | Hansaviertel high-rises: white/pale concrete with balcony patterns, colours differ per block [believed]. |
| Schlossbrücke (Palace Bridge) | floodlit | #d4cfc0 | Schlossbrücke: pale marble/stone arches with white statues [believed]. |
| Friedrichsbrücke (Museum Island, Bode Museum) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Weidendammer Brücke (Friedrichstraße) | floodlit | #3f4a44 | Weidendammer Brücke: dark green-grey painted cast iron [believed]. |
| Marschallbrücke (Reichstag Ufer / Dorotheenstraße) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Moltkebrücke (Spreebogen) | floodlit | #b08868 | Moltkebrücke: red-brown sandstone [believed]. |
| Kronprinzenbrücke (Spree, Kanzleramt/Reichstag) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Gertraudenbrücke (Spree, Fischerinsel) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Mühlendammbrücke (Spree, Nikolaiviertel) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Jannowitzbrücke (Spree) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Schillingbrücke (Spree) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Elsenbrücke (Spree, Alt-Treptow) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Michaelbrücke (Luisenstadt, Spree) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Potsdamer Brücke (Landwehrkanal, Potsdamer Straße) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Hansabrücke, Lessingbrücke and Gotzkowskybrücke (Spree, Moabit/Hansaviertel) | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Kottbusser Brücke (Landwehrkanal) and Hochbahn Skalitzer Straße | floodlit | #a8a496 | STRUCTURE (bridge): stone/steel; not sampled. |
| Berlin Hochbahn viaduct U1/U3 (Kreuzberg) | floodlit | #4a5a6a | Hochbahn: STRUCTURE; blue-grey painted steel truss girder (a Pratt/Warren lattice, seen from below in refs/hochbahn-kreuzberg/01: dark steel against blue sky, est. #3f4f63) on steel pier frames; the stations Warschauer Straße/Goerlitzer Bahnhof are glass-and-steel halls. |
| Berlin Stadtbahn viaduct (S-Bahn brick arches, Mitte) | floodlit | #7e4a3c | Stadtbahn viaduct: red-brown brick arches with window/door infill at street level (refs/sbahn-viaduct/07: sampled shaded brick box 0.03,0.30,0.30,0.65 mean #513f3c, median #543d39: tint #7e4a3c est. for sunlit brick); the steel deck on top with a wall plate; arches of ~ 5-7 m span used as shops. |
| Fischerinsel high-rises (Mitte) | concretepanel | #b8b4a8 | Fischerinsel towers [believed]. |
| Leipziger Straße high-rises (Mitte, 1977) | concretepanel | #b8b4a8 | Leipziger Straße slabs: concrete panels sand-grey [believed]. |
| Rochstraße 9 and Mollstraße Wohnhochhäuser | concretepanel | #b8b4a8 | Rochstraße 9 [believed]. |
| Nikolaiviertel (Berlin old town replica) | house | #e4d6a8 | Nikolaiviertel: pastel plaster [believed]. |
| Hackesche Höfe (Mitte) | brickstone | #c8bca4 | Hackesche Höfe: glazed brick and ceramic, courtyards [believed]. |
| Friedrichstadt-Palast (Friedrichstraße) | panel | #d8d4c0 | Friedrichstadt-Palast [believed]. |
| Tränenpalast (Friedrichstraße border pavilion) | glass | #9fb0c0 | Tränenpalast: glass cube [believed]. |
| Friedrichstraße station (S/U, Mitte) | panel | #b0b4b8 | Station hall [believed]. |
| Volkspark Friedrichshain bunker hills | floodlit | #7a8a60 | TERRAIN, not a building. |
| Viktoriapark Kreuzberg and the National Monument | floodlit | #7a8a60 | TERRAIN with the Schinkel cast-iron monument (dark grey iron). |
| Neues Kreuzberger Zentrum (NKZ, Kottbusser Tor) | concretepanel | #9a8c7e | NKZ: brown-grey concrete with colour panels [believed]. |
| New Synagogue Berlin (Neue Synagoge, golden dome) | monument | #c89a58 | Neue Synagoge: red/yellow striped brick front with a gilded dome (#d2a64a est.) [believed]. |
| St. Matthew's Church (Matthäuskirche), Kulturforum | brickstone | #b49a6a | St Matthew's: yellow/red clinker [believed]. |
| Zion Church (Zionskirche), Mitte | brickstone | #a8664a | Zionskirche: brick and sandstone [believed]. |
| Ludwig-Erhard-Haus (Berlin stock exchange; the 'Armadillo') | panel | #b8c0c8 | Börse: steel and glass arches (silver-white) [believed]. |
| Pariser Platz (Adlon Kempinski, Akademie der Künste, Palais am Pariser Platz) | limestone | #c4bba4 | Pariser Platz: stone-clad 22 m blocks [believed]. |
| Bauakademie (Schinkel's Building Academy; reconstruction) | brickstone | #a8573f | Bauakademie: red brick with terracotta [believed]. |
| Federal Foreign Office (Auswärtiges Amt) | limestone | #b8aa90 | Foreign Office: limestone [believed]. |
| Mosse-Palais and Leipziger Platz | limestone | #c0b8a4 | Leipziger Platz stone blocks [believed]. |
| Town hall of Friedrichshain-Kreuzberg (Yorckstraße) | brickstone | #b09a7a | Context. |
| International Trade Centre (IHZ), Friedrichstraße | glass | #7a8c98 | IHZ: GDR ribbed curtain-wall slab, blue-grey glass and panels [believed]; not photo-sampled. |
| Grandaire residential tower (Alexanderplatz) | concretepanel | #b9b6ae | Grandaire: stone-grey cladding [believed]; not photo-sampled. |
| Silver Tower (Friedrichshain, near Ostbahnhof) | glass | #7a8c98 | Silver Tower: not researched. |
| Pressehaus Berlin (Karl-Liebknecht-Straße) | concretepanel | #b0aca4 | Pressehaus: GDR panel slab [believed]. |
