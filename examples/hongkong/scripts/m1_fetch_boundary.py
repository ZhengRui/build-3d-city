"""M1: the OSM inputs of the boundary snap (scripts/m1_boundary.py), through the engine's Overpass helper with its
answer cache (run with CITY3D_OVERPASS_CACHE=../data/hongkong/raw/overpass_cache, the same cache 01_osm replays):
the Sai Kung district's relation id, the nine districts' relations (the very query 01_osm's boundary() sends) and
the country parks and other protected areas over option E's box. Retries until every answer is in."""
import json
from pathlib import Path
import sys
import time

from city3d.common import overpass

BOX = "(22.22,114.08,22.43,114.34)"
IDS = [2558879, 2558883, 2558880, 2670978, 2800201, 2800200, 2800277, 2800276]


def ask(q, tries=20):
    for k in range(tries):
        try:
            return overpass(q, timeout=300)
        except Exception as e:  # noqa: BLE001
            print(f"try {k + 1}: {str(e)[:300]}", flush=True)
            time.sleep(60)
    sys.exit("gave up")


saikung = ask("""[out:json][timeout:60];
is_in(22.3816,114.2735)->.a; rel(pivot.a)["boundary"="administrative"]; out tags;""")
for e in saikung["elements"]:
    print(e["id"], e["tags"].get("admin_level"), e["tags"].get("name:en"), e["tags"].get("name"), flush=True)
sk = [e["id"] for e in saikung["elements"] if e["tags"].get("admin_level") == "6"]
print("Sai Kung admin_level 6:", sk, flush=True)
for rid in IDS + sk:
    r = ask(f"""
        [out:json][timeout:120];
        rel({rid});
        out geom;
    """)
    print(rid, r["elements"][0]["tags"].get("name:en"), flush=True)
parks = ask(f"""[out:json][timeout:300];
(way["boundary"="protected_area"]{BOX}; rel["boundary"="protected_area"]{BOX};
 way["leisure"="nature_reserve"]{BOX}; rel["leisure"="nature_reserve"]{BOX};
 way["boundary"="national_park"]{BOX}; rel["boundary"="national_park"]{BOX};);
out geom;""")
print("protected areas:", len(parks["elements"]), flush=True)
json.dump({"saikung": sk}, open(Path(__file__).resolve().parents[2] / "data/hongkong/raw/overpass_cache/_m1_ids.json", "w"))
print("DONE", flush=True)
