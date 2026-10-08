# London landmark list: sources, disputes, OSM errors, structures and bridges

Companion to `landmarks_london.csv` (127 rows, same 13 columns as Paris's `landmarks_paris.csv`; a local or alternate
name in `name_zh`, the English name in `name_en`). Research note for London M1 (the city after Paris), 2026-09-30, made
before the london branch exists (it moves into the repo with the branch). Heights are the **Wikipedia EN "List of
tallest buildings and structures in London" (raw wikitext of 2026-09-30: heights, floors, completion years, list
coordinates)**, the page of each monument, the OSM `height` tag where the row says "OSM only", and a few web checks
(1 Undershaft, 50 Fenchurch, 2 Finsbury Avenue, Westminster Cathedral campanile, St Paul's galleries, Old Royal Naval
College domes). OSM state: Overpass mirrors maps.mail.ru and overpass.private.coffee (the public ones time out about
every other call), base timestamp of 2026-09-29. **CTBUH pages could not be read from here** (the Skyscraper Center
was not fetched): the Wikipedia list cites CTBUH for most rows, but "CTBUH" is not confirmed independently in this
note. `use_height=True` on 92 rows, `False` on 35. 108 rows are >= 80 m, 19 are below (monuments and the O2/Tate
structures).

Area: City of London, City of Westminster (all), the Southwark and Lambeth riverside strips, Tower Hamlets west to
Limehouse plus the Isle of Dogs, the Battersea/Nine Elms clip, Camden south (BT Tower, Euston Tower, Centre Point), the
Greenwich clip (Peninsula, O2, park, Observatory). Area test = Phase-0 polygons (`demos/data/phase0/units.gpkg`,
`clips.json`); rows marked BORDERLINE are within ~110 m of the polygon.

**Not exhaustive between 80 and 100 m**: only the Wikipedia list (>= 100 m) and OSM `height` tags (few buildings have
one) feed that band; an OSM 80-100 m tower without a `height` tag is missing. Unresolved 80 m item: OSM w/742635807
(19 levels, h80, 51.50737,-0.10398, Bankside/Sampson House area) is unnamed and not in the CSV.

## How the landmark height applies (important for M4)

Same rule as Paris: `04_buildings.apply_landmarks` gives the height to the footprint under the point; **where the
footprint is made of `building:part`s, the parts keep their own heights** and the landmark only sets the name. In London
many towers and all the monuments are part-built (Shard, 22 Bishopsgate, Gherkin, 8 Bishopsgate, Walkie-Talkie, Big
Ben, St Paul's, Tower Bridge, London Eye, BPS chimneys), so the OSM part heights win: the errors below matter.

## MUST-HAVE rows (the user's list)

| Landmark | Height in CSV | What it means | OSM |
|---|---|---|---|
| The Shard | 309.6 m | tip of the spire (Wikipedia page 309.6; the list intro says 306 m; OSM 310), 72 occupied floors | outline w/31110737 (h310 lv95) + stepped parts 310/290/260/254/252/235, correct |
| 22 Bishopsgate | 278 m | roof/crown (Wikipedia list 278.2), 62 floors, 2020 | outline w/717332347 (h278 lv61) + parts 278/260/220/212 |
| The Gherkin (30 St Mary Axe) | 179.8 m | tip (Wikipedia 179.8; OSM 180) | outline w/4959489 h180 lv41 |
| 20 Fenchurch (Walkie-Talkie) | 160.1 m | top (OSM 160, ~300 stepped parts) | outline w/201247295 named "Sky Garden" (h160 lv37) + parts w/949000150-949000302 |
| The Leadenhall Building (Cheesegrater) | 224.5 m | roof | outline w/309413981 h224.5 lv48; parts 224.5, 196 |
| St Paul's Cathedral | 111 m | tip of the cross (365 ft) | outline w/369161987 only 35 m; ~100 parts up to 111 m (w/664613338) |
| Tower Bridge | 65 m (towers) | STRUCTURE (below) | towers as OSM parts 58/65 m |
| Tower of London (White Tower) | 27.5 m ESTIMATED from memory, turrets ~32 m | not re-fetched: verify against Historic England | w/369135772 (no height) |
| Big Ben (Elizabeth Tower) | 96 m | tip (Parliament factsheet) | w/123557148 h96 + ~60 stacked parts |
| Palace of Westminster | 91 m Central Tower; Victoria Tower 98.5 m | with Big Ben | r/1567699 (+ parts, roofs 25.5-40 m) |
| London Eye | 135 m | STRUCTURE (below) | OSM 136.5 m block of ~150 stacked parts: ERROR |
| Battersea Power Station | 103 m chimneys, 55 m main building | four chimneys 103 m; boiler house roof 50-55 m | chimney parts w/223254725, w/223255111, w/223255300, w/223255478 (h103, min 50); main outline w/4965216 h30 (wrong), parts w/452939929-933 (50-55) |
| One Canada Square | 235 m | pyramid tip (CTBUH/OSM 235; Wikipedia list 236) | w/5986754 h235 lv50 |
| BT Tower | 177.4 m main structure (189 m with aerial rigging; OSM 188.4) | Camden clip | w/5022282 h188.4 lv37; parts w/331901552 (188.4, min 174), 331903530, 331901551, 331903528, 331903531 |

Other named landmarks in the CSV: One Blackfriars (166.3), South Bank Tower (150.4), St George Wharf Tower (180.6),
Southbank Place (One/Thirty/Four Casson Square), the Nine Elms towers (One Nine Elms 199.4, DAMAC 169.8, One Thames
City, River Park, Sky Gardens, Gladwin, Rudolf Place, Keybridge), the Canary Wharf group (Landmark Pinnacle 233.2,
Newfoundland 219.7, Aspen 215.8, South Quay Plaza 1 214.5, One Park Drive 204.9, 25 and 8 Canada Square 201/199.5,
Harcourt Gardens 192.4, Wardian East/West 187.2/168.1, Amory 182.0, 40 Charter Street 178.6 topped out, One Thames Quay
157.6, One Churchill Place, Baltimore, Pan Peninsula, ...), Heron Tower / 110 Bishopsgate 230, 8 Bishopsgate 203.7, the
Scalpel 190.1, Tower 42 182.9, 100 Bishopsgate 171.6, 1 Leadenhall 165.2, 40 Leadenhall 156.7, Broadgate Tower 161.3,
Centre Point 117.3, Millbank Tower 118.9, Euston Tower 124.6, the Barbican towers 123, Portland House 101, Hilton Park
Lane 101, Westmark Tower (Paddington) 101.7, Guy's Tower 148.7. Monuments: Buckingham Palace 24, Westminster Abbey 69
(towers), Westminster Cathedral campanile 87, the Monument 61.6, Tate Modern chimney 99 and Blavatnik 64.5, the O2 (52
dome, 100 masts), Royal Observatory (ESTIMATED 20), Old Royal Naval College domes (ESTIMATED 50), Cutty Sark, HMS
Belfast, Nelson's Column 51.6, Wellington Arch (ESTIMATED 20), Somerset House and the National Gallery (ESTIMATED),
Broadcasting House 34, St Bride's steeple 69, IFS Cloud Cable Car south tower 60.

**Not sourced or not done (time box)**: Old Bailey dome, St Mary-le-Bow, Southwark Cathedral, City Hall, Lambeth
Palace, St Pancras Renaissance clock tower (Camden edge), Guildhall, Royal Exchange, Bank of England, Somerset House and
National Gallery heights are estimates, the Royal Observatory and Old Royal Naval College heights are estimates,
Westminster Abbey west towers (69) and St Paul's are sourced. Old Royal Naval College dome positions are the outline
centre, not the dome centres.

## Status notes

- **1 Undershaft**: **not built**. Wikipedia (2026): 294 m, 74 floors, full consent Dec 2025, contractor appointment
  expected late 2026, construction start 2028; press (Construction Enquirer 2026-06-01) calls it "One London" at 309.6
  m, completion 2033. The row is in the CSV as `approved, not built` with `use_height=False`. **St Helen's tower
  (117.9 m, Aviva Tower) on the site is being deconstructed** (Keltbray, ~18 months from 2026): OSM w/166431068 still
  has it at h118; the CSV row is `use_height=False`, watch it.
- **Topped out, not complete** (Wikipedia list 2026): 40 Charter Street (178.6 m, 2027), 2 Finsbury Avenue East Tower
  (156 m Wikipedia vs 170 m Sir Robert McAlpine, topped out 26 Jan 2026, completion mid-2027; no footprint matched).
- **Under construction, not in the CSV**: 50 Fenchurch Street (149.6 m, 36 floors, core rising June 2026, 2028),
  Cuba Street (172 m, Isle of Dogs, 2028), 30 Marsh Wall (156 m), One North Quay (123.8 m per Wikipedia; a search
  result says 135 m, 23 floors, KPF life-sciences, completion 2027), Sampson House B (120 m, Bankside), Edge London
  Bridge (107 m), 72 Upper Ground (105 m), The Bellamy (104 m).
- **Approved** (not built): 55 Bishopsgate 268.6 m, 100 Leadenhall 249 m, 99 Bishopsgate (new) 240 m; the Wikipedia
  skyline caption lists all three with 1 Undershaft by 2030.
- Battersea Power Station opened 14 October 2022 (restoration completed).
- Excluded as outside the area: Elephant and Castle (Strata 148, Highpoint 148.7, One The Elephant), Shoreditch/Hackney
  (Principal Tower, The Stage, Atlas), Islington (Carrara, Valencia, Chronicle, Finsbury Tower), Stratford, Lewisham,
  Rotherhithe/Canada Water (The Founding 123.9), RBKC (Trellick Tower, Empress State, Basil Spence Tower, Imperial
  College Queen's Tower), Royal Albert Hall and the Natural History Museum (Kensington is not in the area).

## Disagreements and how they were resolved

| Building | Sources | Kept |
|---|---|---|
| The Shard | Wikipedia page 309.6 (tip), list intro 306, OSM 310 | 309.6 |
| 22 Bishopsgate | Wikipedia list 278.2, CTBUH/OSM 278 | 278 |
| One Canada Square | CTBUH/OSM 235, Wikipedia list 236 | 235 |
| One Park Drive | 204.9 (Wikipedia), OSM 205, press 215 (wrong) | 204.9 |
| 8 Bishopsgate | Wikipedia 203.7, OSM top part 205 | 203.7 |
| One Blackfriars | Wikipedia list 166.3, OSM 163 (the 2017 topped-out figure) | 166.3 |
| 1 Leadenhall Street | Wikipedia 165.2 (32 floors), OSM 158.8 (38 levels) | 165.2 |
| South Bank Tower | Wikipedia 150.4, OSM 155 | 150.4 |
| Guy's Tower | Wikipedia 148.7, OSM 140 | 148.7 |
| 1 Casson Square (Southbank Place) | Wikipedia 122.3, OSM 105 | 122.3 |
| 4 Casson Square | Wikipedia 100.0, OSM 105 | 100 |
| 25 Churchill Place | Wikipedia 118, OSM 130 | 118 |
| BT Tower | main structure 177, with aerial rigging 189 (Wikipedia); OSM 188.4 | 177.4 (OSM parts keep their 188.4 needle) |
| Victoria Tower | Parliament 98.5, Wikipedia list 102 (flagstaff), OSM 96 (+ an OSM 120 m part) | 98.5 |
| Westminster Cathedral campanile | cathedral 87 (284 ft), OSM 82 | 87 |
| Landmark Pinnacle | 77 floors (Wikipedia), 75 levels (OSM) | 233.2 m, 77 |
| 2 Finsbury Avenue East | Wikipedia 156, contractor 170 | 156 (unverified) |
| 1 Undershaft | Wikipedia 294, press 309.6 | 294, not built |
| London Eye | Wikipedia 135, OSM 136.5 | 135 |
| Lloyd's building | OSM 88, recalled 95.1 | 88 (OSM only) |

## OSM errors found

- **London Eye**: a solid block. About 150 stacked `building:part`s (w/1133007191-304 up to 71 m and
  w/1133013730-14026 up to 136.5 m) plus the outline w/204068874 (h136.5): the wheel as a filled mass. Exclude all of
  them from the building table.
- **Battersea Power Station**: outline w/4965216 says h30; the boiler house parts (w/452939929-933) are 50-55 m and
  the four chimneys (h103, min 50) are correct.
- **One Nine Elms City Tower**: outline w/1052491831 has building:levels 66 (57 floors) and no height.
- **Landmark Pinnacle, Newfoundland Quay, Wardian East/West, Amory Tower, Harcourt Tower, 40 Charter Street, Maine
  Tower, Sirocco Tower, One Thames Quay, 10 Park Drive, 50-60 Charter Street 1 and 2, Charrington Tower, Dollar Bay,
  Chapter London Bridge and dozens more Canary Wharf/Nine Elms towers**: levels only, no `height`. They need a
  landmark height or a floors x 3.3 m estimate (Harcourt Tower has 64 levels for 56 floors: use the Wikipedia floors).
- **Hilton London Park Lane**: the building outline w/404488197 is named "MR PORTER Steakhouse, Bar & Lounge London".
- **Victoria Tower**: part w/1127232166 h120 (min 88.5), 20 m above anything sourced.
- **Westminster Abbey**: part w/1149648650 h77 at 51.4996,-0.1284; nave/transept roof parts 43-51 m look tall.
- **Tower 42**: parts w/309500200 (183), 309500202 (168, min 20), 309500203 (162, min 30) are stacked, fine.
- **BT Tower**: OSM heights (188.4, 174, 170, 166, 158, 152) include the aerial rigging; the shaft is 177 m.
- **St Paul's**: outline w/369161987 is 35 m; the real mass is in parts.
- **St Helen's (118 m)**: exists in OSM, being taken down (see status).
- **O2**: r/1895281 (h50) is a cylinder for a fabric dome.
- **Aspen at Consort Place / Alta at Consort Place / One Thames City No. 8 / River Park Tower / Keybridge Lofts / No.9
  Thames City / One Crown Place South / 2 Finsbury Avenue East**: no OSM footprint matched within 70 m; positions are
  from the Wikipedia list, `use_height=False` in the CSV (Alta shares a footprint with the Novotel, 40 Marsh Wall, so
  Alta has no row).
- **Hackney/City boundary**: Broadgate Tower (201 Bishopsgate) is listed as City of London by Wikipedia but sits on
  the Hackney line; test against the boundary polygon.

## Boundary finding for M0/M1

The **Nine Elms/Vauxhall towers lie south of the Phase-0 L_riverside clip** (its south edge is lat 51.483; One Nine
Elms is at 51.4843, One Thames City No. 8 at 51.4831, Sky Gardens at 51.4818, Gladwin Tower at 51.4815, No.9 Thames City
at 51.4826). The Battersea clip starts at lon -0.13 east limit, so a strip between lon -0.13 and -0.108 south of
51.483 (Nine Elms, the U.S. Embassy, Vauxhall Cross, New Covent Garden) is in neither clip. Extend L_riverside south to
about lat 51.478 (or add the strip to the Battersea clip) so that the Nine Elms row block and the Battersea Power
Station - Vauxhall skyline is complete. Westmark Tower (Paddington, lon -0.172) is at the far west of Westminster,
outside every Phase-0 clip: include it only if the whole borough is used.

## Structures: how each should enter

The engine takes non-building structures through `[[structures]]` (kind `figure`: `sections`, `prisms`, `tubes`,
`boxes`, or a `model` glb), as New York does for the Statue of Liberty and Paris for the Eiffel Tower. Recommendations
(all rows have `feature=structure`, `use_height=False`, and exclude the OSM ids listed in the CSV notes from the
building table):

- **Tower Bridge (hybrid, do not build in the building table)**: keep the two towers as OSM part prisms or rebuild them
  as `sections` (65 m, four corner turrets, granite/Portland stone, Gothic top). Add a figure for the two bascule leaves
  (roadway, 61 m clear span, two 30 m leaves), the high-level walkways (a horizontal box 44 m above high tide between
  the towers, with the suspension rods to the abutments), and the two 82 m side spans with suspension chains
  (`tubes`). Blue/white steel colour. Closed roadway clearance 8.6 m at high water; navigational clearance open 42-44 m.
  The roadway is about 8.6 m above high water (7 m tidal range: the deck does not move; the water does).
- **London Eye**: `tubes` for the rim (120 m diameter torus of thin tubes), spokes (cable pairs, ~ 4 per capsule), the
  A-frame legs and the axle (hub ~ 75 m), 32 `boxes` for capsules (egg-shaped in reality). The axle is cantilevered over
  the river, so the wheel plane runs roughly along the river's flow at Jubilee Gardens; take the orientation from the
  base OSM outline. Exclude w/204068874 and every part (w/1133007xxx, w/1133013xxx, w/1133014xxx).
- **The O2 (dome)**: `sections` loft, 365 m diameter, 52 m at the centre, edge ~ 25-30 m; no building outline (exclude
  r/1895281). **Masts**: 12 `tubes` 100 m tall in a ring (nodes n/2377736208-262), stays as thin tubes to the rim
  (~ 24 cable pairs). White fabric roof; yellow masts.
- **Cutty Sark**: `figure` with `sections` hull loft (length 64.8 m hull, 85 m LOA, beam 11 m), three `tubes` masts
  (main ~ 46 m ESTIMATED, fore/mizzen slightly shorter) and yard `tubes`; sits 3 m over the dock floor in a glass skirt
  (raised).
- **The Monument and Nelson's Column**: small `figure`s (shaft `tube`, base `box`, urn/statue `sections`). Otherwise the
  OSM outlines are extruded as square prisms 62 m/51.6 m.
- **HMS Belfast**: `figure` hull loft + a lattice mast, 187 m long.
- **IFS Cloud Cable Car**: tube pylon (South Tower 60 m in the clip) + two cable `tubes` across the river.
- **BPS chimneys**: OSM parts are fine (four 103 m parts on the 50-55 m building).
- **Thames Barrier** (Woolwich) and other structures are outside the area.

## Thames bridges in the area (for M3 decks)

The Thames is **tidal**: range about 7 m at London Bridge; the river level moves twice a day. Verified numbers: the
Environment Agency Tower Pier gauge shows a usual range of **-2.84 to +4.20 m AOD (ODN)** for 90 % of observations,
a 12-month range of -4.32 to +4.42 m, and a highest recorded level of **+4.81 m (1 March 1990)**. **Approximate,
not verified this session**: mean tide level ~ +0.3 m ODN (midpoint of the usual range is +0.68), mean high water
springs ~ +3.7 to +4.0 m ODN, mean low water springs ~ -2.6 to -2.9 m ODN, Chart Datum at London Bridge ~ 3.2 m below
ODN (the PLA tide booklet and PLA bridge-heights page returned 403 from here). Model the water at a single level of
about **0 to +0.3 m ODN (mean tide)** for the static scene; at low water the foreshore (mud, gravel, Bankside beach) is
exposed to ~ 3 m below mean tide. The Thames Barrier upstream/downstream control keeps the design flood level at about
+5.2 to +5.8 m ODN in central London (TE2100, recalled).

Deck heights over mean tide are **ESTIMATED or derived from clearance at LAT** (Lowest Astronomical Tide is ~ 3.3 m
below mean tide): soffit over mean tide = clearance at LAT - ~3.3 m. Use the DSM/DTM first and these numbers as checks.

| Bridge | Type | Opened | Length / main span | Clearance (source) | Note |
|---|---|---|---|---|---|
| Chelsea Bridge (in the Battersea clip) | self-anchored suspension (steel), 3 spans | 1937 | 213 m (698 ft) / 101 m (332 ft); 19.5 m wide; tower 21 m | 13.0 m at LAT (42 ft 9 in) (Wikipedia) | soffit about 9.7 m over mean tide |
| Albert Bridge (outside, lon -0.167) | Ordish-Lefeuvre cable-stayed/suspension/beam hybrid | 1873 | 216 m (710 ft) / 56 m (185 ft after 1973); 12.5 m wide | 11.5 m at LAT (37 ft 9 in) | outside the area; the "Trembling Lady", 4 pylons |
| Grosvenor Bridge | steel railway arch, rebuilt 1963-67 | 1860 / 1967 | 283.5 m / 53.3 m; 54 m wide | not sourced | Victoria line into Victoria station |
| Vauxhall Bridge | 5 steel arches on granite piers | 1906 | 246.6 m (809 ft); 24.4 m (80 ft) wide | 12.1 m at LAT (39 ft 9 in) | soffit about 8.8 m over mean tide |
| Lambeth Bridge | 5-span steel arch (box), 1932 | 1932 | about 250 m (RECALLED) | not sourced | red (House of Lords colour) |
| Westminster Bridge | 7 cast-iron arches | 1862 | 250 m; 26 m wide | not sourced | the Houses of Parliament view |
| Hungerford Bridge and Golden Jubilee Bridges | steel truss rail bridge (1864) between two cable-stayed footbridges (2002) | 1864 / 2002 | about 300 m (RECALLED) | not sourced | Charing Cross |
| Waterloo Bridge | reinforced-concrete box girder, 5 spans | 1942 | 375 m (1,230 ft) / 71 m (233 ft); 24.4 m (80 ft) wide | not sourced | "Ladies' Bridge" |
| Blackfriars Bridge | 5 wrought-iron arches | 1869 | 281 m (923 ft); 32 m (105 ft) wide | not sourced | red-painted piers; Blackfriars Railway Bridge (1886, arch) 30 m upstream, station on it |
| Millennium Bridge | lateral-suspension footbridge | 2000 | 325 m / 144 m main span; 4 m wide | not sourced | flat suspension; St Paul's axis |
| Southwark Bridge | 5 steel arches | 1921 | 244 m (800 ft) / 73 m (240 ft); 16.8 m (55 ft) wide | not sourced | |
| Cannon Street Railway Bridge | steel-truss railway bridge | 1866, rebuilt | not sourced | not sourced | |
| London Bridge | prestressed-concrete box girder, 3 spans | 1973 | 269 m / 104 m; 32 m wide | 8.9 m (Wikipedia; datum not stated, likely high water) | 5th bridge on the site; the "London Bridge" of the OSM is w/3709270 etc. |
| Tower Bridge | bascule + suspension (steel, stone clad) | 1894 | 244 m (940 ft with abutments 290 m) / 61 m between towers; side spans 82 m | 8.6 m closed at high water (Wikipedia: 29 ft at Trinity HW per the spec); 42-44 m open; walkways 44 m over the river | STRUCTURE; towers 65 m |

Downstream (Isle of Dogs, Greenwich): no Thames bridges except the cable car; the docks have small swing/lift and
footbridges (Glengall Bridge w/744311590 movable, Greenwich Reach Swing Bridge w/688458443 movable, Poet's Bridge,
Adams Plaza Bridge, West India Down Viaduct, Millwall Viaduct). The Rotherhithe Tunnel and Blackwall Tunnel are
underground. Bridge deck heights on the DLR viaducts (Isle of Dogs) are not sourced.

OSM bridge ids: Westminster Bridge w/216998718, w/920237496/500/507/508; Lambeth w/119724182, w/201619353, w/378460900/901;
Vauxhall w/378283142, w/742204210, w/749336136; Chelsea w/257000703, w/316367189/91, w/536526736; Waterloo w/200596577,
w/200598186/189, w/208169532; Blackfriars w/35900729, w/123464163, w/147968997 (rail); Southwark w/2700151, w/378492763;
London Bridge w/3709270, w/292167550; Millennium w/3713268, w/659424463; Tower Bridge w/378541210, w/24951423, w/97440715
(movable, "h30 feet"), w/153173956-59, r/5641637; Golden Jubilee w/4254120/23, w/186931859; Hungerford w/184107136.

## Sources

- Wikipedia EN "List of tallest buildings and structures in London" (raw wikitext, fetched 2026-09-30; cites CTBUH
  Skyscraper Center per row), and the pages of Palace of Westminster, Victoria Tower, Westminster Abbey, St Paul's
  Cathedral, Tower Bridge, London Eye, Battersea Power Station, The O2, Tate Modern, BT Tower, The Shard, Millbank
  Tower, Buckingham Palace, Nelson's Column, Broadcasting House, St Bride's, Westminster Cathedral, 1 Undershaft,
  Vauxhall/Chelsea/Albert/Waterloo/London/Blackfriars/Southwark bridges.
- OSM via Overpass (2026-09-29 base): height/levels queries over the area bbox, `around` queries on each monument.
- Web checks 2026-09-30: Construction Enquirer (1 Undershaft, 2026-06-01), St Paul's site/tour pages (galleries),
  westminstercathedral.org.uk (campanile), riverlevels.uk (Tower Pier levels), Wikipedia (50 Fenchurch, 2 Finsbury Avenue),
  SRM/Hare press (2 Finsbury Avenue topping out).
- Not reachable from here: CTBUH Skyscraper Center pages (not fetched), PLA tide booklet, PLA bridge heights (403),
  Historic England (not fetched).
