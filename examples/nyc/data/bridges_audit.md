# Bridge audit (28 September 2026)

This audit compares the parametric bridges in `city.toml` (`[[structures]]`, `roads.decks`) with published
facts and reference photos. It was done by a research subagent. HAER/LoC, Structurae and nycroads.com
refused access, so the facts come from:
- Wikipedia (which cites HAER and Ammann);
- the PANYNJ and Modjeski & Masters pages;
- Michael Minn's RFK page;
- OSM pylon and pier footprints;
- colour samples from Wikimedia Commons photos.

"est." marks an estimate.

## Applied

| Bridge | Change |
|---|---|
| George Washington | Towers placed at the OSM pylons, 1,066 m apart. Two lattice legs (columns ±15.5/±32, 23 m deep, tapering to 15 m); the portal is braced only near the top. Side spans 186/198 m. Cables ±14.8/±17.5, r 0.46. Upper deck 75 m, lower 66.5 m (clearance 64.6 m under the lower deck). Open side trusses between the decks. NY anchorage 85 × 55 m. |
| Williamsburg | Towers at the OSM pylons, 488 m apart. Leg columns ±11.2/±18.5, 12.2 m deep. Side spans on piers: no suspenders there, straight backstays. Hangers every 6.1 m. Two trusses 12.2 m deep, 20.4 m apart, from anchorage to anchorage. Roadway at 43 m. Anchorages 54 × 47 × 24 m. Grey #8a8c92. |
| Robert F. Kennedy | Towers at the OSM pylons, 421 m apart. Side spans 213 m. Warren truss 6.1 m deep. Deck 45 m. |
| Queensboro | Truss planes 18.3 m apart (60 ft). Tan #b09b82: it was dark blue-grey. Bottom chord at the 41 m clearance, top chord about 55 m at mid-channel and 96 m over the piers (est.). |
| Brooklyn | Suspenders about 3.8 m apart. 12 diagonal stays per cable on each side of each tower, reaching 125 m. Stiffening trusses. Central promenade about 5.5 m over the roadways. Cable low point 47.5 m. |
| Manhattan | Four Warren trusses 7.6 m deep. Upper roadways at 48.5 m. The lower roadway and the subway on the bottom chord at 42 m (41 m clearance). Anchorages 72 × 55 × 41 m. Suspenders about 4.6 m apart. |

## Not done yet (by visual impact; items 1 and 2 were done the same day)

1. Queensboro:
   - explicit pier sites and anchor arms (OSM pylons 40.758877,-73.959130 / 40.757267,-73.955417 / 40.756410,-73.953453 / 40.755072,-73.950357);
   - pier towers with spires to about 107 m;
   - granite piers 40 × 12 m with an arch opening.
2. Hell Gate:
   - a two-hinged spandrel-braced arch: the lower rib springs near the water and crowns at about 81 m, the upper chord runs from about 51 m at the towers to 93 m at the centre;
   - granite towers 67 m tall, about 43 × 30 m, down to the water.
3. GWB: a round-arched lattice portal over the decks; the legs' outer faces battered.
4. Finials and lanterns: the Manhattan Bridge's spheres to 106.7 m, the RFK's 9 m Art Deco lanterns.
5. RFK: plated legs with an Art Deco portal screen instead of lattice.
6. Williamsburg: cable pairs converging from 34 ft apart at the anchorages to 4 ft at midspan.

## Open models

No CC0 or account-free model exists for any of the seven bridges. The CC BY candidates are all on Sketchfab
and need an account to download. The best is "LowPoly Manhattan Bridge" (SUSUSUBE, 57k triangles):
https://sketchfab.com/3d-models/50861561576949f4931da99bdd2d940b

## Sources

- Wikipedia: George_Washington_Bridge, Williamsburg_Bridge, Robert_F._Kennedy_Bridge, Queensboro_Bridge,
  Hell_Gate_Bridge, Brooklyn_Bridge, Manhattan_Bridge
- GWB: https://portfolio.panynj.gov/2016/06/23/gwb-did-you-know/ and
  https://modjeski.com/projects/suspension/george-washington-bridge-suspension-system-rehabilitation/
- RFK: https://michaelminn.net/newyork/mobility/manhattan-bridges/triboro-bridge/suspension-span/index.html
- OSM pylons:
  - GWB ways 741784699 and 741784700
  - Williamsburg 1016434034 and 1016434035
  - RFK 1016642595 and 1016642596
  - Queensboro 1016487154–1016487170
  - Hell Gate 1016643613 and 1016643614
