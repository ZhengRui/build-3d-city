# Paris landmark list: sources, disputes, OSM errors, structures and bridges

Companion to `landmarks_paris.csv` (160 rows, same 13 columns as New York's `landmarks_manhattan.csv`; French name in
`name_zh`). Area: the 20 arrondissements, La Défense (lon 2.2300-2.2580, lat 48.8850-48.8990) and Neuilly along the
Avenue Charles-de-Gaulle. Heights are Wikipedia FR (mostly "Liste des plus hauts bâtiments d'Île-de-France" and
"Liste des bâtiments de la Défense", plus the page of each building), CTBUH where a search confirmed it, or the OSM
`height` tag where the notes say "OSM only". Web checks (2026-09-30): Tour Triangle, The Link. OSM state: Overpass
snapshot 2026-09-29. `use_height=True` on 121 rows, `False` on 39.

Not done (time box): Chapelle de la Sorbonne (no OSM part above 25 m), Saint-Germain-des-Prés and La Trinité
(approximate points, rows kept with `use_height=False`), Petit Palais, Gare du Nord, Fondation Louis Vuitton (all
under the useful skyline threshold or not sourced). Not resolved in OSM: Tour Landscape (101 m) and Tour Blanche
(100 m) in La Défense (dropped from the CSV); Tour Seine of The Link and the second Cœur Défense tower (rows kept,
approximate points, `use_height=False`).

## How the landmark height applies (important for M4)

`04_buildings.apply_landmarks` gives the height to the footprint under the point. **When that footprint is made of OSM
`building:part`s, the parts keep their own heights** and the landmark only sets the name. So for the towers made of
parts (Tour First, the Grande Arche, Notre-Dame, Sacré-Cœur, Panthéon, Invalides, Opéra Garnier, the BnF towers, Tour
Super-Italie) the OSM part heights, right or wrong, win. Fix the wrong parts (below) or override by OSM id.

## MUST-HAVE rows (the user's list)

| Landmark | Height in CSV | What it means | OSM |
|---|---|---|---|
| Tour Eiffel | 330 m | tip of the antenna (top platform 300 m, 3rd deck 276-279 m, 2nd 115.7 m, 1st 57.6 m; 312 m in 1889, 324 m before 2022) | structure, see below |
| Arc de Triomphe | 50 m (49.54) | attic top; vault passages 29.19 m and 18.68 m high stay open | outline way/226413508 + parts |
| Notre-Dame | 96 m | rebuilt spire (reopened 2024); towers 69 m; nave/choir ridge 45 m; nave vault 33 m | spire way/1299835416; outline is only 10.5 m |
| Sacré-Cœur | 83 m | dome lantern (OSM outline 84 m) | dome part way/226727321 |
| Louvre Pyramid | 21.65 m | glass apex, 35.42 m square base | way/375076234 (h21.65, correct) |
| Louvre Palace | about 30 m ESTIMATED | mansard roofs 20-30 m, pavilions to about 35 m | rel/3262297 |
| Tour Montparnasse | 210 m | top of terrace screen (209 m plus 2.9 m glass screen; 59 floors) | way/16406633 (h210, correct) |
| Panthéon | 83 m | dome with lanternon (OSM part says 90 m) | way/1200917614 |
| Invalides dome | 107 m | dome 90 m + lantern and spire (OSM stops at 100 m) | way/227662030 |
| Opéra Garnier | 70 m | outline top (OSM); stage house 58 m; dome 51 m | way/54667456 + parts |
| Grande Arche | 110 m (110.9) | roof of the hollow cube, 112 x 106.9 m, void 70 x 100 m | way/19441489 + stacked parts |

## Disagreements and how they were resolved

| Building | Sources | Kept |
|---|---|---|
| Tour Areva / Framatome | OSM and CTBUH 184, Wikipedia FR list 178 | 184 (architectural incl. crown) |
| Tour T1 (Engie) | Wikipedia 185, OSM 169 | 185 (crown incl.; roof about 169) |
| Tour D2 | Wikipedia 171, OSM 175 | 171 |
| Tour Trinity | OSM 151, Wikipedia/CTBUH 167 | 167 |
| Tour Hopen (ex-Adria) | OSM 155, Wikipedia 167 after the 2024-25 restructuring | 167 (verify) |
| Tour Aurore | OSM 110, Wikipedia 131 after the 2023 renovation | 131 |
| Tour Les Poissons | OSM 150, Wikipedia 129.5 / 130 | 130 |
| Tour Défense 2000 | 134 (OSM, ladef list), 136 (IDF list) | 134 |
| Tour CGI / Neptune | 117 vs 110 / 113 vs 117 | CGI 117, Neptune 113 |
| Tour First | outline 225 (roof), CTBUH 231 architectural; OSM parts up to 259 | 231 |
| Hekla | 220 (Wikipedia) vs 221 (OSM) | 220 |
| Tour Saint-Jacques | FR 54 m to the balustrade, OSM 52 | 54 |
| Madeleine | Wikipedia 30, OSM 36 | 30 |
| Hyatt Regency Paris Étoile | Wikipedia 137 (190 m with antenna), OSM outline 174 | 137 |
| Panthéon | Wikipedia 83, OSM cone 90 | 83 |
| Sacré-Cœur | Wikipedia 83, OSM outline 84 | 83 |
| Val-de-Grâce | OSM 62 to the lantern; no confirmation (drum statues at 45 m) | 62, unverified |

## OSM errors found

- **Tour Eiffel**: modelled as ten stacked solid prisms (outline way/5013364 h330, way/1462597762 300-330,
  way/308021389 276-300, four pier parts 115.7-276.1 m, four roof parts 57.6-115.7 m, rel/4114842 and rel/4114839):
  a solid block. Exclude these.
- **Notre-Dame**: outline way/201611261 is 10.5 m (the footprint only); the real volumes are parts. Parts
  way/201760771/772 (78 m) and way/201611273/274 (73 m) over the towers exceed the official 69 m.
- **Tour First**: parts up to 259 m (way/227353363), 250, 244, 240, 234 m: nothing above 231 m is sourced.
- **Hyatt Regency**: rel/3074643 and way/229301758 say 174 m; the building is 137 m.
- **Tour Duo**: both footprints (way/942459281, 1894 m2, alt_name "Tour BPCE Ouest", and way/1130750788, 2781 m2,
  "Tour BPCE Est") are named "Tour Duo 1", 39 levels, 180 m. Duo 2 is 122 m (FR text) / 125 m (FR list), 27 floors.
  The CSV assigns the 180 m to the smaller footprint (unverified) and both rows have `use_height=False`.
- **Tour Les Poissons**: 150 m in OSM, 129.5 m real. **Tour Aurore**: 110 m, real 131 m since the 2023 works.
- **Tribunal de Paris**: no height on any part (levels only); the outline way/481196425 is the 8-level podium.
- **Tour Égée**, **Cœur Défense** (rel/3071676 has height "1"): missing or bad height tags.
- **Saint-Eustache**: outline height 10. **Saint-Augustin**: 16 zero-area 79 m parts (way/354604773-788).
- **Tour Franklin**: two ways with the same name; **Tour Initiale**: outline way/79864257 has 1 level, the 109 m
  part way/50013026 is a `building:part=commercial`.
- **Tour Triangle**: `building=construction` (180 m tag): needs an override to be extruded.
- **Front de Seine chimney** (way/245189975, "Tour de chaudière"): `building=yes` h130, a 130 m box for a chimney.
- Duplicate ids in the Front de Seine towers (rel and way for Perspective 2, Espace 2000): the CSV uses one.

## Status notes

- **Tour Triangle** (15e): structure topped out, interior fit-out in 2026, opening announced 2026 to early 2027.
  Included (180 m, 44 floors).
- **The Link** (La Défense): completed 2025, 242 m Arche tower (Wikipedia; OSM 241). Twin Seine tower 178 m has no
  OSM outline yet.
- **Tour Montparnasse**: a renovation with a new envelope and a proposed 18 m winter garden (232 m) is planned; the
  height stays 210 m in every source and the CSV keeps 210 m.
- **Tours Duo**: complete since 2021 (Duo 1 180 m, Duo 2 122 m).
- **Notre-Dame**: reopened December 2024; the spire is rebuilt to 96 m.
- **Cancelled**: Tours du pont de Neuilly (220 m, 2010), Hermitage Plaza (320 m), Tour Phare and others; not in the
  data. Sisters, Odyssey, Jardins de l'Arche are permits only, not built.
- **Outside the area, not in the CSV**: Tour Sequana (Issy), Tour Pleyel (Saint-Denis), Les Mercuriales (Bagnolet),
  Tour Horizons and Citylights (Boulogne), Tours Nuages 1-2 (Nanterre, lon 2.227), Tour TDF des Lilas, Tour Cityscope
  (Montreuil), Tour La Villette (Aubervilliers), Préfecture de Nanterre. Tour France (Puteaux, lat 48.883) is in the
  CSV as BORDERLINE-OUTSIDE.

## Eiffel Tower: how it should enter

The Eiffel Tower is a lattice, not a building. Do it like New York's non-building structures: `feature=structure`,
`use_height=False` in the CSV (done), exclude the OSM ids above from the building table, and add a `[[structures]]`
entry in `demos/paris/city.toml`. The `kind = "figure"` entry (as the Statue of Liberty and the Edge deck) takes
`at`, `facing`, `sections` (lofted rings: y, x, z, rx, rz), `prisms`, `tubes` (p0, p1, radius), `boxes`, or a `model`
(glb). Proposed build:

- four legs as `tubes` in segments along the curve from a 129.2 m square base to about 40 m square at the 1st floor
  (57.6 m), 20 m square at the 2nd (115.7 m), and 5 m at the 3rd (276 m); arches between the legs as tubes up to
  57 m;
- `boxes` for the decks: 1st floor about 70 x 70 m, 2nd about 42 x 42 m, 3rd about 16.5 x 16.5 m;
- a tapered `sections` loft (or thin tubes) for the shaft above 115 m, with the antenna a tube to 330 m;
- colour "Eiffel brown" (#6d5a4a to #8b7355), floodlit style for the night glitter.

An open lattice needs an engine feature (a `lattice` facade style with cutout alpha, or a scan model in
`raw/models`); a solid loft reads as a rocket. Position: (48.858262, 2.294496), axis about 32 degrees from north
(legs face the Trocadéro and the École militaire).

## Seine bridges in the area (for M3 decks)

Deck heights over normal water level are ESTIMATED except where noted: the Seine in Paris is held near 26.5 m NGF
by the Suresnes and Port-à-l'Anglais weirs, the quay road lies about 5 to 6 m over the water, and the navigation
clearance is about 5.3 m; most low arch bridges sit at 6-8 m; Bir-Hakeim's metro viaduct and Bercy's viaduct are
the exceptions. Use the DEM/quay levels first and these numbers as checks.

| Bridge | Type | Length | Deck over water (est.) | Note |
|---|---|---|---|---|
| Pont de Neuilly | 5 concrete-and-stone arches (rebuilt 1942, 1772 by Perronet) | about 219 m (5 spans) | 7-8 m | Neuilly, 35 m wide, Avenue Charles-de-Gaulle |
| Pont de Puteaux / Courbevoie | concrete girder | 350 m (Puteaux) | 8 m | west of La Défense, outside the box |
| Pont de Grenelle | steel (two 85 m spans) | 220 m, 30 m wide | 8 m | crosses the Île aux Cygnes |
| Pont de Bir-Hakeim | steel two-level: roadway and Metro line 6 viaduct on top, masonry piers | about 237 m | roadway about 6 m; Metro deck about 15 m (ESTIMATED) | Line 6 viaduct crosses on a colonnade |
| Pont d'Iéna | stone, 5 arches of 28 m | 155 m | 6-7 m | eagles on the arches |
| Passerelle Debilly | steel arch, footbridge | about 125 m | 5-6 m | 1900 |
| Pont de l'Alma | steel arch (1972), single-span-like | about 150 m | 6-7 m | |
| Pont des Invalides | stone, 3 arches | about 150 m | 6-7 m | |
| Pont Alexandre-III | one steel arch, 107.5 m span, hinged, 40-45 m wide; low rise | about 160 m | 6.5 m (low rise) | gilded lamp posts, 4 pylons 17 m |
| Pont de la Concorde | stone, 5 arches | 153 m, 35 m wide | 6-7 m | |
| Passerelle Léopold-Sédar-Senghor (ex-Solférino) | steel arch footbridge, two levels | 106 m | 5.5 m | 1999 |
| Pont Royal | stone, 5 arches (23.4 m centre) | about 110 m | 6-7 m | |
| Pont du Carrousel | steel and concrete, 3 arches | 169.5 m, 11.85 m wide (between rails) | 6 m | |
| Pont des Arts | steel footbridge, 9 arches of 16.8 m | 157.5 m, 10 m wide | 5-6 m | rebuilt 1984 |
| Pont Neuf | stone, 12 arches (7 and 5 over the two arms) | 238 m, 20.5 m wide | 6-7 m | oldest bridge in Paris (1607) |
| Pont au Change, Pont Notre-Dame, Pont Saint-Michel | stone, 7 / 3 / 3 arches | 105-130 m | 5-6 m | |
| Pont d'Arcole | steel single arch 80 m | about 80 m, 20 m wide | 6 m | 1856 |
| Pont Louis-Philippe, Pont Marie, Pont de la Tournelle, Pont de l'Archevêché | stone arches | 68-100 m | 5-6 m | Île Saint-Louis |
| Pont de Sully | cast-iron (3 arches 46-49 m) and stone | 159 m (south arm) | 6 m | |
| Pont d'Austerlitz | 5 cast-iron arches (32 m), widened 1885 | 173.8 m, 30.6 m wide | 6 m | |
| Pont de Bercy | 5 stone arches (29 m), 1904 metro viaduct on top: two levels | 175 m, 40 m wide | roadway about 6.5 m; Metro deck about 14 m (ESTIMATED) | Line 6 above |
| Passerelle Simone-de-Beauvoir | steel footbridge, two lens-shaped 190 m span decks | 304 m | 8 m (lens top about 12 m) | 2006, no piers in the river |
| Pont de Tolbiac | stone-and-steel arches, 5 elliptical (29-35 m) | 168 m | 6 m | |
| Pont Charles-de-Gaulle | prestressed concrete box | about 300 m | 7 m | 1996 |
| Pont National | 5 masonry arches (1853) | 188.5 m | 6 m | |

No suspension bridges are within the area. The cable-stayed / suspended footbridges are outside. The Seine's normal
water level at the Pont Royal is 26.5 m NGF; Paris quay edges are about 32 m NGF.
