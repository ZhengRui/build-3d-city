# Manhattan (New York City) — region preset research

Compiled 2026-09-28 for the build-3d-city engine (Shenzhen-derived). Units: metres unless noted
(1 ft = 0.3048 m). **(est.)** = my estimate or unsourced common knowledge; **(sampled)** = PIL colour
sampled from a Wikimedia Commons photo (method in §5.3); **(derived)** = computed from sourced numbers.

---

## 0. Headline preset values

| Key | Value |
|---|---|
| Driving side | **Right** (US; confirmed §9) |
| Centre line (two-way) | Double solid yellow, 2 × 4–6 in (0.10–0.15 m) lines, ~4–6 in gap |
| Lane line | White broken, **10 ft dash / 30 ft gap (3.05 / 9.14 m)**, 4–6 in wide; dotted extension 3 ft / 9 ft |
| Stop bar | White, 18–24 in (0.45–0.6 m) wide, ≥ 4 ft (1.2 m) before crosswalk |
| Crosswalk | White high-visibility bars ("zebra"/continental, some ladder), bars 0.6 m wide, gaps ~0.6–0.9 m, crosswalk 3–4.5 m wide (est.) |
| Bus lane | Red "terra cotta" paint, 11–12 ft (3.4–3.7 m), "BUS ONLY" in white |
| Bike lane | Green paint (full or at conflict points), protected path ~1.8 m + 0.9 m hatched buffer + parking (est.) |
| Travel lane | 10 ft (3.05 m) typical; 11–12 ft (3.35–3.65 m) for bus/truck lanes |
| Parking lane | 8 ft (2.45 m), both kerbs |
| Avenue | 100 ft (30.5 m) ROW → ~60–70 ft (18–21 m) roadway, 15–20 ft (4.5–6 m) sidewalks |
| Side street | 60 ft (18.3 m) ROW → ~30–34 ft (9–10 m) roadway, ~13–15 ft (4–4.5 m) sidewalks |
| Grid | Rotated ~29° clockwise from true north; ~20 N–S blocks per mile (≈ 80 m street spacing) |
| Speed limit | 25 mph (40 km/h) default; FDR 40 mph; Route 9A 30 mph (Battery–59th) |
| Sun, 2026-10-10 | Declination −6.82°, EoT +13.1 min, sunset 18:23 EDT, civil dusk end 18:51 EDT |
| 15:15 EDT on 2026-10-10 | = 14:32 local apparent solar time; sun altitude 31.0°, azimuth 225.5° (SW) |

---

## 1. Road markings and street geometry

### 1.1 Longitudinal markings (MUTCD, as applied in New York)
NYC DOT's Street Design Manual (SDM) says markings follow the federal MUTCD and NYC DOT's own
"Typical Pavement Markings" drawings (H-1003A/B). The drawings aren't online as text, so the numbers
below come from the NYS DOT standard sheet 685-01. It uses the same MUTCD patterns.

| Marking | Colour | Pattern / size | Source |
|---|---|---|---|
| Centre line, two-way street | Yellow | Double solid (normal line 4–6 in, gap ≈ line width) | MUTCD; NYSDOT 685-01 ("gap is the same width as lines") |
| Lane line (same direction) | White | Broken: **10 ft line / 30 ft gap**, 4–6 in (10–15 cm) wide | NYSDOT 685-01 (xBLL), MUTCD 3B |
| Dotted lane / extension line | White | **3 ft line / 9 ft gap** | NYSDOT 685-01 (xDLL/xDEL) |
| Edge line | Yellow on left, white on right | Solid, 4–6 in | NYSDOT 685-01 note 2 |
| One-way street left edge | Yellow if marked | Often omitted in Manhattan: parking lane on both kerbs (est.) | MUTCD / observation |
| Stop line | White | Solid, **18 in (or 24 in)**, at least 4 ft upstream of crosswalk | NYSDOT 685-01 |
| Wide lane lines (turn lanes, bus lanes) | White | 8–12 in solid or dotted | MUTCD (est. for NYC use) |

In Manhattan, city-street lane lines are usually the full 10/30 ft pattern. Dashes look shorter
mainly because they are worn or occluded. I found no evidence of a separate NYC short-dash standard.

### 1.2 Crosswalks and stop bars
- NYC DOT's current standard at signalised Manhattan intersections is the **high-visibility crosswalk**:
  longitudinal white bars parallel to traffic. Some are "ladder" crosswalks (bars between two
  transverse 12-in lines). Older crosswalks use only the two transverse lines. All crosswalk markings
  are white thermoplastic (SDM "Pavement Markings" page; NYSDOT 685-01 types S/L/LS: "ALL CROSSWALK
  MARKINGS SHALL BE WHITE", transverse lines 1'-0" typ.).
- MUTCD values for high-visibility bars: **12–24 in (0.3–0.6 m) wide, 12–60 in gaps**. The optimal
  layout is 24-in bars with 24-in gaps, placed so tyres run in the gaps. For NYC, use **bar 0.6 m,
  gap 0.6–0.75 m**, bar length = crosswalk width **3.0–4.5 m** (10 ft minimum; 15 ft common on
  avenues) (est.).
- Stop bar: 0.45–0.6 m white, placed about **1.2–2.4 m before the crosswalk** (NYSDOT ≥ 4 ft).
- Crosswalks sit at every corner of the grid, so a Manhattan block edge carries a crosswalk at both ends.

### 1.3 Bus lanes
- Colour: **red / "terra cotta"** epoxy or MMA. Manhattan's first red lane was on 57th St (2007 pilot).
  On 34th St, "the two curbside lanes [were] painted bright terra cotta" (NYC DOT 2008 press release,
  Urban Omnibus 2024). "BUS ONLY" is stencilled in white, repeated about every block (est.).
- Suggested hex: **#B0473A** (faded) to **#C0392B** (fresh) (est.).
- Width 11–12 ft (3.35–3.65 m) (SDM "Lanes"). Offset lanes run one lane in from the kerb, with parking
  or loading at the kerb. Kerbside lanes are used on 34th, 14th (busway), 23rd, 42nd, 57th, 125th,
  and 1st/2nd, 5th/Madison and 3rd/Lexington Avenues (est. list).

### 1.4 Bike lanes
- Green paint. On newer protected paths it runs the full length or is concentrated at intersection
  conflict zones and driveways. Hex **#3E8E5E** fresh to **#5B8C6A** worn (est.).
- Manhattan avenues with protected paths: **1st, 2nd, 5th (part), 6th, 7th, 8th, 9th, 10th (part),
  Broadway, Columbus, Amsterdam**, plus Hudson/Lafayette/Allen and crosstown 26th/29th/52nd/55th
  (NYC DOT 2014 PBL analysis, amNY 6th Ave, DOT 2018 crosstown release). Timeline: 9th Ave 2007
  (the first), 8th Ave 2008–10, 1st/2nd 2010, Columbus 2010/11, Broadway 2008+ (NYC DOT 2014
  "Protected Bicycle Lanes in NYC").
- Typical parking-protected cross-section on a one-way avenue, from the kerb out: sidewalk | **bike
  path 6 ft (1.8 m)** | **buffer 3 ft (0.9 m)** with white hatch and flexible posts or a concrete
  island at corners | **floating parking 8–10 ft (2.4–3.0 m)** | travel lanes (est., consistent with
  NYC DOT designs). Two-way paths are 8–12 ft (est.).
- The protected path sits on the **left kerb** of the one-way avenue, the driver's side: 1st Ave
  (northbound) west kerb, 2nd Ave (southbound) east kerb, 8th west, 9th east.

### 1.5 Lanes and widths
| Element | ft | m | Source |
|---|---|---|---|
| Travel lane | 10 | 3.05 | SDM "Lanes": "typical width for moving vehicles is 10 feet" |
| Bus/truck lane | 11–12 | 3.35–3.65 | SDM "Lanes" |
| Parking lane | 8 (min 6) | 2.45 | SDM "Lanes" |
| Avenue ROW | 100 | 30.5 | 1811 Commissioners' Plan; Baruch NYCdata |
| Major crosstown ROW (14th, 23rd, 34th, 42nd, 57th, 72nd, 79th, 86th, 96th, 110th, 116th, 125th...) | 100 | 30.5 | 1811 plan |
| Ordinary crosstown street ROW | 60 | 18.3 | 1811 plan |
| Lexington / Madison ROW | 75 / 75–80 | 22.9 / 23–24 | 1892 World Almanac (via stuffnobodycaresabout) |
| Broadway above 59th | 150 | 45.7 | same |
| Avenue roadway (kerb to kerb) | ~60–70 | 18–21 | derived: 100 − 2×(15–20) |
| Side-street roadway | ~30–34 | 9–10.4 | derived: 60 − 2×13–15; NYC DOT 1st Ave doc shows 30 ft cross-street roadway |
| Avenue sidewalk | 15–20 (5th Ave 30 historically) | 4.5–6 (9) | 1904 World Almanac: streets 100 ft+ → 22 ft; Madison 19; Lexington 18.5 |
| Side-street sidewalk | 13–15 | 4–4.5 | 1904 World Almanac: 60-ft streets → 15 ft sidewalks |
| Kerb height (reveal) | 7 in | 0.18 | NYC DOT standard details (7" curb reveal) |
| Street tree bed | 5 × 10 ft (4 × 10 ideal min) | 1.5 × 3.0 | NYC Parks Tree Planting Standards |

Typical cross-sections (est.):
- **One-way avenue (e.g. 2nd Ave, 70 ft roadway):** parking 8 | bike 6 + buffer 3 | parking 8 |
  3 × travel 10–11 | bus lane 11 | parking/loading 8.
- **One-way avenue without a bike path (e.g. Lexington, ~50 ft roadway):** parking 8 | 3 travel lanes
  at 10 | bus lane 11 | parking 8 (some are narrower).
- **Side street (30–34 ft):** parking 8 | travel 12–14 (one lane, or one lane plus a 5-ft painted bike
  lane) | parking 8.
- **Two-way major crosstown (e.g. 34th, 57th, 100 ft ROW):** 2 lanes each way plus kerbside bus or
  parking, double yellow centre, sometimes a painted median.

### 1.6 One-way pattern
- **Most avenues are one-way and alternate** (converted in the 1950s–60s; est. from common
  knowledge):

  | Direction | Avenues |
  |---|---|
  | Northbound | 1st, 3rd, Madison, 6th, 8th, 10th/Amsterdam |
  | Southbound | 2nd, Lexington, 5th, 7th, Broadway (below Columbus Circle), 9th/Columbus |
  | Two-way | **Park, York, 11th/West End, Central Park West, Broadway north of 59th, Lenox/Malcolm X, Adam Clayton Powell and Frederick Douglass Blvds (north of 110th), St Nicholas, Riverside Dr, Bowery** |

- Protected bike paths sit on the **left** kerb of the one-way avenue: 1st Ave west side, 2nd Ave
  east side, 8th west, 9th east.
- **Crosstown streets are one-way and alternate: even-numbered go east, odd-numbered go west**
  (general rule with exceptions, e.g. 1st–14th downtown are irregular) (est.).
- **The 100-ft major crosstowns are two-way**, and so are Houston, Canal and Delancey.
- **Parking or loading on both kerbs** is the default for side streets and most avenues. Midtown kerbs
  are dominated by commercial loading, taxi drop-off, "No Standing" zones and hydrants, and there is
  no parking within 20 ft of crosswalks (NYSDOT 685-01, "20'-0" from crosswalk no parking") (est. for
  occupancy: 70–90 % of legal kerb length occupied by day).

### 1.7 Grid geometry (useful for procedural placement)
- The 1811 grid runs about **29° east of true north** (streets "run east–west" on the Manhattan grid).
- Street spacing N–S is about 200 ft of block plus a 60-ft street, **≈ 80 m pitch**, "20 blocks = 1
  mile" (block lengths 181–206 ft per 1892 Almanac data).
- Avenue spacing E–W is 600–920 ft (180–280 m) (est.; common knowledge).

---

## 2. Vehicles

### 2.1 Traffic mix (Manhattan CBD, daytime)
- Schaller (2017, *Empty Seats, Full Streets*): taxis and TNC ride-hail "comprise **50 percent to as
  much as 75 percent** of all traffic in the CBD, depending on time of day", and "50 percent or more"
  of vehicles crossing the 60th St cordon.
- The TLC's roughly 30 % "FHV share of all traffic in Midtown" comes from the NYC DCAS FHV emissions
  report.
- Yellow taxis: **13,587 medallions** by law (TLC). **About 10,400 active** in 2025, with 3,196
  medallions in storage. About 9,900 are active in the Congestion Relief Zone as of Aug 2025, and
  more than 50 % of the active fleet is wheelchair-accessible (WAV) (TLC/MMR 2025 via web search).
- FHVs: about 80,000+ app-based vehicles citywide, mostly black/grey/white Toyota Camry, Highlander,
  RAV4, Sienna, Honda Accord/Odyssey, Tesla Model Y and Nissan Rogue, plus black Suburban/Tahoe/
  Escalade "black cars" (TLC Medium post via search). The Camry is about 15 % of all TLC-licensed
  vehicles and 75 % of the top-ten models.

**Suggested spawn mix for a Midtown/Downtown avenue at daytime (est.):**

| Class | Share | Notes |
|---|---|---|
| Yellow taxi | **22 %** | In the 1990s–2010s this was 35–45 %. Now lower because ride-hail took over |
| Ride-hail/black car (sedan/SUV, mostly black/grey/white) | 25 % | TLC plates visible |
| Private car/SUV | 25 % | NJ/NY/CT plates |
| Delivery van (Sprinter/Transit/Promaster, Amazon, UPS, FedEx) | 12 % | double-parked often |
| Box/straight truck (16–26 ft) | 7 % | |
| Pickup/utility/construction | 3 % | |
| MTA bus (local, SBS, express coach) | 4 % | more on bus-lane avenues |
| Other (NYPD, FDNY, Con Ed, sanitation) | 2 % | |

Uptown residential streets have more private cars (~45 %) and fewer taxis (~8 %) (est.).

### 2.2 Yellow taxi
- Colour: "taxi yellow", **DuPont M6284** or equivalent (TLC Rules ch. 67; TLC tweet). Commonly cited
  hex **#F7B731** (crispedge). My suggested render value is **#F4B928** (est.). Use a slight
  orange-yellow, not lemon.
- Livery: "NYC TAXI" logo on the front doors, black-and-white checker stripe on the rear fenders,
  medallion number on the rear quarter, and a roof light-box (LED ad-topper on many) (Wikipedia
  "Taxis of NYC").
- Fleet models, 2025 (est. shares): **Toyota Camry Hybrid ~35 %, Toyota RAV4 Hybrid ~15 %, Toyota
  Sienna/Chrysler Pacifica/Voyager/Ford Transit Connect WAV minivans ~35 %** (the WAV majority),
  **Nissan NV200 "Taxi of Tomorrow" ~5 % and declining**, Ford Escape Hybrid (legacy), Tesla Model Y
  (Gravity fleet) and Toyota Highlander ~10 %. Sources: TLC Medium (Camry dominance), Wikipedia,
  Jalopnik. Shares are est.

### 2.3 MTA buses
| Model | L × W × H (m) | Notes | Source |
|---|---|---|---|
| New Flyer Xcelsior XD40 / XE40 | 12.5 × 2.59 × 3.20 (3.38 hybrid/BEB) | ~630 XD40 plus 247 XE40 on order | Wikipedia (New Flyer Xcelsior; MTA fleet) |
| New Flyer Xcelsior XD60 / XE60 (articulated) | 18.5 × 2.59 × 3.20 (3.38) | ~420 XD60; many on SBS | same |
| Nova Bus LFS / LFS Artic | 12.2 × 2.59 × 3.1 / 18.6 × 2.59 × 3.1 (est.) | ~1,000 in total | same |
| MCI D4500 / Prevost X3-45 express coach | 13.7 × 2.6 × 3.5 (est.) | ~600 Prevost and MCI units run to Midtown | same |

Liveries:
- **Legacy livery:** white body, a single **blue stripe** along the side and black window band. It was
  used from the late 1970s until 2016.
- **SBS livery:** white with a **light blue** (≈ #5AB4E5, est.) and white wrap below the windows and
  "+selectbusservice" branding. Many SBS buses carry a flashing blue headsign light pair (est.).
- **Current livery (since May 2016, "Cuomo/Excelsior"):** mostly **navy/MTA blue** (≈ #0039A6, est.)
  front and sides, a light-blue and **yellow** (≈ #FCCC0A, est.) swoosh, and a yellow rear.

### 2.4 Car colours (US, new-vehicle share)
Axalta 2025 report, US: **white 29 %, black 23 %, grey 22 %, silver 7 %, blue 6 %**. North America
overall: white 31 %, blue 10 %, red 7 %.

Suggested fleet palette for private cars and ride-hail (est.):

| Colour | Share | Hex |
|---|---|---|
| White | 26 % | #EDEDEA |
| Black | 24 % | #141517 |
| Grey | 20 % | #6B6E72 |
| Silver | 10 % | #B5B8BB |
| Blue | 8 % | #1F3C66 |
| Red | 6 % | #8C1C1C |
| Other (green, brown, beige, orange) | 6 % | — |

Ride-hail should skew black and grey. The NYC ride-hail fleet is about 40 % black (est.).

### 2.5 Dimensions (L × W × H, m; manufacturer figures from memory, rounded)
| Type | Representative | L × W × H |
|---|---|---|
| Sedan | Toyota Camry | 4.92 × 1.84 × 1.44 |
| Compact SUV | Toyota RAV4 | 4.60 × 1.86 × 1.69 |
| Mid SUV | Toyota Highlander | 4.95 × 1.93 × 1.73 |
| Full-size SUV (black car) | Chevrolet Suburban | 5.73 × 2.06 × 1.92 |
| Minivan / WAV taxi | Toyota Sienna | 5.18 × 1.99 × 1.78 |
| Taxi of Tomorrow | Nissan NV200 taxi | 4.73 × 1.73 × 1.87 |
| Pickup | Ford F-150 SuperCrew | 5.89 × 2.03 × 1.96 |
| Cargo van | Ford Transit 148" mid roof / Sprinter 170" | 5.98 × 2.06 × 2.53 / 7.37 × 2.02 × 2.75 |
| UPS package car | Morgan Olson P70/P80 | ~7.3 × 2.4 × 3.3 (est.) |
| Box truck | 16-ft body / 26-ft body | 7.6 × 2.4 × 3.5 / 10.4 × 2.6 × 4.0 (est.) |
| City bus | New Flyer XD40 | 12.5 × 2.59 × 3.2 |
| Articulated bus | New Flyer XD60 | 18.5 × 2.59 × 3.2 |
| Taxi (Camry hybrid) | as sedan plus roof sign | 4.92 × 1.84 × 1.44 + 0.30 sign |

Delivery colours (est.): **UPS "Pullman brown" #351C15 with gold #FFB500 logo**; **FedEx white body,
purple #4D148C and orange #FF6600 lettering**; **Amazon** white or grey vans with blue Prime smile
branding; **USPS** white with a blue eagle; **DSNY** sanitation trucks white; **Con Ed** blue-and-white.

### 2.6 Speed limits
- **25 mph (40 km/h) citywide default** since Nov 2014 (Vision Zero). Many streets have 20 mph slow
  zones, and Sammy's Law (2024) allows 20 mph on selected streets.
- **FDR Drive: 40 mph** (64 km/h) (search results, Flickr sign photo).
- **West Side Highway / Route 9A, Battery Place to 59th: 30 mph** (lowered from 35 in 2019; NYC DOT PR
  19-065). North of 72nd it becomes the Henry Hudson Parkway at 35–50 mph.
- Harlem River Drive: 40 mph (est.).
- Realistic Midtown average travel speed is only **~7–9 mph (11–15 km/h)** (Schaller: CBD speeds down
  23 % since 2010) (est. value).

---

## 3. Street trees and parks

### 3.1 Manhattan street tree species (2015 Street Tree Census, Manhattan only)
I computed these myself from the census as republished on GBIF (dataset d1e9202b…, filtered to GADM
New York County USA.33.32_1, n = 62,569 live trees; the census reports ~65,400 for Manhattan).
Honeylocust only matched at family level in GBIF, so I counted it as Fabaceae minus its named genera.

| # | Species | Share | Count |
|---|---|---|---|
| 1 | **Honeylocust** (*Gleditsia triacanthos* var. *inermis*) | **21.1 %** | 13,195 |
| 2 | **Callery pear** (*Pyrus calleryana*) | **11.7 %** | 7,316 |
| 3 | **Ginkgo** | **9.4 %** | 5,863 |
| 4 | **Pin oak** (*Quercus palustris*) | **7.4 %** | 4,602 |
| 5 | **Japanese pagoda tree** (*Styphnolobium japonicum*) | **7.1 %** | 4,455 |
| 6 | **London planetree** (*Platanus × acerifolia*) | **6.6 %** | 4,141 |
| 7 | **Japanese zelkova** | **5.8 %** | 3,606 |
| 8 | **Little-leaf linden** (*Tilia cordata*) | **5.3 %** | 3,330 |
| 9 | American elm | 2.7 % | 1,698 |
| 10 | American linden | 2.5 % | 1,584 |
| 11 | Northern red oak | 1.8 % | 1,138 |
| 12 | Willow oak | 1.4 % | 889 |
| 13 | Chinese elm | 1.3 % | 785 |
| 14 | Green ash | 1.2 % | 770 |
| 15 | Swamp white oak | 1.1 % | 690 |
| – | Silver linden 0.9 %, goldenrain 0.6 %, red maple 0.6 %, sawtooth oak 0.6 %, Kentucky coffeetree 0.6 %, Norway maple 0.5 %, other | ~9 % | |

This agrees with NYC Parks ("almost 1 in 5 Manhattan street trees are honeylocusts"). Citywide the
order differs: London planetree 13 %, then honeylocust and Callery pear.

Genus totals in Manhattan: oaks 14.0 %, pear 11.7 %, ginkgo 9.4 %, lindens 8.7 %, pagoda 7.1 %,
plane 6.6 %, zelkova 5.8 %, elms 4.2 %, cherry (*Prunus*) 1.9 %, maples 1.5 %.

### 3.2 Size, form and spacing
Size by species (heights and crowns est. from DBH plus species norms):

| Species | Typical Manhattan height | Crown | Form / notes |
|---|---|---|---|
| Honeylocust | 9–15 m | 7–10 m | Open, airy, fine pinnate leaves; light dappled shade |
| Callery pear | 7–11 m | 5–8 m | Dense oval/pyramidal; white bloom in April |
| Ginkgo | 8–15 m | 4–7 m (young ones columnar) | Fan leaves |
| Pin oak | 12–20 m | 8–12 m | Pyramidal, drooping lower branches |
| Japanese pagoda | 9–14 m | 8–12 m | Rounded |
| London planetree | 15–25 m | 12–18 m | Mottled bark; the big old trees on wide avenues and in parks |
| Zelkova | 10–16 m | 8–12 m | Vase shape |
| Little-leaf linden | 10–14 m | 6–9 m | Dense oval |

- DBH: see §3.5. Most Manhattan street trees are young to mid-age (median DBH ≈ 8–12 in /
  20–30 cm), so typical rendered height is **8–12 m**. Trees sit **below the 4th–5th floor**.
- **Spacing:** NYC Parks minimum trunk to trunk is **20–30 ft (6–9 m)** depending on species.
  Real Manhattan blocks run ~25–35 ft (8–11 m) with gaps for driveways, hydrants, subway entrances,
  bus stops and vaults. Occupancy is ~74 % of planting sites citywide (census).
- Tree beds are 5 × 10 ft (1.5 × 3 m), often with low metal guards (~45 cm) (NYC Parks standards). Beds
  sit in the furnishing zone, about 0.45 m back from the kerb (SDM: 18 in clear of kerb).
- Midtown avenues between 34th and 59th are sparsely planted, especially 5th/6th/7th/Broadway
  (est.). Residential streets (UES/UWS/Village/Chelsea) are nearly continuously planted.

### 3.3 Central Park
- About **18,000 trees and 170 species** (Central Park Conservancy).
- American elms: about 1,200–1,800 (sources vary). The **Mall/Literary Walk** holds one of the largest
  surviving stands of mature American elm in North America, some over 90 ft (27 m) tall, forming a
  cathedral arch.
- The dominant species by count is **black cherry**, then American elm (search summary citing the
  Central Park inventory). Also common or signature: oaks (pin, red, black, bur, Turkey), London
  plane, red and sugar maple, sweetgum, black tupelo, hackberry, black locust, tulip tree, European
  beech and conifers (Norway spruce, eastern white pine) in the Ramble/North Woods (est.).
- Structure: open lawns (Sheep Meadow, Great Lawn), the Reservoir, and dense woodland in the Ramble
  and North Woods. Rock outcrops of grey Manhattan schist (#6E6A64, est.).

### 3.4 Early-October foliage
- Central Park peak colour is usually **early to mid November** (late October to early November
  range). In **early October the canopy is still ~90–95 % green** (est.).
- For an Oct 5–12 scene: overall green with slight yellowing and thinning.
  - **Honeylocusts** start turning yellow early and drop small leaflets, so give 10–20 % of them a
    yellow-green tint (#B8B04A).
  - **Ginkgo** stays green until late October/November.
  - **Callery pear** is green, turning purple-red in November.
  - **London plane** is olive green with some brown leaves.
  - Park **red maples** and **tupelos** may show early red, about 5 % of trees.
- Suggested foliage base colours (est.): honeylocust #7F9A3C (lighter, yellower), pear #3F5E2A,
  ginkgo #6C8B34, oaks #4A6130, plane #5B6E35, lindens #4F6B2F.

### 3.5 DBH sample (GBIF, first 600 Manhattan records per species)
These are the first 600 GBIF records per species (in record order, not a random sample). The
honeylocust sample is n = 852.

| Species | Median DBH | 90th pct DBH | Suggested render height (median / p90) (est.) |
|---|---|---|---|
| Honeylocust | 9 in (23 cm) | 14 in (36 cm) | 10 m / 14 m |
| Callery pear | 8 in (20 cm) | 14 in | 8 m / 11 m |
| Ginkgo | 8 in (20 cm) | 13 in | 9 m / 13 m |
| Pin oak | 8 in (20 cm) | 19 in | 10 m / 17 m |
| Japanese pagoda | 7 in (18 cm) | 16 in | 8 m / 13 m |
| London planetree | 13 in (33 cm) | 22 in | 14 m / 20 m |
| Zelkova | 6 in (15 cm) | 12 in | 7 m / 12 m |
| Little-leaf linden | 7 in (18 cm) | 12 in | 8 m / 11 m |
| American elm (street) | 10 in (25 cm) | 25 in | 11 m / 20 m |

In short, Manhattan street trees are young: a median trunk of about 20 cm and a height of about
8–10 m. Only about 10 % of them reach 13–20 m (London planes, old oaks and elms).

---

## 4. Rooftops

### 4.1 Wooden water tanks
- **Count: 10,000–17,000 citywide** (Untapped NY: 10,000–15,000; other sources up to 17,000). Most are
  in Manhattan on 6–20-storey pre-war residential and loft buildings (est. ~60 % of pre-war buildings
  over 6 storeys have one).
- **Size:** "Most tanks in New York City are around **12 ft (3.7 m) high and similar in diameter**"
  (Wikipedia). Capacity is **5,000 gal** (small) to **36,000 gal** (large towers); **10,000 gal** is
  the typical tank. Check: π·6²·12 ft³ ≈ 10,150 gal, so a 12 × 12 ft tank is consistent.

  | Class | Diameter | Staves height | Share | Hex |
  |---|---|---|---|---|
  | small | 3.0 m | 3.0 m | 30 % | |
  | typical | 3.7 m | 3.7 m | 50 % | |
  | large | 4.5–5 m | 4.5–6 m | 20 % | |

  Staves taper slightly (top about 5 % narrower) (est.).
- **Roof:** a shallow **conical cap**, 25–35° pitch, about 0.8–1.2 m high, with a small finial or
  vent and a hatch. It sometimes overhangs slightly (est.).
- **Hoops:** 6–12 steel hoops or rods, closer together near the bottom (higher pressure) (est.).
- **Support:** a steel dunnage frame of **4–6 steel legs 3–5 m high** (H-sections) on the bulkhead
  roof or the main roof. There is usually a steel grating platform at the tank base, a caged ladder
  and cross-bracing (est.).
- **Wood:** Western red cedar, yellow cedar or California redwood staves held by steel hoops, with no
  nails or glue. Tanks last 30–35 years. Builders are Rosenwach, Isseks Bros and American Pipe & Tank
  (Untapped NY; 6sqft).
- **Colours (sampled, Commons "Water Towers (135539585)", overcast Midtown):**

  | Part | Hex |
  |---|---|
  | Weathered tank body | **#5E5D62 to #686869** (silver-grey, slightly cool) |
  | New cedar roof or tank | **#D9BB9C** (tan) |
  | Steel legs | dark grey-black **#2A2A2C** (est.) |

  Use weathered grey-brown (#6B635A, est. blend) for most tanks, with about 15 % new tan-orange tanks
  (#B98A5E, est.).

### 4.2 Other rooftop clutter, by building type (est. shares)
| Building type | Water tank | Stair/elevator bulkhead | HVAC / cooling tower | Chimneys | Other |
|---|---|---|---|---|---|
| Brownstone/rowhouse | 0 % | 80 % small stair hatch/skylight | 30 % small condensers | **90 %**, 2–4 brick stacks on party walls | parapet + cornice; roof decks 20 % |
| Tenement (5–6 st) | 20 % | 90 % brick stair bulkhead (2.5 × 3 × 2.5 m) | 30 % window/split AC units on roof | 60 % | fire-escape gooseneck ladders to roof; satellite dishes 15 % |
| Pre-war apartment (9–20 st) | **70 %** | 100 % brick elevator/stair penthouse (6–10 m × 4–6 m × 3–4 m) | 20 % | 40 % (boiler flue) | set-back terraces with planters 30 % |
| Cast-iron loft | 50 % | 90 % | 40 % | 30 % | roof decks and penthouse additions 30 % |
| 1920s–30s setback office | 20 % (hidden) | 100 %, crown/mechanical penthouse | **80 %** cooling towers | – | setback terraces, some landscaped |
| Post-war glass office | 0 % | 100 % mechanical penthouse with louvred screen, 2 storeys | **100 %** cooling towers (screened) | – | window-washing davit rails, antennas |
| Modern glass condo | 0 % | 100 % screened mech | 90 % | – | amenity roof decks, pools 20 % |
| NYCHA tower | 10 % | 100 % brick elevator machine room | 20 % | 1 tall boiler stack per development | TV antennas, cell antennas 40 % |

- **Rooftop antennas and cell sites** are very common on tall residential buildings: panel antennas on
  bulkhead walls, 30–40 % (est.).
- **Green roofs:** only 736 citywide (~60 acres, 0.15 % of roof area), more than half of them in
  Manhattan (Treglia et al. 2022, *Ecology & Society*; TNC). Treat as rare: about 1 % of Manhattan
  roofs, mainly on new towers, institutions and some setback terraces.
- **Setback terrace planters:** common on pre-war and post-1916-zoning buildings, 25–40 % of setbacks
  carry boxwood, arborvitae or small trees in planters (est.).

### 4.3 Roof surface colour
- Traditional NYC roofs are **black tar, asphalt or modified bitumen**.
- Reflective coatings cover **at least 36 % of NYC roofs** (Heris et al., cited by Healthbeat 2025,
  from the NYC CoolRoofs/HOPE program), out of 1.6 billion sq ft of rooftop.

Suggested Manhattan mix (est.):

| Surface | Share | Hex |
|---|---|---|
| Silver aluminium-coated | 25 % | #A9ABAA |
| White elastomeric / TPO | 20 % | #D8D8D2, weathered #C2C1BA |
| Black/dark-grey bitumen or EPDM | 35 % | #2E2E2E to #444343 |
| Grey gravel ballast | 10 % | #8A8781 |
| Pavers / wood decks | 7 % | #9C8F7E |
| Green | 1 % | #5C7A3A |
| Glass / other | 2 % | |

Brownstone and tenement roofs are mostly silver-coated (est.).

---

## 5. Facades by building type

### 5.1 Types
**Brownstone / rowhouse** (UWS, UES, Harlem, Village, Chelsea; 1850s–1900s)
- 4 storeys plus a raised basement (occasionally 5), about 15–19 m to the cornice.
- 16–25 ft wide lots; **20 ft (6.1 m) is standard**, 40–45 ft deep.
- Heights:

  | Level | Floor-to-floor |
  |---|---|
  | Basement (garden) | 7.5–8 ft ceiling (≈ 2.8 m) |
  | Parlour floor | 10–12 ft+ ceiling (≈ 3.9–4.2 m) |
  | Upper floors | 3.3–3.6 m |

- **Stoop** of 12–16 steps up about 1.8–2.4 m to the parlour door, with cast-iron railings.
- **Bays:** 3 windows per 20-ft front, **bay module ≈ 2.0 m**. Windows are about 1.1 m wide and
  2.0–2.4 m tall on the parlour floor.
- Bracketed wood or pressed-metal **cornice** about 0.6–1.0 m deep, painted dark brown or black.

**Tenement** (LES, East Village, Chinatown, Hell's Kitchen, Harlem; 1870s–1920s)
- 5–6 storeys (the 1879 law capped them at 6).
- **25 × 100 ft lot**, 4 windows across the front, so the **bay module ≈ 1.9 m**.
- Floor-to-floor **3.0–3.3 m** (est.). Ground-floor shops are 3.8–4.5 m.
- Black steel **fire escapes** cover the central 2–4 bays on every floor, with balconies about
  0.9–1.2 m deep, drop ladders and a gooseneck to the roof.
- Pressed-metal **cornice** about 0.6–0.9 m, plus stone lintels and sills.

**Pre-war apartment building** (UWS/UES, Riverside, West End, Washington Heights; 1900s–1930s)
- 9–16 storeys (up to ~20 on Central Park West and 5th Ave). Floor-to-floor **3.1–3.4 m**
  (ceilings 9–10 ft), with a double-height base.
- **Limestone or rusticated base** of 1–3 storeys, and brick above: buff, tan, red or brown.
- Windows are regular, about 1.1–1.3 m wide on a **bay module of 1.8–2.4 m**, often grouped in pairs
  and triples.
- Stone string courses and a cornice or parapet at the top, often with a water tank.

**Cast-iron loft** (SoHo, Tribeca, NoHo, lower Broadway; 1850s–1880s)
- 5–7 storeys. Ground floor **4.5–5.5 m**; upper floors **4.0–4.5 m** (12–14 ft ceilings plus
  structure) (SoHo broker sources).
- Rhythm of Corinthian columns and piers. **Bays 2.8–3.5 m**, each with a large sash window about
  1.5–1.8 m wide and 2.6–3.2 m tall, and arched heads common.
- Painted white, cream, grey or occasionally pale green, blue or ochre (see colours).
- Loading docks (raised concrete, ~1 m) with steel canopies in Tribeca/SoHo. Vault-light sidewalk
  edges.

**1920s–30s setback office / Art Deco** (Midtown, FiDi)
- Shape follows the 1916 zoning "wedding cake": base 10–20 storeys, then setbacks, then a tower.
- Floor-to-floor **3.6–4.0 m** (derived: Empire State Building 1,250 ft / 102 floors ≈ 12.3 ft =
  3.74 m).
- Materials: **limestone** (base), **buff/tan brick** (bulk), terra cotta and setback piers.
- Windows are 1.2–1.5 m wide in vertical strips with recessed dark spandrels. Pier module
  **1.5–1.8 m** (est.).

**Post-war International Style glass box** (Park Ave, 6th Ave "Rockefeller Center XYZ", 3rd Ave)
- 20–50 storeys. Floor-to-floor **3.7–4.1 m**. Seagram: 515 ft / 38 floors ≈ 13.5 ft; a 4.1 m
  average including the lobby (derived).
- **Mullion module 1.5 m (5 ft)**: Seagram about 4'7½" (1.41 m) (est.), Lever House 1.37–1.52 m (est.).
- Colours: bronze/dark (Seagram), blue-green glass (Lever), light grey-green glass with aluminium
  (typical 1960s), or black glass and aluminium.
- Plazas at the base (1961 zoning bonus).

**NYCHA tower-in-the-park** (LES/East River: Riis, Wald, Baruch, Smith, Jefferson, Wagner, Drew
Hamilton; 1940s–60s)
- 6–21 storeys; the typical Manhattan slab or tower is **13–16 storeys**. Floor-to-floor **2.6–2.8 m**
  (8-ft ceilings) (est.).
- Plans: **cruciform/X, T or double-cruciform**, set diagonally on superblocks with lawns, benches and
  London plane trees.
- Materials: **red-orange or red-brown brick**, punched windows about 1.2 m wide (ribbon-less), and
  a modest brick parapet.
- Recent rooftop additions include solar or cell antennas.

**Modern glass condo / office towers** (Hudson Yards, Billionaires' Row, FiDi, Chelsea; 2000s–now)
- Residential floor-to-floor **3.2–3.8 m** (supertalls 4–4.5 m). Office **4.1–4.6 m**; One Manhattan
  West slab-to-slab is 13.5 ft (Wikipedia).
- **Curtain-wall module 1.5 m** (office) or 1.5–3.0 m (residential, floor-to-ceiling glass).
- Glass colours: high-performance low-e glass in light grey-blue, silver or pale green. Terracotta or
  stone fins on some (e.g. 220 CPS limestone, 53W53 concrete) (est.).

### 5.2 Summary table
| Type | Storeys | Floor-to-floor (m) | Bay module (m) | Wall colour hex |
|---|---|---|---|---|
| Brownstone | 4–5 (+ basement) | 2.8 (basement) / 4.0 (parlour) / 3.4 | 2.0 | **#7C5149** sunlit stoop, **#93706C** facade in shade (sampled Harlem); render albedo #7A5446 |
| Limestone / whitestone rowhouse | 4–5 | as brownstone | 2.0 | **#C1BEC1** (sampled W 96th St, overcast); warm limestone #CFC6B4 (est.) |
| Tenement, red brick | 5–6 | 3.1–3.3 (shop 4.2) | 1.9 | **#C97C68** (sampled, 97 Orchard St, sunlit); mean red brick #7F5F52 (sampled, shaded Midtown); buff #C7B08A (est.), brown #6E4A3A (est.) |
| Pre-war apartment | 9–20 | 3.2–3.4 (base 4.5–6) | 1.8–2.4 | brick tan/buff #B89A78 (est.), red-brown #8C5A48 (est.), limestone base #CFC6B4 (est.) |
| Cast-iron loft | 5–7 | 4.2–4.5 (ground 5.0) | 2.8–3.5 | **#F0EEE3** cream-white (sampled, 102 Greene sunlit); **#A5A29A** grey-stone paint (sampled 132-140 Greene); shade pixels #4F453A |
| 1920s–30s setback office | 20–80 | 3.7–4.0 | 1.5–1.8 | limestone #CBC2AE (est.), buff brick #BFA27E (est.), Chanin brown brick in shade #4B4B48 (sampled, backlit, unreliable) |
| Post-war glass box | 20–50 | 3.8–4.1 | 1.4–1.5 | glass **#1C323E** dominant / **#425C67** median (sampled Park Ave tower, overcast); aluminium #A8ACAE; Seagram bronze #4A3A2A (est.) |
| NYCHA | 13–21 | 2.7 | 1.2–1.5 (window) / 3–3.5 (structural) | red-brown brick #8A4B3A (est.). Photo sample (Riis Houses, hazy backlit) gave #4C524D, not usable |
| Modern glass | 30–90 | 3.3–4.5 | 1.5 | #6F8796 blue-grey glass (est.), #9FB0B8 reflective silver (est.) |

Cornices and trim (est.): black or dark brown (#2B2521) on brownstones and tenements; galvanised
pressed-metal cornices painted cream (#D8D0BE) or dark green. Fire escapes are black (#1D1D1D).
Window frames: black or white on tenements, bronze or black aluminium on newer buildings.

### 5.3 Colour sampling method
- Commons 960 px thumbnails, downloaded with a polite User-Agent and rate-limited.
- A rectangular region was chosen by viewing each photo with a 10 × 10 grid. For each region I report
  the mean, the median and the largest k-means (k = 3) cluster ("dominant").
- Photos used:
  - Water towers: "Water Towers (135539585).jpeg"
  - Rowhouses: "34-42 West 96th Street.jpg"
  - Cast iron: "132-140 Greene Street.jpg", "102 Greene Street.jpg"
  - Brownstones: "Harlem, New York brownstones.jpg", "Lenox 123 rowhouses jeh.jpg"
  - Tenement: "97 Orchard Street Front.jpg"
  - NYCHA: "FDR Drive td (2019-06-02) 04 - Riis Houses.jpg"
  - Art Deco: "Chanin Building.jpg"
  - Glass: "Park Av Nov 2025 02.jpg"
  - Rivers: "View from the East River Esplanade 029.jpg", "Lower Manhattan-East River.jpg",
    "Hudson River Park td (2019-04-24) 046 - Pier 45.jpg"
- Values are camera-exposure dependent, so treat them as sRGB albedo **hints**. Sunlit samples read
  brighter than true albedo; shaded ones read darker.

---

## 6. Night

- **Street lights:**
  - NYC converted its **~250,000 street lights to LED** under a 2013 plan, completed in about
    2017–2019. By 2017 about 72 % were done: Brooklyn and Queens first, then Manhattan, the Bronx and
    Staten Island (Bloomberg/amNY).
  - The first batches were **~4,000 K** cobra-heads. After complaints DOT dropped the wattage from 78
    to 64 W. Council bill Int. 0822-2015 sought a 3,000 K cap (Gothamist, Sierra Club).
  - For Manhattan today, render **neutral-white 4,000 K (#FFE9D2-ish, est.)** for most cobra-head
    fixtures. Add some **3,000 K** decorative "Bishop's Crook" and "Flatbush" poles in parks and
    historic districts (#FFD9A8, est.).
  - A few remaining **HPS** fixtures (2,000 K, #FFB35C) remain on highways and bridges, and on some
    FDR/HHP ramps (<5 %, est.).
  - Pole spacing is about 25–35 m, alternating on avenues. Mounting height is 9–10 m on avenues and
    about 7.5 m on side streets (est.).
- **Times Square** (43rd–50th Streets on 7th Ave/Broadway, Special Times Square signage district,
  ZR 81-732):
  - Signs are **required**: at least 50 sq ft of sign per linear foot of frontage, up to 12,000 sq ft
    per lot.
  - Brightness is measured in LUTS: ≥ 1.5 LUTS for exposed-lamp signs, ≥ 0.4 LUTS for backlit ones.
  - Signs must be lit **dusk to at least 1:00 a.m.** daily and are 10–120 ft above the kerb.
  - LED screens run at thousands of nits. One unverified source claims 5,000 nits by day and 500
    nits at night.
  - For rendering (est.):
    - Emissive screens with luminance roughly **10–30× typical facade light**. Bloom is essential.
    - Palette: saturated brand colours (Coca-Cola red, Samsung blue, white video, magenta and green
      bursts), with frequent **white-dominant** video frames.
    - The average hue mix is roughly neutral-warm. Street level is lit to near-daylight (plaza
      illuminance ~500–1,000 lux, est.).
- **Office lights (Midtown, est.):**

  | Time | Floors lit |
  |---|---|
  | 07:00–19:00 | 80–95 % |
  | 19:00–22:00 | ~50 % (cleaners move floor by floor) |
  | 22:00–01:00 | 20–30 % |
  | overnight | 10–15 % (security, trading floors, always-on lobbies) |

  - Crowns and spires are floodlit from dusk until about midnight to 2 a.m.
  - **Bird-migration "Lights Out"** (NYC Audubon, voluntary; mid-Aug to mid-Nov, **midnight to
    dawn**) covers early October, so some towers switch their crowns off after midnight.
- **Empire State Building:**
  - LED system installed in 2012 (Philips Color Kinetics), **16 million colours**. Tower lights run
    **sunset to 2 a.m.**
  - The default is **white**. Colours are frequent for events, e.g. orange/pink for October causes,
    red-white-blue for holidays, sometimes animated shows.
  - Light is aimed at the 72nd–103rd floor setbacks, the mast and the spire (ESB tower-lights page).
- **Chrysler Building crown:** white/cool fluorescent-like triangular chevrons (#E8F0FF, est.).
- **One World Trade:** white spire, with the base and podium glass washed white (est.).

---

## 7. Sun and date

Location: **40.7128° N, 74.0060° W** (City Hall), time zone **EDT (UTC−4)** in October. DST ends
2026-11-01. Computed with the NOAA/Meeus solar algorithm (my script `sun.py`; refraction −0.833° for
sunrise/sunset).

| Date (2026) | Declination | Equation of time | Solar noon (EDT) | Sunrise (EDT) | Sunset (EDT) | Civil twilight ends | Sunset in local apparent solar time |
|---|---|---|---|---|---|---|---|
| Oct 5 | −4.91° | +11.6 min | 12:44:23 | 06:56:43 | **18:31:24** | 18:58:42 | 17:47 |
| Oct 8 | −6.06° | +12.5 min | 12:43:31 | 06:59:50 | **18:26:33** | 18:53:55 | 17:43 |
| **Oct 10** | **−6.82°** | **+13.06 min** | **12:42:58** | **07:01:56** | **18:23:22** | **18:50:46** | **17:40:28** |
| Oct 12 | −7.57° | +13.6 min | 12:42:27 | 07:04:03 | **18:20:14** | 18:47:41 | 17:37:51 |

For 2026-10-10:
- Nautical twilight ends at 19:22 EDT.
- **15:15 EDT is 19:15 UTC.** Local mean time is UTC − 4 h 56 min 01.4 s (74.006°·4 min) = **14:18:59
  LMT**. Adding the equation of time (+13.06 min) gives **14:32:04 local apparent solar time**.
- The hour angle is +38.0°, so the **sun's altitude is 31.0° and azimuth 225.5°** (SW, bearing from
  true north).
- Relative to the Manhattan grid (rotated 29° east of north), that azimuth is about 196.5° in "grid
  south" terms. The sun then sits nearly down the avenues from grid-south, so **avenue canyons get
  sun and cross streets are in shadow** (derived).
- Day length on Oct 10 is about 11 h 21 min.
- The sun sets at azimuth ~ 262° (WSW), close to the New Jersey Palisades (est.; the grid-aligned
  "Manhattanhenge" sunset is late May / mid-July, so there is no alignment in October).

Caveat: numbers are ±1 min against USNO or timeanddate (timeanddate returned 403, so I couldn't
cross-check). Sunset on Oct 10 at about 6:23 PM matches common NYC almanac values.

---

## 8. Water and waterfront

- **Water colour:**
  - The Hudson is turbid (tidal resuspension of mud and silt) and is usually described as "murky
    green". It turns browner after storms, carrying reddish Catskills clay (Hudson River Park,
    Gothamist, NYSDEC).
  - Samples:

    | Condition | Sample hex | Scene |
    |---|---|---|
    | Sunny, blue sky reflected | **#5A789A** | East River at Roosevelt Island |
    | Sunny, low sun glare | **#879CAE** | Hudson at Pier 45 |
    | Overcast | **#898E8B** | East River below Brooklyn Bridge |

  - Suggested water body (the non-reflective base, est.):

    | Condition | Hex |
    |---|---|
    | Normal, deep | **#3E4A44** (murky green-grey) |
    | Normal, shallow/turbid | **#4F5A4E** |
    | After rain | **#5C5646** (brown-grey) |

  - Reflection dominates at grazing angles. Keep Fresnel strong, since in photos the sky reflection
    decides the look.
- **Surface:** ferry, NY Waterway and NYC Ferry wakes plus tidal currents of 2–4 kn in the East River.
  The East River is a tidal strait with visible eddies, choppier than the Hudson. Wind chop is
  0.1–0.4 m on typical October days (est.).
- **Tides:** The Battery (NOAA 8518750) **mean range 4.5 ft (1.37 m)**, **great diurnal range
  5.06 ft (1.54 m)**, semidiurnal. For a static scene put the water plane about 0.7 m below mean
  higher high water. Bulkhead caps sit about 1.5–2 m above MLW (est.).
- **Wind in October** (my analysis of LaGuardia ASOS, Oct 2015–2024, n = 6,602 hourly observations):
  - Mean 8.9 kt (4.6 m/s), calm 5 %.
  - The direction is **bimodal**: NE 16.9 %, NW 15.9 %, S 15.1 %, SW 13.3 %, N 12.6 %, W 10.6 %.
  - In the afternoon (13–18 h local) the leader is **S 20 %** (sea breeze), then NE 18 % and NW 17 %,
    at a mean of 10.4 kt.
  - For a fair-weather October afternoon, use **wind from the S–SW at ~4–6 m/s**. For a
    crisp-after-cold-front day, use **NW at 6–8 m/s**. (Commonly cited "prevailing NW" is the annual
    or winter signal.)
- **Waterfront edge types:**

  | Edge | Where | Description |
  |---|---|---|
  | Granite bulkhead / seawall | Battery to W 59th (Hudson River Park) | A continuous historic structure with **6-ft granite capstones**; most of it is buried. Pile-supported **relieving platforms** sit behind it (Hudson River Park Trust). The esplanade on top is **granite and bluestone pavers** with steel pipe railings (~1.1 m) (RGR Landscape). Piers (45, 46, 51, 57, 62–64, etc.) are pile-supported concrete decks with lawns and sheds. Riprap at the bulkhead toe is limited |
  | Battery Park City esplanade | West side, on 1970s–80s landfill | A granite-faced bulkhead with ornate black cast-iron-style railings and lamp posts, a wide paved promenade with plantings, and a relieving platform on piles at the edge (est.) |
  | East River Esplanade | East side | A narrow (4–8 m) concrete and asphalt esplanade on a **pile-supported relieving platform** squeezed between the FDR Drive and the river, with steel railings. Sections are deteriorating, and parts run beneath the FDR (Sutton, 60s) (est.). Downtown: East River Waterfront Esplanade under the FDR viaduct (Pier 15, Pier 17 pavilions). Lower East Side: East River Park is being raised by ~2.4–2.7 m under the ESCR flood project (2021–26), with new bulkheads (est.) |
  | Riprap / natural-ish | Inwood Hill Park, Harlem River Park, Swindler Cove, Riverside Park north of 72nd | Stone revetments, with some riprap by the Henry Hudson Parkway (est.) |

  Share of Manhattan edge (est.): bulkhead/seawall ~60 %, pile-supported platforms and piers ~25 %,
  riprap and naturalised ~15 %.

---

## 9. Driving side
**Right-hand traffic** (US). Left-hand-drive vehicles; overtaking on the left. Parking on both kerbs
of one-way streets. NYC has **no right turn on red** unless signed (a unique NYC rule). There are
double yellow centre lines on two-way streets. Buses and taxis load at the right kerb. Protected bike
lanes on one-way avenues are often on the **left** kerb.

---

## Sources
- MUTCD Ch. 3B/3C (FHWA; up.codes mirror): lane/crosswalk marking dimensions.
- NYSDOT Standard Sheet 685-01 (2013), pavement markings: 10/30 broken, 3/9 dotted, stop line 18/24 in, crosswalk types S/L/LS. https://www.dot.ny.gov/main/business-center/engineering/cadd-info/drawings/standard-sheets-us-repository/685-01_050213.pdf
- NYC Street Design Manual (nycstreetdesign.info): Lanes, Full Sidewalk, Pavement Markings, Crosswalks pages.
- NYC Parks Tree Planting Standards: 5 × 10 ft beds, 20–30 ft spacing.
- NYC DOT, "Protected Bicycle Lanes in NYC" (2014) and "1st Ave Protected Bicycle Lane" (2016).
- NYC DOT 2008 press release (34th St SBS terra cotta lanes); Urban Omnibus "Stay in Your Lane" (2024).
- stuffnobodycaresabout.com (1892/1904 World Almanac street and sidewalk widths); Baruch NYCdata (grid).
- Schaller Consulting, *Empty Seats, Full Streets* (2017).
- NYC TLC (13,587 medallions; DuPont M6284); Wikipedia "Taxis of New York City"; 2025 TLC MMR / substack (active fleet).
- Wikipedia "New Flyer Xcelsior", "MTA Regional Bus Operations bus fleet".
- Axalta 2025 Global Automotive Color Popularity Report.
- NYC DOT PR 19-065 (Route 9A 30 mph); FDR Drive 40 mph.
- 2015 NYC Street Tree Census via GBIF API (dataset d1e9202b-7300-4712-868c-d25133fb6f08), my own Manhattan aggregation.
- Central Park Conservancy (elms, 18,000 trees); NBC NY / centralpark.com (foliage timing).
- Wikipedia "Rooftop water tower"; Untapped New York; 6sqft (water tanks).
- Treglia et al. 2022, *Ecology & Society* (green roofs); Healthbeat 2025 (36 % reflective roofs).
- Bloomberg/amNY/Gothamist/Sierra Club (LED street lights); ESB tower-lights page; NYC ZR 81-732 (Times Square).
- NOAA CO-OPS 8518750 datums; Iowa Environmental Mesonet ASOS archive (LGA winds).
- Hudson River Park Trust (historic bulkhead); RGR Landscape; Hudson River Park water-quality dashboard.
- Wikimedia Commons photos listed in §5.3.
