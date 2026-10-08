# New areas: landmark notes (Brooklyn waterfront and Downtown, Hudson County waterfront)

Companion to `landmarks_new.csv` (113 rows: 98 towers of 100 m or more, taken from the CTBUH-sourced
Wikipedia lists for Brooklyn and Jersey City, plus 15 low landmarks). Heights are CTBUH or Wikipedia unless
the notes say OSM or ESTIMATED.

Scope decisions:
- **Hoboken, Weehawken and Union City have no buildings of 100 m or more.** The tallest are W Hoboken
  (83 m, included), Marine View Plaza (73 m), Troy Towers and the Doric in Union City (22 to 24 floors), and
  Parkview Towers (24 floors). None of them are in the CSV except W Hoboken.
- **Journal Square is left out.** It is outside the Heights and Downtown: Journal Squared 1, 2 and 3, The Journal
  I and II, 505 Summit, 425 Summit and 100 Clifton Place. Hudson House East (102 m, at Hoboken Ave, where
  Downtown meets the Heights) is included but flagged, because Wikipedia files it under Journal Square.
- **Rows south of Atlantic Ave are flagged "OUTSIDE?".** These are Barclays Center, Brooklyn Crossing
  (18 6th Ave) and 461 Dean. The Axel is flagged "EDGE" because it sits just east of Vanderbilt Ave.
- **Towers under construction are left out** (listed at the end). The CSV keeps 55 Hudson and 420 Marin
  because CTBUH lists both as completed.
- **Rows with no OSM tower outline** use the Wikipedia list coordinate. The notes say so and name the stale way:
  111 Willoughby, Eighty Nine DeKalb, 55 Willoughby, DWTN BK, Verdant Fort Greene, 420 Marin Blvd and VYV South.
  In OSM these lots still show the older low-rise buildings, which will need to be removed or replaced when the
  tower is placed.
- **Estimated positions and heights.** Hoboken Terminal's clock tower has no OSM element, so its point is
  estimated from photos. The Colgate Clock (top of the frame), the Howe Center (14 floors), the terminal roof and
  the Port Imperial ferry terminal have estimated heights. The Colgate Clock row uses `feature=structure`
  because it is not a building.

## (a) Facades of the most visible buildings

Colours are medians sampled from the linked Commons photos (thumbnails). Sunlit glass mostly shows reflected
sky, so each entry gives a suggested base colour to use as the material albedo. Photos are on
commons.wikimedia.org.

### The Brooklyn Tower (9 DeKalb Ave, 315.3 m)
- **Material:** a glass curtain wall with projecting vertical mullion fins. The fins have sharp, staggered edges
  and are dark bronze or black with stainless trim. The stone at the base matches the bank, and the facade
  darkens as it rises.
- **Colour:** the shaft sampled #47556e in sun (sky in the glass) and #36455e in shade. Suggested base: glass
  #2b3038, fins #3a332c with bronze highlights #8a6a48.
- **Glass tint:** dark smoky grey.
- **Shape:** a hexagonal plan. Each of the six faces steps in several times (clear notches at about 1/3, 2/3 and
  near the top) and ends in a faceted crown of fins with no spire. The 1908 Dime Savings Bank (white Pentelic
  marble with a colonnade and a low dome) sits at its foot on DeKalb Ave. The marble sampled #c1aa96 in shade;
  suggested #e3ddd2.
- **Photos:** [Brooklyn_Tower_(55268723550).jpg](https://commons.wikimedia.org/wiki/File:Brooklyn_Tower_(55268723550).jpg),
  [The_Brooklyn_Tower_010.jpg](https://commons.wikimedia.org/wiki/File:The_Brooklyn_Tower_010.jpg)

### Williamsburgh Savings Bank Tower (1 Hanson Pl, 156.1 m to the tip)
- **Material:** the first six floors are limestone over a granite dado. Above that, the tower is buff brick with
  terracotta.
- **Colour:** stone sampled #bfb4a6 in sun and #ada393 in shade. Suggested #c8bca8.
- **Glass tint:** ordinary punched windows, dark.
- **Shape:** a massing of 1916-zoning setbacks up to a square clock stage. It has four 27 ft (8.2 m) clock faces
  with centres about 131 m up, cream faces #c8bbae and gilt hands and dots. Above the clock stage is an arcaded
  belfry, then a ribbed dome, estimated bronze and gold-brown #8a6d45, with a small lantern.
- **Photos:** [Williamsburgh_Savings_Bank_Tower_9128_crop.JPG](https://commons.wikimedia.org/wiki/File:Williamsburgh_Savings_Bank_Tower_9128_crop.JPG),
  [Williamsburgh_Savings_Bank_Tower_from_Hanson_Place_closer.jpg](https://commons.wikimedia.org/wiki/File:Williamsburgh_Savings_Bank_Tower_from_Hanson_Place_closer.jpg)

### Brooklyn Point (138 Willoughby St, 220.3 m)
- **Material:** a pale silver-white metal and precast frame grid with punched window bays of reflective glass.
- **Colour:** overall #707c88 sampled; the light panels #6c727c in shade. Suggested frame #c9ccd0 and glass
  #5d6f85.
- **Glass tint:** blue-grey.
- **Shape:** a slim prism with angled faces, a flat top and a rooftop infinity pool with no crown feature.
- **Photos:** [BrooklynPointII.jpg](https://commons.wikimedia.org/wiki/File:BrooklynPointII.jpg)

### 11 Hoyt (188.4 m)
- **Material:** precast panels scalloped around bay windows, which ripple across the facade in waves (Studio
  Gang).
- **Colour:** overall sampled #4d5560 in shade (sky in the glass). Suggested panels #b9bcbf and glass #3d4d66.
- **Glass tint:** blue.
- **Shape:** the corners flare out and the top edge is concave. Scalloped, not straight.
- **Photos:** [11_Hoyt_007.jpg](https://commons.wikimedia.org/wiki/File:11_Hoyt_007.jpg)

### Clocktower Building (1 Main St, DUMBO, 65.8 m)
- **Material:** cream-painted reinforced concrete, with arched windows at the top floors.
- **Colour:** sampled #cfd0c9. Suggested #d8d4c8.
- **Glass tint:** clear, with dark mullions.
- **Shape:** a 12-storey block with a 4-storey clock stage on the south front. Each side has a big round clock
  with a white face and a green-bronze surround (estimated #6f8f80). The stage is capped by a grey hipped metal
  roof (sampled #8e898d) and a flat-roofed glass lantern.
- **Photos:** [The_Clocktower_Building,_1_Main_Street.JPG](https://commons.wikimedia.org/wiki/File:The_Clocktower_Building,_1_Main_Street.JPG),
  [The_Clocktower_and_the_Manhattan_Bridge_from_15_Clark_Street.jpg](https://commons.wikimedia.org/wiki/File:The_Clocktower_and_the_Manhattan_Bridge_from_15_Clark_Street.jpg)

### Watchtower Building / Panorama (25 Columbia Heights, 43.7 m)
- **Material:** a pale brick and concrete industrial block (the former Squibb building).
- **Colour:** estimated #b9ad98.
- **Sign:** the famous roof sign now reads **WELCOME**, in red letters #d8322e (estimated). It is about
  24 x 4.6 m, faces Manhattan and sits on the old WATCHTOWER frame. The frame is dark steel on the roof, with
  small posts. The old WATCHTOWER sign was removed in 2017 and the WELCOME sign went up in 2019.
- **Photos:** [Watchtower_Building_welcome_sign_as_seen_from_Pier_11,_Financial_District,_Manhattan_-_20200904.jpg](https://commons.wikimedia.org/wiki/File:Watchtower_Building_welcome_sign_as_seen_from_Pier_11,_Financial_District,_Manhattan_-_20200904.jpg)

### 99 Hudson Street (271 m)
- **Material:** light limestone piers running the full height between strips of glass, in an Art Deco reading.
- **Colour:** the glass shaft sampled #4b5b74. The piers are thin and read lighter; estimated #d4cbbb.
- **Glass tint:** dark blue-grey, #3f4f66.
- **Shape:** a square tower that steps in near the top into a glass crown box (sampled #486488). The crown box
  has fine vertical fins and a flat top with small mechanical equipment. There is an eight-storey podium.
- **Photos:** [99_Hudson_St_Jersey_City.jpg](https://commons.wikimedia.org/wiki/File:99_Hudson_St_Jersey_City.jpg)

### 30 Hudson Street, Goldman Sachs Tower (238.1 m)
- **Material:** a clear silver-blue glass curtain wall with dense thin vertical mullions and a few louvre bands
  at the mechanical floors.
- **Colour:** glass sampled #8092a1. Suggested #7d8fa0.
- **Glass tint:** silver-blue, fairly clear.
- **Shape:** the corners are notched and chamfered in steps as the tower rises. The crown is a dark metal louvre
  screen (sampled #2b2f36) wrapped around the top 4 to 5 floors. It is higher at the corners, like a notched
  cap. There is a 7-storey glass podium on the river side.
- **Photos:** [Goldman_Sachs_Tower_(2011-04-09).jpg](https://commons.wikimedia.org/wiki/File:Goldman_Sachs_Tower_(2011-04-09).jpg)

### Sable, formerly Jersey City Urby (200 Greene St, 213.5 m)
- **Material:** dark navy glass with light spandrel bands.
- **Colour:** sampled #17437c in the dark areas and #2f6196 in the bands, both dominated by a blue sky.
  Suggested glass #1f2c3d and bands #8c9aa8.
- **Shape:** a stack of about 8 boxes, each shifted and cantilevered to one side of the one below (Concrete
  Architectural Associates). On top is an open steel-lattice screen box, a crown of grey steel trusses.
- **Photos:** [Jersey_City_Urby_011.jpg](https://commons.wikimedia.org/wiki/File:Jersey_City_Urby_011.jpg),
  [Hudson_River_Park_td_(2019-10-28)_016_-_Jersey_City_Urby_(200_Greene_Street).jpg](https://commons.wikimedia.org/wiki/File:Hudson_River_Park_td_(2019-10-28)_016_-_Jersey_City_Urby_(200_Greene_Street).jpg)

### 101 Hudson Street (167 m)
- **Material:** a tan granite and precast grid with punched windows.
- **Colour:** sampled #ab9b82. Suggested #b8a88c.
- **Glass tint:** dark brown and bronze.
- **Shape:** the corners step back several times toward the top. The crenellated crown is a ring of pier-like
  pinnacles around the roof, and it is lit at night.
- **Photos:** [101_Hudson_Street_Jersey_City.JPG](https://commons.wikimedia.org/wiki/File:101_Hudson_Street_Jersey_City.JPG),
  [101_Hudson_St_fr_Montgomery_jeh.jpg](https://commons.wikimedia.org/wiki/File:101_Hudson_St_fr_Montgomery_jeh.jpg)

### Exchange Place Centre (10 Exchange Place, 157.1 m to the fin)
- **Material:** a reflective green glass curtain wall.
- **Colour:** sampled #7a9a90. Suggested #5f7f78.
- **Glass tint:** sea green.
- **Shape:** a stepped flat top at about 149.5 m, with a tall slanted glass fin like a sail on the NE corner
  rising to 157 m.
- **Photos:** [Exchange_Place_Center_Jersey_City.JPG](https://commons.wikimedia.org/wiki/File:Exchange_Place_Center_Jersey_City.JPG)

### Hoboken Terminal and clock tower (roof about 20 m, tower 68.6 m)
- **Material:** a steel frame clad in copper, now a dark bronze brown (sampled #5d5b5a under overcast;
  suggested #6e4f3d). Verdigris-green trim and cornices are estimated at #5e8f7c.
- **Details:** big arches over the ferry slips, and "LACKAWANNA" in tall letters on the roof above the slips.
- **Clock tower:** at the north end of the slips. It is a tall shaft of brown copper with white clock faces
  (12 ft across), a belfry and a steep pyramidal cap.
- **Photos:** [Hoboken_Terminal_(7081990289).jpg](https://commons.wikimedia.org/wiki/File:Hoboken_Terminal_(7081990289).jpg),
  [Erie-Lackawanna_Railroad_Terminal.jpg](https://commons.wikimedia.org/wiki/File:Erie-Lackawanna_Railroad_Terminal.jpg)

### Colgate Clock (Jersey City)
- **Shape:** an octagonal frame 15.2 m across on steel legs.
- **Colour:** frame black #2a2d33 (estimated; the sample is sky-tinted), face of white louvres #e8ecef, red
  hour markers #b0302a (estimated), and black hands with red edging.
- **Photos:** [Colgate_Clock_Jersey_City_001.jpg](https://commons.wikimedia.org/wiki/File:Colgate_Clock_Jersey_City_001.jpg),
  [Colgate_Clock_Jersey_City_from_Battery_Park_City.jpg](https://commons.wikimedia.org/wiki/File:Colgate_Clock_Jersey_City_from_Battery_Park_City.jpg)

### Wesley J. Howe Center, Stevens (about 52 m, on a bluff about 30 m high)
- **Material:** beige-grey precast concrete panels, sampled #a29f99.
- **Glass tint:** two full-height vertical strips of dark glass (#44484e) with black mullions on the long faces.
- **Shape:** a flat roof with a small bulkhead.
- **Photos:** [Stevens_Howe_Center.jpg](https://commons.wikimedia.org/wiki/File:Stevens_Howe_Center.jpg),
  [Stevens_Howe_Center_from_Distance.jpg](https://commons.wikimedia.org/wiki/File:Stevens_Howe_Center_from_Distance.jpg)

## (b) Camera presets for the Places menu

These use the same format as `[views.areas]` in `city.toml`. **Constraint:** the viewer clamps
`controls.maxPolarAngle` to 86°, so elevations below 4° will probably be raised to 4°. The low views below
therefore use elevation 4 with a small target height.

```toml
"Hoboken" = [-74.0300, 40.7430, 2200, 25, 110, 0]
"Jersey City waterfront (Exchange Place)" = [-74.0350, 40.7160, 1500, 6, 100, 60]
"Newport" = [-74.0335, 40.7270, 1600, 8, 80, 50]
"Grove Street" = [-74.0431, 40.7196, 450, 16, 250, 5]
"DUMBO (Washington Street)" = [-73.98944, 40.70512, 280, 4, 182, 8]
"Brooklyn Heights Promenade" = [-74.0026, 40.7010, 700, 4, 140, 0]
"Downtown Brooklyn" = [-73.9840, 40.6905, 2000, 14, 300, 60]
# optional
"Port Imperial" = [-74.0120, 40.7760, 1200, 12, 100, 20]
```

What each preset should show:
- **Hoboken:** an overview of the Mile Square City from over the Hudson, looking WNW. On the left (south) are
  Hoboken Terminal with its clock tower and the ferry slips. In the middle are the grid of 4 to 5 storey
  rowhouses, Washington St, Sinatra Drive and the waterfront parks. On the right (north) is Castle Point with
  Stevens and the Howe Center on the cliff. The Palisades and Union City rise behind.
- **Jersey City waterfront (Exchange Place):** from the river off Battery Park City, looking west at the full
  Exchange Place and Paulus Hook wall. You should see 99 Hudson, 30 Hudson (Goldman Sachs), 101 Hudson,
  Exchange Place Centre, Harborside, Sable/Urby, Haus25, Trump Plaza and Trump Bay Street. The Colgate Clock is
  in the foreground on the esplanade (left of centre), and Paulus Hook's low blocks are on the left.
- **Newport:** from mid-river looking west. You should see Newport Tower, the Newport Office Centers along
  Washington Blvd, and the residential slabs: Southampton, Atlantic, East Hampton, Riverside, Ellipse,
  Park and Shore, Aquablu and Bisby. Newport marina is in front, with Hoboken's south end and the terminal on the
  right.
- **Grove Street:** from the WSW, about 130 m up, looking ENE over the Grove Street PATH plaza and the Newark
  Ave pedestrian mall. City Hall and the brownstone blocks of Van Vorst and Hamilton Park are in front. The
  Downtown towers rise behind: 70 and 90 Columbus, 50 Columbus, The Hendrix, Trump Plaza and Sable/Urby.
- **DUMBO (Washington Street):** the postcard view from Washington St at Front St, looking about N (2°) up the
  cobbled street. The Manhattan Bridge viaduct and its Brooklyn tower close the view. The Empire State
  Building should show in the gap between the tower legs above the deck. The camera ends up about 27 m high;
  if the viewer allows lower elevations, use `[-73.98944, 40.70512, 280, 1, 182, 25]`.
- **Brooklyn Heights Promenade:** the camera sits over the Promenade at Pierrepont St, about 49 m up, looking
  NW (320°) across the East River. You should see the whole Lower Manhattan skyline: One WTC, 3 WTC, 70 Pine
  and the Financial District, with the Brooklyn Bridge on the right. Brooklyn Bridge Park piers, the BQE
  cantilever and Pier 1 / 1 Hotel are in the foreground at the bottom right.
- **Downtown Brooklyn:** from the NW over DUMBO and the river, looking SE at the cluster: The Brooklyn Tower,
  Brooklyn Point, City Point, AVA DoBro, 388 Bridge, the MetroTech office slabs, and the Borough Hall and
  Montague-Court area on the right. The Williamsburgh Savings Bank dome should be visible past the cluster
  toward Atlantic Terminal, with Fort Greene on the left.
- **Port Imperial:** the Weehawken waterfront from the river. You should see the ferry terminal, the
  RiversEdge and RiverParc blocks, the Palisades cliff and the Lincoln Tunnel helix to the south (left).

Coordinates checked:
- **DUMBO:** the camera lands at about 40.7026, -73.9896, over Washington St at Front St.
- **Promenade:** the camera lands at about 40.6962, -73.9973, over the Promenade at Pierrepont St.

## Tall buildings under construction or approved (not in the CSV)

- **Brooklyn:**
  - One Montague Place, 205 Montague St: 205 m, 47 floors, due 2029 (Brooklyn Heights).
  - 95 Rockwell Place: 188 m, due 2029 (Fort Greene).
  - 356 Fulton St: 164 m, due 2028.
  - Brooklyn Borough-Based Jail, 275 Atlantic Ave: 102.7 m, due 2029.
- **Jersey City:**
  - Harborside 8: 216 m.
  - Harborside 4: 209 m, due 2029.
  - 20 Long Slip: 160 m, due 2027 (Newport, on the Hoboken line).
  - 50 Hudson: 145 m.
  - Urby towers 2 and 3: approved, 206 m.
  - 560 and 580 Marin Blvd: approved.
- **Unidentified OSM building:** way/875618590 (BIN 3393804, 29 levels, h110, mirror glass) at about 40.6883,
  -73.9787 by Ashland Pl and Fulton St. It is not on the Wikipedia list and I could not name it.

## Sources
- **Wikipedia:**
  - [List of tallest buildings in Brooklyn](https://en.wikipedia.org/wiki/List_of_tallest_buildings_in_Brooklyn)
    and [List of tallest buildings in Jersey City](https://en.wikipedia.org/wiki/List_of_tallest_buildings_in_Jersey_City),
    whose heights come from CTBUH.
  - [List of tallest buildings in New Jersey](https://en.wikipedia.org/wiki/List_of_tallest_buildings_in_New_Jersey).
  - Individual building articles: Brooklyn Tower, Williamsburgh Savings Bank Tower, Hoboken Terminal,
    Colgate Clock, 99 Hudson Street and 30 Hudson Street.
- **CTBUH:** [The Brooklyn Tower](https://www.skyscrapercenter.com/building/the-brooklyn-tower/20684) and
  [Jersey City](https://www.skyscrapercenter.com/city/jersey-city).
- **Other web sources:**
  - [New York YIMBY on Dock 72](https://newyorkyimby.com/2018/05/the-brooklyn-navy-yards-dock-72-nears-completion.html).
  - [Brownstoner on the Pierhouse bulkhead](https://www.brownstoner.com/development/pierhouse-brooklyn-bridge-park-lawsuit-dismissed-bulkhead/).
  - [6sqft on the WELCOME sign](https://www.6sqft.com/watchtower-replacing-welcome-sign-unveiled-in-brooklyn-heights/).
  - [Stevens tour: Howe Center](https://tour.stevens.edu/#!BLD_2017092688966).
- **OSM:** Overpass (maps.mail.ru and overpass-api.de) and the OSM API, queried on 2026-09-28.
