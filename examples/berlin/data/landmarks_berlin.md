# Berlin landmark list: sources, disputes, OSM errors, structures and bridges

Companion to `landmarks_berlin.csv` (140 rows, the same 13 columns as London's `landmarks_london.csv`; the German
name in `name_zh`, the English name in `name_en`; names are German spellings with umlauts). Research note for Berlin
M1 (the third city after Paris and London), 2026-10-02, written before the berlin branch exists. All data stays under
`demos/data/berlin/research/`.

**Sources.** (1) Wikipedia EN "List of tallest buildings in Berlin" (raw wikitext fetched 2026-10-02: heights, years,
the under-construction table; it lists 176 m Estrel Tower in Neukoelln as the tallest, outside the boundary).
(2) Wikipedia DE and EN articles of single landmarks (raw wikitext and article intros, 2026-10-02): Fernsehturm
(infobox 368.03 m, sphere deck 203.78 m, restaurant 207.53 m, sphere centre 213.78 m, sphere 32 m, shaft 16 m to 9 m,
foundation 42 m), Reichstag (dome 23.5 m high, 38-40 m wide, platform 40.7 m, building 47 m), Berliner Dom (98 m now, 114-116 m
before 1944, dome 33 m), Rotes Rathaus (74 m to the parapet, 94 m to the tip), Oberbaumbruecke (towers 34 m, seven arches 7.5-22 m),
Siegessaeule (Victoria 8.32 m, platform 50.66 m), Hauptbahnhof (Buegel 46 m, upper hall 321 m), Treptowers (125 m),
Molecule Man (30 m), East Side Gallery (1,316 m), Ludwig-Erhard-Haus (arches to 38.6 m), Sony Center (roof 67 m high),
Kollhoff-Tower and Bahntower (EN infobox roof/spire), Brandenburg Gate (EN infobox 26 m x 62.5 m). (3) **OSM**
(Overpass `maps.mail.ru`, base timestamp 2026-10-01; the public `overpass-api.de` returned runtime errors and
`private.coffee` timed out, as in the London note): every `building`+`name`, every `building`+`height`, all
`building:part`+`height`, named bridge ways and `man_made`/`historic`/`tourism` objects in the box 13.30..13.48 E,
52.47..52.55 N (about 3 MB JSON, kept in the private scratch). Ids in the `source` column are `w/` way, `r/` relation, `n/` node.
Where a landmark is made of parts the CSV note prints how many `building:part`s with h >= 15 m lie within 40-100 m and their
top heights. (4) The phase-0 note `demos/data/phase0/berlin.md` (units, landmark coordinates).

**Not done / gaps.** No CTBUH/Emporis pages could be read. Dimensions marked `[believed]` or `ESTIMATED` come from my own
knowledge and are unverified; every other number names its source. 15 rows have no OSM id (not found by name, or nothing to match: area rows and unbuilt towers): Forum Tower (Potsdamer Platz); Kudamm-Karree (Fürst Tower, Kurfürstendamm); Breitscheidplatz ensemble (Gedächtniskirche, Europa-Center, Zoofenster); Covivio Tower (Alexanderplatz, ALX); Hines Alexander Tower (next to Alexa); Tour Total (Europacity); Karl-Marx-Allee Wohnbauten and Strausberger Platz; Café Moskau (Karl-Marx-Allee); Neptunbrunnen and Marx-Engels-Forum (Fernsehturm park); TU Berlin main building and Ernst-Reuter-Platz; Fischerinsel high-rises (Mitte); Leipziger Straße high-rises (Mitte, 1977); Rochstraße 9 and Mollstraße Wohnhochhäuser; Friedrichstraße station (S/U, Mitte); Neues Kreuzberger Zentrum (NKZ, Kottbusser Tor). There is no
Berlin footprint table yet, so the "height applies to the footprint under the point" behaviour (`apply_landmarks`) is
described, not tested. The official Berlin LoD2 (see phase0 `berlin.md`) is the planned footprint/height source:
its `measuredHeight` will replace most OSM heights in this list, which then serve as a cross-check, as the
phase-0 note says OSM has only 7 % of buildings with a `height` tag.

`use_height=True` on 74 rows, `False` on 66 (structures, bridges, unbuilt towers, rows without a height). 100 rows carry
a height; 25 of them are >= 80 m and 14 are >= 100 m.

## Boundary

Ortsteile Mitte, Tiergarten, Moabit, Hansaviertel, Friedrichshain, Kreuzberg, Alt-Treptow and Charlottenburg east of
lon 13.3055 (about 53 km2; `the Phase 0 boundary note`). The inside/outside test is in the table at the
bottom of this note; rows outside are kept as context (Tempelhof, Estrel is not a row).

## How the landmark height applies (important)

Same rule as Paris and London: the landmark height is given to the footprint under the point; **where the footprint is
made of `building:part`s, the parts keep their own heights**. Berlin's must-haves split into three cases:
(a) mapped as parts (Zoofenster and Upper West: 90 m base + 119 m top parts; Hauptbahnhof: the two Buegel as
46-48 m roof parts, 28-32 m annex parts; Kanzleramt: a 36 m part; Kollhoff-Tower probably);
(b) mapped as one prism with a height (Fernsehturm 368, Dom 98, Bahntower 103, Park Inn is NOT: only the 3-level podium is tagged);
(c) mapped without a height (Humboldt Forum 32 m for the whole palace outline, the museums, Rotes Rathaus, most churches).

## MUST-HAVE rows

| Landmark | Height in CSV | What it means | OSM |
|---|---|---|---|
| Fernsehturm | 368.03 m (CSV 368) | tip of the antenna; sphere 32 m dia centred 213.78 m, deck 203.78 m | w/556435241 h368 as a single prism: ERROR (a 368 m column on the pedestal's footprint); build as a figure |
| Brandenburger Tor | 26 m | top of the quadriga (EN infobox), 62.5 m wide | w/518071791 h26 (way) + r/7288267 (relation) |
| Reichstag with dome | 48 m (DE 47) | top of the dome lantern; dome 23.5 m high, 38-40 m dia | r/2201742 h48; the dome is not separately mapped |
| Berliner Dom | 98 m | present height; old 114-116 m | w/313670734 h98 |
| Rotes Rathaus | 94 m (74 to the parapet) | DE vs EN list disagree | r/4211905 (lv 4, no height) |
| Kollhoff-Tower | 103 m roof (115 m tip) | EN infobox roof 103, spire 115; OSM 115 | w/658563176 h115 lv25 |
| Bahntower (DB Tower) | 103 m (EN infobox roof 94) | | w/11080117 h103 lv26 |
| Sony Center roof | 67 m | tent roof, structure | no roof in OSM |
| Gedaechtniskirche | 71 m old tower; 53.5 m new bell tower; octagon 20.5 m | OSM 71 / 53.5 / 22 | w/15218373, w/15218372, w/15218371 |
| Siegessaeule | 67 m | structure (column) | w/718035022 (no height) |
| Hauptbahnhof | 46 m (Buegel) | OSM main outline says 23 m; parts 46-48 | r/3600565; parts w/128280629/30, w/11348359/90 |
| Oberbaumbruecke | towers 34 m | bridge structure | w/288514442 (bridge, h6), w/4686103/4 |
| Humboldt Forum | ~70 m dome (unverified), body 32 m | | r/3007958 h32 lv4 |
| Park Inn | 125 m (EN) | roof; 149.5 m with the crown (EN infobox) | not tagged for the tower (w/23723125 is the podium, 3 levels) |
| Alexanderplatz new towers | Berlinian 146 m (topped out 14 Jan 2026), Covivio 130 m, Hines 150 m | only the first is built as a shell | w/1335157930 h146 lv33 |

Other rows: Potsdamer Platz (Atrium Tower 106, Beisheim 70), Breitscheidplatz (Zoofenster 118, Upper West 118, Europa-Center
103 or 86, Bikini, Kudamm-Karree 102, Kranzler Eck 60), the Museum Island buildings (Altes Museum, Neues Museum, Alte
Nationalgalerie, Pergamonmuseum, Bode-Museum, James-Simon-Galerie), Unter den Linden (Zeughaus closed since 2021, Neue
Wache, Staatsoper, St. Hedwig's), Gendarmenmarkt (Konzerthaus, Franzoesischer and Deutscher Dom 70-78 m), the government
quarter (Kanzleramt 36, Paul-Loebe-Haus 23, Marie-Elisabeth-Lueders-Haus 36 m tower, HKW, Bellevue), Moabit/Europacity
(Einz Tower 84, Cube 43.8, Upbeat 82, Charite tower 82), Friedrichshain/Treptow (EDGE East Side Tower 142, Stream Tower 97.5,
Spreeturm 70, Treptowers 125, Molecule Man 30, East Side Gallery 1,316 m wall), Karl-Marx-Allee, Kreuzberg
(Jewish Museum, Axel-Springer 78, Hochbahn viaduct), TU/Ernst-Reuter-Platz (Telefunken-Hochhaus 77-80), the Hansaviertel
slabs (51-53 m), the Spree bridges (16 rows), the two railway viaducts, the hills (Mont Klamott 78 m a.s.l., Kreuzberg 66 m).

## Disputed heights

| Landmark | Sources | In CSV |
|---|---|---|
| Rotes Rathaus | DE: 74 m to the parapet, 94 m to the tip; EN list: 74 | 94 (tip) |
| Kollhoff-Tower | EN infobox roof 103 m, spire 115 m; EN list 103; OSM 115 | 103 |
| Bahntower | EN list 103 m; EN infobox roof 94 m, spire 103; DE text 103 m total; OSM 103 | 103 |
| Europa-Center | EN article intro: 86 m; EN list: 103 m | 103 (list; roof 86) |
| Zoofenster / Upper West | EN list 119 m, OSM outline 118, parts 119 | 118 |
| Stream Tower | EN list 97.5 m, OSM 90 | 97.5 |
| Charite tower | EN list 82 m, OSM 75 (outline) and 84 (part) | 82 |
| Franzoesischer/Deutscher Dom | EN list 78 m, DE sources 70 m [believed] | 70 |
| Treptowers | 125 m everywhere (EN, DE, OSM) | 125 |
| Park Inn | roof 125 m, tip 149.5 m (EN infobox) | 125 |
| Haus des Reisens | OSM 67, EN list 65 | 67 |
| Koenigstadt-Carree | OSM 80, EN list 79 | 80 |
| Schloss Bellevue | OSM h10 (too low), real ~20 [believed] | 20 |
| Neue Synagoge | OSM 21.3 (the street block), dome ~50 [believed] | 50 |
| Telefunken-Hochhaus | OSM 77, EN list 80 | 77 |

## OSM errors and oddities found

- **Fernsehturm**: one 368 m prism (w/556435241): do not extrude.
- **Hauptbahnhof**: the relation says 23 m; the Buegel parts are 46-48 m, the annexes 28-32 m: use the parts.
- **Schloss Bellevue**: h=10 (a ~20 m palace).
- **Telekom Innovation Laboratories r/4155696**: tagged h=100, lv=4 (looks wrong: a 4-level building).
- **Park Inn**: the tower is not tagged (w/23723125 is a 3-level podium).
- **M50 w/33171141**: `building=construction`, 89 m, 23 levels (state in Oct 2026 unverified).
- **Neue Synagoge**: the 21.3 m outline is the street block; the dome is not a tall part.
- **Zoofenster**: stacked parts (90 m base slabs, 119 m tops, plus 6 m annex slivers): fine, mind the min_height of 90 m.
- **Kudamm-Karree, Beisheim Center, Forum Tower, Tour Total, Cafe Moskau**: no name match in OSM; positions are estimates.
- The OSM `The Berlinian` (w/1335157930) already carries its final height (146 m) though the building is still unfinished.

## Structures and bridges (not boxes)

Fernsehturm (shaft + sphere + antenna), Siegessaeule (column), the Sony Center tent roof, Molecule Man (perforated aluminium
figures), the Holocaust memorial (2,711 stelae, 0.2-4.7 m), the East Side Gallery (a 1,316 m wall, 3.6 m high), the Weltzeituhr,
Checkpoint Charlie hut, the Berlin Wall memorial strip, the Hochbahn (U1/U3) viaduct, the Stadtbahn brick viaduct, the 16 bridge rows
(OSM ways named in the CSV) and the terrain features (Mont Klamott 78 m a.s.l., Kreuzberg hill 66 m a.s.l.): those
belong to `[[structures]]` or the DEM. `feature = structure` / `bridge` marks them; `use_height=False` on all.

## Not built / under construction (as of 2026-10-02)

| Row | State |
|---|---|
| The Berlinian (146 m) | topped out 14 Jan 2026 (DE); completion 2027 (EN list) |
| Covivio tower (130 m) / ALX | under construction; DE says completion end 2028; no OSM building |
| Hines Alexander Tower (150 m) | construction start 2025 (DE); not built |
| M50 (89 m) | OSM `construction` |
| Bauakademie | reconstruction announced; state not verified |
| Zeughaus | closed for renovation since June 2021 (DE) |
| Pergamonmuseum | closed since 2023 (south wing; EN) |
| Kudamm-Karree / Fuerst Tower | conversion with added floors (EN list) |
| Estrel Tower (176 m, topped out 2025) | in Neukoelln: outside the boundary |

## Inside / outside the boundary

See the `inside` check in the table at the end of this file (generated from the OSM Ortsteil relations 16566, 55750,
28339, 16567, 55763, 55765, 55762, 110126 clipped at lon 13.3055).

## Area test table (generated)

Test: each row's point against the OSM Ortsteil relations Mitte 16566, Tiergarten 55750, Moabit 28339, Hansaviertel 16567, Friedrichshain 55763, Kreuzberg 55765, Alt-Treptow 55762 and Charlottenburg 110126 clipped at lon 13.3055 (union 52.1 km2 here, the phase-0 note quotes 53.3). Rows within ~110 m of the boundary are BORDERLINE.

Counts of rows by Ortsteil: Mitte 66, Tiergarten 17, Friedrichshain 16, Kreuzberg 14, Charlottenburg (east of 13.3055) 13, Moabit 8, Alt-Treptow 1, Hansaviertel 1.

Rows not plainly inside:

| Row | Test | Distance to boundary |
|---|---|---|
| Potsdamer Platz Forum Tower (PwC) | ? | 0 m |
| Gedenkstaette Berliner Mauer (Bernauer Straße) | BORDERLINE outside | 27 m |
| Königstadt-Carree | BORDERLINE inside | 78 m |
| Flughafen Tempelhof (Terminal und Radarturm) | OUTSIDE | 419 m |
| Kottbusser Brücke / Skalitzer Hochbahn | BORDERLINE inside | 52 m |
| Berlin Mitte Plattenbau: Mollstraße and Rochstraße | ? | 0 m |

Rows without a point: Forum Tower and Rochstrasse 9. Tempelhof (outside) is kept as context; the Berlin Wall Memorial lies at the north edge of Mitte (the strip partly in Gesundbrunnen). Deutsche Oper (lon 13.3084) is inside the Charlottenburg clip by about 250 m.

## Completeness check against OSM (2026-10-02)

Every OSM building (name+height or levels >= 15; the named/height-tagged set above) inside the boundary polygon that is >= 50 m or has >= 15 levels
was matched to a CSV row within 150 m. Left over (added or noted): Internationales Handelszentrum (93.5 m, now a row), Grandaire (65 m, row),
Silver Tower and Pressehaus (levels only, rows with `use_height=False`), and the Hansaviertel slabs (51-53 m: one grouped row), the
Motel One at Alexanderplatz (18 levels) and the E1 and John-Jahr-Haus buildings (18 levels; not rows). OSM misses most tall buildings
without a `height` tag; the 80-100 m band comes from the Wikipedia EN list (>= 65 m) and OSM `height` tags only, as in London's note.
OSM `building:part` stacks exist for the Fernsehturm, Siegessaeule, Dom, Oberbaumbruecke, Park Inn, Zoofenster, Upper West and
Hauptbahnhof (see the notes).
