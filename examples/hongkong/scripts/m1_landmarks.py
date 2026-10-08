"""M1: data/landmarks.csv from Phase 0's 45 places (demos/data/hongkong/phase0/research.json) and a few towers
Phase 0 left out, each height checked against a second source (Wikipedia / CTBUH's figures, then LandsD's
TopHeight minus the ground: scripts/m1_sources.py prints that cross-check into checks/m1_sources.md).
Columns as every city's list (name_zh, name_en, height_m, height_type, floors, status, year, lat, lon, source,
notes, feature, use_height). feature: building (matched to a footprint), area (a place for the menu: park,
market, beach, campus), hill. use_height false where the listed figure reaches a mast or spire above the roof
(the Bank of China, Central Plaza, The Center: the LandsD roof stands, masts are M4's), or where no height was
checked. Run once; edit the CSV by hand afterwards."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
R = json.load(open(HERE.parents[1] / "demos/data/hongkong/phase0/research.json"))

# id -> (height_m, height_type, floors, year, second source, use_height, notes); None height: not a height row
W = "Wikipedia EN"
CHK = {
    "icc": (484, "architectural (CTBUH)", 108, 2010, f"{W} International Commerce Centre; CTBUH 484 m; LandsD TopHeight 490.0 mPD", True, "Tallest in HK. 118 numbered floors (108 real). sky100 at 393 m."),
    "ifc": (412, "architectural (CTBUH; crown fins to 412)", 88, 2003, f"{W} International Finance Centre; CTBUH 412 m; LandsD TopHeight 408.2 mPD", True, "Crown of open fins above the roof."),
    "boc": (367.4, "to the mast tips; roof 315 m", 72, 1990, f"{W} Bank of China Tower (367.4 m with masts, 315 m roof); LandsD TopHeight 310.3 mPD over base 7.0", False, "Two masts on the top prism. M2: the LandsD roof (~303-315 m) stands; the masts are thin parts for M4."),
    "hsbc": (178.8, "architectural", 44, 1985, f"{W} HSBC Main Building; CTBUH 178.8 m; LandsD TopHeight 180.9 mPD over base 3.7", True, "Foster's hanger structure, masts on the roof are part of the 178.8."),
    "central_plaza": (374, "to the mast tip; roof 309 m", 78, 1992, f"{W} Central Plaza (374 m with the mast, 309 m roof); LandsD TopHeight 380.7 mPD over base 3.9 (includes the mast)", False, "LandsD's top includes the 65 m mast: cap the body at ~309 m (+ base) in M2, the mast a thin part in M4."),
    "the_center": (346, "to the mast tip; roof ~292 m", 73, 1998, f"{W} The Center (346 m with the mast); LandsD TopHeight 299.6 mPD over base 7.9", False, "Neon-lit stepped crown with a mast. M2: LandsD roof; mast in M4."),
    "ckc": (283, "architectural", 63, 1999, f"{W} Cheung Kong Center; CTBUH 283 m", True, ""),
    "lippo": (186, "architectural (Tower 1; Tower 2 172 m)", 48, 1988, f"{W} Lippo Centre (Tower 1 186 m, Tower 2 172 m)", True, "Twin towers: the point is Tower 1; Tower 2 keeps its LandsD height."),
    "jardine": (178.5, "architectural", 52, 1973, f"{W} Jardine House 178.5 m", True, "Round windows."),
    "times_square": (194, "architectural (office tower)", 46, 1994, f"{W} Times Square (Hong Kong) 194 m", True, ""),
    "clock_tower": (44, "to the lightning rod", None, 1915, f"{W} Former Kowloon-Canton Railway Clock Tower 44 m", False, "Red brick and granite. The point matches the Cultural Centre's Auditoria Building (LandsD 56 m) within 40 m: use_height would lower it; the tower needs its own footprint (OSM) in M2."),
    "chungking": (None, "", 17, 1961, f"{W} Chungking Mansions (17 storeys)", False, "Height not checked (17 storeys ~55 m [believed]): LandsD stands."),
    "peak_tower": (None, "", 7, 1997, f"{W} Peak Tower (Sky Terrace 428 at 428 mPD)", False, "428 is the terrace's altitude above Principal Datum, not a building height."),
    "lion_rock": (495, "summit, m above sea level", None, None, f"{W} Lion Rock 495 m; OSM natural=peak ele", False, "A hill: terrain, checked in M3's terrain.md."),
}
EXTRA = [  # towers Phase 0 did not list, inside E; positions from OSM/LandsD names, checked in m1_sources.md
    ("合和中心", "Hopewell Centre", 216, "architectural", 64, 1980, 22.27466, 114.17197, f"{W} Hopewell Centre 216 m", True, "Round tower, revolving restaurant on top (Wan Chai)."),
    ("港島東中心", "One Island East", 298.3, "architectural", 68, 2008, 22.28621, 114.21390, f"{W} One Island East 298 m", True, "Taikoo Place, Quarry Bay."),
    ("國際金融中心一期", "One International Finance Centre", 210, "architectural", 38, 1998, 22.28455, 114.15835, f"{W} International Finance Centre (One IFC 210 m); LandsD One IFC row Top 203.7 mPD", False, "The first point matched the IFC Mall podium (LandsD 34 m): take the position from LandsD's One IFC row (OBJECTID 161137) before use_height."),
    ("天璽", "The Cullinan (Sun Tower)", 270, "architectural", 68, 2008, 22.30479, 114.16066, f"{W} The Cullinan (270 m); LandsD The Cullinan II Top 275.9 mPD, ground 5.6", True, "Two towers on Union Square beside the ICC; point on LandsD's The Cullinan II row (Top - ground 270.3 m)."),
    ("擎天半島 1座", "Sorrento Tower 1", 256, "architectural", 75, 2003, 22.30673, 114.16145, f"{W} Sorrento (Hong Kong) Tower 1 256 m; LandsD Top 251.9 mPD, ground 5.1", True, "Union Square; point on LandsD's Sorrento Tower 1 row (Top - ground 246.8 m, 9 m under the published figure)."),
    ("凱旋門", "The Arch", 231, "architectural", 81, 2005, 22.30380, 114.16330, f"{W} The Arch (Hong Kong) 231 m", False, "Union Square; position to match by LandsD name before use_height."),
    ("曉廬", "Highcliff", 252.3, "architectural", 73, 2003, 22.26509, 114.18417, f"{W} Highcliff 252.3 m; LandsD Top 378.2 mPD, Base 168.0", False, "Slender tower on Stubbs Road above Happy Valley, on a slope: point on LandsD's Highcliff row; its ground on the slope decides the height (M2)."),
    ("友邦金融中心", "AIA Central", 185, "architectural", 37, 2005, 22.28129, 114.16183, f"{W} AIA Central 185 m; LandsD Top 173.6 mPD, Base 4.7", False, "Height [believed]: LandsD says ~169 m above its base; LandsD stands until checked."),
]

rows = []
for l in R["landmarks"]:
    h, ht, fl, yr, src, use, note = CHK.get(l["id"], (None, "", None, None, "", False, ""))
    if l["id"] not in CHK and l.get("height_m"):
        h, ht = l["height_m"], "Phase 0"
    feat = "hill" if l["id"] == "lion_rock" else ("building" if l["kind"] in ("tower", "heritage", "culture", "viewpoint") and l["id"] not in ("tko", "lohas_park", "hkust", "tvb_city", "kai_tak_sports_park", "sai_kung_town") else "area")
    rows.append({"name_zh": l.get("name_local") or l["name"], "name_en": l["name"], "height_m": h if h else "",
                 "height_type": ht, "floors": fl or "", "status": "completed", "year": yr or "",
                 "lat": l["lat"], "lon": l["lon"],
                 "source": "; ".join(s for s in (src, l.get("wikipedia", ""), "Phase 0 research.json") if s),
                 "notes": " ".join(s for s in (note, l.get("why", "")) if s), "feature": feat,
                 "use_height": bool(use and h)})
for zh, en, h, ht, fl, yr, la, lo, src, use, note in EXTRA:
    rows.append({"name_zh": zh, "name_en": en, "height_m": h, "height_type": ht, "floors": fl, "status": "completed",
                 "year": yr, "lat": la, "lon": lo, "source": src, "notes": note + " (added in M1)",
                 "feature": "building", "use_height": use})
out = HERE / "data/landmarks.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{out}: {len(rows)} rows, {sum(r['use_height'] for r in rows)} with use_height")
